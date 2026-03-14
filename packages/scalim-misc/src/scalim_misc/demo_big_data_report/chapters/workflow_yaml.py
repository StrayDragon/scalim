from pathlib import Path
from typing import Any, Dict

from scalim.dsl.by_yaml import run_workflow

from ..loaders import (
    ECommerceConfig,
    get_workflow_preload_counter_calls,
    reset_workflow_preload_counter_calls,
    set_config,
)
from ._types import ChapterResult


def run_workflow_yaml(cfg: ECommerceConfig, *, workflow_yaml_path: Path) -> ChapterResult:
    """Workflow 主线: 运行 deterministic fixture 并对拍可观察点."""
    set_config(cfg)

    allowed_modules = frozenset(["scalim_misc.demo_big_data_report.loaders"])
    reset_workflow_preload_counter_calls()

    try:
        result = run_workflow(
            str(workflow_yaml_path),
            allowed_modules=allowed_modules,
            runtime_vars={"order_ids": []},
        )
    except Exception as exc:  # noqa: BLE001
        summary = "workflow failed: {}: {}".format(type(exc).__name__, exc)
        return ChapterResult(chapter_id="workflow_yaml", passed=False, summary=summary, details={"exc_type": type(exc).__name__})

    errors = result.errors()
    preload_calls = get_workflow_preload_counter_calls()
    run_ids = [o.run_id for o in result.outcomes]

    passed = bool(not errors and preload_calls == 1 and run_ids == ["r1", "r2"])
    summary = "outcomes={} preload_calls={} errors={}".format(len(result.outcomes), preload_calls, len(errors))
    if errors:
        summary = summary + "\nfirst_error: {} {}".format(errors[0].exc_type, errors[0].message)

    details: Dict[str, Any] = {
        "run_ids": run_ids,
        "preload_calls": preload_calls,
        "errors": errors,
        "outcomes": result.outcomes,
    }
    return ChapterResult(chapter_id="workflow_yaml", passed=passed, summary=summary, details=details)
