from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


def _to_short_str(value: Any, *, limit: int = 280) -> str:
    try:
        text = str(value)
    except Exception:  # noqa: BLE001
        text = repr(value)
    text = text.replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _flatten_details(details: Any, *, prefix: str, max_depth: int) -> Iterable[Tuple[str, Any]]:
    if max_depth <= 0:
        yield (prefix, details)
        return

    if isinstance(details, dict):
        for key in sorted(details.keys(), key=str):
            value = details[key]
            next_prefix = "{}.{}".format(prefix, key) if prefix else str(key)
            yield from _flatten_details(value, prefix=next_prefix, max_depth=max_depth - 1)
        return

    yield (prefix, details)


def details_to_rows(details: Optional[Dict[str, Any]], *, max_depth: int = 3, max_rows: int = 200) -> List[Dict[str, str]]:
    """Convert `details` payload into rows friendly for notebook table rendering.

    - Deterministic order (sorted keys)
    - No dependency on marimo
    """
    if not details:
        return []

    rows: List[Dict[str, str]] = []
    for key_path, value in _flatten_details(details, prefix="", max_depth=int(max_depth)):
        key_str = key_path or "details"
        rows.append({"key": str(key_str), "value": _to_short_str(value)})
        if len(rows) >= int(max_rows):
            rows.append({"key": "...", "value": f"truncated (max_rows={max_rows})"})
            break
    return rows
