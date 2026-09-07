from dataclasses import dataclass, field
from typing import Any

from .._internal.config_parsing.error_envelope import ErrorEnvelope


@dataclass(frozen=True)
class FrontendDiagnostics:
    """编译前端诊断信息(稳定输出,不导入/不执行用户模块)."""

    errors: tuple[ErrorEnvelope, ...] = ()
    warnings: tuple[ErrorEnvelope, ...] = ()

    def ok(self) -> bool:
        return not self.errors

    def as_snapshot(self) -> dict[str, Any]:
        return {
            "errors": [e.as_dict() for e in self.errors],
            "warnings": [w.as_dict() for w in self.warnings],
        }


@dataclass(frozen=True)
class StaticCompilation:
    """单个需求 YAML 的静态编译产物(编译期视角)."""

    diagnostics: FrontendDiagnostics = field(default_factory=FrontendDiagnostics)
    effective_yaml: dict[str, Any] | None = None
    import_fragment_files: tuple[str, ...] = ()
    demand_ir: Any | None = None
    plan: Any | None = None
    plan_snapshot: dict[str, Any] | None = None
    deps_snapshot: dict[str, Any] | None = None

    def as_frontend_snapshot(self, *, schema_version: str = "yaml_dsl_frontend/v1") -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": str(schema_version),
            "diagnostics": self.diagnostics.as_snapshot(),
            "import_fragment_files": list(self.import_fragment_files),
        }
        if self.effective_yaml is not None:
            payload["effective_yaml"] = self.effective_yaml
        return payload


__all__ = (
    "FrontendDiagnostics",
    "StaticCompilation",
)
