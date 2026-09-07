from dataclasses import dataclass
from typing import Any

EXAMPLE_KIND_SMOKE = "smoke"
EXAMPLE_KIND_ORACLE = "oracle"
EXAMPLE_KIND_FIXTURE = "fixture"


@dataclass(frozen=True)
class ExampleResult:
    example_id: str
    passed: bool
    kind: str
    summary: str
    details: dict[str, Any] | None = None

    def raise_if_failed(self) -> None:
        if self.passed:
            return
        msg = f"[{self.example_id}] {self.summary}"
        raise AssertionError(msg)
