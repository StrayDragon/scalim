from typing import Any, Dict, Optional, Sequence, Tuple

from .....exceptions import ScalimYamlError
from .....vendor.dataclassesx import dataclass


@dataclass(frozen=True)
class ErrorLoc:
    line: int
    column: int

    def as_dict(self) -> Dict[str, int]:
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
    loc: Optional[ErrorLoc] = None
    suggestions: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
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
    def line(self) -> Optional[int]:
        return self.loc.line if self.loc is not None else None

    @property
    def column(self) -> Optional[int]:
        return self.loc.column if self.loc is not None else None


class ScalimYamlValidationError(ScalimYamlError):
    errors: Tuple[ErrorEnvelope, ...]
    warnings: Tuple[ErrorEnvelope, ...]

    def __init__(
        self,
        message: str,
        *,
        errors: Sequence[ErrorEnvelope],
        warnings: Optional[Sequence[ErrorEnvelope]] = None,
    ) -> None:
        super(ScalimYamlValidationError, self).__init__(message)
        self.errors = tuple(errors)
        self.warnings = tuple(warnings or ())


__all__ = []
