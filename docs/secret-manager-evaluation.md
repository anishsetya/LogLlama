# Self-hosted secret manager evaluation

Evaluation date: 2026-07-28

## Decision

Keep secret-manager support as a backend control-plane integration, with OpenBao
as the recommended self-hosted default. Keep HashiCorp Vault and AWS Secrets
Manager as supported alternatives.

Do not bundle a secret-manager server into the Python SDK and do not fetch a
secret during model generation. The SDK preloads provider credentials at
startup, refreshes them in the background, and uses its in-process snapshot for
normal requests.

## Candidates

- OpenBao: recommended self-hosted default. It provides the required KV v2 API
  without requiring an AWS deployment.
- HashiCorp Vault: use when a customer already operates Vault or needs its
  enterprise ecosystem.
- AWS Secrets Manager: use when the backend already runs in AWS and the managed
  service is more valuable than minimizing control-plane network latency.
- Infisical: not benchmarked locally. Its documented Docker Compose deployment
  requires Infisical, PostgreSQL, and Redis, with a 4 GB memory and 20 GB disk
  minimum. That is a large embedded footprint for three provider credentials,
  while LogLlama already supplies the admin workflow.
- In-memory: development and tests only; it is not persistent.

The Vault and OpenBao tests used their official dev-mode containers. Dev mode is
not a production topology; production deployments require persistent storage,
TLS, restricted policies, audit logging, backups, and an unseal strategy.

## Method

Hardware and network: the local development machine, with each manager in a
Docker container bound to `127.0.0.1`. Values were synthetic and containers were
removed after testing.

Direct KV benchmark:

- 5,000 warmed reads
- 1,000 writes
- 100 delete-and-restore cycles
- Identical stdlib HTTP adapter and KV v2 data model

Full preload benchmark:

- Three provider credentials: OpenAI, Anthropic, and Gemini
- 1,000 requests to `/v1/runtime/provider-credentials`
- Includes runtime-key authentication, PostgreSQL lookup, three concurrent
  secret reads, serialization, and loopback HTTP

Warmed SDK benchmark:

- 200,000 cached credential lookups
- 100,000 provider-routed local calls
- No provider network request

## Results

| Path | p50 | p95 | p99 |
| --- | ---: | ---: | ---: |
| Memory KV read | 0.0002 ms | 0.0003 ms | 0.0003 ms |
| Vault KV read | 0.9543 ms | 1.2337 ms | 2.2445 ms |
| OpenBao KV read | 0.9832 ms | 1.3447 ms | 2.7009 ms |
| Vault KV write | 1.0845 ms | 1.4217 ms | 2.7817 ms |
| OpenBao KV write | 1.1124 ms | 1.4563 ms | 2.7251 ms |
| Vault three-key preload | 4.6516 ms | 6.1123 ms | 7.4026 ms |
| OpenBao three-key preload | 4.8852 ms | 7.6176 ms | 9.2447 ms |
| Warm managed-cache overhead | 0.084 us | - | 0.458 us total |
| Provider-router overhead | 2.417 us | - | 3.166 us total |

The Vault/OpenBao preload difference is about 0.23 ms at p50 on this machine.
It is too small, and too far outside the generation path, to outweigh
deployment and governance considerations.

## Latency budget

The secret manager is allowed on:

- Admin writes and rotations
- SDK startup preload
- Background refresh

It is not allowed on:

- `LLM.generate(...)`
- Provider adapter execution
- Telemetry capture or delivery

The measured normal request-path cost remains the cached lookup plus routing,
about 2.5 microseconds p50 before provider SDK and network latency. If a future
change introduces a secret-store call per generation, it should be rejected or
reverted.

## Reproduce

Use the official Vault and OpenBao dev containers, then:

```bash
cd backend
PYTHONPATH=. .venv/bin/python benchmarks/secret_store_latency.py \
  --vault-addr http://127.0.0.1:8200 --vault-token test-token \
  --openbao-addr http://127.0.0.1:8300 --openbao-token test-token
```

For the complete preload path:

```bash
PYTHONPATH=. .venv/bin/python benchmarks/runtime_preload_latency.py \
  --endpoint http://127.0.0.1:8000 \
  --runtime-key llama-runtime-key
```

References:

- https://developer.hashicorp.com/vault/docs/get-started/developer-qs
- https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2
- https://openbao.org/docs/install/
- https://openbao.org/docs/secrets/kv/kv-v2/
- https://infisical.com/docs/self-hosting/deployment-options/docker-compose
