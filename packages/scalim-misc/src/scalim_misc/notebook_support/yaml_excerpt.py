from __future__ import annotations

import re
from pathlib import Path


def _read_lines(path: str | Path) -> str:
    p = path if isinstance(path, Path) else Path(path)
    return p.read_text(encoding="utf-8")


def excerpt_head(path: str | Path, *, max_lines: int = 80) -> str:
    text = _read_lines(path)
    lines = text.splitlines()
    return "\n".join(lines[: int(max_lines)]).rstrip()


def excerpt_by_regex(
    path: str | Path,
    *,
    start_regex: str | None = None,
    end_regex: str | None = None,
    max_lines: int = 120,
) -> str:
    text = _read_lines(path)
    lines = text.splitlines()

    start_idx = 0
    if start_regex:
        pattern = re.compile(start_regex)
        for i, line in enumerate(lines):
            if pattern.search(line):
                start_idx = i
                break

    end_idx = len(lines)
    if end_regex:
        pattern = re.compile(end_regex)
        for i in range(start_idx + 1, len(lines)):
            if pattern.search(lines[i]):
                end_idx = i
                break

    excerpt = lines[start_idx:end_idx]
    excerpt = excerpt[: int(max_lines)]
    return "\n".join(excerpt).rstrip()
