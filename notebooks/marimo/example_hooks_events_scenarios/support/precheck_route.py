# force-en
"""ch020 SSOT: app-layer estimate → HTTP dispatch → sync/async."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from scalim.dsl import yaml_dsl as api
from scalim.dsl.yaml_dsl.workflow_types import WorkflowExecutionOptions, WorkflowRunOptions, WorkflowRuntimeOptions
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

from .fixtures import (
    ALLOWED_MODULES,
    ASYNC_ESTIMATED_ROWS,
    SYNC_ESTIMATED_ROWS,
    write_minimal_demand_yaml,
    write_minimal_workflow_yaml,
)
from .http_mock import MockHttpServer, post_dispatch, start_mock_http_server

_EXAMPLE_ID = "example_hooks_events_scenarios/ch020_precheck_route_sync_async"


def estimate_job(*, estimated_rows: int) -> Dict[str, Any]:
    # force-en
    """App-layer mock precheck (not Scalim workflow_preflight)."""
    return {"estimated_rows": int(estimated_rows), "estimated_duration_secs": max(1, int(estimated_rows) // 1000)}


def _demand_options(*, output_root: Path) -> api.DemandRunOptions:
    overrides = api.RunOverrides.csv_file(
        output_root=str(output_root),
        fields=["item_id", "dim_id"],
        header_fields_output_by="name",
    )
    return api.DemandRunOptions(
        security=api.DemandRunSecurityOptions(allowed_modules=ALLOWED_MODULES),
        runtime=api.DemandRunRuntimeOptions(batch_size=10),
        outputs=api.DemandRunOutputOptions(overrides=overrides),
    )


def route_and_maybe_run(
    *,
    server: MockHttpServer,
    job_id: str,
    estimated_rows: int,
    entrypoint: str,
    demand_path: Path,
    workflow_path: Path,
    output_root: Path,
    async_queue: List[Dict[str, Any]],
) -> Dict[str, Any]:
    estimate = estimate_job(estimated_rows=estimated_rows)
    decision = post_dispatch(
        server.base_url,
        {"job_id": job_id, "entrypoint": entrypoint, **estimate},
    )
    mode = str(decision.get("mode") or "")
    record: Dict[str, Any] = {
        "job_id": job_id,
        "entrypoint": entrypoint,
        "estimate": estimate,
        "mode": mode,
        "ran": False,
        "total_rows": None,
        "enqueued": False,
    }
    if mode == "async":
        async_queue.append({"job_id": job_id, "entrypoint": entrypoint, "estimate": estimate})
        record["enqueued"] = True
        return record

    if mode != "sync":
        msg = "unexpected dispatch mode: {!r}".format(mode)  # force-en
        raise RuntimeError(msg)  # force-en

    if entrypoint == "demand":
        result = api.run(str(demand_path), options=_demand_options(output_root=output_root))
        record["ran"] = True
        record["total_rows"] = int(result.total_rows)
        return record

    if entrypoint == "workflow":
        wf = api.run_workflow(
            str(workflow_path),
            options=WorkflowRunOptions(
                demand=_demand_options(output_root=output_root),
                runtime=WorkflowRuntimeOptions(
                    execution=WorkflowExecutionOptions(max_concurrency=1, failure_policy="all_fail"),
                ),
            ),
        )
        total_rows = 0
        for outcome in wf.outcomes:
            if outcome.error is None and outcome.result is not None:
                total_rows += int(outcome.result.total_rows)
        record["ran"] = True
        record["total_rows"] = total_rows
        return record

    msg = "unknown entrypoint: {!r}".format(entrypoint)  # force-en
    raise RuntimeError(msg)  # force-en


def run_precheck_route_sync_async() -> ExampleResult:
    server: Optional[MockHttpServer] = None
    async_queue: List[Dict[str, Any]] = []
    try:
        server = start_mock_http_server(async_rows_threshold=100)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            demand_path = write_minimal_demand_yaml(tmp / "demand.yaml")
            workflow_path = write_minimal_workflow_yaml(tmp / "workflow.yaml", demand_rel="demand.yaml")

            sync_demand = route_and_maybe_run(
                server=server,
                job_id="sync-demand",
                estimated_rows=SYNC_ESTIMATED_ROWS,
                entrypoint="demand",
                demand_path=demand_path,
                workflow_path=workflow_path,
                output_root=tmp / "sync_demand_out",
                async_queue=async_queue,
            )
            sync_workflow = route_and_maybe_run(
                server=server,
                job_id="sync-workflow",
                estimated_rows=SYNC_ESTIMATED_ROWS,
                entrypoint="workflow",
                demand_path=demand_path,
                workflow_path=workflow_path,
                output_root=tmp / "sync_workflow_out",
                async_queue=async_queue,
            )
            async_demand = route_and_maybe_run(
                server=server,
                job_id="async-demand",
                estimated_rows=ASYNC_ESTIMATED_ROWS,
                entrypoint="demand",
                demand_path=demand_path,
                workflow_path=workflow_path,
                output_root=tmp / "async_demand_out",
                async_queue=async_queue,
            )
            async_workflow = route_and_maybe_run(
                server=server,
                job_id="async-workflow",
                estimated_rows=ASYNC_ESTIMATED_ROWS,
                entrypoint="workflow",
                demand_path=demand_path,
                workflow_path=workflow_path,
                output_root=tmp / "async_workflow_out",
                async_queue=async_queue,
            )

            async_files = list((tmp / "async_demand_out").rglob("*")) + list((tmp / "async_workflow_out").rglob("*"))
            async_files = [p for p in async_files if p.is_file()]

            passed = bool(
                sync_demand["mode"] == "sync"
                and sync_demand["ran"]
                and sync_demand["total_rows"] == 3
                and sync_workflow["mode"] == "sync"
                and sync_workflow["ran"]
                and sync_workflow["total_rows"] == 3
                and async_demand["mode"] == "async"
                and async_demand["enqueued"]
                and not async_demand["ran"]
                and async_workflow["mode"] == "async"
                and async_workflow["enqueued"]
                and not async_workflow["ran"]
                and len(async_queue) == 2
                and len(async_files) == 0
                and len(server.state.dispatches) == 4
            )
            summary = ("sync_demand_rows={} sync_workflow_rows={} async_queue={} dispatches={} async_files={}").format(
                sync_demand.get("total_rows"),
                sync_workflow.get("total_rows"),
                len(async_queue),
                len(server.state.dispatches),
                len(async_files),
            )
            details: Dict[str, Any] = {
                "sync_demand": sync_demand,
                "sync_workflow": sync_workflow,
                "async_demand": async_demand,
                "async_workflow": async_workflow,
                "async_queue": list(async_queue),
                "dispatches": list(server.state.dispatches),
                "note": "precheck is app-layer estimate→HTTP; same router wraps demand run and workflow run_workflow",
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
