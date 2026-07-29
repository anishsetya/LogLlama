from __future__ import annotations

import argparse
import json
import statistics
import time
import uuid
from collections.abc import Callable
from typing import Any

from app.secret_store import MemorySecretStore, SecretStore, VaultKvV2SecretStore


def percentile(values: list[float], pct: int) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * pct / 100))
    return ordered[index]


def summarize(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "mean_ms": round(statistics.mean(values), 4),
        "p50_ms": round(percentile(values, 50), 4),
        "p95_ms": round(percentile(values, 95), 4),
        "p99_ms": round(percentile(values, 99), 4),
    }


def samples(call: Callable[[], Any], iterations: int) -> list[float]:
    values = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        call()
        values.append((time.perf_counter_ns() - started) / 1_000_000)
    return values


def benchmark_store(
    name: str,
    store: SecretStore,
    read_iterations: int,
    write_iterations: int,
) -> dict[str, Any]:
    reference = f"logllama/benchmark/{uuid.uuid4().hex}"
    value = "benchmark-secret-not-a-real-key"
    try:
        store.put(reference, value)
        for _ in range(10):
            assert store.get(reference) == value

        reads = samples(lambda: store.get(reference), read_iterations)
        writes = samples(lambda: store.put(reference, value), write_iterations)
        deletes = samples(
            lambda: _delete_cycle(store, reference, value),
            max(10, write_iterations // 10),
        )
        return {
            "backend": name,
            "get": summarize(reads),
            "put": summarize(writes),
            "delete_and_restore": summarize(deletes),
        }
    finally:
        store.delete(reference)


def _delete_cycle(store: SecretStore, reference: str, value: str) -> None:
    store.delete(reference)
    store.put(reference, value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-addr")
    parser.add_argument("--vault-token")
    parser.add_argument("--openbao-addr")
    parser.add_argument("--openbao-token")
    parser.add_argument("--read-iterations", type=int, default=1000)
    parser.add_argument("--write-iterations", type=int, default=250)
    args = parser.parse_args()

    stores: list[tuple[str, SecretStore]] = [("memory", MemorySecretStore())]
    if args.vault_addr and args.vault_token:
        stores.append(
            (
                "vault",
                VaultKvV2SecretStore(args.vault_addr, args.vault_token),
            )
        )
    if args.openbao_addr and args.openbao_token:
        stores.append(
            (
                "openbao",
                VaultKvV2SecretStore(args.openbao_addr, args.openbao_token),
            )
        )

    results = [
        benchmark_store(name, store, args.read_iterations, args.write_iterations)
        for name, store in stores
    ]
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
