from typing import Dict, List, Optional

from ......vendor.dataclassesx import dataclass
from ....schema_dsl.models import DerivedFieldConfig, SourceFieldConfig
from ..models import FieldDefIndex


@dataclass(frozen=True)
class ParsedFieldsResult:
    source_fields: Dict[str, SourceFieldConfig]
    derived_fields: Dict[str, DerivedFieldConfig]
    output_fields: Optional[List[str]]
    main_source_fields: Dict[str, SourceFieldConfig]
    source_fields_by_source: Dict[str, Dict[str, SourceFieldConfig]]
    source_field_id_map: Dict[str, Dict[str, str]]
    field_def_index: FieldDefIndex


__all__ = ()
