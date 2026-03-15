import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Sequence

from ..cases import build_test_config_small
from ..loaders import ECommerceConfig
from ..shared import TARGET_FIELDS_FULL
from ._types import ChapterResult
from .basics import run_basics
from .derived_set_aggregations import run_derived_set_aggregations
from .diagnostics import run_diagnostics
from .guardrails import run_guardrails
from .loader_retry import run_loader_retry
from .memory_opt import run_memory_optimization
from .observability import run_observability
from .output_composition import run_output_composition
from .parallel_mode import run_parallel_mode
from .sinks import run_sinks
from .workflow_yaml import run_workflow_yaml
from .yaml_dsl import run_yaml_dsl

_ALL_CHAPTER_IDS = [
    "basics",
    "yaml_dsl",
    "workflow_yaml",
    "sinks",
    "memory_opt",
    "observability",
    "parallel_mode",
    "diagnostics",
    "guardrails",
    "loader_retry",
    "output_composition",
    "derived_set_aggregations",
]

_TMPDIR_CHAPTER_IDS = {"output_composition", "derived_set_aggregations"}
_ChapterRunner = Callable[[Path], ChapterResult]


def all_chapter_ids() -> List[str]:
    return list(_ALL_CHAPTER_IDS)


def _build_chapter_runners(*, cfg: ECommerceConfig, yaml_path: Path, workflow_yaml_path: Path) -> Dict[str, _ChapterRunner]:
    return {
        "basics": lambda _tmp_path: run_basics(cfg, targets=TARGET_FIELDS_FULL, batch_size=10),
        "yaml_dsl": lambda _tmp_path: run_yaml_dsl(cfg, yaml_path=yaml_path),
        "workflow_yaml": lambda _tmp_path: run_workflow_yaml(cfg, workflow_yaml_path=workflow_yaml_path),
        "sinks": lambda _tmp_path: run_sinks(cfg, targets=TARGET_FIELDS_FULL[:12], batch_size=10),
        "memory_opt": lambda _tmp_path: run_memory_optimization(cfg, batch_size=10, write_delay=0.0),
        "observability": lambda _tmp_path: run_observability(cfg, targets=TARGET_FIELDS_FULL[:12], batch_size=10),
        "parallel_mode": lambda _tmp_path: run_parallel_mode(cfg, targets=TARGET_FIELDS_FULL[:12], batch_size=10),
        "diagnostics": lambda _tmp_path: run_diagnostics(cfg),
        "guardrails": lambda _tmp_path: run_guardrails(),
        "loader_retry": lambda _tmp_path: run_loader_retry(),
        "output_composition": run_output_composition,
        "derived_set_aggregations": run_derived_set_aggregations,
    }


def run_selected_chapters(
    *,
    yaml_path: Path,
    chapter_ids: Sequence[str],
    slow_ok: bool = False,
) -> List[ChapterResult]:
    """运行指定章节集合(用于 runner 过滤运行).

    Args:
        yaml_path: 唯一完整 YAML DSL 示例路径(通常为 `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`)
        slow_ok: 预留开关(未来可用于包含更重的演示路径);当前始终走快速配置.
        chapter_ids: 章节 id 集合;其取值必须来自 `all_chapter_ids()`.
    """
    _ = slow_ok
    cfg = build_test_config_small()

    results: List[ChapterResult] = []

    wanted = list(chapter_ids)
    unknown = sorted(set(wanted) - set(_ALL_CHAPTER_IDS))
    if unknown:
        known = ", ".join(_ALL_CHAPTER_IDS)
        unknown_str = ", ".join(unknown)
        msg = f"unknown chapter_ids: {unknown_str} (known: {known})"
        raise ValueError(msg)

    workflow_yaml_path = yaml_path.parent / "workflow_fixture.yaml"
    runners = _build_chapter_runners(cfg=cfg, yaml_path=yaml_path, workflow_yaml_path=workflow_yaml_path)

    needs_tmpdir = any(chapter_id in _TMPDIR_CHAPTER_IDS for chapter_id in wanted)
    if needs_tmpdir:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            for chapter_id in wanted:
                results.append(runners[chapter_id](tmp_path))
        return results

    cwd = Path.cwd()
    for chapter_id in wanted:
        results.append(runners[chapter_id](cwd))

    return results


def run_all_chapters(*, yaml_path: Path, slow_ok: bool = False) -> List[ChapterResult]:
    return run_selected_chapters(yaml_path=yaml_path, chapter_ids=_ALL_CHAPTER_IDS, slow_ok=slow_ok)
