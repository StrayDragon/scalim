from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ChapterResult:
    chapter_id: str
    passed: bool
    summary: str
    details: Optional[Dict[str, Any]] = None

    def raise_if_failed(self) -> None:
        if self.passed:
            return
        msg = "[{}] {}".format(self.chapter_id, self.summary)
        raise AssertionError(msg)
