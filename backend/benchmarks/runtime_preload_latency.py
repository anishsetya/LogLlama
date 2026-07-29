from __future__ import annotations

import argparse
import json
import statistics
import time
from urllib import request


def percentile(values: list[float], pct: int) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * pct / 100))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000")
    parser.add_argument("--runtime-key", required=True)
    parser.add_argument("--iterations", type=int, default=1000)
    args = parser.parse_args()

    url = f"{args.endpoint.rstrip('/')}/v1/runtime/provider-credentials"

    def fetch() -> int:
        req = request.Request(
            url,
            headers={"X-LogLlama-Runtime-Key": args.runtime_key},
        )
        with request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return len(payload.get("credentials", []))

    credential_count = fetch()
    for _ in range(10):
        assert fetch() == credential_count

    timings = []
    for _ in range(args.iterations):
        started = time.perf_counter_ns()
        assert fetch() == credential_count
        timings.append((time.perf_counter_ns() - started) / 1_000_000)

    print(
        json.dumps(
            {
                "iterations": len(timings),
                "credential_count": credential_count,
                "mean_ms": round(statistics.mean(timings), 4),
                "p50_ms": round(percentile(timings, 50), 4),
                "p95_ms": round(percentile(timings, 95), 4),
                "p99_ms": round(percentile(timings, 99), 4),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
