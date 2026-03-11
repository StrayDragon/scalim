import json
import logging
from dataclasses import asdict, dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, cast

from ....vendor.compact.importlibx import import_module, require_optional_dependency

if TYPE_CHECKING:
    import yaml
    from yaml.nodes import MappingNode, SequenceNode
else:
    yaml = require_optional_dependency(
        "yaml",
        context="scalim.dsl.by_yaml.config_parsing.validator",
        install_name="pyyaml",
    )
    _yaml_nodes = require_optional_dependency(
        "yaml.nodes",
        context="scalim.dsl.by_yaml.config_parsing.validator",
        install_name="pyyaml",
    )
    MappingNode = _yaml_nodes.MappingNode
    SequenceNode = _yaml_nodes.SequenceNode

from .errors import ConfigValidationError
from .models import RawDemand, ensure_mapping
from .security import SecureComputeEngine, build_compute_engine
from .unknown_fields import find_unknown_fields
from .validators.fields import OutputFieldIssueCollector, ValidatorFieldsMixin
from .validators.issues import (
    MAX_VALIDATION_ERROR_LINES,
    VALIDATION_SEVERITY_ERROR,
    VALIDATION_SEVERITY_WARNING,
    ValidationIssue,
    ValidationReport,
)

_OutputFieldIssueCollector = OutputFieldIssueCollector

try:
    jsonschema = import_module("jsonschema")

    _has_jsonschema: bool = True
except ImportError:
    jsonschema = None  # type: ignore[assignment]
    _has_jsonschema = False

HAS_JSONSCHEMA: bool = _has_jsonschema

_VALIDATOR_LOGGER = logging.getLogger("scalim.dsl.by_yaml.validator")

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
    "_OutputFieldIssueCollector",
    "attach_locations",
    "build_yaml_location_index",
    "lookup_yaml_location",
    "validate_yaml_text",
    "validate_yaml_text_json",
]


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
        obs_dict = cast("Dict[str, Any]", obs_raw)
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
        raise ConfigValidationError(msg, errors=errors, issues=report.issues)

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

        if enable_jsonschema_validation:
            self._validate_with_jsonschema(raw.data, errors)
        self._validate_unknown_fields(raw.data, errors, strict=strict_unknown_fields)

        return ValidationReport(issues=errors)

    def _load_schema(self) -> Dict[str, Any]:
        if self._schema is None:
            with Path(self._schema_path).open("r", encoding="utf-8") as f:
                self._schema = json.load(f)
        if self._schema is None:  # pragma: no cover
            msg = "Schema failed to load"
            raise RuntimeError(msg)
        return self._schema

    def _validate_with_jsonschema(self, config: Dict[str, Any], errors: List[ValidationIssue]) -> None:
        if not HAS_JSONSCHEMA or jsonschema is None:  # pragma: no cover
            msg = "JSONSchema is not available, skipping schema validation"
            _VALIDATOR_LOGGER.warning(msg)
            errors.append(ValidationIssue(severity=VALIDATION_SEVERITY_WARNING, message=msg, path="(schema)"))
            return
        try:
            schema = self._load_schema()
            validate_fn = self._jsonschema_validate_fn or jsonschema.validate
            _ = validate_fn(config, schema)
        except jsonschema.ValidationError as e:  # type: ignore[union-attr]
            absolute_path = getattr(e, "absolute_path", None)
            path = ".".join(str(p) for p in absolute_path) if absolute_path else ""
            self._add_error(errors, "Schema validation error: {}".format(e.message), path=path)
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


YamlLocationIndex = Dict[str, Tuple[int, int]]


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


def _issues_to_rows(issues: Iterable[Any]) -> List[YamlValidationIssue]:
    rows: List[YamlValidationIssue] = []
    for issue in issues:
        path = getattr(issue, "path", "") or ""
        message = getattr(issue, "message", str(issue))
        suggestions = list(getattr(issue, "suggestions", []) or [])
        rows.append(YamlValidationIssue(path=path, message=message, suggestions=suggestions))
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


def _record_location(locations: YamlLocationIndex, path: List[str], mark: Any) -> None:
    if mark is None:
        return
    path_key = ".".join(path)
    if path_key in locations:
        return
    locations[path_key] = (mark.line + 1, mark.column + 1)


def _index_yaml_node(
    node: Any,
    path: List[str],
    locations: YamlLocationIndex,
    *,
    record_current: bool = True,
) -> None:
    if node is None:
        return
    if record_current:
        _record_location(locations, path, getattr(node, "start_mark", None))

    if isinstance(node, MappingNode):
        for key_node, value_node in node.value:
            key = str(getattr(key_node, "value", ""))
            key_path = [*path, key]
            _record_location(locations, key_path, getattr(key_node, "start_mark", None))
            _index_yaml_node(value_node, key_path, locations, record_current=False)
        return

    if isinstance(node, SequenceNode):
        for idx, item_node in enumerate(node.value):
            idx_path = [*path, str(idx)]
            _record_location(locations, idx_path, getattr(item_node, "start_mark", None))
            _index_yaml_node(item_node, idx_path, locations, record_current=False)


def _compose_yaml_node(yaml_text: str) -> Optional[object]:
    return cast("Optional[object]", yaml.compose(yaml_text, Loader=yaml.SafeLoader))  # pyright: ignore[reportUnknownMemberType]


def build_yaml_location_index(yaml_text: str) -> YamlLocationIndex:
    try:
        root = _compose_yaml_node(yaml_text)
    except Exception:  # noqa: BLE001
        return {}
    if root is None:
        return {}
    locations: YamlLocationIndex = {}
    _index_yaml_node(root, [], locations, record_current=True)
    return locations


def lookup_yaml_location(path: str, locations: YamlLocationIndex) -> Optional[Tuple[int, int]]:
    if path in locations:
        return locations[path]
    if not path:
        return locations.get("")
    parts = path.split(".")
    while parts:
        _ = parts.pop()
        candidate = ".".join(parts)
        if candidate in locations:
            return locations[candidate]
    return locations.get("")


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
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    if mark is None:
        return None
    line = getattr(mark, "line", None)
    column = getattr(mark, "column", None)
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
                    message="YAML parse error: {}".format(exc),
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

    ok = (not errors) and (not (strict_unknown_fields and warnings))
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
