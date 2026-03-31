import marimo

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from scalim.dsl.by_yaml import RunOverrides, run_workflow
from scalim.ob.presets.viz import VizObserverConfig
from scalim_misc.demo_big_data_report.cases import build_test_config_small
from scalim_misc.demo_big_data_report.loaders import (
    ECommerceConfig,
    get_config,
    reset_workflow_preload_counter_calls,
    set_config,
)
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

__generated_with = "0.20.2"
app = marimo.App(width="full")

_EXAMPLE_ID = "demo_big_data_report/workflow_cache_pool_pin"
_ALLOWED_MODULES = frozenset(["scalim_misc.demo_big_data_report.loaders"])


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        events.append(json.loads(text))
    return events


def _workflow_events_path(base_dir: Path) -> Path:
    return base_dir / "scalim-viz" / "workflow" / "viz_events.jsonl"


def _extract_cache_signals(events: Sequence[Mapping[str, Any]]) -> Tuple[List[str], List[str]]:
    reasons: List[str] = []
    release_is_pinned: List[str] = []
    for e in events:
        if not isinstance(e, dict):
            continue
        event_type = str(e.get("event_type") or "")
        payload = e.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        if event_type == "workflow_cache_evict":
            reasons.append(str(payload.get("reason") or ""))
        if event_type == "workflow_cache_release":
            release_is_pinned.append(str(payload.get("is_pinned") or ""))
    return reasons, release_is_pinned


def run_workflow_cache_pool_pin(
    cfg: Optional[ECommerceConfig] = None,
    *,
    workflow_yaml_no_pin: Optional[Path] = None,
    workflow_yaml_pin: Optional[Path] = None,
) -> ExampleResult:
    if cfg is None:
        cfg = build_test_config_small()
    demo_dir = Path(__file__).resolve().parents[1]
    if workflow_yaml_no_pin is None:
        workflow_yaml_no_pin = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_fixture.yaml"
    if workflow_yaml_pin is None:
        workflow_yaml_pin = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_fixture_cache_pool_pin.yaml"

    prev = get_config()
    set_config(cfg)
    try:
        with tempfile.TemporaryDirectory(prefix="scalim-wf-pin-") as tmpdir:
            tmp = Path(tmpdir)
            viz_no_pin = tmp / "no_pin"
            viz_pin = tmp / "pin"

            reset_workflow_preload_counter_calls()

            # 1) 基线: 没有 `pin` -> 引用计数归零时会触发 `refcount_zero` 淘汰
            _ = run_workflow(
                str(workflow_yaml_no_pin),
                allowed_modules=_ALLOWED_MODULES,
                init_vars={"order_ids": []},
                overrides=RunOverrides(viz_config=VizObserverConfig(output_dir=str(viz_no_pin))),
            )
            events_no_pin = _read_jsonl(_workflow_events_path(viz_no_pin))
            reasons_no_pin, releases_no_pin = _extract_cache_signals(events_no_pin)

            # 2) 启用 `pin`: 引用计数归零时不淘汰,仅在 `workflow_end` 统一释放
            _ = run_workflow(
                str(workflow_yaml_pin),
                allowed_modules=_ALLOWED_MODULES,
                init_vars={"order_ids": []},
                overrides=RunOverrides(viz_config=VizObserverConfig(output_dir=str(viz_pin))),
            )
            events_pin = _read_jsonl(_workflow_events_path(viz_pin))
            reasons_pin, releases_pin = _extract_cache_signals(events_pin)

            ok_no_pin = "refcount_zero" in set(reasons_no_pin)
            ok_pin = ("workflow_end" in set(reasons_pin)) and ("refcount_zero" not in set(reasons_pin))
            ok_release_flag = ("True" in set(releases_pin)) and ("True" not in set(releases_no_pin))

            passed = bool(ok_no_pin and ok_pin and ok_release_flag)
            summary = "no_pin={} pin={} release_is_pinned={}".format(ok_no_pin, ok_pin, ok_release_flag)
            details: Dict[str, Any] = {
                "workflow_yaml_no_pin": str(workflow_yaml_no_pin),
                "workflow_yaml_pin": str(workflow_yaml_pin),
                "viz_dirs": {"no_pin": str(viz_no_pin), "pin": str(viz_pin)},
                "evict_reasons": {"no_pin": reasons_no_pin, "pin": reasons_pin},
                "release_is_pinned": {"no_pin": releases_no_pin, "pin": releases_pin},
                "events_count": {"no_pin": len(events_no_pin), "pin": len(events_pin)},
            }
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=passed,
                kind=EXAMPLE_KIND_ORACLE,
                summary=summary,
                details=details,
            )
    finally:
        set_config(prev)


