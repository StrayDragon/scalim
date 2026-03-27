from typing import Any, Dict, List, Optional, Set, cast

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
        self._step_allowed_fields_by_source: Dict[str, Set[str]] = {}
        self._step_field_ids_by_source_data_key: Dict[str, Dict[str, Set[str]]] = {}

    def _add_error(self, errors: List[ValidationIssue], message: str, path: str = "") -> None:
        errors.append(ValidationIssue(severity=VALIDATION_SEVERITY_ERROR, message=message, path=path))


class ValidatorFieldBaseMixin(ValidatorMixinBase):
    _compute_engine: Optional[SecureComputeEngine] = None

    def _require_compute_engine(self) -> SecureComputeEngine:
        compute_engine = self._compute_engine
        if compute_engine is None:
            msg = "Secure compute engine is not initialized"
            raise RuntimeError(msg)
        return compute_engine

    def _validate_field_id_not_reserved(self, field_id: str, errors: List[ValidationIssue], *, path: str) -> None:
        if field_id not in _RESERVED_FIELD_IDS:
            return
        msg = (
            "Field '{}' uses a reserved name that conflicts with compute builtins/constants. "
            "Rename the field_id to avoid ambiguous or broken compute dependency resolution (e.g. '{}_value')."
        ).format(field_id, field_id)
        self._add_error(errors, msg, path=path)

    def _add_field_def(
        self,
        field_id_raw: Any,
        kind: str,
        source_id: Optional[str],
        data_raw: Any,
        field_defs: List[FieldDef],
        defs_by_id: Dict[str, List[FieldDef]],
        alias_index: AliasIndex,
        errors: List[ValidationIssue],
    ) -> Optional[FieldDef]:
        if not isinstance(data_raw, dict):
            self._add_error(errors, "Field '{}' must be a dictionary".format(field_id_raw))
            return None
        field_id = str(field_id_raw)
        field_dict = cast("Dict[str, Any]", data_raw)  # pragma: allow-cast yaml mapping typed narrowing
        field_def = FieldDef(field_id=field_id, kind=kind, source_id=source_id, data=field_dict)
        field_defs.append(field_def)
        defs_by_id.setdefault(field_id, []).append(field_def)
        alias_index.add(field_dict, field_def)
        return field_def


__all__ = ["ValidatorFieldBaseMixin", "ValidatorMixinBase"]
