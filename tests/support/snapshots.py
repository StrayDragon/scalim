import json
import os
from difflib import unified_diff
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _truthy_env(name: str) -> bool:
    raw = str(os.environ.get(name) or "").strip().lower()
    if not raw:
        return False
    return raw not in {"0", "false", "no"}


def update_golden_enabled() -> bool:
    return _truthy_env("UPDATE_GOLDEN")


def _to_pretty_json_lines(payload: Any) -> List[str]:
    dumped = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return dumped.splitlines(keepends=True)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _diff_lines(a: Iterable[str], b: Iterable[str], *, fromfile: str, tofile: str) -> str:
    return "".join(unified_diff(list(a), list(b), fromfile=fromfile, tofile=tofile))


def assert_json_snapshot(
    snapshot_path: Path,
    snapshot: Any,
    *,
    schema_version: int = 1,
) -> None:
    payload: Dict[str, Any] = {
        "schema_version": int(schema_version),
        "snapshot": snapshot,
    }

    if snapshot_path.exists():
        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if expected == payload:
            return

        if update_golden_enabled():
            _write_json(snapshot_path, payload)
            return

        diff = _diff_lines(
            _to_pretty_json_lines(expected),
            _to_pretty_json_lines(payload),
            fromfile=str(snapshot_path) + " (expected)",
            tofile=str(snapshot_path) + " (actual)",
        )
        raise AssertionError("snapshot mismatch: {}\n{}".format(snapshot_path, diff))

    if update_golden_enabled():
        _write_json(snapshot_path, payload)
        return

    raise AssertionError("missing snapshot: {} (re-run with UPDATE_GOLDEN=1)".format(snapshot_path))


__all__ = [
    "assert_json_snapshot",
    "update_golden_enabled",
]
