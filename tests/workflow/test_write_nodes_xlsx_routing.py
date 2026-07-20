from scalim.sinks.memory import InMemoryCsv
from scalim.spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowArtifactsIr,
    WorkflowIr,
    WorkflowNodeType,
    WorkflowOptionsIr,
    WriteSheetNodeIr,
)
from scalim.workflow import write_nodes as write_nodes_mod
from scalim.workflow.artifacts import WorkflowArtifactsDirectory


def test_is_managed_xlsx_book() -> None:
    class _Mgr:
        def __init__(self, *, has_book: bool) -> None:
            self._has_book = has_book

        def has_xlsx_book(self, _book_id: str) -> bool:
            return bool(self._has_book)

    assert write_nodes_mod.is_managed_xlsx_book(_Mgr(has_book=True), "report") is True  # type: ignore[arg-type]
    assert write_nodes_mod.is_managed_xlsx_book(_Mgr(has_book=False), "report") is False  # type: ignore[arg-type]


def test_book_write_and_append_non_xlsx_kind_uses_csv_resolve() -> None:
    workflow_ir = WorkflowIr(
        nodes=(),
        edges=(),
        options=WorkflowOptionsIr(max_concurrency=1, failure_policy="all_fail"),
        resources=(),
        artifacts=WorkflowArtifactsIr(slots_by_node_id={}),
    )
    artifacts_dir = WorkflowArtifactsDirectory(workflow_ir)
    # Same node id for producer/consumer so visibility allows self-read in this unit test.
    artifacts_dir.publish("w", "outputs", {"detail": ""})
    artifacts_dir.publish("w", "in_memory_csv_outputs", {"detail": InMemoryCsv(header=["id"], rows=[["1"]])})

    class _Mgr:
        def has_xlsx_book(self, _book_id: str) -> bool:
            return False

        def apply_book_sheet(self, **kwargs: object) -> None:
            self.sheet_kwargs = dict(kwargs)

        def apply_book_append(self, **kwargs: object) -> None:
            self.append_kwargs = dict(kwargs)

    mgr = _Mgr()
    write_nodes_mod.run_workflow_write_sheet_node(
        WriteSheetNodeIr(
            node_id="w",
            node_type=WorkflowNodeType.WRITE_SHEET,
            decl_order=0,
            deps=(),
            resource_type="book",
            resource_id="unknown",
            sheet="S",
            input_node_id="w",
            input_output_id="detail",
            on_conflict="error",
        ),
        artifacts_dir=artifacts_dir,
        resource_manager=mgr,  # type: ignore[arg-type]
    )
    assert isinstance(mgr.sheet_kwargs["input_csv"], InMemoryCsv)

    write_nodes_mod.run_workflow_append_sheet_node(
        AppendSheetNodeIr(
            node_id="w",
            node_type=WorkflowNodeType.APPEND_SHEET,
            decl_order=0,
            deps=(),
            resource_type="book",
            resource_id="unknown",
            sheet="S",
            input_node_id="w",
            input_output_id="detail",
            align_by="field_id",
            header_policy="once",
            on_mismatch="error",
        ),
        artifacts_dir=artifacts_dir,
        resource_manager=mgr,  # type: ignore[arg-type]
    )
    assert isinstance(mgr.append_kwargs["input_csv"], InMemoryCsv)
