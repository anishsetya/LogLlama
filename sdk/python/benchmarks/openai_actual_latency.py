from __future__ import annotations

import argparse
import json
import os
import random
import ssl
import statistics
import time
from pathlib import Path
from typing import Any
from urllib import request

import logllama


ROOT = Path(__file__).resolve().parents[3]


def ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi
    except Exception:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.model = payload.get("model")
        self.usage = payload.get("usage")

    def model_dump(self) -> dict[str, Any]:
        return self._payload


class Responses:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.context = ssl_context()

    def create(self, **kwargs: Any) -> Response:
        body = json.dumps(kwargs).encode("utf-8")
        req = request.Request(
            "https://api.openai.com/v1/responses",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=60, context=self.context) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return Response(payload)


class Client:
    def __init__(self, api_key: str) -> None:
        self.responses = Responses(api_key)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "mean_ms": round(statistics.mean(values), 2),
        "p50_ms": round(percentile(values, 50), 2),
        "p95_ms": round(percentile(values, 95), 2),
        "p99_ms": round(percentile(values, 99), 2),
        "min_ms": round(min(values), 2),
        "max_ms": round(max(values), 2),
    }


def timed_call(client: Any, model: str, request_id: str, include_logllama_metadata: bool) -> float:
    payload = {
        "model": model,
        "input": "Reply with only: ok",
        "instructions": "Keep the response as short as possible.",
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "low"},
        "max_output_tokens": 16,
    }
    if include_logllama_metadata:
        payload["logllama_metadata"] = {
            "request_id": request_id,
            "route": "/benchmarks/openai-latency",
            "tags": ["latency-benchmark"],
        }

    started = time.perf_counter()
    client.responses.create(**payload)
    return (time.perf_counter() - started) * 1000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests-per-case", type=int, default=100)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--stop-after-failures", type=int, default=6)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is missing from .env or environment.")

    model = os.getenv("LOGLLAMA_OPENAI_TEST_MODEL", "gpt-5-nano")
    cases = {
        "raw": Client(api_key),
        "wrapped_sample0": logllama.wrap_openai(
            Client(api_key),
            api_key=os.getenv("LOGLLAMA_API_KEY"),
            endpoint=os.getenv("LOGLLAMA_ENDPOINT"),
            sample_rate=0,
            capture_otel=False,
        ),
        "wrapped_full": logllama.wrap_openai(
            Client(api_key),
            api_key=os.getenv("LOGLLAMA_API_KEY"),
            endpoint=os.getenv("LOGLLAMA_ENDPOINT"),
            sample_rate=1,
            capture_prompts=True,
            capture_responses=True,
            capture_otel=False,
        ),
    }
    timings = {name: [] for name in cases}
    failures: list[dict[str, str]] = []
    rng = random.Random(args.seed)

    print(
        json.dumps(
            {
                "model": model,
                "requests_per_case": args.requests_per_case,
                "cases": list(cases),
            }
        )
    )
    for index in range(args.requests_per_case):
        names = list(cases)
        rng.shuffle(names)
        for name in names:
            request_id = f"actual-latency-{name}-{index}"
            try:
                elapsed = timed_call(cases[name], model, request_id, name != "raw")
                timings[name].append(elapsed)
            except Exception as exc:
                failures.append({"case": name, "request_id": request_id, "error": repr(exc)})
                print(json.dumps({"case": name, "index": index, "error": exc.__class__.__name__}))
                if len(failures) >= args.stop_after_failures and not any(timings.values()):
                    raise SystemExit("Stopping early because all initial requests are failing.")
        if (index + 1) % 10 == 0:
            print(json.dumps({"completed_per_case": index + 1}))

    summary = {name: summarize(values) for name, values in timings.items()}
    raw_p50 = summary["raw"]["p50_ms"] if summary["raw"]["count"] else 0.0
    for name, stats in summary.items():
        stats["p50_overhead_vs_raw_ms"] = round(stats["p50_ms"] - raw_p50, 2)
    print(json.dumps({"summary": summary, "failures": failures}, indent=2))


if __name__ == "__main__":
    main()
