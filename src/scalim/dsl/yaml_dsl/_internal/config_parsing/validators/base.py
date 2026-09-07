from typing import Any, cast

from ..models import AliasIndex, FieldDef
from ..security import SecureComputeEngine
from .issues import VALIDATION_SEVERITY_ERROR, ValidationIssue

_RESERVED_FIELD_IDS = frozenset(
    set(SecureComputeEngine.SAFE_BUILTINS)
    | set(SecureComputeEngine.FORBIDDEN_NAMES)
    | {
        "True",
        "False",
        "None",
    }
)


class ValidatorMixinBase:
    def __init__(self) -> None:
        self._step_allowed_fields_by_source: dict[str, set[str]] = {}
        self._step_field_ids_by_source_data_key: dict[str, dict[str, set[str]]] = {}

    def _add_error(self, errors: list[ValidationIssue], message: str, path: str = "") -> None:
        errors.append(ValidationIssue(severity=VALIDATION_SEVERITY_ERROR, message=message, path=path))


class ValidatorFieldBaseMixin(ValidatorMixinBase):
    _compute_engine: SecureComputeEngine | None = None

    def _require_compute_engine(self) -> SecureComputeEngine:
        compute_engine = self._compute_engine
        if compute_engine is None:
            msg = "Secure compute engine is not initialized"
            raise RuntimeError(msg)
        return compute_engine

    def _validate_field_id_not_reserved(self, field_id: str, errors: list[ValidationIssue], *, path: str) -> None:
        if field_id not in _RESERVED_FIELD_IDS:
            return
        msg = (
            f"Field '{field_id}' uses a reserved name that conflicts with compute builtins/constants. "
            f"Rename the field_id to avoid ambiguous or broken compute dependency resolution (e.g. '{field_id}_value')."
        )
        self._add_error(errors, msg, path=path)

    def _add_field_def(
        self,
        field_id_raw: Any,
        kind: str,
        source_id: str | None,
        data_raw: Any,
        field_defs: list[FieldDef],
        defs_by_id: dict[str, list[FieldDef]],
        alias_index: AliasIndex,
        errors: list[ValidationIssue],
    ) -> FieldDef | None:
        if not isinstance(data_raw, dict):
            self._add_error(errors, f"Field '{field_id_raw}' must be a dictionary")
            return None
        field_id = str(field_id_raw)
        field_dict = cast("dict[str, Any]", data_raw)  # pragma: allow-cast yaml mapping typed narrowing
        field_def = FieldDef(field_id=field_id, kind=kind, source_id=source_id, data=field_dict)
        field_defs.append(field_def)
        defs_by_id.setdefault(field_id, []).append(field_def)
        alias_index.add(field_dict, field_def)
        return field_def


__all__ = ()
