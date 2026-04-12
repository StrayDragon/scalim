import json
from pathlib import Path

import pytest

from scalim.workflow import resources_base as resources_base_mod
from scalim.workflow.resources_base import ScalimWorkflowWriteError, WorkflowResourceManagerBase


class _NoopInstrumentation:
    def emit(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        return None


class _DummyManager(WorkflowResourceManagerBase):
    def _commit_workbook(self, _plan: object) -> None:
        return None

    def _commit_csv(self, _plan: object) -> None:
        return None

    def _commit_sheetbook(self, _plan: object) -> None:
        return None

    def _discard_workbook(self, _plan: object, *, workflow_node_id: str, reason: str) -> None:
        return None

    def _discard_csv(self, _plan: object, *, workflow_node_id: str, reason: str) -> None:
        return None

    def _discard_sheetbook(self, _plan: object, *, workflow_node_id: str, reason: str) -> None:
        return None


def _make_manager(exec_id: str) -> _DummyManager:
    return _DummyManager(
        workflow_exec_id=str(exec_id),
        instrumentation=_NoopInstrumentation(),
        workbook_defs={},
        csv_defs={},
        sheetbook_defs={},
    )


def test_publish_staged_outputs_writes_manifest_and_latest_for_files(tmp_path: Path) -> None:
    mgr = _make_manager("exec_1")

    root = tmp_path / "out"
    final_path = root / "versions" / "exec_1" / "files" / "detail_csv.csv"
    staged_path = tmp_path / "staged.csv"
    staged_path.write_text("id,name\n1,a\n", encoding="utf-8")

    mgr._staged_outputs = [  # noqa: SLF001
        resources_base_mod._StagedOutput(
            resource_type="csv",
            resource_id="detail_csv",
            workflow_node_id="node_1",
            staged_path=str(staged_path),
            final_path=str(final_path),
        )
    ]
    mgr._publish_staged_outputs()  # noqa: SLF001

    latest_path = root / "manifest" / "latest.json"
    manifest_path = root / "versions" / "exec_1" / "manifest.json"
    assert latest_path.is_file()
    assert manifest_path.is_file()

    manifest_payload = json.loads(manifest_path.read_text("utf-8"))
    assert manifest_payload["version_id"] == "exec_1"
    assert manifest_payload["books"] == {}
    assert manifest_payload["files"]["detail_csv"] == "files/detail_csv.csv"


def test_publish_staged_outputs_rejects_version_id_mismatch(tmp_path: Path) -> None:
    mgr = _make_manager("exec_1")

    root = tmp_path / "out"
    final_path = root / "versions" / "exec_2" / "files" / "detail_csv.csv"
    staged_path = tmp_path / "staged.csv"
    staged_path.write_text("id,name\n1,a\n", encoding="utf-8")

    mgr._staged_outputs = [  # noqa: SLF001
        resources_base_mod._StagedOutput(
            resource_type="csv",
            resource_id="detail_csv",
            workflow_node_id="node_1",
            staged_path=str(staged_path),
            final_path=str(final_path),
        )
    ]

    with pytest.raises(ScalimWorkflowWriteError, match=r"version_id mismatch"):
        mgr._publish_staged_outputs()  # noqa: SLF001