def run_chapter() -> ExampleResult:
    return run_workflow_cache_pool_pin()


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        r"""
        # demo_big_data_report / workflow_cache_pool_pin

        ## 背景

        当一个 workflow 里有多个节点都依赖同一份 `preload_forever` 小表时,`cache_pool` 可以让它在 workflow 内复用。

        但默认的 `release_policy=dag_refcount` 会在“最后一个消费者完成”后淘汰条目(原因 `refcount_zero`)。
        某些场景下,我们希望把这个小表 **pin 到 workflow 结束**:
        - 便于 debug/replay 时稳定复用
        - 避免在后续节点/阶段里重复 preload（当图结构/消费者集合变化时更稳）

        ## 需求方提问（自然语言）

        平台同学：workflow YAML 里能不能声明“哪些 source 要 pin”,并且在 CI 里验证 pin 生效？

        ## 本章覆盖的 YAML DSL 能力

        - `workflow.options.cache_pool.pin`：把指定 `(kind, source_id)` 的条目 pin 住(不因 `refcount_zero` 被淘汰)

        ## 对拍点（deterministic）

        - 无 pin：workflow cache evict reason 包含 `refcount_zero`
        - 有 pin：workflow cache evict reason 只出现 `workflow_end`,且 release 事件 `is_pinned=True`

        SSOT:
        - `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch140_workflow_cache_pool_pin.py::run_workflow_cache_pool_pin`
        """
    )
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

    _ = ensure_repo_root_on_sys_path(__file__)
    demo_dir = Path(__file__).resolve().parents[1]
    workflow_yaml_no_pin = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_fixture.yaml"
    workflow_yaml_pin = demo_dir / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "workflow_fixture_cache_pool_pin.yaml"
    return demo_dir, workflow_yaml_no_pin, workflow_yaml_pin


@app.cell(hide_code=True)
def _(mo, workflow_yaml_no_pin, workflow_yaml_pin):
    from scalim_misc.notebook_support.yaml_excerpt import excerpt_head

    mo.md("## Workflow YAML (no pin)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(workflow_yaml_no_pin, max_lines=120)))
    mo.md("## Workflow YAML (with pin)")
    mo.md("```yaml\n{}\n```".format(excerpt_head(workflow_yaml_pin, max_lines=160)))
    return (excerpt_head,)


@app.cell
def _(workflow_yaml_no_pin, workflow_yaml_pin):
    cfg = build_test_config_small()
    result = run_workflow_cache_pool_pin(cfg, workflow_yaml_no_pin=workflow_yaml_no_pin, workflow_yaml_pin=workflow_yaml_pin)
    return cfg, result


@app.cell(hide_code=True)
def _(mo, result):
    mo.callout(mo.md("## {}".format("PASS" if result.passed else "FAIL")), kind="success" if result.passed else "danger")
    mo.md("```\n{}\n```".format(result.summary))
    return


@app.cell(hide_code=True)
def _(mo, result):
    from scalim_misc.notebook_support.results_view import details_to_rows

    rows = details_to_rows(result.details)
    mo.ui.table(rows, selection=None)
    return (rows,)


if __name__ == "__main__":
    app.run()
