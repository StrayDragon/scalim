from __future__ import absolute_import

import hashlib
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple

from ...typedefs import FailurePolicy, KeyNormalizationMode, RowData
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass
from ..derived_outputs import (
    AggMetricSpec,
    GroupByAggregator,
    IRowAggregator,
    PostFieldSpec,
    RankedGroupByAggregator,
    RankFieldSpec,
    build_finalize_dag_plan,
)
from ..output_contracts import ExportLayout, OutputSpec

OutputRowPredicate = Callable[[RowData], bool]


@dataclass(frozen=True)
class OutputTargetSpec:
    """输出目标(`IR/Python-only`); `layout.field_ids` 控制取值顺序, `output.sheet_name` 仅用于同工作簿 `excel` 写入."""

    target_id: str
    layout: ExportLayout
    output: OutputSpec
    in_memory: bool = False
    predicate: Optional[OutputRowPredicate] = None
    is_primary: bool = False
    requires: Optional[Tuple[str, ...]] = None
    workflow_export_header: Optional[Tuple[str, ...]] = None
    managed_artifact_kind: Optional[str] = None


class IDerivedAggregationSpec(ABC):
    @abstractmethod
    def required_fields(self) -> Tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def fingerprint_parts(self) -> Tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def validate_parallel_mode(self, parallel_mode: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_aggregator(self, *, key_normalization: KeyNormalizationMode = "raw") -> IRowAggregator:
        raise NotImplementedError


def metric_fingerprint_part(m: AggMetricSpec) -> str:
    field_id = str(m.field_id) if m.field_id else ""
    field_ids = ",".join(str(x) for x in (m.field_ids or ()))
    threshold = "" if m.threshold is None else str(m.threshold)
    return "{}|op={}|field_id={}|field_ids={}|threshold={}".format(str(m.out_field_id), str(m.op), field_id, field_ids, threshold)


def rank_field_fingerprint_part(r: RankFieldSpec) -> str:
    return "{}|kind={}|by={}|partition_by={}|order={}|order_by={}|top_k={}|top_k_mode={}".format(
        str(r.out_field_id),
        str(r.kind),
        str(r.by),
        ",".join(str(x) for x in (r.partition_by or ())),
        str(r.order),
        ",".join(str(x) for x in (r.order_by or ())),
        int(r.top_k),
        str(r.top_k_mode),
    )


def post_field_fingerprint_part(p: PostFieldSpec) -> str:
    return "{}|kind={}|deps={}|fingerprint={}".format(
        str(p.out_field_id),
        str(p.kind),
        ",".join(str(x) for x in (p.dependencies or ())),
        str(p.fingerprint),
    )


@dataclass(frozen=True)
class DerivedGroupBySpec(IDerivedAggregationSpec):
    """派生汇总输出(内置 `group_by`)."""

    group_by: Tuple[str, ...]
    metrics: Tuple[AggMetricSpec, ...]
    rank_fields: Tuple[RankFieldSpec, ...] = ()
    post_fields: Tuple[PostFieldSpec, ...] = ()

    @override
    def required_fields(self) -> Tuple[str, ...]:
        agg = GroupByAggregator(group_by=self.group_by, metrics=self.metrics)
        return agg.required_fields()

    @override
    def fingerprint_parts(self) -> Tuple[str, ...]:
        parts: List[str] = []
        parts.append("kind=group_by")
        parts.append("group_by=" + ",".join(str(x) for x in self.group_by))
        parts.append("metrics=")
        for m in self.metrics:
            parts.append("  " + metric_fingerprint_part(m))
        parts.append("rank_fields=")
        for r in sorted(self.rank_fields, key=lambda x: str(x.out_field_id)):
            parts.append("  " + rank_field_fingerprint_part(r))
        parts.append("post_fields=")
        for p in sorted(self.post_fields, key=lambda x: str(x.out_field_id)):
            parts.append("  " + post_field_fingerprint_part(p))
        parts.append("finalize_dag_plan=")
        plan = build_finalize_dag_plan(rank_fields=self.rank_fields, post_fields=self.post_fields)
        for item in plan.items:
            deps = ",".join(str(x) for x in (item.dependencies or ()))
            parts.append(
                "  {}|producer_key={}|phase={}|deps={}".format(
                    str(item.out_field_id),
                    str(item.producer_key),
                    str(item.phase),
                    deps,
                )
            )
        return tuple(parts)

    @override
    def validate_parallel_mode(self, parallel_mode: str) -> None:
        # 内置 group_by metrics 在 adaptive 下保持确定性；顺序依赖装配（旧 dedup_by.on_conflict）已移除。
        _ = str(parallel_mode or "").lower()

    @override
    def build_aggregator(self, *, key_normalization: KeyNormalizationMode = "raw") -> IRowAggregator:
        if self.rank_fields or self.post_fields:
            return RankedGroupByAggregator(
                group_by=self.group_by,
                metrics=self.metrics,
                rank_fields=self.rank_fields,
                post_fields=self.post_fields,
                key_normalization=key_normalization,
            )
        return GroupByAggregator(
            group_by=self.group_by,
            metrics=self.metrics,
            key_normalization=key_normalization,
        )


@dataclass(frozen=True)
class DerivedOutputTargetSpec:
    """派生输出目标: 从明细流聚合并在 `close()` 时输出."""

    target_id: str
    derived: IDerivedAggregationSpec
    output_layout: ExportLayout
    output: OutputSpec
    in_memory: bool = False
    predicate: Optional[OutputRowPredicate] = None
    is_primary: bool = False
    requires: Optional[Tuple[str, ...]] = None
    workflow_export_header: Optional[Tuple[str, ...]] = None
    managed_artifact_kind: Optional[str] = None


@dataclass(frozen=True)
class MetaSheetSpec:
    """元信息工作表: 以 `key`/`value` 两列写入运行信息与输出统计."""

    target_id: str
    output: OutputSpec
    sheet_name: str
    in_memory: bool = False


@dataclass(frozen=True)
class AuditSheetSpec:
    """审计工作表: 以结构化行写入派生输出错误等审计信息."""

    target_id: str
    output: OutputSpec
    sheet_name: str
    in_memory: bool = False


@dataclass(frozen=True)
class OutputCompositionSpec:
    """多输出组合请求.

    `failure_policy`:
    - `all_fail`: 任一目标失败即失败
    - `primary_only`: 非主输出失败将被记录并禁用该输出,不阻断主输出
    """

    targets: Tuple[OutputTargetSpec, ...] = ()
    derived_targets: Tuple[DerivedOutputTargetSpec, ...] = ()
    meta_sheet: Optional[MetaSheetSpec] = None
    audit_sheet: Optional[AuditSheetSpec] = None
    failure_policy: str = FailurePolicy.ALL_FAIL.value
    include_full_error_message: bool = False


@dataclass(frozen=True)
class OutputTargetStats:
    target_id: str
    input_row_count: int
    row_count: int
    error_count: int
    duration_seconds: float
    disabled: bool
    output_path: Optional[str]
    sheet_name: Optional[str]
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_message_hash: Optional[str] = None


def fingerprint_for_derived_target(*, target_id: str, derived: IDerivedAggregationSpec) -> str:
    # 指纹仅用于稳定标识符/对拍与归因,不用于签名/认证/加密等安全用途.
    # 注意: 指纹会进入 `meta/audit`,属于“对外可见的稳定输出”;本次切换到 `sha256` 属于显式破坏性变更(值变化,长度 40->64).
    h = hashlib.sha256()
    payload = "\n".join(["target_id=" + str(target_id), *derived.fingerprint_parts()]).encode("utf-8", errors="replace")
    h.update(payload)
    return h.hexdigest()
