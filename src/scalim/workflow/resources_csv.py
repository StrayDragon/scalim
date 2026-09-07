"""`workflow` 共享输出资源: `csv` 实现(内部模块).

说明:
- 承载 `csv_append` 的计划构建、对齐与提交落盘
- 运行时需兼容 `Python 3.6`
"""

import csv
import io
from abc import ABC
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from typing_extensions import override

from ..events import EventType
from ..events._events import DiagnosticWarningEvent
from ..sinks._internal.base import atomic_replace_temp_path, best_effort_remove_temp_path, create_temp_path
from ..sinks.memory import InMemoryCsv
from .resources_base import ScalimWorkflowWriteError, WorkflowResourceManagerBase

WorkflowCsvInput = str | InMemoryCsv


def _read_csv_header(input_csv: WorkflowCsvInput) -> list[str]:
    if isinstance(input_csv, InMemoryCsv):
        header = [str(x or "").strip() for x in input_csv.header]
        if not header or any(not x for x in header):
            msg = "Input CSV has invalid header (empty field): <in_memory>"
            raise ScalimWorkflowWriteError(msg)
        return header

    path = str(input_csv)
    p = Path(path)
    if not p.exists():
        msg = f"Missing input CSV: {path!r}"
        raise ScalimWorkflowWriteError(msg)
    with p.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            msg = f"Input CSV is empty (missing header): {path!r}"
            raise ScalimWorkflowWriteError(msg) from None
    header = [str(x or "").strip() for x in header]
    if not header or any(not x for x in header):
        msg = f"Input CSV has invalid header (empty field): {path!r}"
        raise ScalimWorkflowWriteError(msg)
    return header


def _iter_csv_rows(input_csv: WorkflowCsvInput) -> Iterator[list[str]]:
    if isinstance(input_csv, InMemoryCsv):
        for row in input_csv.rows:
            yield [str(v) for v in row]
        return

    p = Path(str(input_csv))
    with p.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        _header = next(reader, None)
        for row in reader:
            yield [str(v) for v in row]


def _describe_header_diff(expected: Sequence[str], actual: Sequence[str]) -> list[str]:
    exp_set = {str(x) for x in expected}
    act_set = {str(x) for x in actual}
    missing = sorted(exp_set.difference(act_set))
    extra = sorted(act_set.difference(exp_set))
    return [
        "expected={}".format(",".join(str(x) for x in expected)),
        "actual={}".format(",".join(str(x) for x in actual)),
        "missing={}".format(",".join(missing) if missing else "(none)"),
        "extra={}".format(",".join(extra) if extra else "(none)"),
    ]


def _build_alignment_mapping(expected: Sequence[str], actual: Sequence[str]) -> list[int]:
    index_by_key: dict[str, int] = {}
    for idx, key in enumerate(actual):
        k = str(key)
        if k not in index_by_key:
            index_by_key[k] = int(idx)
    mapping: list[int] = []
    for key in expected:
        mapping.append(int(index_by_key.get(str(key), -1)))
    return mapping


@dataclass
class _AppendSegment:
    decl_order: int
    input_csv: WorkflowCsvInput
    header_policy: str
    mapping: list[int]
    on_mismatch: str
    align_by: str
    input_header: list[str]


@dataclass
class _CsvPlan:
    resource_id: str
    path: str
    baseline_header: list[str] | None = None
    export_header: list[str] | None = None
    segments: list[_AppendSegment] | None = None
    last_workflow_node_id: str | None = None


