from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any

from ..vendor.compact.typing_extensionsx import Literal

GuardrailMode = Literal["quiet", "fast_fail"]


class GuardrailViolationError(RuntimeError):
    """当触发运行时护栏时抛出（或记录）该异常。"""

    code: str
    context: dict[str, Any]

    def __init__(
        self,
        message: str,
        *,
        code: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.context = dict(context or {})


# 向后兼容的别名（为稳定性保留历史命名）。
GuardrailViolation = GuardrailViolationError


@dataclass(frozen=True)
class GuardrailsLoaderPolicy:
    validate_result: bool = False
    required_fields: tuple[str, ...] = ()
    on_transform_error: GuardrailMode | None = None


@dataclass(frozen=True)
class GuardrailsRelationsPolicy:
    null_key_max_rate: float | None = None
    type_error_max_rate: float | None = None


@dataclass(frozen=True)
class GuardrailsComputePolicy:
    on_error: GuardrailMode | None = None


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
