from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .....exceptions import ScalimYamlError


@dataclass(frozen=True)
class ErrorLoc:
    line: int
    column: int

    def as_dict(self) -> dict[str, int]:
        return {"line": int(self.line), "column": int(self.column)}


@dataclass(frozen=True)
class ErrorEnvelope:
    """可机器消费的稳定错误结构.

    注意: 该结构用于跨入口(`compile`/`run`/`CLI validate`/`workflow validate`)对齐错误输出.
    """

    code: str
    message: str
    source_path: str
    path: str
    loc: ErrorLoc | None = None
    suggestions: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": str(self.code),
            "message": str(self.message),
            "source_path": str(self.source_path),
            "path": str(self.path),
        }
        if self.loc is not None:
            payload["loc"] = self.loc.as_dict()
        if self.suggestions:
            payload["suggestions"] = list(self.suggestions)
        return payload

    @property
    def line(self) -> int | None:
        return self.loc.line if self.loc is not None else None

    @property
    def column(self) -> int | None:
        return self.loc.column if self.loc is not None else None


class ScalimYamlValidationError(ScalimYamlError):
    errors: tuple[ErrorEnvelope, ...]
    warnings: tuple[ErrorEnvelope, ...]

    def __init__(
        self,
        message: str,
        *,
        errors: Sequence[ErrorEnvelope],
        warnings: Sequence[ErrorEnvelope] | None = None,
    ) -> None:
        super().__init__(message)
        self.errors = tuple(errors)
        self.warnings = tuple(warnings or ())


__all__ = ()
