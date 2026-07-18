#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c15 MVP: compare InMemoryRows FieldValue gate vs openpyxl vs numpy/pandas eq/hash.

Run from repo root:

    uv run python llmanspec/changes/c15-tabular-bus-object-sink-accept-precheck/evidence/mvp_type_probe.py

Output default: .tmp/evidence/rows-object-bus-mvp/type_probe.json
Override: SCALIM_C15_PROBE_OUT=/path/to/out.json
"""

from __future__ import absolute_import, print_function

import json
import os
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import openpyxl
import pandas as pd
from openpyxl import Workbook

from scalim.sinks.accept_types import is_excel_accepted_cell
from scalim.sinks._internal.rows import InMemoryRowsSink
from scalim.typedefs import format_field_value_expected_types


def _main():
    out = {
        "field_value_expected": format_field_value_expected_types(),
        "cases": [],
        "eq_pairs": [],
        "openpyxl_write": [],
        "rows_sink": [],
    }

    naive = datetime(2024, 1, 2, 3, 4, 5)  # noqa: DTZ001
    aware = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    ts = pd.Timestamp("2024-01-02 03:04:05")
    ts_aware = pd.Timestamp("2024-01-02 03:04:05", tz="UTC")

    samples = [
        ("int", 1),
        ("bool", True),
        ("float", 1.5),
        ("Decimal", Decimal("1.5")),
        ("str", "x"),
        ("None", None),
        ("datetime_naive", naive),
        ("datetime_aware", aware),
        ("date", date(2024, 1, 2)),
        ("time", time(3, 4, 5)),
        ("timedelta", timedelta(days=1)),
        ("list", [1]),
        ("dict", {"a": 1}),
        ("object", object()),
        ("np.int64", np.int64(1)),
        ("np.float64", np.float64(1.5)),
        ("np.datetime64", np.datetime64("2024-01-02T03:04:05")),
        ("pd.Timestamp", ts),
        ("pd.Timestamp_aware", ts_aware),
        ("pd.NaT", pd.NaT),
    ]

    for name, v in samples:
        try:
            hash(v)
            hashable = True
            herr = None
        except Exception as e:
            hashable = False
            herr = type(e).__name__ + ": " + str(e)
        out["cases"].append(
            {
                "name": name,
                "type": type(v).__module__ + "." + type(v).__name__,
                "in_FIELD_VALUE_TYPES": is_excel_accepted_cell(v),
                "isinstance_datetime": isinstance(v, datetime),
                "hashable": hashable,
                "hash_error": herr,
            }
        )

    for name, v in [
        ("datetime_naive", naive),
        ("np.datetime64", np.datetime64("2024-01-02T03:04:05")),
        ("pd.Timestamp", ts),
        ("list", [1]),
        ("object", object()),
    ]:
        sink = InMemoryRowsSink(field_ids=["v"])
        try:
            sink.write_row({"v": v})
            out["rows_sink"].append({"name": name, "ok": True})
        except Exception as e:
            out["rows_sink"].append({"name": name, "ok": False, "error": type(e).__name__ + ": " + str(e)})

    pairs = [
        ("np.int64(1)", np.int64(1), "int(1)", 1),
        ("np.datetime64", np.datetime64("2024-01-02T03:04:05"), "datetime_naive", naive),
        ("pd.Timestamp", ts, "datetime_naive", naive),
    ]
    for a_name, a, b_name, b in pairs:
        try:
            eq = bool(a == b)
        except Exception as e:
            eq = "ERR:" + type(e).__name__
        try:
            ha, hb = hash(a), hash(b)
            hash_eq = ha == hb
        except Exception as e:
            ha = hb = None
            hash_eq = "ERR:" + type(e).__name__
        out["eq_pairs"].append({"a": a_name, "b": b_name, "eq": eq, "hash_equal": hash_eq, "hash_a": ha, "hash_b": hb})

    out["pd.Timestamp_meta"] = {
        "issubclass_datetime": issubclass(pd.Timestamp, datetime),
        "in_FIELD_VALUE": is_excel_accepted_cell(ts),
    }

    with TemporaryDirectory() as td:
        for name, val in samples:
            wb = Workbook()
            ws = wb.active
            try:
                ws.append([val])
                path = Path(td) / (name.replace(".", "_") + ".xlsx")
                wb.save(str(path))
                wb2 = openpyxl.load_workbook(str(path))
                cell = wb2.active["A1"]
                out["openpyxl_write"].append(
                    {
                        "name": name,
                        "ok": True,
                        "data_type": cell.data_type,
                        "py_type": type(cell.value).__module__ + "." + type(cell.value).__name__,
                        "is_str": isinstance(cell.value, str),
                    }
                )
                wb2.close()
            except Exception as e:
                out["openpyxl_write"].append({"name": name, "ok": False, "error": type(e).__name__ + ": " + str(e)})
            finally:
                wb.close()

    out_path = Path(os.environ.get("SCALIM_C15_PROBE_OUT") or ".tmp/evidence/rows-object-bus-mvp/type_probe.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    summary = {
        "rows_sink": out["rows_sink"],
        "eq_pairs": out["eq_pairs"],
        "pd.Timestamp_meta": out["pd.Timestamp_meta"],
        "openpyxl_fail": [x for x in out["openpyxl_write"] if not x.get("ok")],
        "not_in_FIELD_VALUE": [c["name"] for c in out["cases"] if not c["in_FIELD_VALUE_TYPES"]],
        "out_path": str(out_path),
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    _main()
