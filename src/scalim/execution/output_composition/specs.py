from __future__ import absolute_import

import hashlib
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Set, Tuple

from ...typedefs import FailurePolicy, KeyNormalizationMode, RowData
from ...vendor.compact.typing_extensionsx import override
from ...vendor.dataclassesx import dataclass
from .._output_composition_policies import DedupOnConflictPolicy, DerivedOverflowPolicy
from ..derived_outputs import (
    AggMetricSpec,
    DedupByThenAggregator,
    GroupByAggregator,
    IRowAggregator,
    PostFieldSpec,
    RankedGroupByAggregator,
    RankFieldSpec,
    TwoStageGroupByAggregator,
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
    max_groups: int = 0
    max_distinct: int = 0
    distinct_on_overflow: str = "error"

    @override
    def required_fields(self) -> Tuple[str, ...]:
        agg = GroupByAggregator(group_by=self.group_by, metrics=self.metrics, max_groups=0)
        return agg.required_fields()

    @override
    def fingerprint_parts(self) -> Tuple[str, ...]:
        parts: List[str] = []
        parts.append("kind=group_by")
        parts.append("group_by=" + ",".join(str(x) for x in self.group_by))
        parts.append("max_groups=" + str(int(self.max_groups)))
        parts.append("max_distinct=" + str(int(self.max_distinct)))
        parts.append("distinct_on_overflow=" + (self.distinct_on_overflow or DerivedOverflowPolicy.ERROR).lower())
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
        _ = str(parallel_mode or "").lower()
        overflow = (self.distinct_on_overflow or DerivedOverflowPolicy.ERROR).lower()
        if overflow not in (DerivedOverflowPolicy.ERROR, DerivedOverflowPolicy.TRUNCATE):
            msg = "Unsupported distinct_on_overflow: {!r}".format(self.distinct_on_overflow)
            raise ValueError(msg)

    @override
    def build_aggregator(self, *, key_normalization: KeyNormalizationMode = "raw") -> IRowAggregator:
        if self.rank_fields or self.post_fields:
            return RankedGroupByAggregator(
                group_by=self.group_by,
                metrics=self.metrics,
                rank_fields=self.rank_fields,
                post_fields=self.post_fields,
                max_groups=int(self.max_groups),
                max_distinct=int(self.max_distinct),
                distinct_on_overflow=str(self.distinct_on_overflow),
                key_normalization=key_normalization,
            )
        return GroupByAggregator(
            group_by=self.group_by,
            metrics=self.metrics,
            max_groups=int(self.max_groups),
            max_distinct=int(self.max_distinct),
            distinct_on_overflow=str(self.distinct_on_overflow),
            key_normalization=key_normalization,
        )


@dataclass(frozen=True)
class DedupBySpec:
    key_fields: Tuple[str, ...]
    on_conflict: str = "error"
    max_distinct: int = 0
    on_overflow: str = "error"

    def fingerprint_parts(self) -> Tuple[str, ...]:
        parts: List[str] = []
        parts.append("kind=dedup_by")
        parts.append("key_fields=" + ",".join(str(x) for x in self.key_fields))
        parts.append("on_conflict=" + (self.on_conflict or DedupOnConflictPolicy.ERROR).lower())
        parts.append("max_distinct=" + str(int(self.max_distinct)))
        parts.append("on_overflow=" + (self.on_overflow or DerivedOverflowPolicy.ERROR).lower())
        return tuple(parts)

    def validate_parallel_mode(self, parallel_mode: str) -> None:
        mode = str(parallel_mode or "").lower()
        on_conflict = (self.on_conflict or DedupOnConflictPolicy.ERROR).lower()
        if on_conflict not in (DedupOnConflictPolicy.ERROR, DedupOnConflictPolicy.FIRST, DedupOnConflictPolicy.LAST):
            msg = "Unsupported dedup_by.on_conflict: {!r}".format(self.on_conflict)
            raise ValueError(msg)
        on_overflow = (self.on_overflow or DerivedOverflowPolicy.ERROR).lower()
        if on_overflow not in (DerivedOverflowPolicy.ERROR, DerivedOverflowPolicy.TRUNCATE):
            msg = "Unsupported dedup_by.on_overflow: {!r}".format(self.on_overflow)
            raise ValueError(msg)
        if mode == "adaptive" and on_conflict in (DedupOnConflictPolicy.FIRST, DedupOnConflictPolicy.LAST):
            msg = (
                "dedup_by.on_conflict={!r} is order-dependent and is not supported in parallel_mode='adaptive'; "
                "use parallel_mode='seq' or switch to on_conflict='error'"
            ).format(on_conflict)
            raise ValueError(msg)


@dataclass(frozen=True)
class DerivedDedupByGroupBySpec(IDerivedAggregationSpec):
    dedup_by: DedupBySpec
    group_by: DerivedGroupBySpec

    @override
    def required_fields(self) -> Tuple[str, ...]:
        required: List[str] = list(self.dedup_by.key_fields) + list(self.group_by.required_fields())
        # 去重但保留顺序.
        seen: Set[str] = set()
        ordered: List[str] = []
        for fid in required:
            if fid in seen:
                continue
            seen.add(fid)
            ordered.append(fid)
        return tuple(ordered)

    @override
    def fingerprint_parts(self) -> Tuple[str, ...]:
        parts: List[str] = ["kind=dedup_by+group_by", "dedup_by:"]
        parts.extend(["  " + x for x in self.dedup_by.fingerprint_parts()])
        parts.append("group_by:")
        parts.extend(["  " + x for x in self.group_by.fingerprint_parts()])
        return tuple(parts)

    @override
    def validate_parallel_mode(self, parallel_mode: str) -> None:
        self.dedup_by.validate_parallel_mode(parallel_mode)
        self.group_by.validate_parallel_mode(parallel_mode)

    @override
    def build_aggregator(self, *, key_normalization: KeyNormalizationMode = "raw") -> IRowAggregator:
        base = self.group_by.build_aggregator(key_normalization=key_normalization)
        return DedupByThenAggregator(
            key_fields=self.dedup_by.key_fields,
            on_conflict=str(self.dedup_by.on_conflict),
            max_distinct=int(self.dedup_by.max_distinct),
            on_overflow=str(self.dedup_by.on_overflow),
            downstream=base,
            key_normalization=key_normalization,
        )


@dataclass(frozen=True)
class TwoStageGroupBySpec(IDerivedAggregationSpec):
    stage1: DerivedGroupBySpec
    stage2: DerivedGroupBySpec

    @override
    def required_fields(self) -> Tuple[str, ...]:
        return self.stage1.required_fields()

    @override
    def fingerprint_parts(self) -> Tuple[str, ...]:
        parts: List[str] = ["kind=two_stage_group_by", "stage1:"]
        parts.extend(["  " + x for x in self.stage1.fingerprint_parts()])
        parts.append("stage2:")
        parts.extend(["  " + x for x in self.stage2.fingerprint_parts()])
        return tuple(parts)

    @override
    def validate_parallel_mode(self, parallel_mode: str) -> None:
        if self.stage1.rank_fields or self.stage1.post_fields or self.stage2.rank_fields or self.stage2.post_fields:
            msg = "two_stage_group_by does not support rank/post fields in stage specs"
            raise ValueError(msg)
        self.stage1.validate_parallel_mode(parallel_mode)
        self.stage2.validate_parallel_mode(parallel_mode)

        stage1_fields: Set[str] = set(self.stage1.group_by)
        stage1_fields.update([str(m.out_field_id) for m in self.stage1.metrics])
        missing = [x for x in self.stage2.required_fields() if x not in stage1_fields]
        if missing:
            msg = "two_stage_group_by stage2 requires fields not produced by stage1: {}".format(", ".join(sorted(missing)))
            raise ValueError(msg)

    @override
    def build_aggregator(self, *, key_normalization: KeyNormalizationMode = "raw") -> IRowAggregator:
        agg1 = GroupByAggregator(
            group_by=self.stage1.group_by,
            metrics=self.stage1.metrics,
            max_groups=int(self.stage1.max_groups),
            max_distinct=int(self.stage1.max_distinct),
            distinct_on_overflow=str(self.stage1.distinct_on_overflow),
            key_normalization=key_normalization,
        )
        agg2 = GroupByAggregator(
            group_by=self.stage2.group_by,
            metrics=self.stage2.metrics,
            max_groups=int(self.stage2.max_groups),
            max_distinct=int(self.stage2.max_distinct),
            distinct_on_overflow=str(self.stage2.distinct_on_overflow),
            key_normalization=key_normalization,
        )
        return TwoStageGroupByAggregator(stage1=agg1, stage2=agg2)


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
