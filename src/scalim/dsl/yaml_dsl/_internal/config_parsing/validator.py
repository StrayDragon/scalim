# pragma: allow-cast-file yaml validation boundary typed narrowing
# pragma: allow-c901-file plan: c60
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from typing import TypeGuard
from dataclasses import field as dataclass_field

from ...init_var_nodes import ScalimInitVarNodeTypeError, ScalimInitVarNodeValueError, parse_init_var_mapping_node
from ...schema_dsl.models import (
    BOOK_KEYS,
    BOOK_XLSX_KEYS,
    DEMAND_KEYS,
    FILE_CSV_FILE_KEYS,
    FILE_KEYS,
    OUTPUT_TARGET_KEYS,
    RESOURCES_KEYS,
)
from .book_branch_parse import removed_xlsx_file_message, removed_xlsx_memory_message
from .error_envelope import ScalimYamlValidationError
from .errors import ScalimConfigValidationError
from .imports import contains_import_syntax
from .models import FieldDefIndex, RawDemand, collect_field_defs, ensure_mapping
from .security import SecureComputeEngine, build_compute_engine
from .validator_migrations import ValidatorMigrationsMixin
from .validator_unknown_fields import ValidatorUnknownFieldsMixin
from .validators.fields import ValidatorFieldsMixin
from .validators.issues import (
    MAX_VALIDATION_ERROR_LINES,
    ValidationIssue,
    ValidationReport,
)
from .yaml_load import (
    YamlLocationIndex,
    load_yaml_mapping_text,
    lookup_yaml_location,
    normalize_yaml_diagnostic_path,
)

__all__ = ()


def _is_list(value: Any) -> "TypeGuard[list[Any]]":
    return isinstance(value, list)


def _is_dict(value: Any) -> "TypeGuard[dict[Any, Any]]":
    return isinstance(value, dict)


