from dataclasses import dataclass
from typing import Any, Dict, Optional

EXAMPLE_KIND_SMOKE = "smoke"
EXAMPLE_KIND_ORACLE = "oracle"
EXAMPLE_KIND_FIXTURE = "fixture"


@dataclass(frozen=True)
class ExampleResult:
    example_id: str
    passed: bool
    kind: str
    summary: str
    details: Optional[Dict[str, Any]] = None

    def raise_if_failed(self) -> None:
        if self.passed:
            return
        msg = "[{}] {}".format(self.example_id, self.summary)
        raise AssertionError(msg)