class _WorkflowCsvResourceMixin(WorkflowResourceManagerBase, ABC):
    def _get_or_create_csv(self, csv_id: str, *, workflow_node_id: str) -> _CsvPlan:
        key = str(csv_id)

        def _create() -> _CsvPlan:
            raw_path = self._csv_defs.get(key)
            if raw_path is None:
                msg = f"Unknown csv resource id: {key!r}"
                raise ScalimWorkflowWriteError(msg)
            return _CsvPlan(resource_id=key, path=str(raw_path))

        def _on_create(plan: _CsvPlan) -> None:
            self._emit_resource_create(
                workflow_node_id=str(workflow_node_id),
                resource_type="csv",
                resource_id=key,
                path=str(plan.path),
            )

        plan = self._get_or_create_plan(
            resource_type="csv",
            resource_id=key,
            plans=self._csvs,
            create_fn=_create,
            on_create=_on_create,
        )
        return cast("_CsvPlan", plan)  # pragma: allow-cast csv plan typed narrowing

    def apply_csv_append(
        self,
        *,
        workflow_node_id: str,
        decl_order: int,
        csv_id: str,
        input_node_id: str,
        input_output_id: str,
        input_csv: WorkflowCsvInput,
        header_policy: str,
        on_mismatch: str,
        export_header: tuple[str, ...] | None = None,
    ) -> None:
        plan = self._get_or_create_csv(csv_id, workflow_node_id=str(workflow_node_id))
        input_header = _read_csv_header(input_csv)

        pending_warning: DiagnosticWarningEvent | None = None
        pending_warning_meta: dict[str, Any] | None = None
        pending_skip = False

        if plan.baseline_header is None:
            plan.baseline_header = list(input_header)
            plan.export_header = list(export_header) if export_header is not None else None
            plan.segments = []

        expected = list(plan.baseline_header or [])
        mapping = _build_alignment_mapping(expected, input_header)

        if list(input_header) != expected:
            diff = _describe_header_diff(expected, input_header)
            if on_mismatch == "error":
                msg = f"Field alignment mismatch (csv_append): csv={str(csv_id)!r}"
                raise ScalimWorkflowWriteError(msg, diff=diff)
            if on_mismatch == "warn":
                pending_warning = DiagnosticWarningEvent(
                    message=f"Field alignment mismatch (warn): csv={str(csv_id)!r}",
                    source_id=None,
                    field_id=None,
                    lookup_key={"expected": expected, "actual": list(input_header)},
                    row_id=None,
                )
                pending_warning_meta = {"workflow_exec_id": self._workflow_exec_id, "workflow_node_id": str(workflow_node_id)}
            if on_mismatch == "skip":
                plan.last_workflow_node_id = str(workflow_node_id)
                pending_skip = True

        if not pending_skip:
            cast("list[_AppendSegment]", plan.segments).append(  # pragma: allow-cast csv segments typed narrowing
                _AppendSegment(
                    decl_order=int(decl_order),
                    input_csv=input_csv,
                    header_policy=str(header_policy),
                    mapping=mapping,
                    on_mismatch=str(on_mismatch),
                    align_by="header",
                    input_header=list(input_header),
                )
            )
            plan.last_workflow_node_id = str(workflow_node_id)

        if pending_warning is not None:
            _ = self._instrumentation.emit(EventType.DIAGNOSTIC_WARNING, pending_warning, meta=pending_warning_meta)

        if pending_skip:
            self._emit_resource_write(
                workflow_node_id=str(workflow_node_id),
                resource_type="csv",
                resource_id=str(csv_id),
                path=str(plan.path),
                write_kind="csv_append",
                action="skip",
                input_node_id=str(input_node_id),
                input_output_id=str(input_output_id),
            )
            return

        self._emit_resource_write(
            workflow_node_id=str(workflow_node_id),
            resource_type="csv",
            resource_id=str(csv_id),
            path=str(plan.path),
            write_kind="csv_append",
            action="append",
            input_node_id=str(input_node_id),
            input_output_id=str(input_output_id),
        )

    @override
    def _commit_csv(self, plan: _CsvPlan) -> None:
        p = plan
        if p.segments is None or p.baseline_header is None:
            return

        final_path = str(p.path)
        staging_path = self._staging_path_for_final_output(final_path)

        temp_path = create_temp_path(staging_path, ".csv.tmp")
        temp_obj = Path(temp_path)

        try:
            with io.open(str(temp_obj), "w", encoding="utf-8", newline="") as handle:  # noqa: UP020  # 测试经 io.open 打桩
                writer = csv.writer(handle)
                header_written = False
                segments = sorted(p.segments, key=lambda seg: int(seg.decl_order))
                for seg in segments:
                    if seg.header_policy == "always" or (seg.header_policy == "once" and not header_written):
                        writer.writerow(list(p.export_header if p.export_header is not None else p.baseline_header))
                        header_written = True

                    for row in _iter_csv_rows(seg.input_csv):
                        out_row: list[str] = []
                        for idx in seg.mapping:
                            out_row.append(row[idx] if idx >= 0 and idx < len(row) else "")
                        writer.writerow(out_row)

            atomic_replace_temp_path(temp_path, staging_path)
        except Exception as exc:
            best_effort_remove_temp_path(temp_path)
            msg = f"CSV commit failed: {type(exc).__name__}: {exc}"
            raise ScalimWorkflowWriteError(msg) from exc

        node_id = p.last_workflow_node_id or "__wf__commit"
        self._register_staged_output(
            resource_type="csv",
            resource_id=p.resource_id,
            workflow_node_id=str(node_id),
            staged_path=str(staging_path),
            final_path=str(final_path),
        )

    @override
    def _discard_csv(self, plan: _CsvPlan, *, workflow_node_id: str, reason: str) -> None:
        p = plan
        node_id = p.last_workflow_node_id or str(workflow_node_id)
        self._emit_resource_discard(
            workflow_node_id=node_id,
            resource_type="csv",
            resource_id=p.resource_id,
            path=str(p.path),
            reason=str(reason),
        )


__all__ = (
    "AppendSegment",
    "CsvPlan",
    "WorkflowCsvResourceMixin",
    "build_alignment_mapping",
    "describe_header_diff",
    "iter_csv_rows",
    "read_csv_header",
)

AppendSegment = _AppendSegment
CsvPlan = _CsvPlan
WorkflowCsvResourceMixin = _WorkflowCsvResourceMixin
read_csv_header = _read_csv_header
iter_csv_rows = _iter_csv_rows
describe_header_diff = _describe_header_diff
build_alignment_mapping = _build_alignment_mapping
