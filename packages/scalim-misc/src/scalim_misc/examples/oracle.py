from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


def stable_json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_sort_rows(rows: Sequence[Mapping[str, Any]], *, by: Sequence[str]) -> list[dict[str, Any]]:
    keys = [str(x) for x in by]
    payload = [dict(r) for r in rows]
    payload.sort(key=lambda r: tuple(str(r.get(k, "")) for k in keys))
    return payload


def diff_first_mismatch(
    actual_rows: Sequence[Mapping[str, Any]],
    expected_rows: Sequence[Mapping[str, Any]],
    *,
    fields: Sequence[str],
) -> tuple[bool, str]:
    if len(actual_rows) != len(expected_rows):
        return False, f"row count mismatch: actual={len(actual_rows)} expected={len(expected_rows)}"

    field_list = [str(f) for f in fields]
    for idx, (actual, expected) in enumerate(zip(actual_rows, expected_rows, strict=False), start=1):
        for field_name in field_list:
            if actual.get(field_name) != expected.get(field_name):
                msg = f"row {idx} field '{field_name}' mismatch: actual={actual.get(field_name)} expected={expected.get(field_name)}"
                return False, msg
    return True, "rows match"
