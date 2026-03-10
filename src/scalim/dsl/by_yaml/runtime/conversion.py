from typing import Dict, FrozenSet, List, Mapping, Optional, Union

from ....spec.ir.demand import DemandIr
from ....spec.ir.fields import DerivedFieldIr, FieldIr  # noqa: TC001
from ....spec.ir.sources import MainSourceIr, SourceIr
from ..config_parsing.security import SecureComputeEngine
from ..schema_dsl.models import DemandConfig
from ._internal.conversion_lookup import LookupCastRegistry
from ._internal.conversion_lookup import validate_source_id as _validate_source_id
from ._internal.conversion_relations import StepInfo
from ._internal.conversion_sources import ConfigToIRConversionSourceMixin
from .errors import ALLOWLIST_REQUIRED_MSG, AllowlistRequiredError, ConversionError
from .references import PythonReferenceResolver, SecurePythonReferenceResolver


class ConfigToIRConverter(ConfigToIRConversionSourceMixin):
    _allow_unsafe_resolver: bool
    _resolver: Optional[PythonReferenceResolver]
    _compute_engine: Optional[SecureComputeEngine]
    _lookup_casts: Optional[LookupCastRegistry]
    _sources_ir: Optional[Dict[str, SourceIr]]
    _main_source_ir: Optional[MainSourceIr]
    _relation_steps: Optional[Dict[str, List[StepInfo]]]
    _relation_adjacency: Optional[Dict[str, List[StepInfo]]]
    _source_field_id_map: Optional[Dict[str, Dict[str, str]]]
    _source_data_key_map: Optional[Dict[str, Dict[str, List[str]]]]
    _runtime_vars: Optional[Mapping[str, object]]

    @classmethod
    def from_allowlist(
        cls,
        *,
        allowed_modules: Optional[FrozenSet[str]] = None,
        allowed_functions: Optional[FrozenSet[str]] = None,
        compute_engine: Optional[SecureComputeEngine] = None,
    ) -> "ConfigToIRConverter":
        if not allowed_modules and not allowed_functions:
            raise AllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)
        resolver = SecurePythonReferenceResolver(
            allowed_modules=allowed_modules,
            allowed_functions=allowed_functions,
        )
        return cls(resolver=resolver, compute_engine=compute_engine)

    def __init__(
        self,
        resolver: Optional[PythonReferenceResolver] = None,
        compute_engine: Optional[SecureComputeEngine] = None,
        runtime_vars: Optional[Mapping[str, object]] = None,
        *,
        allow_unsafe_resolver: bool = False,
    ) -> None:
        resolved = resolver
        allow_unsafe = bool(allow_unsafe_resolver)
        if resolved is None:
            if not allow_unsafe:
                raise AllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)
            resolved = SecurePythonReferenceResolver()
        elif not resolved.has_allowlist() and not allow_unsafe:
            raise AllowlistRequiredError(ALLOWLIST_REQUIRED_MSG)

        self._allow_unsafe_resolver = allow_unsafe
        self._resolver = resolved
        self._compute_engine = compute_engine or SecureComputeEngine()
        self._runtime_vars = runtime_vars
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
            raise ConversionError(msg)

        relation_steps = self._convert_relations(config)
        self._relation_steps = relation_steps
        self._relation_adjacency = self._build_relation_adjacency(relation_steps)

        required_field_ids = self._resolve_required_field_ids(config)
        if required_field_ids is not None:
            known_fields = set(config.source_fields.keys()) | set(config.derived_fields.keys())
            missing = required_field_ids - known_fields
            if missing:
                msg = "Output fields reference unknown fields: {}".format(", ".join(sorted(missing)))
                raise ConversionError(msg)

        fields_ir: List[Union[FieldIr, DerivedFieldIr]] = []

        for field_id, field_config in config.source_fields.items():
            if required_field_ids is not None and field_id not in required_field_ids:
                continue
            fields_ir.append(self._convert_source_field(field_config, config))

        for field_id, derived_config in config.derived_fields.items():
            if required_field_ids is not None and field_id not in required_field_ids:
                continue
            fields_ir.append(self._convert_derived_field(derived_config))

        return DemandIr.from_irs(
            sources=list(sources_ir.values()),
            fields=fields_ir,
            main_source=main_source_ir,
            batch_size_hint=config.batch_size,
            name=config.name,
        )


__all__ = ["ConfigToIRConverter", "LookupCastRegistry", "_validate_source_id"]
