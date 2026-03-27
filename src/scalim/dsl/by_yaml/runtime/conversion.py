from typing import Dict, FrozenSet, List, Mapping, Optional, Union

from ....spec.ir import DemandIr, DerivedFieldIr, FieldIr, MainSourceIr, SourceIr
from ..config_parsing.security import SecureComputeEngine
from ..schema_dsl.models import DemandConfig
from ._internal.conversion_lookup import LookupCastRegistry, validate_source_id
from ._internal.conversion_relations import StepInfo
from ._internal.conversion_sources import ConfigToIRConversionSourceMixin
from .errors import ALLOWLIST_REQUIRED_MSG, ScalimAllowlistRequiredError, ScalimConversionError
from .references import PythonReferenceResolver, SecurePythonReferenceResolver


def _validate_source_id(source_id: str, context: str) -> None:
    validate_source_id(source_id, context)


# 保持 `_validate_source_id` 可导入(用于测试/门禁),但不纳入 `__all__`.
_non_public_exports = (_validate_source_id,)
del _non_public_exports


class ConfigToIRConverter(ConfigToIRConversionSourceMixin):
    _resolver: Optional[PythonReferenceResolver]
    _compute_engine: Optional[SecureComputeEngine]
    _lookup_casts: Optional[LookupCastRegistry]
    _sources_ir: Optional[Dict[str, SourceIr]]
    _main_source_ir: Optional[MainSourceIr]
    _relation_steps: Optional[Dict[str, List[StepInfo]]]
    _relation_adjacency: Optional[Dict[str, List[StepInfo]]]
    _source_field_id_map: Optional[Dict[str, Dict[str, str]]]
    _source_data_key_map: Optional[Dict[str, Dict[str, List[str]]]]
    _init_vars: Optional[Mapping[str, object]]

    @classmethod
    def from_allowlist(
        cls,
        *,
        allowed_modules: Optional[FrozenSet[str]] = None,
        allowed_functions: Optional[FrozenSet[str]] = None,
        compute_engine: Optional[SecureComputeEngine] = None,
    ) -> "ConfigToIRConverter":
        if not allowed_modules and not allowed_functions:
            raise ScalimAllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)
        resolver = SecurePythonReferenceResolver(
            allowed_modules=allowed_modules,
            allowed_functions=allowed_functions,
        )
        return cls(resolver=resolver, compute_engine=compute_engine)

    def __init__(
        self,
        resolver: Optional[PythonReferenceResolver] = None,
        compute_engine: Optional[SecureComputeEngine] = None,
        init_vars: Optional[Mapping[str, object]] = None,
    ) -> None:
        resolved = resolver
        if resolved is None or not resolved.has_allowlist():
            raise ScalimAllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)

        self._resolver = resolved
        self._compute_engine = compute_engine or SecureComputeEngine()
        self._init_vars = init_vars
        self._lookup_casts = LookupCastRegistry()
        self._sources_ir = {}
        self._main_source_ir = None
        self._relation_steps = {}
        self._relation_adjacency = {}
        self._source_field_id_map = {}
        self._source_data_key_map = {}

    def convert(self, config: DemandConfig) -> DemandIr:
        self._sources_ir = {}
        self._main_source_ir = None
        self._relation_steps = {}
        self._relation_adjacency = {}

        source_field_id_map = config.source_field_id_map or {}
        self._source_field_id_map = source_field_id_map
        self._source_data_key_map = self._build_source_data_key_map(source_field_id_map)

        main_source_ir = self._convert_main_source(config.main_source)
        self._main_source_ir = main_source_ir

        sources_ir = self._require_sources_ir()
        for source_id, source_config in config.sources.items():
            sources_ir[source_id] = self._convert_source(source_config)

        if main_source_ir.source_id in sources_ir:
            msg = "Main source '{}' conflicts with sources".format(main_source_ir.source_id)
            raise ScalimConversionError(msg)

        relation_steps = self._convert_relations(config)
        self._relation_steps = relation_steps
        self._relation_adjacency = self._build_relation_adjacency(relation_steps)

        fields_ir: List[Union[FieldIr, DerivedFieldIr]] = []

        for field_config in config.source_fields.values():
            fields_ir.append(self._convert_source_field(field_config, config))

        for derived_config in config.derived_fields.values():
            fields_ir.append(self._convert_derived_field(derived_config))

        return DemandIr.from_irs(
            sources=list(sources_ir.values()),
            fields=fields_ir,
            main_source=main_source_ir,
            batch_size_hint=config.batch_size,
            name=config.name,
        )


__all__ = ["ConfigToIRConverter", "LookupCastRegistry"]
