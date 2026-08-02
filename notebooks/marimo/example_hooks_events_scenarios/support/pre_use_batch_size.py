# force-en
"""ch040 SSOT: Hook overrides batch_size via pre_use_batch_size signal."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from scalim.dsl import yaml_dsl as api
from scalim.dsl.yaml_dsl import UNSET
from scalim.dsl.yaml_dsl.workflow_types import WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions
from scalim.events import Event, EventType, PipelineStartEvent
from scalim.hooks import BaseHook
from scalim.ob.observer import EventDispatchObserver
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

from .fixtures import ALLOWED_MODULES, write_minimal_demand_yaml, write_minimal_workflow_yaml

_EXAMPLE_ID = "example_hooks_events_scenarios/ch040_pre_use_batch_size"
_OVERRIDE_BATCH_SIZE = 2


class ForceBatchSizeHook(BaseHook):
    # force-en
    """Policy hook: rewrite batch_size before run_ir when runtime.batch_size is UNSET."""

    def __init__(self, *, next_value: int, reason: str) -> None:
        self.next_value = int(next_value)
        self.reason = str(reason)
        self.calls = 0
        self.last_prev: Optional[int] = None
        self.last_next: Optional[int] = None
        self.history_len = 0

    def on_pre_use_batch_size(self, decision: Any) -> None:
        self.calls += 1
        self.last_prev = None if decision.value is None else int(decision.value)
        decision.override(self.next_value, reason=self.reason)
        self.last_next = None if decision.value is None else int(decision.value)
        self.history_len = len(decision.history)


class BatchSizeProbe(EventDispatchObserver):
    # force-en
    """Records effective batch_size from PIPELINE_START."""

    def __init__(self) -> None:
        self.event_types: Optional[Set[EventType]] = {EventType.PIPELINE_START}
        self.batch_sizes: List[Optional[int]] = []

    def on_pipeline_start(self, event: Event) -> None:
        body = event.payload
        raw = getattr(body, "batch_size", None)
        self.batch_sizes.append(None if raw is None else int(raw))


def _demand_options(*, components: List[Any], output_root: Path) -> api.DemandRunOptions:
    overrides = api.RunOverrides.csv_file(
        output_root=str(output_root),
        fields=["item_id", "dim_id"],
        header_fields_output_by="name",
    )
    return api.DemandRunOptions(
        security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
        runtime=api.DemandRunRuntimeOptions(components=list(components), batch_size=UNSET),
        outputs=api.DemandRunOutputOptions(overrides=overrides),
    )


def run_pre_use_batch_size() -> ExampleResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        demand_path = write_minimal_demand_yaml(tmp / "demand.yaml")
        workflow_path = write_minimal_workflow_yaml(tmp / "workflow.yaml", demand_rel="demand.yaml")

        demand_hook = ForceBatchSizeHook(next_value=_OVERRIDE_BATCH_SIZE, reason="demo-demand")
        demand_probe = BatchSizeProbe()
        demand_result = api.run(
            str(demand_path),
            options=_demand_options(components=[demand_hook, demand_probe], output_root=tmp / "demand_out"),
        )

        workflow_hook = ForceBatchSizeHook(next_value=_OVERRIDE_BATCH_SIZE, reason="demo-workflow")
        workflow_probe = BatchSizeProbe()
        workflow_result = api.run_workflow(
            str(workflow_path),
            options=WorkflowRunOptions(
                demand=_demand_options(components=[workflow_hook, workflow_probe], output_root=tmp / "workflow_out"),
                runtime=WorkflowRuntimeOptions(
                    execution=WorkflowExecutionOptions(max_concurrency=1, failure_policy="all_fail"),
                ),
            ),
        )

        passed = bool(
            demand_result.total_rows == 3
            and demand_hook.calls == 1
            and demand_hook.last_next == _OVERRIDE_BATCH_SIZE
            and demand_hook.history_len == 1
            and demand_probe.batch_sizes == [_OVERRIDE_BATCH_SIZE]
            and workflow_result is not None
            and workflow_hook.calls == 1
            and workflow_hook.last_next == _OVERRIDE_BATCH_SIZE
            and workflow_probe.batch_sizes == [_OVERRIDE_BATCH_SIZE]
        )
        summary = (
            "demand_hook_calls={} demand_batch={} demand_pipeline_batch={} workflow_hook_calls={} workflow_pipeline_batch={}"
        ).format(
            demand_hook.calls,
            demand_hook.last_next,
            demand_probe.batch_sizes,
            workflow_hook.calls,
            workflow_probe.batch_sizes,
        )
        details: Dict[str, Any] = {
            "demand": {
                "hook_calls": demand_hook.calls,
                "prev": demand_hook.last_prev,
                "next": demand_hook.last_next,
                "pipeline_batch_sizes": list(demand_probe.batch_sizes),
            },
            "workflow": {
                "hook_calls": workflow_hook.calls,
                "prev": workflow_hook.last_prev,
                "next": workflow_hook.last_next,
                "pipeline_batch_sizes": list(workflow_probe.batch_sizes),
            },
            "note": "explicit DemandRunRuntimeOptions.batch_size skips the signal; leave UNSET to opt-in",
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
