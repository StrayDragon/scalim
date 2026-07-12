# pragma: allow-c901-file plan: c60

from pathlib import Path
from typing import IO, Any, Dict, Mapping, Optional, Sequence, Union, cast

from ....._internal.loggingx import get_logger, prefix
from .....typedefs import FailurePolicy
from ...init_var_nodes import OptionalPathNode, parse_init_var_ref
from ...schema_dsl.constants import DEFAULT_BATCH_SIZE, UTF8_ENCODING
from ...schema_dsl.models import (
    BOOK_EXPORT_XLSX_KEYS,
    BOOK_KEYS,
    BOOK_XLSX_FILE_KEYS,
    BOOK_XLSX_MEMORY_KEYS,
    DEMAND_KEYS,
    FILE_CSV_FILE_KEYS,
    FILE_KEYS,
    RESOURCES_KEYS,
    BookConfig,
    BookExportXlsxConfig,
    DemandConfig,
    FileConfig,
    ResourcesConfig,
)
from .error_envelope import ErrorEnvelope, ScalimYamlValidationError
from .imports import ScalimYamlImportExpansionError, contains_import_syntax, expand_imports_inplace
from .models import RawDemand
from .parsers.fields import ParserFieldsMixin
from .parsers.outputs import ParserOutputsMixin
from .parsers.utils import mapping_or_none
from .template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN, maybe_precompile_yaml_text
from .validator import ConfigValidator
from .yaml_load import envelope_from_validation_issue, error_loc_for_yaml_path, load_yaml_mapping_text

__all__ = ()

_LOADER_LOGGER = get_logger("yaml_dsl")


def _create_validator() -> ConfigValidator:
    return ConfigValidator()


