#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

from datetime import datetime
from pathlib import Path
import sys
from typing import List

from scalim.dsl.by_yaml import OutputOverrides, RunOverrides, run
from scalim.execution.output_composition import (
    AggMetricSpec,
    AuditSheetSpec,
    DedupBySpec,
    DerivedDedupByGroupBySpec,
    DerivedGroupBySpec,
    DerivedOutputTargetSpec,
    MetaSheetSpec,
    OutputCompositionSpec,
    OutputTargetSpec,
    TwoStageGroupBySpec,
)
from scalim.execution.output_contracts import ExportLayout, OutputSpec


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    # Ensure `mvp_demo.*` is importable for YAML relative loader refs like `.loaders:...`.
    sys.path.insert(0, str(base_dir.parent))

    yaml_path = str(base_dir / "demo_detail.demand.yaml")
    output_path = "/tmp/scalim_mvp_demo.xlsx"

    detail_fields: List[str] = [
        "order_id",
        "user_id",
        "cs_id",
        "group_name",
        "cs_name",
        "wechat_name",
        "institution_code",
        "institution_name",
        "channel",
        "pay_datetime",
        "amount_cent",
        "amount_yuan",
        "is_quick_pay",
    ]
    detail_headers: List[str] = [
        "订单ID",
        "用户ID",
        "客服ID",
        "组别",
        "客服",
        "微信",
        "机构编码",
        "机构名",
        "渠道",
        "支付时间",
        "金额(分)",
        "金额(元)",
        "快付",
    ]

    def _is_direct(row: dict) -> bool:
        return row.get("channel") == "direct"

    def _is_partner(row: dict) -> bool:
        return row.get("channel") == "partner"

    # Multi-sheet detail distribution via output-composition.
    targets = (
        OutputTargetSpec(
            target_id="detail",
            layout=ExportLayout(field_ids=tuple(detail_fields), header_names=tuple(detail_headers)),
            output=OutputSpec(
                format="excel",
                path=str(output_path),
                streaming=True,
                include_header=True,
                sheet_name="订单明细",
                excel_allow_formulas=True,
            ),
            is_primary=True,
        ),
        OutputTargetSpec(
            target_id="direct_detail",
            layout=ExportLayout(field_ids=tuple(detail_fields), header_names=tuple(detail_headers)),
            output=OutputSpec(
                format="excel",
                path=str(output_path),
                streaming=True,
                include_header=True,
                sheet_name="直客明细",
                excel_allow_formulas=True,
            ),
            predicate=_is_direct,
        ),
        OutputTargetSpec(
            target_id="partner_detail",
            layout=ExportLayout(field_ids=tuple(detail_fields), header_names=tuple(detail_headers)),
            output=OutputSpec(
                format="excel",
                path=str(output_path),
                streaming=True,
                include_header=True,
                sheet_name="渠道明细",
                excel_allow_formulas=True,
            ),
            predicate=_is_partner,
        ),
    )

    # set primitive: `count_distinct` + two-stage + `count_true_gte`
    by_cs = DerivedOutputTargetSpec(
        target_id="by_cs",
        derived=TwoStageGroupBySpec(
            stage1=DerivedGroupBySpec(
                group_by=("cs_id", "cs_name", "group_name", "user_id"),
                metrics=(
                    AggMetricSpec(out_field_id="pay_order_cnt", op="count", field_id="order_id"),
                    AggMetricSpec(out_field_id="sum_amount_yuan", op="sum", field_id="amount_yuan"),
                ),
                max_groups=2000,
            ),
            stage2=DerivedGroupBySpec(
                group_by=("cs_id", "cs_name", "group_name"),
                metrics=(
                    AggMetricSpec(out_field_id="order_cnt", op="sum", field_id="pay_order_cnt"),
                    AggMetricSpec(out_field_id="sum_amount_yuan", op="sum", field_id="sum_amount_yuan"),
                    AggMetricSpec(out_field_id="new_paid_users", op="count_distinct", field_id="user_id"),
                    AggMetricSpec(out_field_id="repeat_paid_users", op="count_true_gte", field_id="pay_order_cnt", threshold=2),
                ),
                max_groups=2000,
                max_distinct=10000,
                distinct_on_overflow="error",
            ),
        ),
        output_layout=ExportLayout(
            field_ids=("cs_id", "cs_name", "group_name", "order_cnt", "sum_amount_yuan", "new_paid_users", "repeat_paid_users"),
            header_names=("客服ID", "客服", "组别", "支付订单数", "支付金额(元)", "新付费用户数", "复购支付用户数"),
        ),
        output=OutputSpec(
            format="excel",
            path=str(output_path),
            streaming=True,
            include_header=True,
            sheet_name="客服汇总",
            excel_allow_formulas=True,
        ),
    )

    # set primitive: `dedup_by(key_fields, on_conflict=first)` + group_by
    by_cs_dedup_users = DerivedOutputTargetSpec(
        target_id="by_cs_dedup_users",
        derived=DerivedDedupByGroupBySpec(
            dedup_by=DedupBySpec(
                key_fields=("cs_id", "user_id"),
                on_conflict="first",
                max_distinct=0,
                on_overflow="error",
            ),
            group_by=DerivedGroupBySpec(
                group_by=("cs_id", "cs_name", "group_name"),
                metrics=(AggMetricSpec(out_field_id="new_paid_users_dedup", op="count", field_id=None),),
                max_groups=2000,
            ),
        ),
        output_layout=ExportLayout(
            field_ids=("cs_id", "cs_name", "group_name", "new_paid_users_dedup"),
            header_names=("客服ID", "客服", "组别", "新付费用户数(dedup_by)"),
        ),
        output=OutputSpec(
            format="excel",
            path=str(output_path),
            streaming=True,
            include_header=True,
            sheet_name="客服去重(用户)",
            excel_allow_formulas=True,
        ),
    )

    output_comp = OutputCompositionSpec(
        targets=targets,
        derived_targets=(
            by_cs,
            by_cs_dedup_users,
        ),
        meta_sheet=MetaSheetSpec(
            target_id="meta",
            output=OutputSpec(format="excel", path=str(output_path), streaming=True, include_header=True),
            sheet_name="Meta",
        ),
        audit_sheet=AuditSheetSpec(
            target_id="audit",
            output=OutputSpec(format="excel", path=str(output_path), streaming=True, include_header=True),
            sheet_name="Audit",
        ),
        failure_policy="all_fail",
    )

    overrides = RunOverrides(output=OutputOverrides(path=None))
    _ = run(
        yaml_path,
        allowed_modules=frozenset([base_dir.name]),
        output_composition=output_comp,
        overrides=overrides,
        parallel_mode="seq",
        runtime_vars={
            "start_datetime": datetime.strptime("2026-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"),
            "end_datetime": datetime.strptime("2026-01-07 00:00:00", "%Y-%m-%d %H:%M:%S"),
        },
    )
    print("written:", output_path)


if __name__ == "__main__":
    main()
