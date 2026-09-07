from dataclasses import dataclass

from ....schema_dsl.models import DerivedFieldConfig, SourceFieldConfig
from ..models import FieldDefIndex


@dataclass(frozen=True)
class ParsedFieldsResult:
    source_fields: dict[str, SourceFieldConfig]
    derived_fields: dict[str, DerivedFieldConfig]
    output_fields: list[str] | None
    main_source_fields: dict[str, SourceFieldConfig]
    source_fields_by_source: dict[str, dict[str, SourceFieldConfig]]
    source_field_id_map: dict[str, dict[str, str]]
    field_def_index: FieldDefIndex


__all__ = ()
