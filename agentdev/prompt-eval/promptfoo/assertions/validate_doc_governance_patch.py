# ruff: noqa: INP001

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Type


def _find_repo_root(start: Path) -> Path:
    current = start
    for _ in range(20):
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return start


def _import_validators(repo_root: Path) -> Tuple[Type[Any], Callable[..., Any]]:
    scripts_dir = repo_root / "scripts"
    sys.path.insert(0, str(scripts_dir))

    module = importlib.import_module("prompt_eval.diff_validation")
    return module.Issue, module.validate_patch_text


def _grading_result(*, passed: bool, score: float, reason: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"pass": passed, "score": score, "reason": reason}
    if details:
        payload["details"] = details
    return payload


def get_assert(output: str, _context: Dict[str, Any]) -> Dict[str, Any]:
    repo_root = _find_repo_root(Path(__file__).resolve())
    _, validate_patch_text = _import_validators(repo_root)

    patch_text = output or ""
    issues: List[Any] = validate_patch_text(patch_text, root=repo_root, allow_gen=False)

    if not patch_text.strip():
        return _grading_result(passed=False, score=0, reason="Empty output; expected a unified diff patch.")

    if not issues:
        return _grading_result(passed=True, score=1, reason="Patch passed governance boundary validators.")

    details = {"issues": [i.as_dict() for i in issues]}
    return _grading_result(
        passed=False,
        score=0,
        reason="Patch violated governance boundaries:\n{}".format(json.dumps(details, ensure_ascii=False, indent=2, sort_keys=True)),
        details=details,
    )
