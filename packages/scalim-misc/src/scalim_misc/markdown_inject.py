from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class InjectBlockSpec:
    begin_marker: str
    end_marker: str
    label: str = ""


class InjectBlockError(RuntimeError):
    pass


def replace_markdown_injected_block(text: str, *, spec: InjectBlockSpec, content: str) -> str:
    """Strict injected-block replacement.

    Rules:
    - begin/end markers MUST exist and MUST each appear exactly once
    - only the block body is replaced; other parts stay unchanged
    """

    lines = text.splitlines(keepends=True)
    begin_positions = [idx for idx, line in enumerate(lines) if line.strip() == spec.begin_marker]
    end_positions = [idx for idx, line in enumerate(lines) if line.strip() == spec.end_marker]

    label = spec.label or "markdown"
    if len(begin_positions) != 1 or len(end_positions) != 1:
        message = "{}: injected block markers must match exactly once (begin={}, end={})".format(
            label,
            len(begin_positions),
            len(end_positions),
        )
        raise InjectBlockError(message)

    begin_index = begin_positions[0]
    end_index = end_positions[0]
    if end_index <= begin_index:
        message = "{}: injected block marker order invalid (end <= begin).".format(label)
        raise InjectBlockError(message)

    content_lines: List[str] = content.splitlines(keepends=True)
    if content and not content.endswith("\n"):
        content_lines.append("\n")

    injected: List[str] = []
    injected.extend(lines[: begin_index + 1])
    injected.extend(content_lines)
    injected.extend(lines[end_index:])
    return "".join(injected)
