# ruff: noqa: INP001

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_SKILL_DOC_ENV = "SCALIM_PROMPT_EVAL_SKILL_DOC_PATH"
_REF_RE = re.compile(r"(references/[A-Za-z0-9_./*\\-]+)")

_TASK_KINDS = {
    "authoring",
    "upgrade_legacy",
    "validate_debug",
    "report_migration",
    "downstream_adaptation",
    "breaking_batch_locate",
}


def _contains_any(haystack: str, needles: List[str]) -> bool:
    return any(n in haystack for n in needles)


def _repo_root() -> Path:
    # .../agentdev/prompt-eval/promptfoo/assertions/<this_file>.py
    return Path(__file__).resolve().parents[4]


def _default_skill_doc_path() -> Path:
    return _repo_root() / "agentdev/skills/scalim-yaml-dsl/SKILL.md"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _skill_doc_path() -> Path:
    raw = (os.environ.get(_SKILL_DOC_ENV) or "").strip()
    if raw:
        return Path(raw)
    return _default_skill_doc_path()


def _extract_refs(skill_doc: str) -> List[str]:
    return sorted({m.group(1) for m in _REF_RE.finditer(skill_doc or "")})


def _extract_cmd_prefixes(skill_doc: str) -> List[str]:
    # Extract backticked commands, then normalize into prefixes (strip placeholders like `<file.yaml>`).
    candidates = re.findall(r"`([^`]+)`", skill_doc or "")
    cmds: List[str] = []
    for c in candidates:
        if "scalim-cli yaml-dsl" not in c:
            continue
        prefix = c.split("<", 1)[0].strip()
        if prefix:
            cmds.append(prefix)
    # Keep stable order, dedupe.
    seen: set[str] = set()
    out: List[str] = []
    for c in cmds:
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def _grading(*, passed: bool, reason: str, score: Optional[float] = None) -> Dict[str, Any]:
    if score is None:
        score = 1.0 if passed else 0.0
    return {"pass": passed, "score": float(score), "reason": reason}


def _strip_code_fences(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```") and s.endswith("```"):
        s = re.sub(r"^```[A-Za-z0-9_-]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    raw = _strip_code_fences(text)
    if not raw or not raw.lstrip().startswith("{"):
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def get_assert(output: str, _context: Dict[str, Any]) -> Dict[str, Any]:
    text = (output or "").strip()
    if not text:
        return _grading(passed=False, reason="Empty output.")

    ctx = _context or {}
    expected_kind = ""
    vars_raw = ctx.get("vars")
    if isinstance(vars_raw, dict):
        expected_kind = str(vars_raw.get("expected_task_kind") or "").strip()

    skill_doc_path = _skill_doc_path()
    if not skill_doc_path.exists():
        return _grading(passed=False, reason="Skill doc not found: {}".format(skill_doc_path))

    skill_doc = _read_text(skill_doc_path)
    allowed_refs = _extract_refs(skill_doc)
    allowed_cmd_prefixes = _extract_cmd_prefixes(skill_doc)

    stripped = _strip_code_fences(text)
    payload = _try_parse_json(text)
    if payload is not None:
        task_kind = str(payload.get("task_kind") or "").strip()
        references = payload.get("references")
        commands = payload.get("commands")
        next_steps = payload.get("next_steps")

        if not task_kind or task_kind not in _TASK_KINDS:
            return _grading(passed=False, reason="Invalid `task_kind` (expected one of {}).".format(", ".join(sorted(_TASK_KINDS))))

        if expected_kind and task_kind != expected_kind:
            return _grading(passed=False, reason="Wrong `task_kind`: expected={} got={}.".format(expected_kind, task_kind))

        if not isinstance(references, list) or not all(isinstance(x, str) for x in references):
            return _grading(passed=False, reason="`references` must be a string list.")
        if len(references) < 1 or len(references) > 3:
            return _grading(passed=False, reason="`references` must have 1-3 items.")
        if allowed_refs:
            unknown = [r for r in references if r not in allowed_refs]
            if unknown:
                return _grading(passed=False, reason="Unknown references (not in skill doc): {}".format(", ".join(unknown)))
        else:
            if not any("references/" in r for r in references):
                return _grading(passed=False, reason="No `references/` paths found in `references` list.")

        if not isinstance(commands, list) or not all(isinstance(x, str) for x in commands):
            return _grading(passed=False, reason="`commands` must be a string list.")
        if len(commands) < 1 or len(commands) > 2:
            return _grading(passed=False, reason="`commands` must have 1-2 items.")
        if allowed_cmd_prefixes:
            bad = [c for c in commands if not _contains_any(c, allowed_cmd_prefixes)]
            if bad:
                return _grading(passed=False, reason="Commands not matching skill templates: {}".format(", ".join(bad)))

        if not isinstance(next_steps, list) or not all(isinstance(x, str) for x in next_steps):
            return _grading(passed=False, reason="`next_steps` must be a string list.")
        if len(next_steps) < 3 or len(next_steps) > 6:
            return _grading(passed=False, reason="`next_steps` must have 3-6 items.")

        # Guardrail: avoid claiming to read everything.
        if re.search(r"(全部|全量|所有).*(reference|资料|文档|catalog)", json.dumps(payload, ensure_ascii=False), flags=re.IGNORECASE):
            return _grading(passed=False, reason="Output suggests reading everything; expected minimal material selection.")

        return _grading(passed=True, reason="Structured routing output looks OK.", score=1.0)

    # If it looks like JSON but failed to parse, fail fast (keeps prompt B objective).
    if stripped.lstrip().startswith("{"):
        return _grading(passed=False, reason="Invalid JSON output (expected a single JSON object).")

    # Freeform fallback (prompt A): must mention at least 1 canonical ref and 1 command template prefix.
    if allowed_refs and not _contains_any(text, allowed_refs):
        return _grading(
            passed=False,
            reason="No canonical reference paths found (expected at least 1 reference from the skill doc).",
        )

    if allowed_cmd_prefixes and not _contains_any(text, allowed_cmd_prefixes):
        return _grading(
            passed=False,
            reason="No expected command template prefix found (from skill doc).",
        )

    # Guardrail: avoid claiming to read everything.
    if re.search(r"(全部|全量|所有).*(reference|资料|文档|catalog)", text, flags=re.IGNORECASE):
        return _grading(passed=False, reason="Output suggests reading everything; expected minimal material selection.")

    return _grading(passed=True, reason="Routing/material-selection looks OK.", score=1.0)