class YamlDemandLoader(
    ParserFieldsMixin,
    ParserOutputsMixin,
):
    _validator: Optional[ConfigValidator]

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
                    ) from exc
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
            if warnings:
                for item in warnings:
                    msg = "{}{}".format(prefix("yaml_dsl"), item.message)
                    if item.path and item.path != "(root)":
                        msg = "{} (path={})".format(msg, item.path)
                    _LOADER_LOGGER.warning(msg)

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
            if warnings:
                for item in warnings:
                    msg = "{}{}".format(prefix("yaml_dsl"), item.message)
                    if item.path and item.path != "(root)":
                        msg = "{} (path={})".format(msg, item.path)
                    _LOADER_LOGGER.warning(msg)

        return self._parse_config(raw_demand)

    def _ensure_validator(self) -> None:
        if self._validator is None:
            self._validator = _create_validator()

    def parse_raw_demand(self, raw: RawDemand) -> DemandConfig:
        """从已加载/已展开 `imports` 的 `RawDemand` 解析 `DemandConfig`.

        说明:
        - 该入口不会做 YAML 解析与 `imports` 展开;调用方需保证 `raw.data` 已满足相应约束.
        - 这是 `compiler_frontend` 等静态编译入口复用 `parser` 的公共入口,避免依赖私有 `_parse_config`.
        """

        return self._parse_config(raw)

    def _parse_config(self, raw: RawDemand) -> DemandConfig:
        name = str(raw.data.get(DEMAND_KEYS["name"], ""))
        description = str(raw.data.get(DEMAND_KEYS["description"], ""))

        removed_runtime_policy_keys = [
            key
            for key in (
                "include_full_error_message",
                "validate_unique_field_names",
            )
            if key in raw.data
        ]
        if removed_runtime_policy_keys:
            msg = "YAML key(s) {} were moved out of demand YAML mainline (runtime policy boundary). ".format(
                ", ".join(sorted(removed_runtime_policy_keys)),
            )
            msg = (
                msg
                + "Hint: configure demand diagnostics via runtime entrypoints: "
                + "scalim.dsl.yaml_dsl.run/compile(..., options=DemandRunOptions("
                + "runtime=DemandRunRuntimeOptions(demand_diagnostics=DemandDiagnosticsPolicy(...)), ...))."
            )
            raise ValueError(msg)

        batch_size = DEFAULT_BATCH_SIZE
        retry = None
        main_source = self._parse_main_source(raw)
        sources = self._parse_sources(raw)
        relations = self._parse_relations(raw)
        field_def_index = self._collect_field_defs(raw, main_source.source_id)
        resources = self._parse_resources(raw)
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

        validate_unique_field_names = True

        failure_policy = FailurePolicy.ALL_FAIL.value

        include_full_error_message = False
        meta = None
        audit = None
        guardrails = None

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
            outputs=outputs,
            validate_unique_field_names=validate_unique_field_names,
            failure_policy=failure_policy,
            include_full_error_message=include_full_error_message,
            meta=meta,
            audit=audit,
        )

    def _parse_resources(self, raw: RawDemand) -> Optional[ResourcesConfig]:  # noqa: C901, PLR0912
        resources_dict = raw.get_mapping(DEMAND_KEYS["resources"])
        if resources_dict is None:
            return None

        books: Dict[str, BookConfig] = {}
        books_dict = mapping_or_none(resources_dict.get(RESOURCES_KEYS["books"]))
        if books_dict is None:
            if RESOURCES_KEYS["books"] in resources_dict:
                msg = "resources.books must be an object"
                raise TypeError(msg)
        else:
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

        files: Dict[str, FileConfig] = {}
        files_dict = mapping_or_none(resources_dict.get(RESOURCES_KEYS["files"]))
        if files_dict is None:
            if RESOURCES_KEYS["files"] in resources_dict:
                msg = "resources.files must be an object"
                raise TypeError(msg)
        else:
            for raw_file_id, raw_file_cfg in files_dict.items():
                file_id = str(raw_file_id or "").strip()
                if not file_id:
                    msg = "resources.files key must be a non-empty string"
                    raise ValueError(msg)

                file_cfg_dict = mapping_or_none(raw_file_cfg)
                if file_cfg_dict is None:
                    msg = "resources.files.{} must be an object".format(file_id)
                    raise TypeError(msg)

                files[file_id] = self._parse_file_config(file_cfg_dict, base_path="resources.files.{}".format(file_id))

        return ResourcesConfig(books=books, files=files)

    def _parse_book_config(self, raw: Dict[str, Any], *, base_path: str) -> BookConfig:  # noqa: C901, PLR0912, PLR0915
        if "write_lock" in raw:
            msg = (
                "{}.write_lock was removed. "
                "Migration: set xlsx_file/xlsx_memory.export_xlsx path to an output root directory "
                "(e.g. './out'), and locate outputs via <root>/manifest/latest.json."
            ).format(base_path)
            raise ValueError(msg)

        if "kind" in raw:
            kind = str(raw.get("kind") or "").strip()
            if kind == "xlsx_file":
                msg = (
                    "{}.kind was removed. "
                    "Migration: use oneOf branch object: {}.xlsx_file: {{path: <output_root>, allow_formulas?: false}}."
                ).format(base_path, base_path)
            elif kind == "xlsx_memory":
                msg = ("{}.kind was removed. Migration: use oneOf branch object: {}.xlsx_memory: {{export_xlsx?: ...}}.").format(
                    base_path, base_path
                )
            else:
                msg = ("{}.kind was removed. Migration: use oneOf branch object: {}.xlsx_file: {{...}} or {}.xlsx_memory: {{...}}.").format(
                    base_path, base_path, base_path
                )
            raise ValueError(msg)

        if "write_defaults" in raw:
            msg = (
                "{}.write_defaults was removed from YAML authoring. "
                "Migration: configure BookWritePolicy via DemandRunOptions.resources_policy "
                "or WorkflowRunOptions.resources_policy (Python SSOT; omit for builtin defaults)."
            ).format(base_path)
            raise ValueError(msg)

        allowed_keys = {BOOK_KEYS["xlsx_file"], BOOK_KEYS["xlsx_memory"]}
        unknown = sorted({str(k) for k in raw} - allowed_keys)
        if unknown:
            msg = "{} has unknown keys: {}".format(base_path, ", ".join(unknown))
            raise ValueError(msg)

        file_branch = None
        if BOOK_KEYS["xlsx_file"] in raw:
            file_branch = mapping_or_none(raw.get(BOOK_KEYS["xlsx_file"]))
            if file_branch is None:
                msg = "{}.xlsx_file must be an object".format(base_path)
                raise TypeError(msg)

        mem_branch = None
        if BOOK_KEYS["xlsx_memory"] in raw:
            mem_branch = mapping_or_none(raw.get(BOOK_KEYS["xlsx_memory"]))
            if mem_branch is None:
                msg = "{}.xlsx_memory must be an object".format(base_path)
                raise TypeError(msg)

        has_file = file_branch is not None
        has_mem = mem_branch is not None
        if has_file == has_mem:
            msg = "{} must choose exactly one variant key: xlsx_file or xlsx_memory".format(base_path)
            raise ValueError(msg)

        if file_branch is not None:
            branch_path = "{}.xlsx_file".format(base_path)
            allowed_branch_keys = {BOOK_XLSX_FILE_KEYS["path"], BOOK_XLSX_FILE_KEYS["allow_formulas"]}
            unknown_branch = sorted({str(k) for k in file_branch} - allowed_branch_keys)
            if unknown_branch:
                if "write_lock" in unknown_branch:
                    msg = (
                        "{}.write_lock was removed. "
                        "Migration: set path to an output root directory and locate outputs via <root>/manifest/latest.json."
                    ).format(branch_path)
                    raise ValueError(msg)
                msg = "{} has unknown keys: {}".format(branch_path, ", ".join(unknown_branch))
                raise ValueError(msg)

            path = self._parse_path_or_init_var(
                file_branch.get(BOOK_XLSX_FILE_KEYS["path"]),
                path="{}.path".format(branch_path),
            )
            if not path or (isinstance(path, str) and not path.strip()):
                msg = "{}.path is required".format(branch_path)
                raise ValueError(msg)

            allow_formulas = bool(file_branch.get(BOOK_XLSX_FILE_KEYS["allow_formulas"], True))
            return BookConfig(
                kind="xlsx_file",
                path=path,
                budget=None,
                export_xlsx=None,
                allow_formulas=allow_formulas,
                write_defaults=None,
            )

        assert mem_branch is not None  # noqa: S101  # pragma: allow-no-cover invariant: has_mem checked above
        branch_path = "{}.xlsx_memory".format(base_path)
        if "budget" in mem_branch:
            msg = (
                "{}.budget was removed from YAML authoring. "
                "Migration: configure BookBudgetPolicy via DemandRunOptions.resources_policy "
                "or WorkflowRunOptions.resources_policy (Python SSOT; omit for unlimited)."
            ).format(branch_path)
            raise ValueError(msg)
        allowed_branch_keys = {BOOK_XLSX_MEMORY_KEYS["export_xlsx"]}
        unknown_branch = sorted({str(k) for k in mem_branch} - allowed_branch_keys)
        if unknown_branch:
            if "write_lock" in unknown_branch:
                msg = ("{}.write_lock was removed. Migration: locate outputs via <root>/manifest/latest.json.").format(branch_path)
                raise ValueError(msg)
            msg = "{} has unknown keys: {}".format(branch_path, ", ".join(unknown_branch))
            raise ValueError(msg)

        export_cfg = None
        export_raw = mapping_or_none(mem_branch.get(BOOK_XLSX_MEMORY_KEYS["export_xlsx"]))
        if export_raw is not None:
            export_cfg = self._parse_book_export_xlsx(export_raw, base_path="{}.export_xlsx".format(branch_path))

        return BookConfig(
            kind="xlsx_memory",
            path=None,
            budget=None,
            export_xlsx=export_cfg,
            allow_formulas=False,
            write_defaults=None,
        )

    def _parse_file_config(self, raw: Dict[str, Any], *, base_path: str) -> FileConfig:
        if "write_lock" in raw:
            msg = (
                "{}.write_lock was removed. "
                "Migration: set resources.files.<id>.csv_file.path to an output root directory "
                "(e.g. './out'), and locate outputs via <root>/manifest/latest.json."
            ).format(base_path)
            raise ValueError(msg)

        if "kind" in raw:
            kind = str(raw.get("kind") or "").strip()
            if kind == "csv_file":
                msg = (
                    "{}.kind was removed. Migration: use oneOf branch object: {}.csv_file: {{path: <output_root>, encoding?: utf-8}}."
                ).format(base_path, base_path)
            else:
                msg = ("{}.kind was removed. Migration: use oneOf branch object: {}.csv_file: {{...}}.").format(base_path, base_path)
            raise ValueError(msg)

        allowed_keys = {FILE_KEYS["csv_file"]}
        unknown = sorted({str(k) for k in raw} - allowed_keys)
        if unknown:
            msg = "{} has unknown keys: {}".format(base_path, ", ".join(unknown))
            raise ValueError(msg)

        if FILE_KEYS["csv_file"] not in raw:
            msg = "{}.csv_file is required".format(base_path)
            raise ValueError(msg)

        csv_branch = mapping_or_none(raw.get(FILE_KEYS["csv_file"]))
        if csv_branch is None:
            msg = "{}.csv_file must be an object".format(base_path)
            raise TypeError(msg)

        branch_path = "{}.csv_file".format(base_path)
        allowed_branch_keys = {FILE_CSV_FILE_KEYS["path"], FILE_CSV_FILE_KEYS["encoding"]}
        unknown_branch = sorted({str(k) for k in csv_branch} - allowed_branch_keys)
        if unknown_branch:
            if "write_lock" in unknown_branch:
                msg = ("{}.write_lock was removed; migrate to versioned outputs and locate results via <root>/manifest/latest.json").format(
                    branch_path
                )
                raise ValueError(msg)
            msg = "{} has unknown keys: {}".format(branch_path, ", ".join(unknown_branch))
            raise ValueError(msg)

        path = self._parse_path_or_init_var(csv_branch.get(FILE_CSV_FILE_KEYS["path"]), path="{}.path".format(branch_path))
        if not path or (isinstance(path, str) and not path.strip()):
            msg = "{}.path is required".format(branch_path)
            raise ValueError(msg)

        encoding = str(csv_branch.get(FILE_CSV_FILE_KEYS["encoding"]) or "").strip() or UTF8_ENCODING
        return FileConfig(kind="csv_file", path=path, encoding=encoding)

    def _parse_path_or_init_var(self, raw: object, *, path: str) -> OptionalPathNode:
        if isinstance(raw, dict):
            return parse_init_var_ref(
                cast("Dict[str, Any]", raw),  # pragma: allow-cast init_var mapping typed narrowing
                path=path,
            )
        if raw is None:
            return None
        if isinstance(raw, str):
            return raw.strip()
        msg = "{} must be a non-empty string or {{$init_var: <name>}}".format(path)
        raise TypeError(msg)

    def _parse_book_export_xlsx(self, raw: Dict[str, Any], *, base_path: str) -> BookExportXlsxConfig:
        export_path = self._parse_path_or_init_var(raw.get(BOOK_EXPORT_XLSX_KEYS["path"]), path="{}.path".format(base_path))
        if not export_path or (isinstance(export_path, str) and not export_path.strip()):
            msg = "{}.path is required".format(base_path)
            raise ValueError(msg)
        allow_formulas = bool(raw.get(BOOK_EXPORT_XLSX_KEYS["allow_formulas"], True))
        return BookExportXlsxConfig(path=export_path, allow_formulas=allow_formulas)
