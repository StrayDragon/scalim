"""Governance: --cov-fail-under in justfile MUST match the value declared in testing-quality spec."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_JUSTFILE = _REPO_ROOT / "justfile"
_SPEC = _REPO_ROOT / "llmanspec" / "specs" / "testing-quality" / "spec.md"


def _extract_justfile_cov_threshold() -> int:
    text = _JUSTFILE.read_text(encoding="utf-8")
    m = re.search(r"--cov-fail-under=(\d+)", text)
    assert m, "Cannot find --cov-fail-under in justfile"
    return int(m.group(1))


def _extract_spec_cov_threshold() -> int:
    text = _SPEC.read_text(encoding="utf-8")
    m = re.search(r"--cov-fail-under=(\d+)", text)
    assert m, "Cannot find --cov-fail-under in testing-quality spec"
    return int(m.group(1))


def test_cov_fail_under_aligned() -> None:
    justfile_val = _extract_justfile_cov_threshold()
    spec_val = _extract_spec_cov_threshold()
    assert justfile_val == spec_val, (
        "Coverage threshold drift: justfile has --cov-fail-under={} but spec declares --cov-fail-under={}. "
        "Update both to the same value.".format(justfile_val, spec_val)
    )
