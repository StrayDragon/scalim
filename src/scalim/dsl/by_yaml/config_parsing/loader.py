from pathlib import Path
from typing import IO, TYPE_CHECKING, Mapping, Optional, Sequence, Union

from ....vendor.compact.importlibx import require_optional_dependency

if TYPE_CHECKING:
    from .validator import ConfigValidator
else:
    # 说明: 在模块导入时显式检查可选依赖,当缺少 `pyyaml` 时让导入/重载快速失败并给出友好提示.
    require_optional_dependency(
        "yaml",
        context="scalim.dsl.by_yaml.config_parsing.loader",
        install_name="pyyaml",
    )

from ..schema_dsl.constants import DEFAULT_BATCH_SIZE, UTF8_ENCODING
from ..schema_dsl.models import DEMAND_KEYS, OUTPUT_EXTRA_SHEET_KEYS, DemandConfig, OutputExtraSheetConfig
from .error_envelope import ErrorEnvelope, ScalimYamlValidationError
from .imports import ScalimYamlImportExpansionError, contains_import_syntax, expand_imports_inplace
from .models import RawDemand
from .parsers.fields import ParserFieldsMixin
from .parsers.guardrails import ParserGuardrailsMixin
from .parsers.output import ParserOutputMixin
from .parsers.outputs import ParserOutputsMixin
from .parsers.results import ParsedFieldsResult
from .parsers.utils import mapping_or_none, str_or_none
from .template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN, maybe_precompile_yaml_text
from .yaml_load import envelope_from_validation_issue, error_loc_for_yaml_path, load_yaml_mapping_text

__all__ = [
    "ParsedFieldsResult",
    "YamlDemandLoader",
]


def _create_validator() -> "ConfigValidator":
    from .validator import ConfigValidator  # noqa: PLC0415

    return ConfigValidator()


