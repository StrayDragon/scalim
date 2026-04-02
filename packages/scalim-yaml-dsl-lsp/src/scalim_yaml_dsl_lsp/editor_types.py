from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class EditorPosition:
    """编辑器位置(以 1 为基准)."""

    line: int
    column: int

    def as_dict(self) -> Dict[str, int]:
        return {"line": int(self.line), "column": int(self.column)}


@dataclass(frozen=True)
class EditorRange:
    """编辑器范围(以 1 为基准, `end` 为半开区间右边界)."""

    start: EditorPosition
    end: EditorPosition

    def as_dict(self) -> Dict[str, Any]:
        return {"start": self.start.as_dict(), "end": self.end.as_dict()}
