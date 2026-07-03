"""工作流 `write` 节点执行助手.

说明:
- 该模块从 `src/scalim/workflow/execute.py` 抽离,用于降低 `execute.py` 体积(`c45`).
"""

from ..spec.ir._workflow import (
    AppendSheetNodeIr,
    WorkflowAnyNodeIr,
    WriteSheetNodeIr,
)
from .artifacts import WorkflowArtifactsDirectory
from .input_artifacts import (
    resolve_workflow_input_csv as _resolve_workflow_input_csv,
)
from .input_artifacts import (
    resolve_workflow_input_tabular as _resolve_workflow_input_tabular,
)
from .input_artifacts import (
    resolve_workflow_output_export_header as _resolve_workflow_output_export_header,
)
from .resources import ScalimWorkflowWriteError, WorkflowResourceManager


def run_workflow_write_sheet_node(
    node: WriteSheetNodeIr,
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    resource_manager: WorkflowResourceManager,
) -> None:
    if str(node.resource_type) == "book":
        book_kind = resource_manager.get_book_kind(str(node.resource_id))
        if book_kind == "xlsx_memory":
            input_csv = _resolve_workflow_input_tabular(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
                error_prefix="write node",
            )
        else:
            input_csv = _resolve_workflow_input_csv(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
                error_prefix="write node",
            )
        resource_manager.apply_book_sheet(
            workflow_node_id=str(node.node_id),
            decl_order=int(node.decl_order),
            book_id=str(node.resource_id),
            sheet=str(node.sheet),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_csv,
            export_header=_resolve_workflow_output_export_header(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
            ),
            on_conflict=str(node.on_conflict or "error"),
        )
        return

    if str(node.resource_type) == "workbook":
        input_csv = _resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id=str(node.node_id),
            consumer_decl_order=int(node.decl_order),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            error_prefix="write node",
        )
        resource_manager.apply_workbook_sheet(
            workflow_node_id=str(node.node_id),
            decl_order=int(node.decl_order),
            workbook_id=str(node.resource_id),
            sheet=str(node.sheet),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_csv,
            export_header=_resolve_workflow_output_export_header(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
            ),
            on_conflict=str(node.on_conflict or "error"),
        )
        return

    if str(node.resource_type) == "sheetbook":
        input_tabular = _resolve_workflow_input_tabular(
            artifacts_dir=artifacts_dir,
            consumer_node_id=str(node.node_id),
            consumer_decl_order=int(node.decl_order),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            error_prefix="write node",
        )
        resource_manager.apply_sheetbook_sheet(
            workflow_node_id=str(node.node_id),
            decl_order=int(node.decl_order),
            sheetbook_id=str(node.resource_id),
            sheet=str(node.sheet),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_tabular,
            export_header=_resolve_workflow_output_export_header(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
            ),
            on_conflict=str(node.on_conflict or "error"),
        )
        return

    msg = "Unsupported write_sheet resource_type: {!r}".format(
        str(node.resource_type)
    )  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated
    raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated


def run_workflow_append_sheet_node(
    node: AppendSheetNodeIr,
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    resource_manager: WorkflowResourceManager,
) -> None:
    if str(node.resource_type) == "book":
        book_kind = resource_manager.get_book_kind(str(node.resource_id))
        if book_kind == "xlsx_memory":
            input_csv = _resolve_workflow_input_tabular(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
                error_prefix="append node",
            )
        else:
            input_csv = _resolve_workflow_input_csv(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
                error_prefix="append node",
            )
        if not node.sheet:  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            msg = "append_sheet requires sheet for book resource (resource_id={!r})".format(
                str(node.resource_id)
            )  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
        resource_manager.apply_book_append(
            workflow_node_id=str(node.node_id),
            decl_order=int(node.decl_order),
            book_id=str(node.resource_id),
            sheet=str(node.sheet),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_csv,
            export_header=_resolve_workflow_output_export_header(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
            ),
            align_by=str(node.align_by or "field_id"),
            header_policy=str(node.header_policy or "once"),
            on_mismatch=str(node.on_mismatch or "error"),
        )
        return

    if str(node.resource_type) == "workbook":
        input_csv = _resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id=str(node.node_id),
            consumer_decl_order=int(node.decl_order),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            error_prefix="append node",
        )
        if not node.sheet:  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            msg = "append_sheet requires sheet for workbook resource (resource_id={!r})".format(
                str(node.resource_id)
            )  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
        resource_manager.apply_workbook_append(
            workflow_node_id=str(node.node_id),
            decl_order=int(node.decl_order),
            workbook_id=str(node.resource_id),
            sheet=str(node.sheet),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_csv,
            export_header=_resolve_workflow_output_export_header(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
            ),
            align_by=str(node.align_by or "field_id"),
            header_policy=str(node.header_policy or "once"),
            on_mismatch=str(node.on_mismatch or "error"),
        )
        return

    if str(node.resource_type) == "csv":
        input_csv = _resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id=str(node.node_id),
            consumer_decl_order=int(node.decl_order),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            error_prefix="append node",
        )
        resource_manager.apply_csv_append(
            workflow_node_id=str(node.node_id),
            decl_order=int(node.decl_order),
            csv_id=str(node.resource_id),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_csv,
            export_header=_resolve_workflow_output_export_header(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
            ),
            header_policy=str(node.header_policy or "once"),
            on_mismatch=str(node.on_mismatch or "error"),
        )
        return

    if str(node.resource_type) == "sheetbook":
        input_tabular = _resolve_workflow_input_tabular(
            artifacts_dir=artifacts_dir,
            consumer_node_id=str(node.node_id),
            consumer_decl_order=int(node.decl_order),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            error_prefix="append node",
        )
        if not node.sheet:  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            msg = "append_sheet requires sheet for sheetbook resource (resource_id={!r})".format(
                str(node.resource_id)
            )  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
            raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover invariant: sheet required by IR
        resource_manager.apply_sheetbook_append(
            workflow_node_id=str(node.node_id),
            decl_order=int(node.decl_order),
            sheetbook_id=str(node.resource_id),
            sheet=str(node.sheet),
            input_node_id=str(node.input_node_id),
            input_output_id=str(node.input_output_id),
            input_csv=input_tabular,
            export_header=_resolve_workflow_output_export_header(
                artifacts_dir=artifacts_dir,
                consumer_node_id=str(node.node_id),
                consumer_decl_order=int(node.decl_order),
                input_node_id=str(node.input_node_id),
                input_output_id=str(node.input_output_id),
            ),
            align_by=str(node.align_by or "field_id"),
            header_policy=str(node.header_policy or "once"),
            on_mismatch=str(node.on_mismatch or "error"),
        )
        return

    msg = "Unsupported append_sheet resource_type: {!r}".format(
        str(node.resource_type)
    )  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated
    raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated


def run_workflow_write_node(
    node: WorkflowAnyNodeIr,
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    resource_manager: WorkflowResourceManager,
) -> None:
    if isinstance(node, WriteSheetNodeIr):
        run_workflow_write_sheet_node(
            node,
            artifacts_dir=artifacts_dir,
            resource_manager=resource_manager,
        )
        return

    if isinstance(node, AppendSheetNodeIr):
        run_workflow_append_sheet_node(
            node,
            artifacts_dir=artifacts_dir,
            resource_manager=resource_manager,
        )
        return

    msg = "Unsupported workflow node type: {}".format(
        type(node).__name__
    )  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated
    raise ScalimWorkflowWriteError(msg)  # pragma: no cover  # pragma: allow-no-cover unreachable: IR validated


__all__ = ()
