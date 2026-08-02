# force-en
"""ch010 SSOT: post-export upload via OUTPUT_TARGET_END Observer."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from scalim.dsl import yaml_dsl as api
from scalim.dsl.yaml_dsl.workflow_types import WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions
from scalim.events import Event, EventType, OutputTargetEndEvent
from scalim.ob.observer import EventDispatchObserver, Observer
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

from .fixtures import ALLOWED_MODULES, write_minimal_demand_yaml, write_minimal_workflow_yaml
from .http_mock import MockHttpServer, build_upload_payload, post_upload, start_mock_http_server

_EXAMPLE_ID = "example_hooks_events_scenarios/ch010_post_export_upload"


class UploadOnOutputEnd(EventDispatchObserver):
    # force-en
    """Demand-layer observer: after each output target closes, POST metadata to mock upload API."""

    def __init__(self, *, base_url: str) -> None:
        self.event_types: Optional[Set[EventType]] = {EventType.OUTPUT_TARGET_END}
        self.base_url = str(base_url)
        self.uploaded: List[Dict[str, Any]] = []
        self.errors: List[str] = []

    def on_output_target_end(self, event: Event) -> None:
        body = event.payload
        payload = build_upload_payload(
            target_id=str(body.target_id),
            output_path=None if body.output_path is None else str(body.output_path),
            row_count=int(body.row_count),
        )
        try:
            _ = post_upload(self.base_url, payload)
            self.uploaded.append(payload)
        except Exception as exc:  # noqa: BLE001
            self.errors.append("{}: {}".format(type(exc).__name__, exc))


class WorkflowNodeEndMarker(Observer):
    # force-en
    """Workflow-layer observer: records WORKFLOW_NODE_END (always-on orchestration event)."""

    def __init__(self) -> None:
        self.event_types: Optional[Set[EventType]] = {EventType.WORKFLOW_NODE_END}
        self.ends: List[Dict[str, Any]] = []

    def on_event(self, event: Any) -> None:
        if getattr(event, "event_type", None) != EventType.WORKFLOW_NODE_END:
            return
        payload = getattr(event, "payload", None)
        self.ends.append(
            {
                "workflow_node_id": None if payload is None else str(getattr(payload, "workflow_node_id", None)),
                "status": None if payload is None else str(getattr(payload, "status", None)),
                "node_type": None if payload is None else str(getattr(payload, "node_type", None)),
            }
        )


def _demand_options(*, components: List[Any], output_root: Path) -> api.DemandRunOptions:
    overrides = api.RunOverrides.csv_file(
        output_root=str(output_root),
        fields=["item_id", "dim_id"],
        header_fields_output_by="name",
    )
    return api.DemandRunOptions(
        security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
        runtime=api.DemandRunRuntimeOptions(components=list(components), batch_size=10),
        outputs=api.DemandRunOutputOptions(overrides=overrides),
    )


def run_post_export_upload() -> ExampleResult:
    server: Optional[MockHttpServer] = None
    try:
        server = start_mock_http_server()
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            demand_path = write_minimal_demand_yaml(tmp / "demand.yaml")
            workflow_path = write_minimal_workflow_yaml(tmp / "workflow.yaml", demand_rel="demand.yaml")

            demand_obs = UploadOnOutputEnd(base_url=server.base_url)
            demand_result = api.run(
                str(demand_path),
                options=_demand_options(components=[demand_obs], output_root=tmp / "demand_out"),
            )

            workflow_obs = UploadOnOutputEnd(base_url=server.base_url)
            workflow_node_end = WorkflowNodeEndMarker()
            workflow_result = api.run_workflow(
                str(workflow_path),
                options=WorkflowRunOptions(
                    demand=_demand_options(components=[workflow_obs], output_root=tmp / "workflow_out"),
                    runtime=WorkflowRuntimeOptions(
                        execution=WorkflowExecutionOptions(max_concurrency=1, failure_policy="all_fail"),
                    ),
                    workflow_components=(workflow_node_end,),
                ),
            )

            demand_uploads = list(demand_obs.uploaded)
            workflow_uploads = list(workflow_obs.uploaded)
            server_uploads = list(server.state.uploads)
            node_ends = list(workflow_node_end.ends)
            main_ok = any(e.get("workflow_node_id") == "main" and e.get("status") == "ok" for e in node_ends)

            def _upload_ok(items: List[Dict[str, Any]]) -> bool:
                return bool(items) and all(u.get("output_path") and int(u.get("row_count") or 0) == 3 for u in items)

            passed = bool(
                demand_result.total_rows == 3
                and _upload_ok(demand_uploads)
                and all(int(u.get("size") or 0) > 0 for u in demand_uploads)
                and not demand_obs.errors
                and workflow_result is not None
                and _upload_ok(workflow_uploads)
                and not workflow_obs.errors
                and main_ok
                and len(server_uploads) == len(demand_uploads) + len(workflow_uploads)
            )
            summary = (
                "demand_rows={} demand_uploads={} workflow_uploads={} "
                "workflow_node_ends={} main_ok={} server_uploads={} errors_d={} errors_w={}"
            ).format(
                demand_result.total_rows,
                len(demand_uploads),
                len(workflow_uploads),
                len(node_ends),
                main_ok,
                len(server_uploads),
                demand_obs.errors,
                workflow_obs.errors,
            )
            details: Dict[str, Any] = {
                "demand_uploads": demand_uploads,
                "workflow_uploads": workflow_uploads,
                "workflow_node_ends": node_ends,
                "server_uploads": server_uploads,
                "injection": {
                    "demand": "DemandRunRuntimeOptions.components → OUTPUT_TARGET_END",
                    "workflow_demand_layer": "WorkflowRunOptions.demand.runtime.components → OUTPUT_TARGET_END",
                    "workflow_orchestration": "WorkflowRunOptions.workflow_components → WORKFLOW_NODE_END",
                },
            }
            return ExampleResult(
                example_id=_EXAMPLE_ID,
                passed=passed,
                kind=EXAMPLE_KIND_ORACLE,
                summary=summary,
                details=details,
            )
    finally:
        if server is not None:
            server.stop()
