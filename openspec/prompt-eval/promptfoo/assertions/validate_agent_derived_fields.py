# ruff: noqa: INP001

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def _grading(*, passed: bool, reason: str, score: Optional[float] = None) -> Dict[str, Any]:
    if score is None:
        score = 1.0 if passed else 0.0
    return {"pass": passed, "score": float(score), "reason": reason}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _strip_code_fences(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```") and s.endswith("```"):
        s = re.sub(r"^```[A-Za-z0-9_-]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    raw = _strip_code_fences(text)
    if not raw:
        return None
    if not raw.lstrip().startswith("{"):
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _top_level_block_lines(text: str, *, key: str) -> Optional[List[str]]:
    lines = text.splitlines()
    start: Optional[int] = None
    for idx, line in enumerate(lines):
        if line.startswith("{}:".format(key)) and (line.strip() == "{}:".format(key)):
            start = idx + 1
            break
    if start is None:
        return None

    block: List[str] = []
    for line in lines[start:]:
        if not line.strip():
            block.append(line)
            continue
        if not line.startswith(" ") and not line.startswith("\t"):
            break
        block.append(line)
    return block


def _has_derived_logic(lines: List[str]) -> bool:
    return any(re.search(r"\b(compute|call_by)\s*:", line) for line in lines)


def get_assert(output: str, context: Dict[str, Any]) -> Dict[str, Any]:
    vars_raw = (context or {}).get("vars") or {}
    if not isinstance(vars_raw, dict):
        return _grading(passed=False, reason="context.vars missing.")

    workdir_raw = str(vars_raw.get("workdir") or "").strip()
    yaml_rel = str(vars_raw.get("yaml_rel_path") or "").strip()
    if not workdir_raw:
        return _grading(passed=False, reason="Missing vars.workdir.")
    if not yaml_rel:
        return _grading(passed=False, reason="Missing vars.yaml_rel_path.")

    workdir = Path(workdir_raw)
    yaml_path = (workdir / yaml_rel).resolve()
    if not yaml_path.exists():
        return _grading(passed=False, reason="YAML file missing: {}".format(yaml_path))

    text = _read_text(yaml_path)

    main_source = _top_level_block_lines(text, key="main_source")
    if main_source and _has_derived_logic(main_source):
        return _grading(passed=False, reason="Derived logic still exists inside top-level `main_source:` block.")

    fields = _top_level_block_lines(text, key="fields")
    if not fields:
        return _grading(passed=False, reason="Missing top-level `fields:` block.")
    if not _has_derived_logic(fields):
        return _grading(passed=False, reason="Expected at least one derived field (compute/call_by) under top-level `fields:`.")

    payload = _try_parse_json(output or "")
    if payload is None:
        return _grading(passed=False, reason="Agent output is not a JSON object.")
    if payload.get("ok") is not True:
        return _grading(passed=False, reason="Agent reported ok!=true.")

    return _grading(passed=True, reason="Derived fields look migrated and agent reported ok.", score=1.0)