class YamlDemandLoader(
    ParserFieldsMixin,
    ParserOutputsMixin,
    ParserOutputMixin,
    ParserGuardrailsMixin,
):
    _validator: Optional["ConfigValidator"]

    def __init__(self) -> None:
        self._validator = None

    def load(
        self,
        source: Union[str, Path, IO[str]],
        *,
        template_vars: Optional[Mapping[str, object]] = None,
        template_sandbox: str = "safe",
        rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
        allowed_yaml_roots: Optional[Sequence[Union[str, Path]]] = None,
        scalim_yaml_override: Optional[Union[str, Path]] = None,
        project_root_override: Optional[Union[str, Path]] = None,
    ) -> DemandConfig:
        yaml_path: Optional[Path] = None
        if isinstance(source, (str, Path)):
            yaml_path = Path(source)
            text = yaml_path.read_text(encoding=UTF8_ENCODING)
            text = maybe_precompile_yaml_text(
                text,
                template_vars=template_vars,
                context_label="需求 `YAML` 文件 `{}`".format(str(yaml_path)),
                context_kind="demand",
                template_sandbox=template_sandbox,
                rendered_yaml_max_len=rendered_yaml_max_len,
            )
            data, locations, _lines = load_yaml_mapping_text(
                text,
                source_path=str(yaml_path),
                detect_duplicate_keys=True,
            )
        else:
            text = source.read()
            text = maybe_precompile_yaml_text(
                text,
                template_vars=template_vars,
                context_label="需求 `YAML` 文本",
                context_kind="demand",
                template_sandbox=template_sandbox,
                rendered_yaml_max_len=rendered_yaml_max_len,
            )
            data, locations, _lines = load_yaml_mapping_text(
                text,
                source_path="(inline)",
                detect_duplicate_keys=True,
            )
        raw_demand = RawDemand.from_raw(data)

        if contains_import_syntax(raw_demand.data):
            if yaml_path is not None:
                try:
                    _ = expand_imports_inplace(
                        raw_demand.data,
                        yaml_path=yaml_path,
                        template_vars=template_vars,
                        template_sandbox=template_sandbox,
                        rendered_yaml_max_len=rendered_yaml_max_len,
                        allowed_yaml_roots=allowed_yaml_roots,
                        scalim_yaml_override=scalim_yaml_override,
                        project_root_override=project_root_override,
                    )
                except ScalimYamlImportExpansionError as exc:
                    logical_path = str(exc.logical_path or "(root)")
                    error_message = "YAML imports expansion failed"
                    raise ScalimYamlValidationError(
                        error_message,
                        errors=[
                            ErrorEnvelope(
                                code="yaml_import_expansion_error",
                                message=str(exc),
                                source_path=str(yaml_path),
                                path=logical_path,
                                loc=error_loc_for_yaml_path(logical_path, locations),
                            )
                        ],
                    ) from None
            else:
                msg = "imports/$import is only supported for file path entrypoints; use YamlDemandLoader.load(<yaml_path>)"
                error_message = "YAML imports expansion is not supported for inline YAML"
                raise ScalimYamlValidationError(
                    error_message,
                    errors=[
                        ErrorEnvelope(
                            code="yaml_import_unsupported",
                            message=msg,
                            source_path="(inline)",
                            path="(root)",
                            loc=error_loc_for_yaml_path("(root)", locations),
                        )
                    ],
                )

        self._ensure_validator()
        if self._validator:
            report = self._validator.validate_report(
                raw_demand.data,
                strict_unknown_fields=True,
                enable_jsonschema_validation=True,
            )
            errors = [
                envelope_from_validation_issue(
                    issue,
                    source_path=str(yaml_path) if yaml_path is not None else "(inline)",
                    locations=locations,
                    default_code="yaml_validate_error",
                )
                for issue in report.errors()
            ]
            warnings = [
                envelope_from_validation_issue(
                    issue,
                    source_path=str(yaml_path) if yaml_path is not None else "(inline)",
                    locations=locations,
                    default_code="yaml_validate_warning",
                )
                for issue in report.warnings()
            ]
            if errors:
                error_message = "YAML DSL validation failed"
                raise ScalimYamlValidationError(
                    error_message,
                    errors=errors,
                    warnings=warnings,
                )

        return self._parse_config(raw_demand)

    def load_string(
        self,
        yaml_string: str,
        *,
        template_vars: Optional[Mapping[str, object]] = None,
        template_sandbox: str = "safe",
        rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    ) -> DemandConfig:
        text = maybe_precompile_yaml_text(
            yaml_string,
            template_vars=template_vars,
            context_label="需求 `YAML` 字符串",
            context_kind="demand",
            template_sandbox=template_sandbox,
            rendered_yaml_max_len=rendered_yaml_max_len,
        )
        data, locations, _lines = load_yaml_mapping_text(
            text,
            source_path="(inline)",
            detect_duplicate_keys=True,
        )
        raw_demand = RawDemand.from_raw(data)

        if contains_import_syntax(raw_demand.data):
            msg = "imports/$import is only supported for file path entrypoints; use YamlDemandLoader.load(<yaml_path>)"
            error_message = "YAML imports expansion is not supported for inline YAML"
            raise ScalimYamlValidationError(
                error_message,
                errors=[
                    ErrorEnvelope(
                        code="yaml_import_unsupported",
                        message=msg,
                        source_path="(inline)",
                        path="(root)",
                        loc=error_loc_for_yaml_path("(root)", locations),
                    )
                ],
            )

        self._ensure_validator()
        if self._validator:
            report = self._validator.validate_report(
                raw_demand.data,
                strict_unknown_fields=True,
                enable_jsonschema_validation=True,
            )
            errors = [
                envelope_from_validation_issue(
                    issue,
                    source_path="(inline)",
                    locations=locations,
                    default_code="yaml_validate_error",
                )
                for issue in report.errors()
            ]
            warnings = [
                envelope_from_validation_issue(
                    issue,
                    source_path="(inline)",
                    locations=locations,
                    default_code="yaml_validate_warning",
                )
                for issue in report.warnings()
            ]
            if errors:
                error_message = "YAML DSL validation failed"
                raise ScalimYamlValidationError(
                    error_message,
                    errors=errors,
                    warnings=warnings,
                )

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
        field_def_index = self._collect_field_defs(raw, main_source.source_id)
        outputs, required_field_ids = self._parse_outputs(raw, field_def_index=field_def_index)

        parsed_fields = self._parse_fields(
            raw,
            main_source.source_id,
            required_field_ids,
            relations,
            field_def_index=field_def_index,
        )
        main_source = self._with_main_source_fields(main_source, parsed_fields.main_source_fields)
        sources = self._with_source_fields(sources, parsed_fields.source_fields_by_source)

        validate_unique_raw = raw.data.get(DEMAND_KEYS["validate_unique_field_names"])
        if validate_unique_raw is None:
            validate_unique_field_names = True
        elif isinstance(validate_unique_raw, bool):
            validate_unique_field_names = bool(validate_unique_raw)
        else:
            msg = "validate_unique_field_names must be a boolean"
            raise TypeError(msg)

        failure_policy = str(raw.data.get(DEMAND_KEYS["failure_policy"], "all_fail") or "all_fail")
        if failure_policy not in ("all_fail", "primary_only"):
            msg = "failure_policy must be 'all_fail' or 'primary_only'"
            raise ValueError(msg)

        include_full_error_message = bool(raw.data.get(DEMAND_KEYS["include_full_error_message"], False))
        meta = self._parse_extra_sheet(raw.data.get(DEMAND_KEYS["meta"]), key="meta")
        audit = self._parse_extra_sheet(raw.data.get(DEMAND_KEYS["audit"]), key="audit")

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
            outputs=outputs,
            validate_unique_field_names=validate_unique_field_names,
            failure_policy=failure_policy,
            include_full_error_message=include_full_error_message,
            meta=meta,
            audit=audit,
            observability=observability,
        )

    def _parse_extra_sheet(self, raw_value: object, *, key: str) -> Optional[OutputExtraSheetConfig]:
        if raw_value is None or raw_value is False:
            return None
        if raw_value is True:
            return OutputExtraSheetConfig()

        sheet_dict = mapping_or_none(raw_value)
        if sheet_dict is None:
            msg = "{} must be a boolean or an object".format(key)
            raise TypeError(msg)

        return OutputExtraSheetConfig(
            path=str_or_none(sheet_dict.get(OUTPUT_EXTRA_SHEET_KEYS["path"])),
            sheet=str_or_none(sheet_dict.get(OUTPUT_EXTRA_SHEET_KEYS["sheet"])),
            allow_formulas=sheet_dict.get(OUTPUT_EXTRA_SHEET_KEYS["allow_formulas"]),
            write_lock=sheet_dict.get(OUTPUT_EXTRA_SHEET_KEYS["write_lock"]),
        )
