from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Dict, Mapping, Optional, Sequence, Union, cast

if TYPE_CHECKING:
    from .validator import ConfigValidator

from ..init_var_nodes import parse_init_var_mapping_node
from ..schema_dsl.constants import DEFAULT_BATCH_SIZE, UTF8_ENCODING
from ..schema_dsl.models import (
    BOOK_BUDGET_KEYS,
    BOOK_EXPORT_XLSX_KEYS,
    BOOK_KEYS,
    BOOK_WRITE_DEFAULTS_KEYS,
    DEMAND_KEYS,
    OUTPUT_EXTRA_SHEET_KEYS,
    OUTPUTS_DEFAULTS_KEYS,
    OUTPUTS_DEFAULTS_TO_KEYS,
    RESOURCES_KEYS,
    BookBudgetConfig,
    BookConfig,
    BookExportXlsxConfig,
    BookWriteDefaultsConfig,
    DemandConfig,
    OutputExtraSheetConfig,
    OutputsDefaultsConfig,
    OutputsDefaultsToConfig,
    ResourcesConfig,
)
from ..schema_dsl.output_enums import (
    BOOK_KINDS,
    BOOK_WRITE_ALIGN_BY_ENUM,
    BOOK_WRITE_HEADER_POLICY_ENUM,
    BOOK_WRITE_MODE_ENUM,
    BOOK_WRITE_ON_CONFLICT_ENUM,
    BOOK_WRITE_ON_MISMATCH_ENUM,
    DEFAULT_BOOK_WRITE_ALIGN_BY,
    DEFAULT_BOOK_WRITE_HEADER_POLICY,
    DEFAULT_BOOK_WRITE_MODE,
    DEFAULT_BOOK_WRITE_ON_CONFLICT,
    DEFAULT_BOOK_WRITE_ON_MISMATCH,
)
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
        resources = self._parse_resources(raw)
        outputs_defaults = self._parse_outputs_defaults(raw)
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
            resources=resources,
            outputs_defaults=outputs_defaults,
            outputs=outputs,
            validate_unique_field_names=validate_unique_field_names,
            failure_policy=failure_policy,
            include_full_error_message=include_full_error_message,
            meta=meta,
            audit=audit,
            observability=observability,
        )

    def _parse_outputs_defaults(self, raw: RawDemand) -> Optional[OutputsDefaultsConfig]:
        defaults_dict = raw.get_mapping(DEMAND_KEYS["outputs_defaults"])
        if defaults_dict is None:
            return None

        to_dict = mapping_or_none(defaults_dict.get(OUTPUTS_DEFAULTS_KEYS["to"]))
        if to_dict is None:
            msg = "outputs_defaults.to must be an object"
            raise TypeError(msg)

        book_id = str(to_dict.get(OUTPUTS_DEFAULTS_TO_KEYS["book"]) or "").strip()
        if not book_id:
            msg = "outputs_defaults.to.book is required"
            raise ValueError(msg)

        return OutputsDefaultsConfig(to=OutputsDefaultsToConfig(book=book_id))

    def _parse_resources(self, raw: RawDemand) -> Optional[ResourcesConfig]:
        resources_dict = raw.get_mapping(DEMAND_KEYS["resources"])
        if resources_dict is None:
            return None

        books_dict = mapping_or_none(resources_dict.get(RESOURCES_KEYS["books"]))
        if books_dict is None:
            # `resources: {}` 允许(空映射).
            if RESOURCES_KEYS["books"] not in resources_dict:
                return ResourcesConfig()
            msg = "resources.books must be an object"
            raise TypeError(msg)

        books: Dict[str, BookConfig] = {}
        for raw_book_id, raw_book_cfg in books_dict.items():
            book_id = str(raw_book_id or "").strip()
            if not book_id:
                msg = "resources.books key must be a non-empty string"
                raise ValueError(msg)

            book_cfg_dict = mapping_or_none(raw_book_cfg)
            if book_cfg_dict is None:
                msg = "resources.books.{} must be an object".format(book_id)
                raise TypeError(msg)

            books[book_id] = self._parse_book_config(book_cfg_dict, base_path="resources.books.{}".format(book_id))

        return ResourcesConfig(books=books)

    def _parse_book_config(self, raw: Dict[str, Any], *, base_path: str) -> BookConfig:  # noqa: C901
        kind = str(raw.get(BOOK_KEYS["kind"]) or "").strip()
        if not kind:
            msg = "{}.kind is required".format(base_path)
            raise ValueError(msg)
        if kind not in BOOK_KINDS:
            msg = "{}.kind={!r} is invalid; expected one of: {}".format(base_path, kind, ", ".join(BOOK_KINDS))
            raise ValueError(msg)

        path = self._parse_path_or_init_var(raw.get(BOOK_KEYS["path"]), path="{}.path".format(base_path))

        budget_cfg = None
        budget_raw = mapping_or_none(raw.get(BOOK_KEYS["budget"]))
        if budget_raw is not None:
            budget_cfg = self._parse_book_budget(budget_raw, base_path="{}.budget".format(base_path))

        export_cfg = None
        export_raw = mapping_or_none(raw.get(BOOK_KEYS["export_xlsx"]))
        if export_raw is not None:
            export_cfg = self._parse_book_export_xlsx(export_raw, base_path="{}.export_xlsx".format(base_path))

        allow_formulas = bool(raw.get(BOOK_KEYS["allow_formulas"], False))
        write_lock = bool(raw.get(BOOK_KEYS["write_lock"], False))

        write_defaults_cfg = None
        write_defaults_raw = mapping_or_none(raw.get(BOOK_KEYS["write_defaults"]))
        if write_defaults_raw is not None:
            write_defaults_cfg = self._parse_book_write_defaults(write_defaults_raw, base_path="{}.write_defaults".format(base_path))

        # 语义层防御性校验(即使 `schema` 已覆盖,仍保持 `fail-fast` 便于诊断).
        if kind == "xlsx_file":
            if not path or (isinstance(path, str) and not path.strip()):
                msg = "{}.path is required for kind=xlsx_file".format(base_path)
                raise ValueError(msg)
            if budget_cfg is not None:
                msg = "{}.budget is not allowed for kind=xlsx_file".format(base_path)
                raise ValueError(msg)
            if export_cfg is not None:
                msg = "{}.export_xlsx is not allowed for kind=xlsx_file".format(base_path)
                raise ValueError(msg)
        if kind == "xlsx_memory":
            if budget_cfg is None:
                msg = "{}.budget is required for kind=xlsx_memory".format(base_path)
                raise ValueError(msg)
            if path is not None:
                msg = "{}.path is not allowed for kind=xlsx_memory".format(base_path)
                raise ValueError(msg)

        return BookConfig(
            kind=kind,
            path=path,
            budget=budget_cfg,
            export_xlsx=export_cfg,
            allow_formulas=allow_formulas,
            write_lock=write_lock,
            write_defaults=write_defaults_cfg,
        )

    def _parse_path_or_init_var(self, raw: object, *, path: str) -> Any:
        if isinstance(raw, dict):
            return {
                "$init_var": parse_init_var_mapping_node(
                    cast("Dict[str, Any]", raw),  # pragma: allow-cast init_var mapping typed narrowing
                    path=path,
                )
            }
        if raw is None:
            return None
        if isinstance(raw, str):
            return raw.strip()
        msg = "{} must be a non-empty string or {{$init_var: <name>}}".format(path)
        raise TypeError(msg)

    def _parse_book_budget(self, raw: Dict[str, Any], *, base_path: str) -> BookBudgetConfig:
        max_sheets_raw = raw.get(BOOK_BUDGET_KEYS["max_sheets"])
        max_total_cells_raw = raw.get(BOOK_BUDGET_KEYS["max_total_cells"])
        if max_sheets_raw is None:
            msg = "{}.max_sheets must be an integer".format(base_path)
            raise TypeError(msg)
        if max_total_cells_raw is None:
            msg = "{}.max_total_cells must be an integer".format(base_path)
            raise TypeError(msg)
        try:
            max_sheets = int(max_sheets_raw)
        except (TypeError, ValueError):
            msg = "{}.max_sheets must be an integer".format(base_path)
            raise TypeError(msg) from None
        try:
            max_total_cells = int(max_total_cells_raw)
        except (TypeError, ValueError):
            msg = "{}.max_total_cells must be an integer".format(base_path)
            raise TypeError(msg) from None
        if max_sheets < 1:
            msg = "{}.max_sheets must be >= 1".format(base_path)
            raise ValueError(msg)
        if max_total_cells < 1:
            msg = "{}.max_total_cells must be >= 1".format(base_path)
            raise ValueError(msg)
        return BookBudgetConfig(max_sheets=max_sheets, max_total_cells=max_total_cells)

    def _parse_book_export_xlsx(self, raw: Dict[str, Any], *, base_path: str) -> BookExportXlsxConfig:
        export_path = self._parse_path_or_init_var(raw.get(BOOK_EXPORT_XLSX_KEYS["path"]), path="{}.path".format(base_path))
        if not export_path or (isinstance(export_path, str) and not export_path.strip()):
            msg = "{}.path is required".format(base_path)
            raise ValueError(msg)
        write_lock = bool(raw.get(BOOK_EXPORT_XLSX_KEYS["write_lock"], False))
        allow_formulas = bool(raw.get(BOOK_EXPORT_XLSX_KEYS["allow_formulas"], False))
        return BookExportXlsxConfig(path=export_path, write_lock=write_lock, allow_formulas=allow_formulas)

    def _parse_book_write_defaults(self, raw: Dict[str, Any], *, base_path: str) -> BookWriteDefaultsConfig:
        mode = str(raw.get(BOOK_WRITE_DEFAULTS_KEYS["mode"]) or DEFAULT_BOOK_WRITE_MODE).strip() or DEFAULT_BOOK_WRITE_MODE
        if mode not in BOOK_WRITE_MODE_ENUM:
            msg = "{}.mode={!r} is invalid; expected one of: {}".format(base_path, mode, ", ".join(BOOK_WRITE_MODE_ENUM))
            raise ValueError(msg)

        align_by = str(raw.get(BOOK_WRITE_DEFAULTS_KEYS["align_by"]) or DEFAULT_BOOK_WRITE_ALIGN_BY).strip() or DEFAULT_BOOK_WRITE_ALIGN_BY
        if align_by not in BOOK_WRITE_ALIGN_BY_ENUM:
            msg = "{}.align_by={!r} is invalid; expected one of: {}".format(base_path, align_by, ", ".join(BOOK_WRITE_ALIGN_BY_ENUM))
            raise ValueError(msg)

        header_policy = (
            str(raw.get(BOOK_WRITE_DEFAULTS_KEYS["header_policy"]) or DEFAULT_BOOK_WRITE_HEADER_POLICY).strip()
            or DEFAULT_BOOK_WRITE_HEADER_POLICY
        )
        if header_policy not in BOOK_WRITE_HEADER_POLICY_ENUM:
            msg = "{}.header_policy={!r} is invalid; expected one of: {}".format(
                base_path, header_policy, ", ".join(BOOK_WRITE_HEADER_POLICY_ENUM)
            )
            raise ValueError(msg)

        on_mismatch = (
            str(raw.get(BOOK_WRITE_DEFAULTS_KEYS["on_mismatch"]) or DEFAULT_BOOK_WRITE_ON_MISMATCH).strip()
            or DEFAULT_BOOK_WRITE_ON_MISMATCH
        )
        if on_mismatch not in BOOK_WRITE_ON_MISMATCH_ENUM:
            msg = "{}.on_mismatch={!r} is invalid; expected one of: {}".format(
                base_path, on_mismatch, ", ".join(BOOK_WRITE_ON_MISMATCH_ENUM)
            )
            raise ValueError(msg)

        on_conflict = (
            str(raw.get(BOOK_WRITE_DEFAULTS_KEYS["on_conflict"]) or DEFAULT_BOOK_WRITE_ON_CONFLICT).strip()
            or DEFAULT_BOOK_WRITE_ON_CONFLICT
        )
        if on_conflict not in BOOK_WRITE_ON_CONFLICT_ENUM:
            msg = "{}.on_conflict={!r} is invalid; expected one of: {}".format(
                base_path, on_conflict, ", ".join(BOOK_WRITE_ON_CONFLICT_ENUM)
            )
            raise ValueError(msg)

        return BookWriteDefaultsConfig(
            mode=mode,
            align_by=align_by,
            header_policy=header_policy,
            on_mismatch=on_mismatch,
            on_conflict=on_conflict,
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
