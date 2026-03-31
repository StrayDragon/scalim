# pragma: allow-cast-file yaml validation boundary typed narrowing
import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, cast

from ...._internal.loggingx import format_kv, get_logger, prefix
from ....vendor.compact.importlibx import import_module
from ....vendor.compact.typing_extensionsx import TypeGuard
from ....vendor.dataclassesx import asdict, dataclass
from ....vendor.dataclassesx import field as dataclass_field
from ....vendor.yamlx import yaml
from ..init_var_nodes import ScalimInitVarNodeTypeError, ScalimInitVarNodeValueError, parse_init_var_mapping_node
from ..schema_dsl.constants import DEFAULT_OUTPUT_HEADER_BY, DEFAULT_OUTPUT_INCLUDE_HEADER, DEMAND_FIELDS_KEY, FIELD_KIND_DERIVED
from ..schema_dsl.models import (
    BOOK_KEYS,
    BOOK_WRITE_DEFAULTS_KEYS,
    DEMAND_KEYS,
    OUTPUT_TARGET_KEYS,
    OUTPUT_TO_KEYS,
    OUTPUT_WRITE_KEYS,
    RESOURCES_KEYS,
)
from ..schema_dsl.output_enums import DEFAULT_BOOK_WRITE_HEADER_POLICY, DEFAULT_BOOK_WRITE_MODE
from .errors import ScalimConfigValidationError
from .imports import contains_import_syntax
from .jsonschema_issues import ScalimJsonSchemaCollectorError, collect_jsonschema_validation_issues
from .models import FieldDef, FieldDefIndex, RawDemand, collect_field_defs, ensure_mapping
from .security import SecureComputeEngine, build_compute_engine
from .unknown_fields import find_unknown_fields
from .validators.fields import ValidatorFieldsMixin
from .validators.issues import (
    MAX_VALIDATION_ERROR_LINES,
    VALIDATION_SEVERITY_ERROR,
    VALIDATION_SEVERITY_WARNING,
    ValidationIssue,
    ValidationReport,
)
from .yaml_load import YamlLocationIndex, build_yaml_location_index, lookup_yaml_location, safe_yaml_parse_error_message

try:
    jsonschema = import_module("jsonschema")

    _has_jsonschema: bool = True
    _jsonschema_import_error: Optional[Exception] = None
except Exception as exc:  # noqa: BLE001
    jsonschema = None  # type: ignore[assignment]
    _has_jsonschema = False
    _jsonschema_import_error = exc

HAS_JSONSCHEMA: bool = _has_jsonschema

_VALIDATOR_LOGGER = get_logger("schema")

__all__ = [
    "HAS_JSONSCHEMA",
    "MAX_VALIDATION_ERROR_LINES",
    "VALIDATION_SEVERITY_ERROR",
    "VALIDATION_SEVERITY_WARNING",
    "ConfigValidator",
    "ValidationIssue",
    "ValidationReport",
    "YamlLocationIndex",
    "YamlValidationIssue",
    "YamlValidationResult",
    "attach_locations",
    "build_yaml_location_index",
    "lookup_yaml_location",
    "validate_yaml_text",
    "validate_yaml_text_json",
]


def _field_def_path(field_def: FieldDef, *, main_source_id: str) -> str:
    if str(field_def.kind) == FIELD_KIND_DERIVED:
        return "{}.{}".format(DEMAND_FIELDS_KEY, field_def.field_id)
    if field_def.source_id and str(field_def.source_id) != str(main_source_id):
        return "sources.{}.fields.{}".format(field_def.source_id, field_def.field_id)
    return "main_source.fields.{}".format(field_def.field_id)


def _normalized_opt_str(value: object) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def _raw_output_book_write_value(config: Dict[str, Any], *, book_id: str, key: str, default: str) -> str:
    resources_raw = config.get(DEMAND_KEYS["resources"])
    if not isinstance(resources_raw, dict):
        return default
    books_raw = cast("Any", resources_raw).get(RESOURCES_KEYS["books"])
    if not isinstance(books_raw, dict):
        return default
    book_raw = cast("Any", books_raw).get(book_id)
    if not isinstance(book_raw, dict):
        return default
    write_defaults_raw = cast("Any", book_raw).get(BOOK_KEYS["write_defaults"])
    if not isinstance(write_defaults_raw, dict):
        return default
    value = _normalized_opt_str(cast("Any", write_defaults_raw).get(key))
    return value or default


