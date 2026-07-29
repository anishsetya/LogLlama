#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${OPENBAO_STATE_DIR:-${ROOT_DIR}/.openbao}"
INIT_FILE="${STATE_DIR}/init.json"
SNAPSHOT_DIR="${STATE_DIR}/snapshots"
BAO_ADDR="http://127.0.0.1:8200"
CONTAINER_SNAPSHOT="/tmp/logllama-openbao.snap"

DOCKER_DESKTOP_BIN="/Applications/Docker.app/Contents/Resources/bin"
if [[ -d "${DOCKER_DESKTOP_BIN}" ]]; then
  export PATH="${DOCKER_DESKTOP_BIN}:${PATH}"
fi

if [[ ! -f "${INIT_FILE}" ]]; then
  echo "Missing ${INIT_FILE}; recovery material is required for a local snapshot." >&2
  exit 1
fi

mkdir -p "${SNAPSHOT_DIR}"
chmod 700 "${SNAPSHOT_DIR}"
umask 077

root_token="$(jq -r '.root_token' "${INIT_FILE}")"
snapshot_file="${SNAPSHOT_DIR}/openbao-$(date -u +%Y%m%dT%H%M%SZ).snap"

cd "${ROOT_DIR}"
docker compose exec -T \
  -e BAO_ADDR="${BAO_ADDR}" \
  -e BAO_TOKEN="${root_token}" \
  openbao bao operator raft snapshot save "${CONTAINER_SNAPSHOT}"
docker compose cp "openbao:${CONTAINER_SNAPSHOT}" "${snapshot_file}" >/dev/null
docker compose exec -T openbao rm -f "${CONTAINER_SNAPSHOT}"
chmod 600 "${snapshot_file}"

echo "OpenBao Raft snapshot: ${snapshot_file}"
