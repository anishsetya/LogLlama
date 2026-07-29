from __future__ import annotations

import statistics
import time

from logllama.credentials import ManagedCredentialCache


def benchmark(iterations: int = 200_000) -> dict[str, float]:
    plain = {"openai": "secret"}
    cache = ManagedCredentialCache(endpoint="http://localhost:8000", runtime_key="unused")
    cache._credentials = dict(plain)

    plain_samples = _samples(lambda: plain.get("openai"), iterations)
    cache_samples = _samples(lambda: cache.get("openai"), iterations)
    return {
        "iterations": iterations,
        "plain_dict_p50_us": _percentile(plain_samples, 50),
        "managed_cache_p50_us": _percentile(cache_samples, 50),
        "managed_cache_p99_us": _percentile(cache_samples, 99),
        "p50_added_us": _percentile(cache_samples, 50) - _percentile(plain_samples, 50),
        "managed_cache_mean_us": statistics.mean(cache_samples),
    }


def _samples(call, iterations: int) -> list[float]:
    samples: list[float] = []
    append = samples.append
    for _ in range(iterations):
        started = time.perf_counter_ns()
        call()
        append((time.perf_counter_ns() - started) / 1000)
    return samples


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * percentile / 100))
    return round(ordered[index], 4)


if __name__ == "__main__":
    print(benchmark())
