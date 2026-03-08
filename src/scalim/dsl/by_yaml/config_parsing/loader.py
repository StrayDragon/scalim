from pathlib import Path
from typing import IO, TYPE_CHECKING, Optional, Union

from ....vendor.compact.importlibx import require_optional_dependency

if TYPE_CHECKING:
    import yaml

    from .validator import ConfigValidator
else:
    yaml = require_optional_dependency(
        "yaml",
        context="scalim.dsl.by_yaml.config_parsing.loader",
        install_name="pyyaml",
    )

from ..schema_dsl.constants import DEFAULT_BATCH_SIZE, UTF8_ENCODING
from ..schema_dsl.models import DEMAND_KEYS, OUTPUT_KEYS, DemandConfig
from .models import RawDemand
from .parsers.fields import ParserFieldsMixin
from .parsers.guardrails import ParserGuardrailsMixin
from .parsers.output import ParserOutputMixin
from .parsers.results import ParsedFieldsResult

__all__ = [
    "ParsedFieldsResult",
    "YamlDemandLoader",
]


def _safe_load_yaml(source: Union[str, IO[str]]) -> object:
    return yaml.safe_load(source)


def _create_validator() -> "ConfigValidator":
    from .validator import ConfigValidator  # noqa: PLC0415

    return ConfigValidator()


class YamlDemandLoader(
    ParserFieldsMixin,
    ParserOutputMixin,
    ParserGuardrailsMixin,
):
    _validator: Optional["ConfigValidator"]

    def __init__(self) -> None:
        self._validator = None

    def load(self, source: Union[str, Path, IO[str]]) -> DemandConfig:
        if isinstance(source, (str, Path)):
            with Path(source).open("r", encoding=UTF8_ENCODING) as f:
                raw = _safe_load_yaml(f)
        else:
            raw = _safe_load_yaml(source)
        raw_demand = RawDemand.from_raw(raw)

        self._ensure_validator()
        if self._validator:
            self._validator.validate(raw_demand.data)

        return self._parse_config(raw_demand)

    def load_string(self, yaml_string: str) -> DemandConfig:
        raw = _safe_load_yaml(yaml_string)
        raw_demand = RawDemand.from_raw(raw)

        self._ensure_validator()
        if self._validator:
            self._validator.validate(raw_demand.data)

        return self._parse_config(raw_demand)

    def _ensure_validator(self) -> None:
        if self._validator is None:
            self._validator = _create_validator()

    def _parse_config(self, raw: RawDemand) -> DemandConfig:
        name = str(raw.data.get(DEMAND_KEYS["name"], ""))
        description = str(raw.data.get(DEMAND_KEYS["description"], ""))
        if DEMAND_KEYS["batch_size"] in raw.data:
            batch_size = raw.data.get(DEMAND_KEYS["batch_size"])
        else:
            batch_size = DEFAULT_BATCH_SIZE
        retry = self._parse_loader_retry(raw.data.get(DEMAND_KEYS["retry"]))
        main_source = self._parse_main_source(raw)
        sources = self._parse_sources(raw)
        relations = self._parse_relations(raw)
        raw_output_fields = None
        raw_output = raw.get_mapping(DEMAND_KEYS["output"])
        if raw_output is not None:
            raw_output_fields = raw_output.get(OUTPUT_KEYS["fields"])

        parsed_fields = self._parse_fields_v3(raw, main_source.source_id, raw_output_fields)
        main_source = self._with_main_source_fields(main_source, parsed_fields.main_source_fields)
        sources = self._with_source_fields(sources, parsed_fields.source_fields_by_source)

        output = self._parse_output(raw.data, parsed_fields.output_fields)
        observability = self._parse_observability(raw.data)
        guardrails = self._parse_guardrails(raw.data, parsed_fields.field_def_index)

        return DemandConfig(
            name=name,
            description=description,
            batch_size=batch_size,
            retry=retry,
            main_source=main_source,
            sources=sources,
            source_fields=parsed_fields.source_fields,
            derived_fields=parsed_fields.derived_fields,
            source_field_id_map=parsed_fields.source_field_id_map,
            relations=relations,
            guardrails=guardrails,
            output=output,
            observability=observability,
        )
