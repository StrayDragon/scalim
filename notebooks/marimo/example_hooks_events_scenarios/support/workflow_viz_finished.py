# force-en
"""ch050 SSOT: WORKFLOW_STARTED/FINISHED via workflow viz + workflow_components."""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from scalim.dsl import yaml_dsl as api
from scalim.dsl.yaml_dsl.workflow_types import WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions
from scalim.events import EventType
from scalim.ob.observer import Observer
from scalim.ob.presets.viz import VizObserverConfig
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

from .fixtures import ALLOWED_MODULES, write_minimal_demand_yaml, write_minimal_workflow_yaml

_EXAMPLE_ID = "example_hooks_events_scenarios/ch050_workflow_viz_finished"


class WorkflowLifecycleMarker(Observer):
    # force-en
    """Records WORKFLOW_STARTED / WORKFLOW_FINISHED (emitted only when workflow viz is enabled)."""

    def __init__(self) -> None:
        self.event_types: Optional[Set[EventType]] = {
            EventType.WORKFLOW_STARTED,
            EventType.WORKFLOW_FINISHED,
        }
        self.started = 0
        self.finished = 0
        self.last_finished_status: Optional[str] = None
        self.seen: List[str] = []

    def on_event(self, event: Any) -> None:
        event_type = getattr(event, "event_type", None)
        if event_type == EventType.WORKFLOW_STARTED:
            self.started += 1
            self.seen.append("workflow_started")
            return
        if event_type == EventType.WORKFLOW_FINISHED:
            self.finished += 1
            self.seen.append("workflow_finished")
            payload = getattr(event, "payload", None)
            self.last_finished_status = None if payload is None else str(getattr(payload, "status", None))


def _demand_options(*, output_root: Path, viz_dir: Path) -> api.DemandRunOptions:
    csv = api.RunOverrides.csv_file(
        output_root=str(output_root),
        fields=["item_id", "dim_id"],
        header_fields_output_by="name",
    )
    overrides = replace(
        csv,
        viz_config=VizObserverConfig(
            output_dir=str(viz_dir),
            payload_policy="summary",
            run_name="hooks-events-workflow-viz",
        ),
    )
    return api.DemandRunOptions(
        security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
        runtime=api.DemandRunRuntimeOptions(batch_size=10),
        outputs=api.DemandRunOutputOptions(overrides=overrides),
    )


def run_workflow_viz_finished() -> ExampleResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        demand_path = write_minimal_demand_yaml(tmp / "demand.yaml")
        workflow_path = write_minimal_workflow_yaml(tmp / "workflow.yaml", demand_rel="demand.yaml")
        viz_dir = tmp / "viz"
        marker = WorkflowLifecycleMarker()

        result = api.run_workflow(
            str(workflow_path),
            options=WorkflowRunOptions(
                demand=_demand_options(output_root=tmp / "out", viz_dir=viz_dir),
                runtime=WorkflowRuntimeOptions(
                    execution=WorkflowExecutionOptions(max_concurrency=1, failure_policy="all_fail"),
                ),
                workflow_components=(marker,),
            ),
        )

        viz_events = list(viz_dir.rglob("viz_events.jsonl"))
        passed = bool(
            result is not None
            and marker.started == 1
            and marker.finished == 1
            and marker.last_finished_status == "ok"
            and marker.seen == ["workflow_started", "workflow_finished"]
            and len(viz_events) >= 1
        )
        summary = "started={} finished={} status={} viz_events_files={} seen={}".format(
            marker.started,
            marker.finished,
            marker.last_finished_status,
            len(viz_events),
            marker.seen,
        )
        details: Dict[str, Any] = {
            "seen": list(marker.seen),
            "finished_status": marker.last_finished_status,
            "viz_events": [str(p) for p in viz_events],
            "note": (
                "WORKFLOW_STARTED/FINISHED require workflow viz "
                "(demand.outputs.overrides.viz_config.output_dir); "
                "without viz use WORKFLOW_NODE_* instead (see ch010)"
            ),
        }
        return ExampleResult(
            example_id=_EXAMPLE_ID,
            passed=passed,
            kind=EXAMPLE_KIND_ORACLE,
            summary=summary,
            details=details,
        )
