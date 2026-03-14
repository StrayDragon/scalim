from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Sequence, Tuple


def stable_json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_sort_rows(rows: Sequence[Mapping[str, Any]], *, by: Sequence[str]) -> List[Dict[str, Any]]:
    keys = [str(x) for x in by]
    payload = [dict(r) for r in rows]
    payload.sort(key=lambda r: tuple(str(r.get(k, "")) for k in keys))
    return payload


def diff_first_mismatch(
    actual_rows: Sequence[Mapping[str, Any]],
    expected_rows: Sequence[Mapping[str, Any]],
    *,
    fields: Sequence[str],
) -> Tuple[bool, str]:
    if len(actual_rows) != len(expected_rows):
        return False, "row count mismatch: actual={} expected={}".format(len(actual_rows), len(expected_rows))

    field_list = [str(f) for f in fields]
    for idx, (actual, expected) in enumerate(zip(actual_rows, expected_rows), start=1):
        for field_name in field_list:
            if actual.get(field_name) != expected.get(field_name):
                msg = "row {} field '{}' mismatch: actual={} expected={}".format(
                    idx, field_name, actual.get(field_name), expected.get(field_name)
                )
                return False, msg
    return True, "rows match"
