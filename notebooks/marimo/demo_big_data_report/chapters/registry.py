from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Sequence

from notebooks.marimo.demo_big_data_report._cases import build_test_config_small
from notebooks.marimo.demo_big_data_report._shared import TARGET_FIELDS_FULL

from ._types import ChapterResult
from .basics import run_basics
from .diagnostics import run_diagnostics
from .guardrails import run_guardrails
from .loader_retry import run_loader_retry
from .memory_opt import run_memory_optimization
from .observability import run_observability
from .output_composition import run_output_composition
from .parallel_mode import run_parallel_mode
from .sinks import run_sinks
from .yaml_dsl import run_yaml_dsl


def run_all_chapters(*, slow_ok: bool = False) -> List[ChapterResult]:
    """用于 `just examples` 的集成对拍入口.

    Args:
        slow_ok: 预留开关(未来可用于包含更重的演示路径);当前始终走快速配置.
    """
    _ = slow_ok
    cfg = build_test_config_small()
    demo_dir = Path(__file__).resolve().parents[1]
    yaml_path = demo_dir / "by_yaml_dsl" / "ecommerce_report.yaml"

    results: List[ChapterResult] = []

    results.append(run_basics(cfg, targets=TARGET_FIELDS_FULL, batch_size=10))
    results.append(run_yaml_dsl(cfg, yaml_path=yaml_path))
    results.append(run_sinks(cfg, targets=TARGET_FIELDS_FULL[:12], batch_size=10))
    results.append(run_memory_optimization(cfg, batch_size=10, write_delay=0.0))
    results.append(run_observability(cfg, targets=TARGET_FIELDS_FULL[:12], batch_size=10))
    results.append(run_parallel_mode(cfg, targets=TARGET_FIELDS_FULL[:12], batch_size=10))
    results.append(run_diagnostics(cfg))
    results.append(run_guardrails())
    results.append(run_loader_retry())
    with tempfile.TemporaryDirectory() as tmpdir:
        results.append(run_output_composition(Path(tmpdir)))

    return results