def _output_item_requires_unique_effective_display_names(  # noqa: C901, PLR0911, PLR0912
    config: Dict[str, Any], output_item: object
) -> bool:
    if not isinstance(output_item, dict):
        return False
    out_dict = cast("Dict[str, Any]", output_item)  # pragma: allow-cast yaml mapping typed narrowing
    to_raw = out_dict.get(OUTPUT_TARGET_KEYS["to"])
    if not isinstance(to_raw, dict):
        return False
    to_dict = cast("Dict[str, Any]", to_raw)  # pragma: allow-cast yaml mapping typed narrowing

    file_id = _normalized_opt_str(to_dict.get(OUTPUT_TO_KEYS["file"]))
    book_id = _normalized_opt_str(to_dict.get(OUTPUT_TO_KEYS["book"]))
    if bool(file_id) == bool(book_id):
        return False

    write_raw = out_dict.get(OUTPUT_TARGET_KEYS["write"])
    write_dict = cast("Optional[Dict[str, Any]]", write_raw if isinstance(write_raw, dict) else None)

    header_by = str(DEFAULT_OUTPUT_HEADER_BY).strip().lower()
    if write_dict is not None:
        header_by_raw = write_dict.get(OUTPUT_WRITE_KEYS["header_fields_output_by"])
        if isinstance(header_by_raw, str) and header_by_raw.strip():
            header_by = header_by_raw.strip().lower()
    if header_by != "name":
        return False

    if file_id:
        include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
        if write_dict is not None:
            include_header_raw = write_dict.get(OUTPUT_WRITE_KEYS["include_header"])
            if isinstance(include_header_raw, bool):
                include_header = bool(include_header_raw)
        return bool(include_header)

    effective_mode = _raw_output_book_write_value(
        config,
        book_id=book_id,
        key=BOOK_WRITE_DEFAULTS_KEYS["mode"],
        default=DEFAULT_BOOK_WRITE_MODE,
    )
    if write_dict is not None:
        mode_raw = write_dict.get(OUTPUT_WRITE_KEYS["mode"])
        if isinstance(mode_raw, str) and mode_raw.strip():
            effective_mode = mode_raw.strip()

    if effective_mode == "append":
        header_policy = _raw_output_book_write_value(
            config,
            book_id=book_id,
            key=BOOK_WRITE_DEFAULTS_KEYS["header_policy"],
            default=DEFAULT_BOOK_WRITE_HEADER_POLICY,
        )
        if write_dict is not None:
            header_policy_raw = write_dict.get(OUTPUT_WRITE_KEYS["header_policy"])
            if isinstance(header_policy_raw, str) and header_policy_raw.strip():
                header_policy = header_policy_raw.strip()
        return header_policy != "never"

    include_header = DEFAULT_OUTPUT_INCLUDE_HEADER
    if isinstance(write_raw, dict):
        include_header_raw = cast("Dict[str, Any]", write_raw).get(OUTPUT_WRITE_KEYS["include_header"])
        if isinstance(include_header_raw, bool):
            include_header = bool(include_header_raw)
    return bool(include_header)


def _outputs_require_unique_effective_display_names(config: Dict[str, Any], outputs: List[object]) -> bool:
    return any(_output_item_requires_unique_effective_display_names(config, item) for item in outputs)


def _collect_duplicate_effective_display_names(field_def_index: FieldDefIndex, *, main_source_id: str) -> Dict[str, List[str]]:
    by_effective: Dict[str, List[str]] = {}

    for fd in field_def_index.field_defs:
        name_raw = fd.data.get("name")
        name = name_raw.strip() if isinstance(name_raw, str) else ""
        effective = name or str(fd.field_id)
        by_effective.setdefault(effective, []).append(_field_def_path(fd, main_source_id=main_source_id))

    return {name: paths for name, paths in by_effective.items() if len(paths) > 1}


def _format_duplicate_effective_display_names_message(duplicates: Dict[str, List[str]]) -> str:
    parts: List[str] = []
    for name in sorted(duplicates.keys()):
        parts.append("{!r}: {}".format(name, ", ".join(sorted(duplicates[name]))))

    conflicts = "; ".join(parts)
    return "".join(
        [
            "Duplicate effective field display names detected while outputs include include_header=true and header_fields_output_by=name. ",
            "Conflicts: {}. Set validate_unique_field_names: false to disable.".format(conflicts),
        ]
    )


