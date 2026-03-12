#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function

from datetime import datetime
from pathlib import Path
import sys
from typing import Dict, List, Optional

from scalim.dsl.by_yaml import OutputOverrides, RunOverrides, run
from scalim.sinks.sink_base import ISink
from scalim.sinks.sink_excel import ExcelWorkbookSink


class MultiSheetWorkbookSink(ISink):
    """当前 Scalim 不支持 YAML 描述“多 sheet 分发”,用最薄 Python sink 兜住."""

    def __init__(
        self,
        output_path: str,
        *,
        field_names: List[str],
        header_names: Optional[List[str]] = None,
        sheet_key_field: str = "channel",
        default_sheet_name: str = "ALL",
    ) -> None:
        self._workbook = ExcelWorkbookSink(output_path)
        self._sheet_sinks: Dict[str, object] = {}
        self._field_names = list(field_names)
        self._header_names = list(header_names) if header_names is not None else list(field_names)
        self._sheet_key_field = str(sheet_key_field)
        self._default_sheet_name = str(default_sheet_name)

    def _get_sheet_name(self, row: dict) -> str:
        value = row.get(self._sheet_key_field)
        if value is None or value == "":
            return self._default_sheet_name
        return str(value)[:31]

    def write_batch(self, rows) -> None:
        for row in rows:
            sheet_name = self._get_sheet_name(row)
            sink = self._sheet_sinks.get(sheet_name)
            if sink is None:
                sink = self._workbook.create_sheet_row_sink(
                    sheet_name,
                    field_names=self._field_names,
                    header_names=self._header_names,
                    include_header=True,
                    allow_formulas=True,
                )
                self._sheet_sinks[sheet_name] = sink
            sink.write_row(row)

    def close(self) -> None:
        for sink in self._sheet_sinks.values():
            sink.close()
        self._workbook.close()


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    # Ensure `mvp_demo.*` is importable for YAML relative loader refs like `.loaders:...`.
    sys.path.insert(0, str(base_dir.parent))

    yaml_path = str(base_dir / "demo_detail.demand.yaml")
    output_path = "/tmp/scalim_mvp_demo.xlsx"

    sink = MultiSheetWorkbookSink(
        output_path,
        field_names=[
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
        ],
        header_names=[
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
        ],
        sheet_key_field="channel",
    )

    overrides = RunOverrides(output=OutputOverrides(path=None))
    _ = run(
        yaml_path,
        allowed_modules=frozenset([base_dir.name]),
        sink=sink,
        overrides=overrides,
        runtime_vars={
            "start_datetime": datetime.strptime("2026-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"),
            "end_datetime": datetime.strptime("2026-01-07 00:00:00", "%Y-%m-%d %H:%M:%S"),
        },
    )
    sink.close()
    print("written:", output_path)


if __name__ == "__main__":
    main()