class ConfigValidator(ValidatorMigrationsMixin, ValidatorUnknownFieldsMixin, ValidatorFieldsMixin):
    _schema_path: str
    _schema: dict[str, Any] | None
    _compute_engine: SecureComputeEngine | None
    _step_allowed_fields_by_source: dict[str, set[str]]
    _max_validation_error_lines: int

    def __init__(
        self,
        schema_path: str | None = None,
        max_validation_error_lines: int | None = None,
    ) -> None:
        super().__init__()
        if schema_path is None:
            schema_path = str(Path(__file__).parent.parent.parent / "schema" / "demand.gen.json")
        self._schema_path = schema_path
        self._schema = None
        self._compute_engine = build_compute_engine()
        self._step_allowed_fields_by_source = {}
        self._max_validation_error_lines = int(
            max_validation_error_lines if max_validation_error_lines is not None else MAX_VALIDATION_ERROR_LINES
        )
        if self._max_validation_error_lines < 1:
            msg = "max_validation_error_lines must be >= 1"
            raise ValueError(msg)

    def validate(self, config: dict[str, Any]) -> None:
        report = self.validate_report(config, strict_unknown_fields=True)
        issues = report.errors()
        if not issues:
            return

        errors: list[str] = []
        for issue in issues[: self._max_validation_error_lines]:
            if issue.path:
                errors.append(f"{issue.path}: {issue.message}")
            else:
                errors.append(issue.message)

        msg = f"Configuration validation failed with {len(issues)} error(s)"
        if len(issues) > self._max_validation_error_lines:
            msg = f"{msg} (showing first {self._max_validation_error_lines} errors)"
        raise ScalimConfigValidationError(msg, errors=errors, issues=report.issues)

    def validate_report(
        self,
        config: dict[str, Any],
        *,
        strict_unknown_fields: bool = False,
    ) -> ValidationReport:
        errors: list[ValidationIssue] = []
        config = self._error_and_strip_legacy_observability(config, errors)
        config = self._error_and_strip_removed_demand_runtime_policy_fields(config, errors)
        config = self._error_and_strip_removed_output_extras_fields(config, errors)
        config = self._error_and_strip_removed_output_write_workbook_fields(config, errors)
        config = self._error_and_strip_removed_resources_write_lock_fields(config, errors)
        config = self._error_and_strip_removed_resources_write_budget_fields(config, errors)
        raw = RawDemand.from_raw(config)

        self._validate_required_fields(raw.data, errors)
        self._validate_legacy_fields(raw.data, errors)

        sources_info = self._validate_sources(raw.data, errors)
        main_source_id = self._validate_main_source(raw.data, errors)
        self._step_allowed_fields_by_source = self._collect_step_allowed_fields(raw.data, main_source_id)
        relation_paths = self._validate_relations(raw.data, errors, sources_info, main_source_id)
        self._validate_fields(raw, errors, sources_info, main_source_id, relation_paths)
        self._validate_outputs_shape(raw.data, errors)
        self._validate_outputs_fields_object_refs(raw, errors, main_source_id=main_source_id)
        self._validate_outputs_detail_requires_fields_or_from(raw.data, errors)
        self._validate_removed_output_container(raw.data, errors)
        self._validate_resource_output_paths(raw.data, errors)

        self._validate_unknown_fields(raw.data, errors, strict=strict_unknown_fields)

        return ValidationReport(issues=errors)

    def _validate_outputs_shape(self, config: dict[str, Any], errors: list[ValidationIssue]) -> None:
        outputs_key = DEMAND_KEYS["outputs"]
        outputs_raw = config.get(outputs_key)
        if outputs_raw is None:
            return
        if not isinstance(outputs_raw, list):
            self._add_error(errors, f"'{outputs_key}' must be a list", path=str(outputs_key))
            return

        outputs_list = cast("list[Any]", outputs_raw)  # pragma: allow-cast yaml list typed narrowing
        for idx, item in enumerate(outputs_list):
            if isinstance(item, dict):
                continue
            self._add_error(errors, f"outputs.{int(idx)} must be a dictionary", path=f"outputs.{int(idx)}")

    def _validate_outputs_detail_requires_fields_or_from(self, config: dict[str, Any], errors: list[ValidationIssue]) -> None:
        outputs_raw: Any = config.get(DEMAND_KEYS["outputs"])
        if not _is_list(outputs_raw):
            return
        outputs = outputs_raw

        fields_key = OUTPUT_TARGET_KEYS["fields"]
        from_key = OUTPUT_TARGET_KEYS["from_"]
        aggregate_key = OUTPUT_TARGET_KEYS["aggregate"]
        name_key = OUTPUT_TARGET_KEYS["name"]

        for idx, item in enumerate(outputs):
            if not isinstance(item, dict):
                continue
            out_dict = cast("dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing

            if "$import" in out_dict and set(out_dict.keys()) == {"$import"}:
                continue

            if out_dict.get(aggregate_key) is not None:
                continue

            fields_raw = out_dict.get(fields_key)
            from_raw = out_dict.get(from_key)
            has_fields = isinstance(fields_raw, list) and bool(cast("list[Any]", fields_raw))
            has_from = isinstance(from_raw, str) and bool(from_raw.strip())
            if has_fields or has_from:
                continue

            name_raw = out_dict.get(name_key)
            output_name = name_raw.strip() if isinstance(name_raw, str) else ""
            label = output_name or str(int(idx))
            msg = f"outputs.{label} requires fields for detail output (or set from to inherit fields)"
            self._add_error(errors, msg, path=f"outputs.{int(idx)}.{fields_key}")

    def _validate_removed_output_container(self, config: dict[str, Any], errors: list[ValidationIssue]) -> None:
        outputs_raw = config.get(DEMAND_KEYS["outputs"])
        if not _is_list(outputs_raw):
            return
        for idx, item in enumerate(outputs_raw):
            if not isinstance(item, dict):
                continue
            out_dict = cast("dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing
            if "container" not in out_dict:
                continue
            msg = (
                f"outputs.{int(idx)}.container was removed; migrate CSV outputs to resources.files "
                f"+ outputs[*].to.file + outputs[*].write, "
                "and .xlsx outputs to resources.books + outputs[*].to.book / outputs[*].to.sheet + outputs[*].write"
            )
            self._add_error(errors, msg, path=f"outputs.{int(idx)}.container")

    def _build_aggregate_field_index(self, aggregate: dict[str, Any]) -> tuple[dict[int, str], list[tuple[str, dict[str, Any]]]]:
        fields_raw: Any = aggregate.get("fields")
        if not _is_dict(fields_raw):
            return {}, []
        fields_dict = fields_raw

        alias_index: dict[int, str] = {}
        field_defs: list[tuple[str, dict[str, Any]]] = []
        for out_field_id_raw, field_raw in fields_dict.items():
            out_field_id = str(out_field_id_raw or "").strip()
            if not out_field_id:
                continue
            if not isinstance(field_raw, dict):
                continue
            field_dict = cast("dict[str, Any]", field_raw)  # pragma: allow-cast yaml mapping typed narrowing
            alias_index[id(field_dict)] = out_field_id
            field_defs.append((out_field_id, field_dict))
        return alias_index, field_defs

    def _outputs_fields_object_item_error(
        self,
        field_def_index: FieldDefIndex,
        item: Any,
        *,
        agg_field_index: tuple[dict[int, str], list[tuple[str, dict[str, Any]]]] | None = None,
    ) -> str | None:
        if not isinstance(item, dict):
            return "must be field_id string, YAML alias(object), or YAML alias(list)"

        typed = cast("dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing
        if agg_field_index is not None:
            alias_index, _ = agg_field_index
            if alias_index.get(id(typed)) is not None:
                return None

        direct = field_def_index.alias_index.get(typed)
        if direct is not None:
            return None

        matches: list[str] = []
        if agg_field_index is not None:
            _, field_defs = agg_field_index
            matches.extend([out_field_id for out_field_id, data in field_defs if data == typed])
        matches.extend([fd.field_id for fd in field_def_index.field_defs if fd.data == typed])

        if not matches:
            return "cannot resolve object to a unique field_id; prefer string field_id"

        unique = sorted(set(matches))
        if len(unique) > 1:
            return "ambiguous object entry; matches multiple id values: {}. Use string field_id to disambiguate.".format(", ".join(unique))
        return None

    def _validate_outputs_fields_list_object_refs(
        self,
        fields_list: list[Any],
        errors: list[ValidationIssue],
        *,
        base_path: str,
        field_def_index: FieldDefIndex,
        agg_field_index: tuple[dict[int, str], list[tuple[str, dict[str, Any]]]] | None = None,
    ) -> None:
        def _walk(item: Any, *, path: str) -> list[tuple[str, Any]]:
            if _is_list(item):
                out: list[tuple[str, Any]] = []
                for idx, sub in enumerate(item):
                    out.extend(_walk(sub, path=f"{path}.{idx}"))
                return out
            return [(path, item)]

        for field_idx, item in enumerate(fields_list):
            root_path = f"{base_path}.{field_idx}"
            for leaf_path, leaf in _walk(item, path=root_path):
                if isinstance(leaf, str):
                    continue
                msg = self._outputs_fields_object_item_error(field_def_index, leaf, agg_field_index=agg_field_index)
                if msg:
                    self._add_error(errors, msg, path=leaf_path)

    def _validate_outputs_fields_object_refs(
        self,
        raw: RawDemand,
        errors: list[ValidationIssue],
        *,
        main_source_id: str,
    ) -> None:
        field_def_index = collect_field_defs(raw, main_source_id=main_source_id)

        outputs_key = DEMAND_KEYS["outputs"]
        outputs_raw = raw.data.get(outputs_key)
        if not isinstance(outputs_raw, list):
            return
        outputs_list = cast("list[Any]", outputs_raw)  # pragma: allow-cast yaml list typed narrowing

        fields_key = OUTPUT_TARGET_KEYS["fields"]

        for output_idx, output_raw in enumerate(outputs_list):
            if not isinstance(output_raw, dict):
                continue
            output_dict = cast("dict[str, Any]", output_raw)  # pragma: allow-cast yaml mapping typed narrowing
            fields_raw = output_dict.get(fields_key)
            if not isinstance(fields_raw, list):
                continue
            fields_list = cast("list[Any]", fields_raw)  # pragma: allow-cast yaml list typed narrowing

            agg_field_index = None
            agg_raw = output_dict.get("aggregate")
            if isinstance(agg_raw, dict):
                agg_field_index = self._build_aggregate_field_index(
                    cast("dict[str, Any]", agg_raw)  # pragma: allow-cast yaml mapping typed narrowing
                )

            base_path = f"{outputs_key}.{output_idx}.{fields_key}"
            self._validate_outputs_fields_list_object_refs(
                fields_list,
                errors,
                base_path=base_path,
                field_def_index=field_def_index,
                agg_field_index=agg_field_index,
            )

    def _validate_resource_output_paths(self, config: dict[str, Any], errors: list[ValidationIssue]) -> None:  # noqa: C901, PLR0912
        resources_raw = config.get(DEMAND_KEYS["resources"])
        if not isinstance(resources_raw, dict):
            return

        files_raw = cast("Any", resources_raw).get(RESOURCES_KEYS["files"])
        if isinstance(files_raw, dict):
            for raw_file_id, raw_file_cfg in cast("dict[Any, Any]", files_raw).items():  # pragma: allow-cast yaml mapping typed narrowing
                file_id = str(raw_file_id or "").strip()
                if not file_id or not isinstance(raw_file_cfg, dict):
                    continue
                file_cfg = cast("dict[str, Any]", raw_file_cfg)  # pragma: allow-cast yaml mapping typed narrowing

                if "kind" in file_cfg:
                    kind = str(file_cfg.get("kind") or "").strip()
                    if kind == "csv_file":
                        msg = (
                            f"resources.files.{file_id}.kind was removed. "
                            f"Migration: use resources.files.{file_id}.csv_file: {{path: <output_root>, encoding?: utf-8}}."
                        )
                    else:
                        msg = f"resources.files.{file_id}.kind was removed. Migration: use resources.files.{file_id}.csv_file: {{...}}."
                    self._add_error(errors, msg, path=f"resources.files.{file_id}.kind")

                csv_raw = file_cfg.get(FILE_KEYS["csv_file"])
                if csv_raw is None:
                    msg = f"resources.files.{file_id}.csv_file is required"
                    self._add_error(errors, msg, path=f"resources.files.{file_id}")
                    continue
                if not isinstance(csv_raw, dict):
                    msg = f"resources.files.{file_id}.csv_file must be an object"
                    self._add_error(errors, msg, path=f"resources.files.{file_id}.csv_file")
                    continue

                csv_cfg = cast("dict[str, Any]", csv_raw)  # pragma: allow-cast yaml mapping typed narrowing
                path_value = csv_cfg.get(FILE_CSV_FILE_KEYS["path"])
                if path_value is None or (isinstance(path_value, str) and not path_value.strip()):
                    msg = f"resources.files.{file_id}.csv_file.path is required"
                    self._add_error(errors, msg, path=f"resources.files.{file_id}.csv_file.path")
                if isinstance(path_value, str) and Path(path_value).suffix.lower() == ".csv":
                    msg = (
                        f"resources.files.{file_id}.csv_file.path now expects an output root directory, not a file path. "
                        "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
                    )
                    self._add_error(errors, msg, path=f"resources.files.{file_id}.csv_file.path")

                path_raw = csv_cfg.get(FILE_CSV_FILE_KEYS["path"])
                if not isinstance(path_raw, dict):
                    continue
                try:
                    _ = parse_init_var_mapping_node(
                        cast("dict[str, Any]", path_raw),  # pragma: allow-cast yaml mapping typed narrowing
                        path=f"resources.files.{file_id}.csv_file.path",
                    )
                except (ScalimInitVarNodeValueError, ScalimInitVarNodeTypeError) as exc:
                    self._add_error(errors, exc.reason, path=exc.path)

        books_raw = cast("Any", resources_raw).get(RESOURCES_KEYS["books"])
        if not isinstance(books_raw, dict):
            return
        self.validate_books_mapping(
            cast("Mapping[Any, Any]", books_raw),  # pragma: allow-cast yaml mapping typed narrowing
            books_root_path="resources.books",
            errors=errors,
        )

    def validate_books_mapping(  # noqa: C901, PLR0912, PLR0915
        self,
        books_raw: Mapping[Any, Any],
        *,
        books_root_path: str,
        errors: list[ValidationIssue],
    ) -> None:
        """静态校验 `books` `mapping`(`demand`: `resources.books`; `workflow`: `workflow.resources.books`)."""

        for raw_book_id, raw_book_cfg in cast("dict[Any, Any]", books_raw).items():  # pragma: allow-cast yaml mapping typed narrowing
            book_id = str(raw_book_id or "").strip()
            if not book_id or not isinstance(raw_book_cfg, dict):
                continue
            book_cfg = cast("dict[str, Any]", raw_book_cfg)  # pragma: allow-cast yaml mapping typed narrowing
            book_path = f"{books_root_path!s}.{book_id}"
            if "kind" in book_cfg:
                kind = str(book_cfg.get("kind") or "").strip()
                if kind == "xlsx_file":
                    msg = f"{book_path}.kind was removed. Migration: use {book_path}.xlsx: {{path: <output_root>}}."
                elif kind == "xlsx_memory":
                    msg = f"{book_path}.kind was removed. Migration: use {book_path}.xlsx: {{}}."
                else:
                    msg = f"{book_path}.kind was removed. Migration: use {book_path}.xlsx: {{path?: ...}}."
                self._add_error(errors, msg, path=f"{book_path}.kind")

            if "xlsx_file" in book_cfg:
                self._add_error(
                    errors,
                    removed_xlsx_file_message(path=book_path),
                    path=f"{book_path}.xlsx_file",
                )

            if "xlsx_memory" in book_cfg:
                mem_raw = book_cfg.get("xlsx_memory")
                has_export = isinstance(mem_raw, dict) and "export_xlsx" in mem_raw
                self._add_error(
                    errors,
                    removed_xlsx_memory_message(path=book_path, has_export=has_export),
                    path=f"{book_path}.xlsx_memory",
                )

            has_xlsx = BOOK_KEYS["xlsx"] in book_cfg
            if not has_xlsx and "xlsx_file" not in book_cfg and "xlsx_memory" not in book_cfg:
                msg = f"{book_path} must declare exactly one variant key: xlsx"
                self._add_error(errors, msg, path=book_path)

            xlsx_raw = book_cfg.get(BOOK_KEYS["xlsx"])
            if xlsx_raw is not None:
                if not isinstance(xlsx_raw, dict):
                    msg = f"{book_path}.xlsx must be an object"
                    self._add_error(errors, msg, path=f"{book_path}.xlsx")
                else:
                    xlsx_cfg = cast("dict[str, Any]", xlsx_raw)  # pragma: allow-cast yaml mapping typed narrowing
                    if "export_xlsx" in xlsx_cfg:
                        msg = (
                            f"{book_path}.xlsx.export_xlsx is not allowed; set {book_path}.xlsx.path "
                            f"for export (or use empty {book_path}.xlsx: {{}} for an in-memory bus)."
                        )
                        self._add_error(errors, msg, path=f"{book_path}.xlsx.export_xlsx")
                    if "write_defaults" in xlsx_cfg:
                        msg = (
                            f"{book_path}.xlsx.write_defaults was removed from YAML authoring. "
                            "Migration: configure BookWritePolicy via Python ResourcesPolicy."
                        )
                        self._add_error(errors, msg, path=f"{book_path}.xlsx.write_defaults")
                    if "budget" in xlsx_cfg:
                        msg = (
                            f"{book_path}.xlsx.budget was removed. Delete this field; book cell/sheet budget "
                            "is no longer supported — rely on host resource limits for memory risk."
                        )
                        self._add_error(errors, msg, path=f"{book_path}.xlsx.budget")

                    path_value = xlsx_cfg.get(BOOK_XLSX_KEYS["path"]) if "path" in xlsx_cfg else None
                    if "path" in xlsx_cfg and (path_value is None or (isinstance(path_value, str) and not path_value.strip())):
                        msg = f"{book_path}.xlsx.path must be a non-empty output root when provided"
                        self._add_error(errors, msg, path=f"{book_path}.xlsx.path")
                    if isinstance(path_value, str) and Path(path_value).suffix.lower() == ".xlsx":
                        msg = (
                            f"{book_path}.xlsx.path expects an output root directory, not a file path. "
                            "Migration: set path to './out' and locate outputs via <root>/manifest/latest.json."
                        )
                        self._add_error(errors, msg, path=f"{book_path}.xlsx.path")

                    path_raw = xlsx_cfg.get(BOOK_XLSX_KEYS["path"]) if "path" in xlsx_cfg else None
                    if isinstance(path_raw, dict):
                        try:
                            _ = parse_init_var_mapping_node(
                                cast("dict[str, Any]", path_raw),
                                path=f"{book_path}.xlsx.path",
                            )
                        except (ScalimInitVarNodeValueError, ScalimInitVarNodeTypeError) as exc:
                            self._add_error(errors, exc.reason, path=exc.path)


@dataclass(frozen=True)
class YamlValidationIssue:
    path: str
    message: str
    suggestions: list[str] = dataclass_field(default_factory=list)
    line: int | None = None
    column: int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.line is None:
            payload.pop("line", None)
        if self.column is None:
            payload.pop("column", None)
        return payload


@dataclass(frozen=True)
class YamlValidationResult:
    ok: bool
    errors: list[YamlValidationIssue] = dataclass_field(default_factory=list)
    warnings: list[YamlValidationIssue] = dataclass_field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


def _issues_to_rows(issues: Iterable[ValidationIssue]) -> list[YamlValidationIssue]:
    rows: list[YamlValidationIssue] = []
    for issue in issues:
        rows.append(
            YamlValidationIssue(
                path=normalize_yaml_diagnostic_path(str(issue.path or "")),
                message=str(issue.message),
                suggestions=list(issue.suggestions),
            )
        )
    return rows


def attach_locations(
    issues: list[YamlValidationIssue],
    locations: YamlLocationIndex,
    *,
    default: tuple[int, int] | None = (1, 1),
) -> list[YamlValidationIssue]:
    if not issues:
        return issues
    output: list[YamlValidationIssue] = []
    for issue in issues:
        if issue.line is not None:
            output.append(issue)
            continue
        loc = lookup_yaml_location(issue.path, locations)
        if loc is None:
            if default is None:
                output.append(issue)
                continue
            line, column = default
        else:
            line, column = loc
        output.append(
            YamlValidationIssue(
                path=issue.path,
                message=issue.message,
                suggestions=issue.suggestions,
                line=line,
                column=column,
            )
        )
    return output


def validate_yaml_text(
    yaml_text: str,
    strict_unknown_fields: bool = False,  # noqa: FBT001, FBT002
    schema_path: str | None = None,
) -> YamlValidationResult:
    """使用 `Scalim` 内置校验器对 `YAML DSL` 文本进行校验.

    此函数会做语义校验(`ConfigValidator`),并基于 `YAML` 语法树(`AST`)位置索引尽力补充行/列定位信息.
    """
    try:
        yaml_data, locations, _lines = load_yaml_mapping_text(
            yaml_text,
            source_path="(memory)",
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        errors: list[YamlValidationIssue] = []
        for envelope in exc.errors:
            loc = envelope.loc
            errors.append(
                YamlValidationIssue(
                    path=str(envelope.path or "(root)"),
                    message=str(envelope.message),
                    suggestions=list(envelope.suggestions),
                    line=loc.line if loc is not None else None,
                    column=loc.column if loc is not None else None,
                )
            )
        warnings: list[YamlValidationIssue] = []
        for envelope in exc.warnings:
            loc = envelope.loc
            warnings.append(
                YamlValidationIssue(
                    path=str(envelope.path or "(root)"),
                    message=str(envelope.message),
                    suggestions=list(envelope.suggestions),
                    line=loc.line if loc is not None else None,
                    column=loc.column if loc is not None else None,
                )
            )
        return YamlValidationResult(ok=False, errors=errors, warnings=warnings)

    if contains_import_syntax(yaml_data):
        msg = "imports/$import is only supported for file path entrypoints; use scalim-cli yaml-dsl validate <file.yaml>"
        return YamlValidationResult(
            ok=False,
            errors=[YamlValidationIssue(path="(root)", message=msg, line=1, column=1)],
            warnings=[],
        )

    validator = ConfigValidator(schema_path=schema_path)
    config_data = ensure_mapping(yaml_data)
    report = validator.validate_report(
        config_data,
        strict_unknown_fields=bool(strict_unknown_fields),
    )

    errors = _issues_to_rows(report.errors())
    warnings = _issues_to_rows(report.warnings())

    errors = attach_locations(errors, locations)
    warnings = attach_locations(warnings, locations)

    ok = not errors
    return YamlValidationResult(ok=bool(ok), errors=errors, warnings=warnings)


def validate_yaml_text_json(
    yaml_text: str,
    strict_unknown_fields: bool = False,  # noqa: FBT001, FBT002
    schema_path: str | None = None,
) -> str:
    """返回与 `YAML DSL` 编辑器的"精确校验器"兼容的 `JSON` 载荷."""
    result = validate_yaml_text(
        yaml_text,
        strict_unknown_fields,
        schema_path,
    )
    return json.dumps(result.as_dict(), ensure_ascii=False)