def _is_list(value: object) -> TypeGuard[List[object]]:
    return isinstance(value, list)


def _is_dict(value: object) -> TypeGuard[Dict[object, object]]:
    return isinstance(value, dict)


class ConfigValidator(ValidatorFieldsMixin):
    _schema_path: str
    _schema: Optional[Dict[str, Any]]
    _compute_engine: Optional[SecureComputeEngine]
    _step_allowed_fields_by_source: Dict[str, Set[str]]
    _max_validation_error_lines: int
    _jsonschema_validate_fn: Optional[Callable[[Dict[str, Any], Dict[str, Any]], None]]

    def __init__(
        self,
        schema_path: Optional[str] = None,
        max_validation_error_lines: Optional[int] = None,
        jsonschema_validate_fn: Optional[Callable[[Dict[str, Any], Dict[str, Any]], None]] = None,
    ) -> None:
        super().__init__()
        if schema_path is None:
            schema_path = str(Path(__file__).parent.parent / "schema" / "demand.gen.json")
        self._schema_path = schema_path
        self._schema = None
        self._compute_engine = build_compute_engine()
        self._step_allowed_fields_by_source = {}
        self._max_validation_error_lines = int(
            max_validation_error_lines if max_validation_error_lines is not None else MAX_VALIDATION_ERROR_LINES
        )
        self._jsonschema_validate_fn = jsonschema_validate_fn
        if self._max_validation_error_lines < 1:
            msg = "max_validation_error_lines must be >= 1"
            raise ValueError(msg)

    def _validate_deprecated_observability_fields(self, config: Dict[str, Any], errors: List["ValidationIssue"]) -> None:
        obs_raw: Any = config.get("observability")
        if not isinstance(obs_raw, dict):
            return
        obs_dict = cast("Dict[str, Any]", obs_raw)  # pragma: allow-cast yaml mapping typed narrowing
        viz_raw: Any = obs_dict.get("viz")
        if isinstance(viz_raw, dict) and "event_mode" in viz_raw:
            self._add_error(
                errors,
                "Legacy field 'observability.viz.event_mode' is not allowed. Use 'observability.viz.trace_enabled'.",
                path="observability.viz.event_mode",
            )

    def validate(self, config: Dict[str, Any]) -> None:
        report = self.validate_report(config, enable_jsonschema_validation=True)
        issues = report.errors()
        if not issues:
            return

        errors: List[str] = []
        for issue in issues[: self._max_validation_error_lines]:
            if issue.path:
                errors.append("{}: {}".format(issue.path, issue.message))
            else:
                errors.append(issue.message)

        msg = "Configuration validation failed with {} error(s)".format(len(issues))
        if len(issues) > self._max_validation_error_lines:
            msg = "{} (showing first {} errors)".format(msg, self._max_validation_error_lines)
        raise ScalimConfigValidationError(msg, errors=errors, issues=report.issues)

    def validate_report(
        self,
        config: Dict[str, Any],
        *,
        strict_unknown_fields: bool = False,
        enable_jsonschema_validation: bool = False,
    ) -> ValidationReport:
        errors: List[ValidationIssue] = []
        raw = RawDemand.from_raw(config)

        self._validate_required_fields(raw.data, errors)
        self._validate_batch_size(raw.data, errors)
        self._validate_legacy_fields(raw.data, errors)
        self._validate_deprecated_observability_fields(raw.data, errors)
        self._validate_loader_retry_should_retry(raw.data.get("retry"), errors, path_prefix="retry")

        sources_info = self._validate_sources(raw.data, errors)
        main_source_id = self._validate_main_source(raw.data, errors)
        self._step_allowed_fields_by_source = self._collect_step_allowed_fields(raw.data, main_source_id)
        relation_paths = self._validate_relations(raw.data, errors, sources_info, main_source_id)
        self._validate_fields(raw, errors, sources_info, main_source_id, relation_paths)
        self._validate_outputs_fields_object_refs(raw, errors, main_source_id=main_source_id)
        self._validate_removed_output_container(raw.data, errors)
        self._validate_resource_output_paths(raw.data, errors)
        self._validate_unique_effective_field_display_names(raw, errors, main_source_id=main_source_id)

        if enable_jsonschema_validation:
            self._validate_with_jsonschema(raw.data, errors, filter_additional_properties=strict_unknown_fields)
        self._validate_unknown_fields(raw.data, errors, strict=strict_unknown_fields)

        return ValidationReport(issues=errors)

    def _validate_unique_effective_field_display_names(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        *,
        main_source_id: str,
    ) -> None:
        validate_raw = raw.data.get(DEMAND_KEYS["validate_unique_field_names"])
        if validate_raw is False:
            return

        outputs_raw: object = raw.data.get(DEMAND_KEYS["outputs"])
        if not _is_list(outputs_raw):
            return
        outputs = outputs_raw
        if not _outputs_require_unique_effective_display_names(raw.data, outputs):
            return

        field_def_index = collect_field_defs(raw, main_source_id=main_source_id)
        duplicates = _collect_duplicate_effective_display_names(field_def_index, main_source_id=main_source_id)
        if not duplicates:
            return

        msg = _format_duplicate_effective_display_names_message(duplicates)
        self._add_error(errors, msg, path=DEMAND_KEYS["validate_unique_field_names"])

    def _validate_removed_output_container(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:
        outputs_raw = config.get(DEMAND_KEYS["outputs"])
        if not _is_list(outputs_raw):
            return
        for idx, item in enumerate(outputs_raw):
            if not isinstance(item, dict):
                continue
            out_dict = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing
            if "container" not in out_dict:
                continue
            msg = (
                "outputs.{}.container was removed; migrate CSV outputs to resources.files + outputs[*].to.file + outputs[*].write, "
                "and .xlsx outputs to resources.books + outputs[*].to.book / outputs[*].to.sheet + outputs[*].write"
            ).format(int(idx))
            self._add_error(errors, msg, path="outputs.{}.container".format(int(idx)))

    def _build_aggregate_field_index(self, aggregate: Dict[str, Any]) -> Tuple[Dict[int, str], List[Tuple[str, Dict[str, Any]]]]:
        fields_raw: object = aggregate.get("fields")
        if not _is_dict(fields_raw):
            return {}, []
        fields_dict = fields_raw

        alias_index: Dict[int, str] = {}
        field_defs: List[Tuple[str, Dict[str, Any]]] = []
        for out_field_id_raw, field_raw in fields_dict.items():
            out_field_id = str(out_field_id_raw or "").strip()
            if not out_field_id:
                continue
            if not isinstance(field_raw, dict):
                continue
            field_dict = cast("Dict[str, Any]", field_raw)  # pragma: allow-cast yaml mapping typed narrowing
            alias_index[id(field_dict)] = out_field_id
            field_defs.append((out_field_id, field_dict))
        return alias_index, field_defs

    def _outputs_fields_object_item_error(
        self,
        field_def_index: FieldDefIndex,
        item: object,
        *,
        agg_field_index: Optional[Tuple[Dict[int, str], List[Tuple[str, Dict[str, Any]]]]] = None,
    ) -> Optional[str]:
        if not isinstance(item, dict):
            return "must be field_id string, YAML alias(object), or YAML alias(list)"

        typed = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing
        if agg_field_index is not None:
            alias_index, _ = agg_field_index
            if alias_index.get(id(typed)) is not None:
                return None

        direct = field_def_index.alias_index.get(typed)
        if direct is not None:
            return None

        matches: List[str] = []
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
        fields_list: List[Any],
        errors: List[ValidationIssue],
        *,
        base_path: str,
        field_def_index: FieldDefIndex,
        agg_field_index: Optional[Tuple[Dict[int, str], List[Tuple[str, Dict[str, Any]]]]] = None,
    ) -> None:
        def _walk(item: object, *, path: str) -> List[Tuple[str, object]]:
            if _is_list(item):
                out: List[Tuple[str, object]] = []
                for idx, sub in enumerate(item):
                    out.extend(_walk(sub, path="{}.{}".format(path, idx)))
                return out
            return [(path, item)]

        for field_idx, item in enumerate(fields_list):
            root_path = "{}.{}".format(base_path, field_idx)
            for leaf_path, leaf in _walk(item, path=root_path):
                if isinstance(leaf, str):
                    continue
                msg = self._outputs_fields_object_item_error(field_def_index, leaf, agg_field_index=agg_field_index)
                if msg:
                    self._add_error(errors, msg, path=leaf_path)

    def _validate_outputs_fields_object_refs(
        self,
        raw: RawDemand,
        errors: List[ValidationIssue],
        *,
        main_source_id: str,
    ) -> None:
        # 注意: `jsonschema` 校验是可选项; `schema-only` 校验不应阻断 `YAML` `alias` 写法.
        # 这里做语义校验,确保 `outputs[*].fields` 的 `object` 条目可解析为唯一 `field_id`.
        field_def_index = collect_field_defs(raw, main_source_id=main_source_id)

        outputs_key = DEMAND_KEYS["outputs"]
        outputs_raw = raw.data.get(outputs_key)
        if not isinstance(outputs_raw, list):
            return
        outputs_list = cast("List[Any]", outputs_raw)  # pragma: allow-cast yaml list typed narrowing

        fields_key = OUTPUT_TARGET_KEYS["fields"]

        for output_idx, output_raw in enumerate(outputs_list):
            if not isinstance(output_raw, dict):
                continue
            output_dict = cast("Dict[str, Any]", output_raw)  # pragma: allow-cast yaml mapping typed narrowing
            fields_raw = output_dict.get(fields_key)
            if not isinstance(fields_raw, list):
                continue
            fields_list = cast("List[Any]", fields_raw)  # pragma: allow-cast yaml list typed narrowing

            agg_field_index = None
            agg_raw = output_dict.get("aggregate")
            if isinstance(agg_raw, dict):
                agg_field_index = self._build_aggregate_field_index(
                    cast("Dict[str, Any]", agg_raw)  # pragma: allow-cast yaml mapping typed narrowing
                )

            base_path = "{}.{}.{}".format(outputs_key, output_idx, fields_key)
            self._validate_outputs_fields_list_object_refs(
                fields_list,
                errors,
                base_path=base_path,
                field_def_index=field_def_index,
                agg_field_index=agg_field_index,
            )

    def _load_schema(self) -> Dict[str, Any]:
        if self._schema is None:
            with Path(self._schema_path).open("r", encoding="utf-8") as f:
                self._schema = json.load(f)
        if self._schema is None:  # pragma: no cover  # pragma: allow-no-cover invariant: schema loaded or raised above
            msg = "Schema failed to load"
            raise RuntimeError(msg)
        return self._schema

    def _validate_with_jsonschema(
        self,
        config: Dict[str, Any],
        errors: List[ValidationIssue],
        *,
        filter_additional_properties: bool,
    ) -> None:
        if not HAS_JSONSCHEMA or jsonschema is None:  # pragma: no cover  # pragma: allow-no-cover optional dependency boundary
            # `JSONSchema` 校验是可选项. 某些旧运行时可能存在但因依赖版本不匹配(例如旧 `attrs`)而不可用,因此这里不能直接失败.
            reason = None
            detail = None
            if _jsonschema_import_error is not None:
                reason = type(_jsonschema_import_error).__name__
                detail = str(_jsonschema_import_error)

            msg = "{}jsonschema 不可用, 已跳过 schema 校验".format(prefix("schema"))
            kv = format_kv(reason=reason, detail=detail)
            if kv:
                msg = "{} {}".format(msg, kv)

            _VALIDATOR_LOGGER.warning(msg)
            errors.append(ValidationIssue(severity=VALIDATION_SEVERITY_WARNING, message=msg, path="(schema)"))
            return
        try:
            schema = self._load_schema()
            validate_fn = self._jsonschema_validate_fn

            # 为兼容测试注入,保留 `jsonschema_validate_fn` 钩子(单条 `ValidationError`).
            if validate_fn is not None:
                _ = validate_fn(config, schema)
                return

            issues = collect_jsonschema_validation_issues(
                config,
                schema,
                jsonschema_module=jsonschema,
                include_context=False,
                filter_additional_properties=bool(filter_additional_properties),
            )
            for issue in issues:
                self._add_error(errors, issue.message, path=issue.path)
        except jsonschema.ValidationError as e:  # type: ignore[union-attr]
            absolute_path = getattr(e, "absolute_path", None)  # pragma: allow-dynattr third-party: jsonschema ValidationError
            path = ".".join(str(p) for p in absolute_path) if absolute_path else ""
            self._add_error(errors, "Schema validation error: {}".format(e.message), path=path)
        except ScalimJsonSchemaCollectorError as exc:
            msg = "JSONSchema validation failed unexpectedly: {}: {}".format(type(exc).__name__, exc)
            errors.append(ValidationIssue(severity=VALIDATION_SEVERITY_WARNING, message=msg, path="(schema)"))
        except Exception as exc:  # noqa: BLE001
            msg = "JSONSchema validation failed unexpectedly: {}: {}".format(type(exc).__name__, exc)
            errors.append(ValidationIssue(severity=VALIDATION_SEVERITY_WARNING, message=msg, path="(schema)"))

    def _validate_unknown_fields(self, config: Dict[str, Any], issues: List[ValidationIssue], *, strict: bool) -> None:
        try:
            schema = self._load_schema()
        except Exception:  # noqa: BLE001
            return

        severity = VALIDATION_SEVERITY_ERROR if strict else VALIDATION_SEVERITY_WARNING
        for unknown in find_unknown_fields(config, schema):
            issues.append(
                ValidationIssue(
                    severity=severity,
                    message=unknown.message,
                    path=unknown.path,
                    suggestions=unknown.suggestions,
                )
            )

    def _validate_resource_output_paths(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:  # noqa: C901, PLR0912
        resources_raw = config.get(DEMAND_KEYS["resources"])
        if not isinstance(resources_raw, dict):
            return

        files_raw = cast("Any", resources_raw).get(RESOURCES_KEYS["files"])
        if isinstance(files_raw, dict):
            for raw_file_id, raw_file_cfg in cast("Dict[Any, Any]", files_raw).items():  # pragma: allow-cast yaml mapping typed narrowing
                file_id = str(raw_file_id or "").strip()
                if not file_id or not isinstance(raw_file_cfg, dict):
                    continue
                path_raw = cast("Any", raw_file_cfg).get("path")
                if not isinstance(path_raw, dict):
                    continue
                try:
                    _ = parse_init_var_mapping_node(
                        cast("Dict[str, Any]", path_raw),  # pragma: allow-cast yaml mapping typed narrowing
                        path="resources.files.{}.path".format(file_id),
                    )
                except (ScalimInitVarNodeValueError, ScalimInitVarNodeTypeError) as exc:
                    self._add_error(errors, exc.reason, path=exc.path)

        books_raw = cast("Any", resources_raw).get(RESOURCES_KEYS["books"])
        if not isinstance(books_raw, dict):
            return
        for raw_book_id, raw_book_cfg in cast("Dict[Any, Any]", books_raw).items():  # pragma: allow-cast yaml mapping typed narrowing
            book_id = str(raw_book_id or "").strip()
            if not book_id or not isinstance(raw_book_cfg, dict):
                continue
            book_cfg = cast("Dict[str, Any]", raw_book_cfg)  # pragma: allow-cast yaml mapping typed narrowing
            for suffix in ("path",):
                path_raw = book_cfg.get(suffix)
                if not isinstance(path_raw, dict):
                    continue
                try:
                    _ = parse_init_var_mapping_node(
                        cast("Dict[str, Any]", path_raw),
                        path="resources.books.{}.{}".format(book_id, suffix),
                    )
                except (ScalimInitVarNodeValueError, ScalimInitVarNodeTypeError) as exc:
                    self._add_error(errors, exc.reason, path=exc.path)
            export_raw = book_cfg.get(BOOK_KEYS["export_xlsx"])
            if not isinstance(export_raw, dict):
                continue
            export_path_raw = cast("Dict[str, Any]", export_raw).get("path")
            if not isinstance(export_path_raw, dict):
                continue
            try:
                _ = parse_init_var_mapping_node(
                    cast("Dict[str, Any]", export_path_raw),
                    path="resources.books.{}.export_xlsx.path".format(book_id),
                )
            except (ScalimInitVarNodeValueError, ScalimInitVarNodeTypeError) as exc:
                self._add_error(errors, exc.reason, path=exc.path)


@dataclass(frozen=True)
class YamlValidationIssue:
    path: str
    message: str
    suggestions: List[str] = dataclass_field(default_factory=list)
    line: Optional[int] = None
    column: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if self.line is None:
            payload.pop("line", None)
        if self.column is None:
            payload.pop("column", None)
        return payload


@dataclass(frozen=True)
class YamlValidationResult:
    ok: bool
    errors: List[YamlValidationIssue] = dataclass_field(default_factory=list)
    warnings: List[YamlValidationIssue] = dataclass_field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


def _issues_to_rows(issues: Iterable[ValidationIssue]) -> List[YamlValidationIssue]:
    rows: List[YamlValidationIssue] = []
    for issue in issues:
        rows.append(
            YamlValidationIssue(
                path=str(issue.path or ""),
                message=str(issue.message),
                suggestions=list(issue.suggestions),
            )
        )
    return rows


def _normalize_issue_path(path: str) -> str:
    if not path:
        return ""
    cleaned = path.strip()
    if cleaned.startswith("↳"):
        cleaned = cleaned.lstrip("↳").strip()
    if cleaned == "(root)":
        return ""
    return cleaned


def attach_locations(
    issues: List[YamlValidationIssue],
    locations: YamlLocationIndex,
    *,
    default: Optional[Tuple[int, int]] = (1, 1),
) -> List[YamlValidationIssue]:
    if not issues:
        return issues
    output: List[YamlValidationIssue] = []
    for issue in issues:
        if issue.line is not None:
            output.append(issue)
            continue
        normalized = _normalize_issue_path(issue.path)
        loc = lookup_yaml_location(normalized, locations)
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


def _extract_yaml_error_location(exc: Exception) -> Optional[Tuple[int, int]]:
    problem_mark = getattr(exc, "problem_mark", None)  # pragma: allow-dynattr third-party: pyyaml YAMLError mark
    context_mark = getattr(exc, "context_mark", None)  # pragma: allow-dynattr third-party: pyyaml YAMLError mark
    mark = problem_mark or context_mark
    if mark is None:
        return None
    line = getattr(mark, "line", None)  # pragma: allow-dynattr third-party: pyyaml Mark
    column = getattr(mark, "column", None)  # pragma: allow-dynattr third-party: pyyaml Mark
    if not isinstance(line, int) or not isinstance(column, int):
        return None
    return line + 1, column + 1


def validate_yaml_text(
    yaml_text: str,
    strict_unknown_fields: bool = False,  # noqa: FBT001, FBT002
    schema_path: Optional[str] = None,
    enable_jsonschema_validation: bool = False,  # noqa: FBT001, FBT002
) -> YamlValidationResult:
    """使用 `Scalim` 内置校验器对 `YAML DSL` 文本进行校验.

    此函数会做语义校验(`ConfigValidator`),并基于 `YAML` 语法树(`AST`)位置索引尽力补充行/列定位信息.
    """
    try:
        yaml_data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        loc = _extract_yaml_error_location(exc)
        line = loc[0] if loc is not None else None
        column = loc[1] if loc is not None else None
        return YamlValidationResult(
            ok=False,
            errors=[
                YamlValidationIssue(
                    path="(root)",
                    message="YAML parse error: {}".format(safe_yaml_parse_error_message(exc)),
                    line=line,
                    column=column,
                )
            ],
            warnings=[],
        )
    if yaml_data is None:
        return YamlValidationResult(
            ok=False,
            errors=[YamlValidationIssue(path="(root)", message="YAML document is empty", line=1, column=1)],
            warnings=[],
        )

    if contains_import_syntax(yaml_data):
        msg = "imports/$import is only supported for file path entrypoints; use scalim-cli yaml-dsl validate <file.yaml>"
        return YamlValidationResult(
            ok=False,
            errors=[YamlValidationIssue(path="(root)", message=msg, line=1, column=1)],
            warnings=[],
        )

    validator = ConfigValidator(schema_path=schema_path)
    config_data = ensure_mapping(yaml_data) if isinstance(yaml_data, dict) else {}
    report = validator.validate_report(
        config_data,
        strict_unknown_fields=bool(strict_unknown_fields),
        enable_jsonschema_validation=bool(enable_jsonschema_validation),
    )

    errors = _issues_to_rows(report.errors())
    warnings = _issues_to_rows(report.warnings())

    locations = build_yaml_location_index(yaml_text)
    errors = attach_locations(errors, locations)
    warnings = attach_locations(warnings, locations)

    ok = not errors
    return YamlValidationResult(ok=bool(ok), errors=errors, warnings=warnings)


def validate_yaml_text_json(
    yaml_text: str,
    strict_unknown_fields: bool = False,  # noqa: FBT001, FBT002
    schema_path: Optional[str] = None,
    enable_jsonschema_validation: bool = False,  # noqa: FBT001, FBT002
) -> str:
    """返回与 `YAML DSL` 编辑器的“精确校验器”兼容的 `JSON` 载荷."""
    result = validate_yaml_text(
        yaml_text,
        strict_unknown_fields,
        schema_path,
        enable_jsonschema_validation,
    )
    return json.dumps(result.as_dict(), ensure_ascii=False)
