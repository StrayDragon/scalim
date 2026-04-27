import os
from typing import Dict, Tuple

import pytest

from scalim._project_constants import ENV_BENCH_SCALE, ENV_BENCH_SCOPE
from scalim.execution.executor.helpers.field_access import extract_field_segments
from scalim_benchlib import BenchmarkRunner


def _bench_scale() -> str:
    return os.getenv(ENV_BENCH_SCALE, "small")


def _bench_scope() -> str:
    return os.getenv(ENV_BENCH_SCOPE, "field-access")


def _bench_iters() -> int:
    scale = _bench_scale()
    return {
        "small": 20_000,
        "medium": 80_000,
        "large": 200_000,
    }.get(scale, 20_000)


def _bench_info(scenario: str, *, iters: int) -> Dict[str, object]:
    return {
        "scenario": scenario,
        "scale": _bench_scale(),
        "scope": _bench_scope(),
        "iters": iters,
    }


@pytest.mark.bench
@pytest.mark.parametrize(
    "segments",
    [
        ("a",),
        ("a", "b", "c"),
    ],
    ids=["len1", "len3"],
)
@pytest.mark.benchmark(group="field-access")
def test_bench_extract_field_segments_mapping_get(benchmark, segments: Tuple[str, ...]) -> None:
    iters = _bench_iters()
    data = {"a": {"b": {"c": 1}}}

    def _run() -> int:
        out = 0
        for _ in range(iters):
            v = extract_field_segments(data, segments)
            out += 1 if v is not None else 0
        return out

    runner = BenchmarkRunner(benchmark)
    runner.run(_run, extra_info=_bench_info("extract_field_segments_mapping_{}".format(len(segments)), iters=iters))
