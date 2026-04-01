"""`execution` 模块中的 `workflow-managed` 工件辅助工具.

说明:
- 把 `workflow-managed` 的类型化/CSV 工件建模与行写入器创建从 `output_composition` 拆出.
- 运行时需兼容 `Python 3.6`.
"""

from typing import TYPE_CHECKING, Optional, Tuple

from ..sinks import InMemoryCsvSink, IRowSink
from ..sinks.rows import InMemoryRowsSink, in_memory_rows_to_in_memory_csv
from ..vendor.dataclassesx import dataclass
from .output_contracts import ExportLayout, OutputSpec

MANAGED_ARTIFACT_KIND_CSV = "csv"
MANAGED_ARTIFACT_KIND_ROWS = "rows"

if TYPE_CHECKING:
    from ..sinks import InMemoryCsv
    from ..sinks.rows import InMemoryRows


@dataclass(frozen=True)
class ManagedArtifactPlan:
    kind: str
    rows_sink: Optional[InMemoryRowsSink] = None
    csv_sink: Optional[InMemoryCsvSink] = None

    def to_rows_artifact(self) -> Optional["InMemoryRows"]:
        if self.rows_sink is None:
            return None
        return self.rows_sink.to_artifact()

    def to_csv_artifact(self) -> Optional["InMemoryCsv"]:
        if self.kind == MANAGED_ARTIFACT_KIND_ROWS and self.rows_sink is not None:
            return in_memory_rows_to_in_memory_csv(self.rows_sink.to_artifact())
        if self.csv_sink is not None:
            return self.csv_sink.to_artifact()
        return None


def create_managed_artifact_sink(
    *,
    target_id: str,
    fmt: str,
    layout: ExportLayout,
    output: OutputSpec,
    managed_artifact_kind: Optional[str],
) -> Tuple[IRowSink, ManagedArtifactPlan]:
    if not output.streaming:
        msg = "Composed outputs only support streaming row sinks for csv (streaming=true)"
        raise ValueError(msg)

    kind = str(managed_artifact_kind or MANAGED_ARTIFACT_KIND_CSV)
    if kind == MANAGED_ARTIFACT_KIND_ROWS:
        rows_sink = InMemoryRowsSink(field_ids=list(layout.field_ids))
        return rows_sink, ManagedArtifactPlan(kind=kind, rows_sink=rows_sink)

    if kind == MANAGED_ARTIFACT_KIND_CSV:
        if fmt != "csv":
            msg = "In-memory composed output only supports format=csv (target_id={}, format={})".format(target_id, fmt)
            raise ValueError(msg)
        field_names = list(layout.field_ids)
        header_names = list(layout.header_names) if layout.header_names is not None else list(field_names)
        csv_sink = InMemoryCsvSink(field_names=field_names, header_names=header_names)
        return csv_sink, ManagedArtifactPlan(kind=kind, csv_sink=csv_sink)

    msg = "Unsupported managed artifact kind: {!r} (target_id={})".format(kind, target_id)
    raise ValueError(msg)


__all__ = (
    "MANAGED_ARTIFACT_KIND_CSV",
    "MANAGED_ARTIFACT_KIND_ROWS",
    "ManagedArtifactPlan",
    "create_managed_artifact_sink",
)
