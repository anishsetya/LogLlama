from __future__ import annotations

import statistics
import time
from types import SimpleNamespace
from typing import Any, Callable

import logllama


class Responses:
    def create(self, **kwargs: Any) -> Any:
        return SimpleNamespace(
            output_text="ok",
            model=kwargs["model"],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1, total_tokens=2),
            status="completed",
        )


class Client:
    def __init__(self) -> None:
        self.responses = Responses()


def benchmark(iterations: int = 100_000) -> dict[str, float]:
    raw_client = Client()
    routed_client = Client()
    llm = logllama.LLM(
        openai=routed_client,
        models={"openai": "gpt-test"},
        instrument=False,
    )
    raw = _samples(lambda: raw_client.responses.create(model="gpt-test", input="ok"), iterations)
    routed = _samples(lambda: llm.generate("ok", provider="openai"), iterations)
    return {
        "iterations": iterations,
        "raw_p50_us": _percentile(raw, 50),
        "router_p50_us": _percentile(routed, 50),
        "router_p99_us": _percentile(routed, 99),
        "p50_added_us": _percentile(routed, 50) - _percentile(raw, 50),
        "router_mean_us": statistics.mean(routed),
    }


def _samples(call: Callable[[], Any], iterations: int) -> list[float]:
    values: list[float] = []
    append = values.append
    for _ in range(iterations):
        started = time.perf_counter_ns()
        call()
        append((time.perf_counter_ns() - started) / 1000)
    return values


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * percentile / 100))
    return round(ordered[index], 4)


if __name__ == "__main__":
    print(benchmark())
