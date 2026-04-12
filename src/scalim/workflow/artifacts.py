"""`workflow` `artifacts` 模块(稳定导入路径)."""

from typing import TYPE_CHECKING, Dict, FrozenSet, Optional, Tuple, cast

from ..spec.ir._workflow import WorkflowIr
from .visibility_index import WorkflowVisibilityIndex

if TYPE_CHECKING:
    from ..sinks.rows import InMemoryRows
    from .resources_csv import WorkflowCsvInput


class WorkflowArtifactsDirectory:
    _visible_by_consumer_node_id: Dict[str, FrozenSet[str]]
    _values_by_producer_node_id: Dict[str, Dict[str, object]]

    def __init__(self, workflow_ir: WorkflowIr) -> None:
        visibility = WorkflowVisibilityIndex.from_workflow_ir(workflow_ir)
        self._visible_by_consumer_node_id = visibility.visible_by_consumer_node_id
        self._values_by_producer_node_id = {}

    def visible_producer_node_ids(self, consumer_node_id: str) -> FrozenSet[str]:
        return self._visible_by_consumer_node_id.get(str(consumer_node_id), frozenset())

    def publish(self, producer_node_id: str, artifact_id: str, value: object) -> None:
        by_artifact = self._values_by_producer_node_id.setdefault(str(producer_node_id), {})
        by_artifact[str(artifact_id)] = value

    def get(self, consumer_node_id: str, producer_node_id: str, artifact_id: str) -> object:
        consumer = str(consumer_node_id)
        producer = str(producer_node_id)
        artifact_key = str(artifact_id)

        if producer != consumer and producer not in self.visible_producer_node_ids(consumer):
            msg = "Artifact '{}' from node '{}' is not visible to node '{}' (declare deps)".format(artifact_key, producer, consumer)
            raise ValueError(msg)

        by_artifact = self._values_by_producer_node_id.get(producer)
        if by_artifact is None or artifact_key not in by_artifact:
            msg = "Unknown artifact '{}' for node '{}'".format(artifact_key, producer)
            raise KeyError(msg)
        return by_artifact[artifact_key]

    def get_optional(self, consumer_node_id: str, producer_node_id: str, artifact_id: str) -> Optional[object]:
        consumer = str(consumer_node_id)
        producer = str(producer_node_id)
        artifact_key = str(artifact_id)

        if producer != consumer and producer not in self.visible_producer_node_ids(consumer):
            msg = "Artifact '{}' from node '{}' is not visible to node '{}' (declare deps)".format(artifact_key, producer, consumer)
            raise ValueError(msg)

        by_artifact = self._values_by_producer_node_id.get(producer)
        if by_artifact is None or artifact_key not in by_artifact:
            return None
        return by_artifact[artifact_key]

    def discard(self, producer_node_id: str, artifact_id: str) -> None:
        producer = str(producer_node_id)
        artifact_key = str(artifact_id)
        by_artifact = self._values_by_producer_node_id.get(producer)
        if not by_artifact:
            return
        _ = by_artifact.pop(artifact_key, None)
        if not by_artifact:
            _ = self._values_by_producer_node_id.pop(producer, None)

    def discard_in_memory_csv_output(self, producer_node_id: str, output_id: str) -> None:
        producer = str(producer_node_id)
        out_id = str(output_id)
        by_artifact = self._values_by_producer_node_id.get(producer)
        if not by_artifact:
            return
        mem = by_artifact.get("in_memory_csv_outputs")
        if not isinstance(mem, dict):
            return
        mem_outputs = cast("Dict[str, WorkflowCsvInput]", mem)  # pragma: allow-cast artifacts dict typed narrowing
        _ = mem_outputs.pop(out_id, None)
        if not mem_outputs:
            _ = by_artifact.pop("in_memory_csv_outputs", None)
        export_headers = by_artifact.get("in_memory_csv_export_headers")
        if isinstance(export_headers, dict):
            typed_export_headers = cast("Dict[str, Tuple[str, ...]]", export_headers)  # pragma: allow-cast artifacts dict typed narrowing
            _ = typed_export_headers.pop(out_id, None)
            if not typed_export_headers:
                _ = by_artifact.pop("in_memory_csv_export_headers", None)
        if not by_artifact:
            _ = self._values_by_producer_node_id.pop(producer, None)

    def discard_all_in_memory_csv_outputs(self) -> None:
        for producer_node_id, by_artifact in list(self._values_by_producer_node_id.items()):
            _ = by_artifact.pop("in_memory_csv_outputs", None)
            _ = by_artifact.pop("in_memory_csv_export_headers", None)
            if not by_artifact:
                _ = self._values_by_producer_node_id.pop(producer_node_id, None)

    def discard_all_in_memory_rows(self) -> None:
        for producer_node_id, by_artifact in list(self._values_by_producer_node_id.items()):
            _ = by_artifact.pop("in_memory_rows", None)
            if not by_artifact:
                _ = self._values_by_producer_node_id.pop(producer_node_id, None)

    def discard_in_memory_rows_output(self, producer_node_id: str, output_id: str) -> None:
        producer = str(producer_node_id)
        out_id = str(output_id)
        by_artifact = self._values_by_producer_node_id.get(producer)
        if not by_artifact:
            return
        mem = by_artifact.get("in_memory_rows_outputs")
        if not isinstance(mem, dict):
            return
        mem_outputs = cast("Dict[str, InMemoryRows]", mem)  # pragma: allow-cast artifacts dict typed narrowing
        _ = mem_outputs.pop(out_id, None)
        if not mem_outputs:
            _ = by_artifact.pop("in_memory_rows_outputs", None)
        if not by_artifact:
            _ = self._values_by_producer_node_id.pop(producer, None)

    def discard_all_in_memory_rows_outputs(self) -> None:
        for producer_node_id, by_artifact in list(self._values_by_producer_node_id.items()):
            _ = by_artifact.pop("in_memory_rows_outputs", None)
            if not by_artifact:
                _ = self._values_by_producer_node_id.pop(producer_node_id, None)


__all__ = ("WorkflowArtifactsDirectory",)
