#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${OPENBAO_STATE_DIR:-${ROOT_DIR}/.openbao}"
INIT_FILE="${STATE_DIR}/init.json"
ROLE_ID_FILE="${STATE_DIR}/role-id"
SECRET_ID_FILE="${STATE_DIR}/secret-id"
ENV_FILE="${STATE_DIR}/backend.env"
BAO_ADDR="http://127.0.0.1:8200"

DOCKER_DESKTOP_BIN="/Applications/Docker.app/Contents/Resources/bin"
if [[ -d "${DOCKER_DESKTOP_BIN}" ]]; then
  export PATH="${DOCKER_DESKTOP_BIN}:${PATH}"
fi

mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"
umask 077

cd "${ROOT_DIR}"
docker compose up -d openbao

for _ in $(seq 1 60); do
  if curl --silent --output /dev/null "${BAO_ADDR}/v1/sys/health"; then
    break
  fi
  if curl --silent --output /dev/null --fail-with-body \
    "${BAO_ADDR}/v1/sys/seal-status"; then
    break
  fi
  sleep 1
done

status_json="$(
  docker compose exec -T \
    -e BAO_ADDR="${BAO_ADDR}" \
    openbao bao status -format=json 2>/dev/null || true
)"
if [[ -z "${status_json}" ]]; then
  echo "OpenBao did not become reachable." >&2
  exit 1
fi

if [[ "$(jq -r '.initialized' <<<"${status_json}")" != "true" ]]; then
  docker compose exec -T \
    -e BAO_ADDR="${BAO_ADDR}" \
    openbao bao operator init \
      -key-shares=1 \
      -key-threshold=1 \
      -format=json >"${INIT_FILE}"
  chmod 600 "${INIT_FILE}"
  echo "Initialized OpenBao. Recovery material is in ${INIT_FILE}."
fi

if [[ ! -f "${INIT_FILE}" ]]; then
  echo "OpenBao is initialized, but ${INIT_FILE} is missing." >&2
  echo "Restore the unseal material before continuing." >&2
  exit 1
fi

unseal_key="$(jq -r '.unseal_keys_b64[0]' "${INIT_FILE}")"
root_token="$(jq -r '.root_token' "${INIT_FILE}")"

status_json="$(
  docker compose exec -T \
    -e BAO_ADDR="${BAO_ADDR}" \
    openbao bao status -format=json 2>/dev/null || true
)"
if [[ "$(jq -r '.sealed' <<<"${status_json}")" == "true" ]]; then
  docker compose exec -T \
    -e BAO_ADDR="${BAO_ADDR}" \
    openbao bao operator unseal "${unseal_key}" >/dev/null
  echo "Unsealed OpenBao."
fi

bao() {
  docker compose exec -T \
    -e BAO_ADDR="${BAO_ADDR}" \
    -e BAO_TOKEN="${root_token}" \
    openbao bao "$@"
}

secrets_json="$(bao secrets list -format=json)"
if ! jq -e 'has("secret/")' >/dev/null <<<"${secrets_json}"; then
  bao secrets enable -path=secret kv-v2 >/dev/null
fi

mount_version="$(bao read -format=json sys/mounts/secret/tune | jq -r '.data.options.version')"
if [[ "${mount_version}" != "2" ]]; then
  echo "The secret/ mount exists but is not KV v2." >&2
  exit 1
fi

bao policy write logllama /openbao/policies/logllama-policy.hcl >/dev/null

auth_json="$(bao auth list -format=json)"
if ! jq -e 'has("approle/")' >/dev/null <<<"${auth_json}"; then
  bao auth enable approle >/dev/null
fi

bao write auth/approle/role/logllama \
  token_policies=logllama \
  token_no_default_policy=true \
  token_ttl=1h \
  token_max_ttl=4h \
  secret_id_ttl=0 \
  secret_id_num_uses=0 >/dev/null

bao read -format=json auth/approle/role/logllama/role-id \
  | jq -r '.data.role_id' >"${ROLE_ID_FILE}"
if [[ ! -s "${SECRET_ID_FILE}" ]]; then
  bao write -f -format=json auth/approle/role/logllama/secret-id \
    | jq -r '.data.secret_id' >"${SECRET_ID_FILE}"
fi
chmod 600 "${ROLE_ID_FILE}" "${SECRET_ID_FILE}"

cat >"${ENV_FILE}" <<EOF
LOGLLAMA_SECRET_BACKEND=openbao
LOGLLAMA_SECRET_STORE_ADDR=${BAO_ADDR}
LOGLLAMA_SECRET_STORE_MOUNT=secret
LOGLLAMA_SECRET_STORE_ROLE_ID_FILE=${ROLE_ID_FILE}
LOGLLAMA_SECRET_STORE_SECRET_ID_FILE=${SECRET_ID_FILE}
LOGLLAMA_SECRET_STORE_TIMEOUT_SECONDS=2
EOF
chmod 600 "${ENV_FILE}"

echo "OpenBao is ready with persistent Raft storage."
echo "Backend environment: ${ENV_FILE}"
