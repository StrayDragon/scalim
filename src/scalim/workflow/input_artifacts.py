"""`workflow` 输入工件解析辅助.

说明:
- 统一处理 `workflow-managed` 输出与可见性校验.
- 运行时需兼容 `Python 3.6`.
"""

from typing import TYPE_CHECKING, Dict, Optional, Tuple, cast

from ..typedefs import RuntimeValue
from .artifacts import WorkflowArtifactsDirectory
from .errors import ScalimWorkflowConfigError
from .resources_base import ScalimWorkflowWriteError
from .resources_csv import WorkflowCsvInput
from .tabular_artifacts import WorkflowTabularInput

if TYPE_CHECKING:
    from ..sinks.rows import InMemoryRows


def _get_optional_workflow_artifact(
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    consumer_node_id: str,
    consumer_decl_order: int,
    input_node_id: str,
    artifact_id: str,
) -> Optional[RuntimeValue]:
    path_prefix = "workflow.runs.{}".format(int(consumer_decl_order))
    try:
        return artifacts_dir.get_optional(str(consumer_node_id), str(input_node_id), str(artifact_id))
    except ValueError as exc:
        raise ScalimWorkflowConfigError(str(exc), path="{}.input_node_id".format(path_prefix)) from exc


def _resolve_workflow_output_binding(
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    consumer_node_id: str,
    consumer_decl_order: int,
    input_node_id: str,
    input_output_id: str,
    error_prefix: str,
) -> Tuple[str, bool, str]:
    outputs_obj = _get_optional_workflow_artifact(
        artifacts_dir=artifacts_dir,
        consumer_node_id=str(consumer_node_id),
        consumer_decl_order=int(consumer_decl_order),
        input_node_id=str(input_node_id),
        artifact_id="outputs",
    )
    outputs = cast("Optional[Dict[str, str]]", outputs_obj)  # pragma: allow-cast workflow output mapping typed narrowing
    if outputs_obj is None:
        msg = "{} requires demand outputs mapping: input_node_id={!r}".format(str(error_prefix), str(input_node_id))
        raise ScalimWorkflowWriteError(msg)

    output_id = str(input_output_id)
    output_in_mapping = outputs is not None and output_id in outputs
    output_path = str(outputs.get(output_id) or "") if output_in_mapping and outputs is not None else ""
    return output_id, bool(output_in_mapping), output_path


def resolve_workflow_input_csv(
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    consumer_node_id: str,
    consumer_decl_order: int,
    input_node_id: str,
    input_output_id: str,
    error_prefix: str,
) -> WorkflowCsvInput:
    output_id, output_in_mapping, output_path = _resolve_workflow_output_binding(
        artifacts_dir=artifacts_dir,
        consumer_node_id=str(consumer_node_id),
        consumer_decl_order=int(consumer_decl_order),
        input_node_id=str(input_node_id),
        input_output_id=str(input_output_id),
        error_prefix=str(error_prefix),
    )

    mem_map_obj = _get_optional_workflow_artifact(
        artifacts_dir=artifacts_dir,
        consumer_node_id=str(consumer_node_id),
        consumer_decl_order=int(consumer_decl_order),
        input_node_id=str(input_node_id),
        artifact_id="in_memory_csv_outputs",
    )
    mem_map = cast("Optional[Dict[str, WorkflowCsvInput]]", mem_map_obj)  # pragma: allow-cast workflow csv mapping typed narrowing
    csv_artifact = mem_map.get(output_id) if mem_map is not None else None
    if csv_artifact is not None:
        return csv_artifact

    if output_path:
        if not str(output_path).lower().endswith(".csv"):
            msg = "workflow writes currently only supports CSV outputs: output_path={!r}".format(str(output_path))
            raise ScalimWorkflowWriteError(msg)
        return output_path
    if output_in_mapping:
        msg = "Missing workflow-managed in-memory CSV artifact: input_node_id={!r}, output_id={!r}".format(str(input_node_id), output_id)
        raise ScalimWorkflowWriteError(msg)
    msg = "Unknown demand output id: input_node_id={!r}, output_id={!r}".format(str(input_node_id), output_id)
    raise ScalimWorkflowWriteError(msg)


def resolve_workflow_input_tabular(
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    consumer_node_id: str,
    consumer_decl_order: int,
    input_node_id: str,
    input_output_id: str,
    error_prefix: str,
) -> WorkflowTabularInput:
    output_id, output_in_mapping, output_path = _resolve_workflow_output_binding(
        artifacts_dir=artifacts_dir,
        consumer_node_id=str(consumer_node_id),
        consumer_decl_order=int(consumer_decl_order),
        input_node_id=str(input_node_id),
        input_output_id=str(input_output_id),
        error_prefix=str(error_prefix),
    )

    rows_map_obj = _get_optional_workflow_artifact(
        artifacts_dir=artifacts_dir,
        consumer_node_id=str(consumer_node_id),
        consumer_decl_order=int(consumer_decl_order),
        input_node_id=str(input_node_id),
        artifact_id="in_memory_rows_outputs",
    )
    rows_map = cast("Optional[Dict[str, InMemoryRows]]", rows_map_obj)  # pragma: allow-cast workflow rows map typed narrowing
    rows_artifact = rows_map.get(output_id) if rows_map is not None else None
    if rows_artifact is not None:
        return rows_artifact

    try:
        return resolve_workflow_input_csv(
            artifacts_dir=artifacts_dir,
            consumer_node_id=str(consumer_node_id),
            consumer_decl_order=int(consumer_decl_order),
            input_node_id=str(input_node_id),
            input_output_id=str(input_output_id),
            error_prefix=str(error_prefix),
        )
    except ScalimWorkflowWriteError:
        if output_in_mapping and not output_path:
            msg = "Missing workflow-managed tabular artifact: input_node_id={!r}, output_id={!r}".format(str(input_node_id), output_id)
            raise ScalimWorkflowWriteError(msg) from None
        raise


def resolve_workflow_output_export_header(
    *,
    artifacts_dir: WorkflowArtifactsDirectory,
    consumer_node_id: str,
    consumer_decl_order: int,
    input_node_id: str,
    input_output_id: str,
) -> Optional[Tuple[str, ...]]:
    path_prefix = "workflow.runs.{}".format(int(consumer_decl_order))
    try:
        headers_obj = artifacts_dir.get_optional(str(consumer_node_id), str(input_node_id), "in_memory_csv_export_headers")
    except ValueError as exc:
        raise ScalimWorkflowConfigError(str(exc), path="{}.input_node_id".format(path_prefix)) from exc

    headers_map = cast("Optional[Dict[str, Tuple[str, ...]]]", headers_obj)  # pragma: allow-cast workflow header map typed narrowing
    if headers_map is None:
        return None
    header = headers_map.get(str(input_output_id))
    if header is None:
        return None
    return tuple(str(x) for x in header)


__all__ = (
    "resolve_workflow_input_csv",
    "resolve_workflow_input_tabular",
    "resolve_workflow_output_export_header",
)
