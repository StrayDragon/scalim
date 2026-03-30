# ruff: noqa: INP001

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional


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


def _extract_schema_header(text: str) -> Optional[str]:
    for line in text.splitlines()[:30]:
        if "$schema=" not in line:
            continue
        m = re.search(r"\$schema=([^\s]+)", line)
        if m:
            return m.group(1).strip()
    return None


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

    expected_schema = str((workdir / "schema" / "demand.gen.json").resolve())
    header = _extract_schema_header(_read_text(yaml_path))
    if header != expected_schema:
        return _grading(
            passed=False,
            reason="Schema header mismatch. expected={} observed={} (file={})".format(expected_schema, header or "(missing)", yaml_rel),
        )

    payload = _try_parse_json(output or "")
    if payload is None:
        return _grading(passed=False, reason="Agent output is not a JSON object.")
    if payload.get("ok") is not True:
        return _grading(passed=False, reason="Agent reported ok!=true.")

    return _grading(passed=True, reason="Schema header fixed and agent reported ok.", score=1.0)
