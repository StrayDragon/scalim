from typing import Any, Dict, List, Optional, Tuple

from .....vendor.dataclassesx import Field
from .....vendor.dataclassesx import fields as dataclass_fields
from ..constants import SCHEMA_META_KEY, SCHEMA_OMIT_KEY
from .demand import DemandConfig
from .field import DerivedFieldConfig, SourceFieldConfig
from .guardrails import GuardrailsComputeConfig, GuardrailsConfig, GuardrailsLoaderConfig, GuardrailsRelationsConfig
from .lookup_bind_relation import (
    BindConfig,
    BindKeysConfig,
    BindRowsConfig,
    LookupCastConfig,
    RelationConfig,
    RelationStepConfig,
)
from .outputs import (
    OutputAggregateConfig,
    OutputExtraSheetConfig,
    OutputTargetConfig,
    OutputToConfig,
    OutputWriteConfig,
)
from .resources import (
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    BookXlsxFileConfig,
    BookXlsxMemoryConfig,
    FileConfig,
    FileCsvFileConfig,
    ResourcesConfig,
)
from .source import LoaderRetryConfig, MainSourceConfig, NormalizeConfig, SourceConfig


class _KeyMap:
    __slots__: Tuple[str, ...] = ("_keys",)
    _keys: Dict[str, str]

    def __init__(self, keys: Dict[str, str]) -> None:
        self._keys = keys

    def __getitem__(self, item: str) -> str:
        return self._keys[item]

    def get(self, item: str, default: Optional[str] = None) -> Optional[str]:
        return self._keys.get(item, default)

    def items(self) -> List[Tuple[str, str]]:
        return list(self._keys.items())


def _schema_name_for_field(dc_field: "Field[Any]") -> str:
    meta = dc_field.metadata.get(SCHEMA_META_KEY, {})
    schema_name = meta.get("schema_name")
    if isinstance(schema_name, str):
        return schema_name
    return dc_field.name


def _build_key_map(cls: type, *, include_omitted: bool = False) -> _KeyMap:
    keys: Dict[str, str] = {}
    for dc_field in dataclass_fields(cls):
        if not include_omitted and dc_field.metadata.get(SCHEMA_OMIT_KEY):
            continue
        keys[dc_field.name] = _schema_name_for_field(dc_field)
    return _KeyMap(keys)


LOOKUP_CAST_KEYS = _build_key_map(LookupCastConfig)
LOADER_RETRY_KEYS = _build_key_map(LoaderRetryConfig)
NORMALIZE_KEYS = _build_key_map(NormalizeConfig)
BIND_KEYS = _build_key_map(BindConfig)
BIND_ROWS_KEYS = _build_key_map(BindRowsConfig)
BIND_KEY_CONFIG_KEYS = _build_key_map(BindKeysConfig)
RELATION_STEP_KEYS = _build_key_map(RelationStepConfig)
RELATION_CONFIG_KEYS = _build_key_map(RelationConfig)
SOURCE_KEYS = _build_key_map(SourceConfig)
MAIN_SOURCE_KEYS = _build_key_map(MainSourceConfig)
SOURCE_FIELD_KEYS = _build_key_map(SourceFieldConfig)
DERIVED_FIELD_KEYS = _build_key_map(DerivedFieldConfig)
OUTPUT_AGGREGATE_KEYS = _build_key_map(OutputAggregateConfig)
OUTPUT_TARGET_KEYS = _build_key_map(OutputTargetConfig)
OUTPUT_EXTRA_SHEET_KEYS = _build_key_map(OutputExtraSheetConfig)
OUTPUT_TO_KEYS = _build_key_map(OutputToConfig)
OUTPUT_WRITE_KEYS = _build_key_map(OutputWriteConfig)
BOOK_BUDGET_KEYS = _build_key_map(BookBudgetConfig)
BOOK_EXPORT_XLSX_KEYS = _build_key_map(BookExportXlsxConfig)
BOOK_WRITE_DEFAULTS_KEYS = _build_key_map(BookWriteDefaultsConfig)
BOOK_XLSX_FILE_KEYS = _build_key_map(BookXlsxFileConfig)
BOOK_XLSX_MEMORY_KEYS = _build_key_map(BookXlsxMemoryConfig)
BOOK_KEYS = _build_key_map(BookConfig)
FILE_CSV_FILE_KEYS = _build_key_map(FileCsvFileConfig)
FILE_KEYS = _build_key_map(FileConfig)
RESOURCES_KEYS = _build_key_map(ResourcesConfig)
GUARDRAILS_LOADER_KEYS = _build_key_map(GuardrailsLoaderConfig)
GUARDRAILS_RELATIONS_KEYS = _build_key_map(GuardrailsRelationsConfig)
GUARDRAILS_COMPUTE_KEYS = _build_key_map(GuardrailsComputeConfig)
GUARDRAILS_KEYS = _build_key_map(GuardrailsConfig)
DEMAND_KEYS = _build_key_map(DemandConfig)

__all__ = ()
