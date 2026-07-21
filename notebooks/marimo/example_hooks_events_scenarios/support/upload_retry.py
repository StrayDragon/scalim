# force-en
"""ch030 SSOT: upload retry on transient HTTP failures."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from scalim.dsl import yaml_dsl as api
from scalim.events import EventType, OutputTargetEndEvent
from scalim.ob.observer import EventDispatchObserver
from scalim_misc.examples._types import EXAMPLE_KIND_ORACLE, ExampleResult

from .fixtures import ALLOWED_MODULES, write_minimal_demand_yaml
from .http_mock import MockHttpServer, build_upload_payload, post_upload_with_status, start_mock_http_server

_EXAMPLE_ID = "example_hooks_events_scenarios/ch030_upload_retry"


class UploadWithRetry(EventDispatchObserver):
    # force-en
    """Observer that retries transient upload failures (application-side retry, not Scalim)."""

    def __init__(self, *, base_url: str, max_attempts: int = 3) -> None:
        self.event_types: Optional[Set[EventType]] = {EventType.OUTPUT_TARGET_END}
        self.base_url = str(base_url)
        self.max_attempts = int(max_attempts)
        self.attempts: List[Dict[str, Any]] = []
        self.uploaded: List[Dict[str, Any]] = []
        self.errors: List[str] = []

    def on_output_target_end(self, event: OutputTargetEndEvent) -> None:
        payload = build_upload_payload(
            target_id=str(event.target_id),
            output_path=None if event.output_path is None else str(event.output_path),
            row_count=int(event.row_count),
        )
        last_error: Optional[str] = None
        for attempt in range(1, self.max_attempts + 1):
            status, data = post_upload_with_status(self.base_url, payload)
            self.attempts.append({"attempt": attempt, "status": status, "body": data})
            if status == 200:
                self.uploaded.append(payload)
                return
            last_error = "status={} body={!r}".format(status, data)
        self.errors.append(last_error or "upload failed")


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


def run_upload_retry() -> ExampleResult:
    server: Optional[MockHttpServer] = None
    try:
        server = start_mock_http_server(upload_failures_remaining=2, upload_fail_status=503)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            demand_path = write_minimal_demand_yaml(tmp / "demand.yaml")
            obs = UploadWithRetry(base_url=server.base_url, max_attempts=3)
            result = api.run(
                str(demand_path),
                options=_demand_options(components=[obs], output_root=tmp / "out"),
            )

            passed = bool(
                result.total_rows == 3
                and len(obs.uploaded) == 1
                and not obs.errors
                and len(obs.attempts) == 3
                and [a["status"] for a in obs.attempts] == [503, 503, 200]
                and len(server.state.uploads) == 1
                and len(server.state.upload_attempts) == 3
            )
            summary = "rows={} attempts={} statuses={} uploaded={} errors={}".format(
                result.total_rows,
                len(obs.attempts),
                [a["status"] for a in obs.attempts],
                len(obs.uploaded),
                obs.errors,
            )
            details: Dict[str, Any] = {
                "attempts": list(obs.attempts),
                "uploaded": list(obs.uploaded),
                "server_uploads": list(server.state.uploads),
                "server_upload_attempts": list(server.state.upload_attempts),
                "note": "retry lives in Observer application code; Scalim only delivers OUTPUT_TARGET_END",
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
