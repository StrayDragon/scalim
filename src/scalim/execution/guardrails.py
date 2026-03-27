from typing import Any, Dict, Optional, Tuple

from ..exceptions import ScalimExecutionError
from ..vendor.compact.typing_extensionsx import Literal
from ..vendor.dataclassesx import dataclass
from ..vendor.dataclassesx import field as dataclass_field

GuardrailMode = Literal["quiet", "fast_fail"]


class ScalimGuardrailViolationError(ScalimExecutionError):
    """当运行时防护触发时抛出(或记录)的异常."""

    code: str
    context: Dict[str, Any]

    def __init__(
        self,
        message: str,
        *,
        code: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.context = dict(context or {})


@dataclass(frozen=True)
class GuardrailsLoaderPolicy:
    validate_result: bool = False
    required_fields: Tuple[str, ...] = ()
    on_transform_error: Optional[GuardrailMode] = None


@dataclass(frozen=True)
class GuardrailsRelationsPolicy:
    null_key_max_rate: Optional[float] = None
    type_error_max_rate: Optional[float] = None


@dataclass(frozen=True)
class GuardrailsComputePolicy:
    on_error: Optional[GuardrailMode] = None


@dataclass(frozen=True)
class GuardrailsPolicy:
    enabled: bool = False
    mode: GuardrailMode = "fast_fail"
    loader: GuardrailsLoaderPolicy = dataclass_field(default_factory=GuardrailsLoaderPolicy)
    relations: GuardrailsRelationsPolicy = dataclass_field(default_factory=GuardrailsRelationsPolicy)
    compute: GuardrailsComputePolicy = dataclass_field(default_factory=GuardrailsComputePolicy)

    @classmethod
    def disabled(cls) -> "GuardrailsPolicy":
        return cls(enabled=False)

    def effective_loader_transform_mode(self) -> GuardrailMode:
        return self.loader.on_transform_error or self.mode

    def effective_compute_mode(self) -> GuardrailMode:
        return self.compute.on_error or self.mode

    def relations_enabled(self) -> bool:
        return self.relations.null_key_max_rate is not None or self.relations.type_error_max_rate is not None


__all__ = []
