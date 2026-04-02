import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, cast

from ..dsl.by_yaml._internal.config_parsing.error_envelope import ErrorEnvelope, ScalimYamlValidationError
from ..dsl.by_yaml._internal.config_parsing.imports import ScalimYamlImportExpansionError, contains_import_syntax, expand_imports_inplace
from ..dsl.by_yaml._internal.config_parsing.jsonschema_issues import ScalimJsonSchemaCollectorError, collect_jsonschema_validation_issues
from ..dsl.by_yaml._internal.config_parsing.unknown_fields import UnknownFieldIssue, find_unknown_fields
from ..dsl.by_yaml._internal.config_parsing.validator import ConfigValidator
from ..dsl.by_yaml._internal.config_parsing.validators.issues import ValidationIssue
from ..dsl.by_yaml._internal.config_parsing.yaml_load import (
    YamlLocationIndex,
    envelope_from_validation_issue,
    error_loc_for_yaml_path,
    load_yaml_mapping_text,
)
from ..dsl.by_yaml.workflow_config import load_workflow_config_from_mapping
from ..dsl.by_yaml.workflow_paths import resolve_workflow_demand_path
from ..dsl.by_yaml.workflow_types import ScalimWorkflowConfigError
from ..exceptions import safe_error_message, safe_error_type
from ..vendor.compact.importlibx import import_module
from ..vendor.dataclassesx import dataclass, field
from ..vendor.yamlx import yaml
from . import yaml_dsl_lsp

try:
    jsonschema = import_module("jsonschema")
except ImportError:
    jsonschema = None  # type: ignore[assignment]
    _HAS_JSONSCHEMA = False  # pyright: ignore[reportConstantRedefinition]
else:
    _HAS_JSONSCHEMA = True


@dataclass
class ValidationPayload:
    mode: str
    """校验模式(例如 `validator`/`schema`)."""

    ok: bool
    """是否通过校验."""

    yaml_path: Optional[str] = None
    """可选:被校验的 `YAML` 文件路径."""

    schema_path: Optional[str] = None
    """可选:使用的 `JSON Schema` 文件路径."""

    errors: List[ErrorEnvelope] = field(default_factory=list)
    """错误列表."""

    warnings: List[ErrorEnvelope] = field(default_factory=list)
    """告警列表."""

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "mode": self.mode,
            "ok": self.ok,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }
        if self.yaml_path is not None:
            payload["yaml_path"] = self.yaml_path
        if self.schema_path is not None:
            payload["schema_path"] = self.schema_path
        return payload


@dataclass
class WorkflowValidationPayload:
    mode: str
    ok: bool
    workflow_yaml_path: str
    results: List[ValidationPayload] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "ok": self.ok,
            "workflow_yaml_path": self.workflow_yaml_path,
            "results": [item.as_dict() for item in self.results],
        }


LEGACY_FIELDS = {
    "relations_sql_like",
    "relations_graph",
    "foreign_key",
    "target",
    "from",
    "via",
    "column",
    "pk",
    "pk_transform",
    "derived",
    "key_transform",
    "primary",
}


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("yaml-dsl", help="YAML DSL utilities")
    _set_help_default(parser)
    yaml_subparsers = parser.add_subparsers(dest="yaml_dsl_command")

    validate_parser = yaml_subparsers.add_parser("validate", help="Validate YAML DSL via internal validator")
    _add_validate_args(validate_parser)
    validate_parser.set_defaults(func=_run_validate)

    schema_parser = yaml_subparsers.add_parser("schema", help="Schema helpers")
    _set_help_default(schema_parser)
    schema_subparsers = schema_parser.add_subparsers(dest="yaml_dsl_schema_command")

    schema_validate_parser = schema_subparsers.add_parser("validate", help="Validate YAML DSL via JSON Schema")
    _add_schema_validate_args(schema_validate_parser)
    schema_validate_parser.set_defaults(func=_run_schema_validate)

    schema_show_parser = schema_subparsers.add_parser("show", help="Print JSON Schema")
    _ = schema_show_parser.add_argument(
        "--type",
        dest="schema_type",
        type=str,
        default=yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE,
        help="Schema 类型(例如 demand/workflow/scalim_yaml)",
    )
    schema_show_parser.set_defaults(func=_run_schema_show)

    schema_path_parser = schema_subparsers.add_parser("path", help="Print JSON Schema path")
    _ = schema_path_parser.add_argument(
        "--type",
        dest="schema_type",
        type=str,
        default=yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE,
        help="Schema 类型(例如 demand/workflow/scalim_yaml)",
    )
    schema_path_parser.set_defaults(func=_run_schema_path)

    upsert_parser = yaml_subparsers.add_parser(
        "upsert-lsp-comment",
        help="Upsert YAML $schema modeline comment (JetBrains/RedHat)",
    )
    _add_upsert_lsp_comment_args(upsert_parser)
    upsert_parser.set_defaults(func=_run_upsert_lsp_comment)


def _set_help_default(parser: argparse.ArgumentParser) -> None:
    def _show_help(_args: argparse.Namespace) -> int:
        parser.print_help()
        return 2

    parser.set_defaults(func=_show_help)


def _add_validate_args(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("yaml_file", type=Path, help="YAML 文件路径")
    _ = parser.add_argument("--schema", "-s", type=Path, default=None, help="JSON Schema 文件路径")
    _ = parser.add_argument(
        "--type",
        dest="yaml_type",
        type=str,
        choices=["auto", "demand", "workflow"],
        default="auto",
        help="校验类型: auto/demand/workflow",
    )
    _ = parser.add_argument(
        "--path-alias",
        dest="path_aliases",
        type=str,
        action="append",
        default=[],
        help="仅 workflow validate: 需求路径别名,格式 <alias>=<path> (可重复)",
    )
    _ = parser.add_argument(
        "--allowed-yaml-root",
        dest="allowed_yaml_roots",
        type=Path,
        action="append",
        default=[],
        help="允许读取 YAML 的根目录(可重复);默认仅允许入口 YAML 所在目录",
    )
    _ = parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    _ = parser.add_argument("--verbose", "-v", action="store_true", help="显示详细错误信息")


def _add_schema_validate_args(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("yaml_file", type=Path, help="YAML 文件路径")
    _ = parser.add_argument("--schema", "-s", type=Path, default=None, help="JSON Schema 文件路径")
    _ = parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    _ = parser.add_argument("--verbose", "-v", action="store_true", help="显示详细错误信息")


def _add_upsert_lsp_comment_args(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "paths",
        type=Path,
        nargs="+",
        help="一个或多个 YAML 文件路径",
    )
    _ = parser.add_argument(
        "--type",
        dest="schema_type",
        type=str,
        default=yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE,
        help="Schema 类型(例如 demand/workflow)",
    )
    _ = parser.add_argument(
        "--schema-path",
        dest="schema_path",
        type=str,
        default=yaml_dsl_lsp.DEFAULT_SCHEMA_PATH,
        help="Schema base URL/dir 或完整 .json URL/path(默认使用内置 schema 目录)",
    )
    _ = parser.add_argument(
        "--comment-style",
        dest="comment_style",
        type=str,
        choices=list(yaml_dsl_lsp.COMMENT_STYLE_CHOICES),
        default=yaml_dsl_lsp.DEFAULT_COMMENT_STYLE,
        help="Schema modeline 风格: all/jetbrains/redhat",
    )


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "dsl" / "by_yaml" / "schema" / "demand.gen.json"


def _resolve_schema_path(arg: Optional[Path]) -> Path:
    return arg.resolve() if arg is not None else _default_schema_path()


_SCHEMA_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def _schema_path_for_schema_type(schema_type: str) -> Path:
    schema_type = (schema_type or "").strip() or yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE
    if not _SCHEMA_TYPE_PATTERN.match(schema_type):
        msg = "Invalid schema type: {}".format(schema_type)
        raise ValueError(msg)
    return Path(__file__).resolve().parents[1] / "dsl" / "by_yaml" / "schema" / "{}.gen.json".format(schema_type)


def _load_json_schema(schema_path: Path) -> Dict[str, Any]:
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _find_legacy_field_errors(
    yaml_data: Dict[str, Any],
    *,
    source_path: str,
    locations: YamlLocationIndex,
) -> List[ErrorEnvelope]:
    errors: List[ErrorEnvelope] = []

    _collect_legacy_fields(errors, yaml_data, None, source_path=source_path, locations=locations)

    sources = yaml_data.get("sources", {})
    if isinstance(sources, dict):
        sources_dict = cast("Dict[str, Any]", sources)  # pragma: allow-cast yaml mapping typed narrowing for legacy field scan
        for source_id, source_data in sources_dict.items():
            if not isinstance(source_data, dict):
                continue
            source_data_dict = cast("Dict[str, Any]", source_data)  # pragma: allow-cast yaml mapping typed narrowing for legacy field scan
            _collect_legacy_fields(
                errors,
                source_data_dict,
                "sources.{}".format(source_id),
                source_path=source_path,
                locations=locations,
            )

    fields = yaml_data.get("fields", {})
    if isinstance(fields, dict):
        fields_dict = cast("Dict[str, Any]", fields)  # pragma: allow-cast yaml mapping typed narrowing for legacy field scan
        for field_id, field_data in fields_dict.items():
            if not isinstance(field_data, dict):
                continue
            field_data_dict = cast("Dict[str, Any]", field_data)  # pragma: allow-cast yaml mapping typed narrowing for legacy field scan
            _collect_legacy_fields(
                errors,
                field_data_dict,
                "fields.{}".format(field_id),
                source_path=source_path,
                locations=locations,
            )

    return errors


def _collect_legacy_fields(
    errors: List[ErrorEnvelope],
    data: Dict[str, Any],
    prefix: Optional[str],
    *,
    source_path: str,
    locations: YamlLocationIndex,
) -> None:
    for key in data:
        if key not in LEGACY_FIELDS:
            continue
        path = "{}.{}".format(prefix, key) if prefix else str(key)
        errors.append(
            ErrorEnvelope(
                code="yaml_legacy_field",
                message="Legacy field '{}' is not allowed".format(key),
                source_path=source_path,
                path=path,
                loc=error_loc_for_yaml_path(path, locations),
            )
        )


def _issues_to_rows(
    issues: Iterable[object],
    *,
    source_path: str,
    locations: YamlLocationIndex,
    default_code: str,
) -> List[ErrorEnvelope]:
    rows: List[ErrorEnvelope] = []
    for issue in issues:
        if isinstance(issue, ErrorEnvelope):
            rows.append(issue)
            continue
        if isinstance(issue, ValidationIssue):
            rows.append(
                envelope_from_validation_issue(
                    issue,
                    source_path=source_path,
                    locations=locations,
                    default_code=default_code,
                )
            )
            continue
        if isinstance(issue, UnknownFieldIssue):
            path = str(issue.path or "(root)")
            rows.append(
                ErrorEnvelope(
                    code=str(default_code),
                    message=str(issue.message),
                    source_path=source_path,
                    path=path,
                    loc=error_loc_for_yaml_path(path, locations),
                    suggestions=tuple(issue.suggestions),
                )
            )
            continue
        rows.append(
            ErrorEnvelope(
                code=str(default_code),
                message=str(issue),
                source_path=source_path,
                path="(root)",
                loc=error_loc_for_yaml_path("(root)", locations),
            )
        )
    return rows


def _find_removed_outputs_defaults_errors(
    yaml_data: Optional[Dict[str, Any]],
    *,
    source_path: str,
    locations: Optional[YamlLocationIndex],
    default_code: str,
) -> List[ErrorEnvelope]:
    if not isinstance(yaml_data, dict) or "outputs_defaults" not in yaml_data:
        return []
    path = "outputs_defaults"
    loc = None if locations is None else error_loc_for_yaml_path(path, locations)
    return [
        ErrorEnvelope(
            code=default_code,
            message=(
                "outputs_defaults was removed; move the book binding to each Excel output's `outputs[*].to.book`. "
                "Reuse it with YAML anchors (`_templates`) or `$import` if needed."
            ),
            source_path=source_path,
            path=path,
            loc=loc,
        )
    ]


def _find_demand_book_binding_errors(
    yaml_data: Optional[Dict[str, Any]],
    *,
    source_path: str,
    locations: Optional[YamlLocationIndex],
    available_book_ids: Optional[Set[str]],
    default_code: str,
) -> List[ErrorEnvelope]:
    if not isinstance(yaml_data, dict):
        return []

    available = tuple(sorted(available_book_ids or set()))
    errors: List[ErrorEnvelope] = []
    for ref_path, book_id in _extract_demand_outputs_book_refs(yaml_data):
        loc = None if locations is None else error_loc_for_yaml_path(ref_path, locations)
        if not book_id:
            errors.append(
                ErrorEnvelope(
                    code=default_code,
                    message=(
                        "Missing outputs to.book binding; set `outputs[*].to.book` explicitly. "
                        "Reuse the binding with YAML anchors (`_templates`) or `$import` if needed."
                    ),
                    source_path=source_path,
                    path=ref_path,
                    loc=loc,
                    suggestions=available,
                )
            )
            continue
        if available_book_ids is not None and book_id not in available_book_ids:
            errors.append(
                ErrorEnvelope(
                    code=default_code,
                    message=(
                        "Unknown book id referenced by outputs binding: {!r} "
                        "(declare resources.books.{} in demand or workflow.resources.books.{} in workflow)"
                    ).format(book_id, book_id, book_id),
                    source_path=source_path,
                    path=ref_path,
                    loc=loc,
                    suggestions=available,
                )
            )
    return errors


def _retry_enabled_missing_should_retry(retry_raw: object) -> bool:
    if not isinstance(retry_raw, dict):
        return False
    retry_dict = cast("Dict[str, Any]", retry_raw)  # pragma: allow-cast yaml retry mapping typed narrowing
    if retry_dict.get("enabled") is not True:
        return False
    should_retry_raw = retry_dict.get("should_retry")
    if not isinstance(should_retry_raw, str):
        return True
    return not bool(should_retry_raw.strip())


def _find_retry_enabled_missing_should_retry_errors(
    yaml_data: Optional[Dict[str, Any]],
    *,
    source_path: str,
    locations: Optional[YamlLocationIndex],
    default_code: str,
) -> List[ErrorEnvelope]:
    if not isinstance(yaml_data, dict):
        return []

    def _add_error(path: str) -> ErrorEnvelope:
        loc = None if locations is None else error_loc_for_yaml_path(path, locations)
        return ErrorEnvelope(
            code=default_code,
            message=(
                "retry.enabled=true requires non-empty should_retry "
                "(provide it in YAML, or rely on runtime driver injection to supply it during compile/run)"
            ),
            source_path=source_path,
            path=path,
            loc=loc,
        )

    errors: List[ErrorEnvelope] = []
    if _retry_enabled_missing_should_retry(yaml_data.get("retry")):
        errors.append(_add_error("retry.should_retry"))

    main_source_raw = yaml_data.get("main_source")
    if isinstance(main_source_raw, dict):
        main_source_dict = cast("Dict[str, Any]", main_source_raw)  # pragma: allow-cast yaml main_source mapping typed narrowing
        if _retry_enabled_missing_should_retry(main_source_dict.get("retry")):
            errors.append(_add_error("main_source.retry.should_retry"))

    sources_raw = yaml_data.get("sources")
    if isinstance(sources_raw, dict):
        for source_id, source_cfg_raw in cast("Dict[str, Any]", sources_raw).items():  # pragma: allow-cast yaml sources typed narrowing
            if not isinstance(source_cfg_raw, dict):
                continue
            source_cfg_dict = cast("Dict[str, Any]", source_cfg_raw)  # pragma: allow-cast yaml source config mapping typed narrowing
            if _retry_enabled_missing_should_retry(source_cfg_dict.get("retry")):
                errors.append(_add_error("sources.{}.retry.should_retry".format(source_id)))

    return errors


def _write_line(text: str) -> None:
    _ = sys.stdout.write(text + "\n")


def _write_line_stderr(text: str) -> None:
    _ = sys.stderr.write(text + "\n")


def _write_raw(text: str) -> None:
    _ = sys.stdout.write(text)


def _display_issue_path(path: str) -> str:
    return path or "(root)"


def _format_issue_location(yaml_path: Path, issue: ErrorEnvelope) -> str:
    if issue.line is None:
        return str(yaml_path)
    if issue.column is not None:
        return "{}:{}:{}".format(yaml_path, issue.line, issue.column)
    return "{}:{}".format(yaml_path, issue.line)


def _emit_source_snippet(issue: ErrorEnvelope, source_lines: Optional[List[str]], *, verbose: bool) -> None:
    if source_lines is None or issue.line is None:
        return
    total_lines = len(source_lines)
    if total_lines == 0:
        return
    line_no = max(1, min(issue.line, total_lines))
    if verbose:
        start = max(1, line_no - 1)
        end = min(total_lines, line_no + 1)
    else:
        start = line_no
        end = line_no

    _write_line("  |")
    for current in range(start, end + 1):
        text = source_lines[current - 1].rstrip("\n")
        _write_line("{:>4} | {}".format(current, text))
        if current == line_no:
            column = issue.column or 1
            pointer = " " * max(column - 1, 0)
            _write_line("  | {}^".format(pointer))


def _print_linter_result(
    yaml_path: Path,
    *,
    errors: List[ErrorEnvelope],
    warnings: List[ErrorEnvelope],
    verbose: bool,
    source_lines: Optional[List[str]],
) -> None:
    if not errors and not warnings:
        _write_line("OK {}".format(yaml_path.name))
        return

    for issue in errors:
        path_suffix = _display_issue_path(issue.path)
        message = issue.message
        if path_suffix != "(root)":
            message = "{} [{}]".format(message, path_suffix)
        _write_line("ERROR {} --> {}".format(message, _format_issue_location(yaml_path, issue)))
        _emit_source_snippet(issue, source_lines, verbose=verbose)
        if issue.suggestions:
            _write_line("help: {}".format(", ".join(issue.suggestions)))
        _write_line("")

    for issue in warnings:
        path_suffix = _display_issue_path(issue.path)
        message = issue.message
        if path_suffix != "(root)":
            message = "{} [{}]".format(message, path_suffix)
        _write_line("WARN {} --> {}".format(message, _format_issue_location(yaml_path, issue)))
        _emit_source_snippet(issue, source_lines, verbose=verbose)
        if issue.suggestions:
            _write_line("help: {}".format(", ".join(issue.suggestions)))
        _write_line("")

    summary_parts: List[str] = []
    if errors:
        summary_parts.append("{} error{}".format(len(errors), "" if len(errors) == 1 else "s"))
    if warnings:
        summary_parts.append("{} warning{}".format(len(warnings), "" if len(warnings) == 1 else "s"))
    summary = ", ".join(summary_parts) if summary_parts else "no issues"
    _write_line("Found {}.".format(summary))


def _render_result(
    yaml_path: Path,
    *,
    errors: List[ErrorEnvelope],
    warnings: List[ErrorEnvelope],
    verbose: bool,
    source_lines: Optional[List[str]],
) -> None:
    _print_linter_result(
        yaml_path,
        errors=errors,
        warnings=warnings,
        verbose=verbose,
        source_lines=source_lines,
    )


def _emit_error(
    message: str,
    *,
    json_output: bool,
    yaml_path: Optional[Path] = None,
    schema_path: Optional[Path] = None,
    mode: Optional[str] = None,
) -> None:
    if json_output:
        source_path = str(yaml_path) if yaml_path is not None else "(unknown)"
        payload = ValidationPayload(
            mode=mode or "error",
            ok=False,
            yaml_path=str(yaml_path) if yaml_path is not None else None,
            schema_path=str(schema_path) if schema_path is not None else None,
            errors=[
                ErrorEnvelope(
                    code="cli_error",
                    message=message,
                    source_path=source_path,
                    path="(root)",
                    loc=None,
                )
            ],
        )
        _write_line(json.dumps(payload.as_dict(), ensure_ascii=False))
        return
    _write_line_stderr("错误: {}".format(message))


def _infer_yaml_type(yaml_text: str) -> str:
    try:
        yaml_data = yaml.safe_load(yaml_text)
    except Exception:  # noqa: BLE001
        return "demand"
    if isinstance(yaml_data, dict) and "workflow" in yaml_data:
        return "workflow"
    return "demand"


def _parse_path_aliases(raw_values: Iterable[str]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    output: Dict[str, str] = {}
    for raw in raw_values:
        item = str(raw or "").strip()
        if not item:
            continue
        if "=" not in item:
            return None, "Invalid --path-alias value: {!r} (expected <alias>=<path>)".format(item)
        alias, base = item.split("=", 1)
        alias = str(alias or "").strip()
        base = str(base or "").strip()
        if not alias:
            return None, "Invalid --path-alias value: {!r} (alias must be non-empty)".format(item)
        if not base:
            return None, "Invalid --path-alias value: {!r} (path must be non-empty)".format(item)
        output[alias] = base
    return output, None


def _extract_demand_book_ids(yaml_data: Optional[Dict[str, Any]]) -> Set[str]:
    if not isinstance(yaml_data, dict):
        return set()
    resources_obj = yaml_data.get("resources")
    if not isinstance(resources_obj, dict):
        return set()
    resources = cast("Dict[str, Any]", resources_obj)  # pragma: allow-cast yaml mapping typed narrowing
    books_obj = resources.get("books")
    if not isinstance(books_obj, dict):
        return set()
    books = cast("Dict[str, Any]", books_obj)  # pragma: allow-cast yaml mapping typed narrowing
    out: Set[str] = set()
    for raw_book_id in books:
        if not isinstance(raw_book_id, str):
            continue
        bid = str(raw_book_id or "").strip()
        if bid:
            out.add(bid)
    return out


def _extract_output_book_ref(item: Dict[str, Any], *, idx: int) -> Tuple[str, str]:
    to_raw_obj = item.get("to")
    if isinstance(to_raw_obj, dict):
        to_raw = cast("Dict[str, Any]", to_raw_obj)  # pragma: allow-cast yaml mapping typed narrowing
        book_raw = to_raw.get("book")
        if isinstance(book_raw, str) and book_raw.strip():
            return "outputs.{}.to.book".format(int(idx)), str(book_raw).strip()
    return "outputs.{}.to.book".format(int(idx)), ""


def _extract_demand_outputs_book_refs(yaml_data: Optional[Dict[str, Any]]) -> List[Tuple[str, str]]:
    """提取需求 `outputs` 中绑定到 `books` 的引用信息.

    返回 `(ref_path, book_id)` 列表:
    - 对于包含 `container` 的 `outputs[*]`(`CSV` 文件输出),不返回任何项.
    - 若某个输出缺失有效 `book_id`,仍返回其 `ref_path`,但 `book_id` 为空字符串.
    """
    if not isinstance(yaml_data, dict):
        return []
    outputs_raw = yaml_data.get("outputs")
    if not isinstance(outputs_raw, list):
        return []
    outputs_list = cast("List[Any]", outputs_raw)  # pragma: allow-cast yaml outputs typed narrowing

    out: List[Tuple[str, str]] = []
    for idx, item in enumerate(outputs_list):
        if not isinstance(item, dict):
            continue
        item_dict = cast("Dict[str, Any]", item)  # pragma: allow-cast yaml mapping typed narrowing
        if item_dict.get("container") is not None:
            continue
        out.append(_extract_output_book_ref(item_dict, idx=int(idx)))

    return out


def _validate_demand_yaml_text(
    yaml_text: str,
    *,
    yaml_path: Path,
    schema_path: Path,
    validator: Optional[ConfigValidator] = None,
    allowed_yaml_roots: Optional[Sequence[Path]] = None,
    available_book_ids: Optional[Set[str]] = None,
) -> Tuple[ValidationPayload, Optional[Dict[str, Any]], Optional[List[str]]]:
    source_lines: List[str] = yaml_text.splitlines()
    try:
        yaml_data_dict, locations, _lines = load_yaml_mapping_text(
            yaml_text,
            source_path=str(yaml_path),
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        return (
            ValidationPayload(
                mode="validate",
                ok=False,
                yaml_path=str(yaml_path),
                schema_path=str(schema_path),
                errors=list(exc.errors),
                warnings=list(exc.warnings),
            ),
            None,
            source_lines,
        )

    try:
        if contains_import_syntax(yaml_data_dict):
            _ = expand_imports_inplace(yaml_data_dict, yaml_path=yaml_path, allowed_yaml_roots=allowed_yaml_roots)
    except ScalimYamlImportExpansionError as exc:
        logical_path = str(exc.logical_path or "(root)")
        errors = [
            ErrorEnvelope(
                code="yaml_import_expansion_error",
                message=str(exc),
                source_path=str(yaml_path),
                path=logical_path,
                loc=error_loc_for_yaml_path(logical_path, locations),
            )
        ]
        return (
            ValidationPayload(
                mode="validate",
                ok=False,
                yaml_path=str(yaml_path),
                schema_path=str(schema_path),
                errors=errors,
                warnings=[],
            ),
            None,
            source_lines,
        )

    demand_validator = validator or ConfigValidator(schema_path=str(schema_path))
    report = demand_validator.validate_report(
        yaml_data_dict,
        strict_unknown_fields=True,
        enable_jsonschema_validation=True,
    )
    errors = [
        envelope_from_validation_issue(
            issue,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_error",
        )
        for issue in report.errors()
    ]
    warnings = [
        envelope_from_validation_issue(
            issue,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_warning",
        )
        for issue in report.warnings()
    ]
    demand_book_ids = _extract_demand_book_ids(yaml_data_dict)
    effective_book_ids = set(demand_book_ids)
    if available_book_ids is not None:
        effective_book_ids.update(available_book_ids)
    errors.extend(
        _find_removed_outputs_defaults_errors(
            yaml_data_dict,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_error",
        )
    )
    errors.extend(
        _find_demand_book_binding_errors(
            yaml_data_dict,
            source_path=str(yaml_path),
            locations=locations,
            available_book_ids=effective_book_ids,
            default_code="yaml_validate_error",
        )
    )
    errors.extend(
        _find_retry_enabled_missing_should_retry_errors(
            yaml_data_dict,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_error",
        )
    )

    ok = not errors
    return (
        ValidationPayload(
            mode="validate",
            ok=ok,
            yaml_path=str(yaml_path),
            schema_path=str(schema_path),
            errors=errors,
            warnings=warnings,
        ),
        yaml_data_dict,
        source_lines,
    )


def _validate_demand_yaml_path(
    yaml_path: Path,
    *,
    schema_path: Path,
    validator: Optional[ConfigValidator] = None,
    allowed_yaml_roots: Optional[Sequence[Path]] = None,
    available_book_ids: Optional[Set[str]] = None,
) -> Tuple[ValidationPayload, Optional[Dict[str, Any]], Optional[List[str]]]:
    if not yaml_path.exists():
        errors = [
            ErrorEnvelope(
                code="yaml_file_not_found",
                message="YAML 文件不存在: {}".format(yaml_path),
                source_path=str(yaml_path),
                path="(file)",
                loc=None,
            )
        ]
        return (
            ValidationPayload(
                mode="validate",
                ok=False,
                yaml_path=str(yaml_path),
                schema_path=str(schema_path),
                errors=errors,
                warnings=[],
            ),
            None,
            None,
        )
    try:
        yaml_text = yaml_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        errors = [
            ErrorEnvelope(
                code="yaml_file_read_error",
                message="YAML 文件读取失败: {}".format(yaml_path),
                source_path=str(yaml_path),
                path="(file)",
                loc=None,
            )
        ]
        return (
            ValidationPayload(
                mode="validate",
                ok=False,
                yaml_path=str(yaml_path),
                schema_path=str(schema_path),
                errors=errors,
                warnings=[],
            ),
            None,
            None,
        )
    return _validate_demand_yaml_text(
        yaml_text,
        yaml_path=yaml_path,
        schema_path=schema_path,
        validator=validator,
        allowed_yaml_roots=allowed_yaml_roots,
        available_book_ids=available_book_ids,
    )


def _run_validate(args: argparse.Namespace) -> int:  # noqa: C901, PLR0912, PLR0915
    yaml_path = args.yaml_file.resolve()
    schema_path = _resolve_schema_path(args.schema)
    args_dict = vars(args)
    yaml_type = str(args_dict.get("yaml_type", "auto") or "auto").strip()
    if yaml_type == "auto":
        try:
            yaml_text = yaml_path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            yaml_text = ""
        yaml_type = _infer_yaml_type(yaml_text)
    raw_aliases = list(args_dict.get("path_aliases", []) or [])
    path_aliases, alias_error = _parse_path_aliases(raw_aliases)
    if alias_error is not None:
        _emit_error(alias_error, json_output=bool(args.json), yaml_path=yaml_path, schema_path=schema_path, mode="validate")
        return 1
    allowed_yaml_roots = list(args_dict.get("allowed_yaml_roots", []) or [])

    if not schema_path.exists():
        _emit_error(
            "Schema 文件不存在: {}".format(schema_path),
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="validate",
        )
        return 1

    if yaml_type == "workflow":
        try:
            workflow_text = yaml_path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            _emit_error(
                "YAML 文件读取失败: {}".format(yaml_path),
                json_output=args.json,
                yaml_path=yaml_path,
                schema_path=schema_path,
                mode="workflow-validate",
            )
            return 1

        workflow_source_lines: List[str] = workflow_text.splitlines()
        workflow_locations: YamlLocationIndex = {}
        workflow_errors: List[ErrorEnvelope] = []
        workflow_warnings: List[ErrorEnvelope] = []

        wf_config = None
        try:
            root, workflow_locations, _lines = load_yaml_mapping_text(
                workflow_text,
                source_path=str(yaml_path),
                detect_duplicate_keys=True,
            )
        except ScalimYamlValidationError as exc:
            workflow_errors.extend(list(exc.errors))
            workflow_warnings.extend(list(exc.warnings))
        else:
            try:
                wf_config = load_workflow_config_from_mapping(root)
            except ScalimWorkflowConfigError as exc:
                path = str(exc.path or "(root)")
                workflow_errors.append(
                    ErrorEnvelope(
                        code="workflow_validate_error",
                        message=str(exc),
                        source_path=str(yaml_path),
                        path=path,
                        loc=error_loc_for_yaml_path(path, workflow_locations),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                safe_type = safe_error_type(exc)
                safe_msg = safe_error_message(exc) or ""
                workflow_errors.append(
                    ErrorEnvelope(
                        code="workflow_validate_error",
                        message="Unexpected error: {}: {}".format(safe_type, safe_msg),
                        source_path=str(yaml_path),
                        path="(root)",
                        loc=error_loc_for_yaml_path("(root)", workflow_locations),
                    )
                )

        demand_results: List[ValidationPayload] = []
        demand_source_lines: List[Optional[List[str]]] = []
        demand_yaml_data: List[Optional[Dict[str, Any]]] = []

        demand_validator = ConfigValidator(schema_path=str(schema_path))
        if wf_config is not None:
            workflow_book_ids = set((wf_config.resources.books or {}).keys())
            for run_idx, run in enumerate(wf_config.runs):
                demand_path: Optional[Path] = None
                try:
                    demand_path = resolve_workflow_demand_path(
                        str(run.demand),
                        workflow_yaml_path=str(yaml_path),
                        path_aliases=path_aliases,
                        run_id=str(run.id),
                        allowed_yaml_roots=allowed_yaml_roots,
                    )
                except ScalimWorkflowConfigError as exc:
                    wf_path = "workflow.runs.{}.demand".format(int(run_idx))
                    workflow_errors.append(
                        ErrorEnvelope(
                            code="workflow_validate_error",
                            message=str(exc),
                            source_path=str(yaml_path),
                            path=wf_path,
                            loc=error_loc_for_yaml_path(wf_path, workflow_locations),
                        )
                    )
                    demand_results.append(
                        ValidationPayload(
                            mode="validate",
                            ok=False,
                            yaml_path=str(run.demand),
                            schema_path=str(schema_path),
                            errors=[
                                ErrorEnvelope(
                                    code="demand_path_resolve_failed",
                                    message="Demand path resolve failed: {}".format(str(exc)),
                                    source_path=str(run.demand),
                                    path="(file)",
                                    loc=None,
                                )
                            ],
                            warnings=[],
                        )
                    )
                    demand_source_lines.append(None)
                    demand_yaml_data.append(None)
                    continue

                if not demand_path.exists():
                    workflow_errors.append(
                        ErrorEnvelope(
                            code="demand_file_not_found",
                            message="Demand YAML 文件不存在: {}".format(demand_path),
                            source_path=str(yaml_path),
                            path="workflow.runs.{}.demand".format(int(run_idx)),
                            loc=error_loc_for_yaml_path(
                                "workflow.runs.{}.demand".format(int(run_idx)),
                                workflow_locations,
                            ),
                        )
                    )
                    payload, demand_data, lines = _validate_demand_yaml_path(
                        demand_path,
                        schema_path=schema_path,
                        validator=demand_validator,
                        allowed_yaml_roots=allowed_yaml_roots,
                        available_book_ids=workflow_book_ids,
                    )
                    demand_results.append(payload)
                    demand_source_lines.append(lines)
                    demand_yaml_data.append(demand_data)
                    continue

                payload, demand_data, lines = _validate_demand_yaml_path(
                    demand_path,
                    schema_path=schema_path,
                    validator=demand_validator,
                    allowed_yaml_roots=allowed_yaml_roots,
                    available_book_ids=workflow_book_ids,
                )
                demand_results.append(payload)
                demand_source_lines.append(lines)
                demand_yaml_data.append(demand_data)
        workflow_ok = not workflow_errors

        workflow_payload = ValidationPayload(
            mode="workflow-validate",
            ok=workflow_ok,
            yaml_path=str(yaml_path),
            errors=workflow_errors,
            warnings=workflow_warnings,
        )

        results: List[ValidationPayload] = [workflow_payload]
        results.extend(demand_results)

        ok = workflow_ok and all(item.ok for item in demand_results)
        payload = WorkflowValidationPayload(
            mode="workflow-validate",
            ok=ok,
            workflow_yaml_path=str(yaml_path),
            results=results,
        )

        if args.json:
            _write_line(json.dumps(payload.as_dict(), ensure_ascii=False))
        else:
            _render_result(
                yaml_path,
                errors=workflow_payload.errors,
                warnings=workflow_payload.warnings,
                verbose=args.verbose,
                source_lines=workflow_source_lines,
            )
            for idx, item in enumerate(demand_results):
                demand_path_str = item.yaml_path or ""
                demand_path = Path(demand_path_str) if demand_path_str else Path("demand.yaml")
                _render_result(
                    demand_path,
                    errors=item.errors,
                    warnings=item.warnings,
                    verbose=args.verbose,
                    source_lines=demand_source_lines[idx] if idx < len(demand_source_lines) else None,
                )

        return 0 if ok else 1

    try:
        yaml_text = yaml_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        _emit_error(
            "YAML 文件读取失败: {}".format(yaml_path),
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="validate",
        )
        return 1

    payload, _yaml_data, source_lines = _validate_demand_yaml_text(
        yaml_text,
        yaml_path=yaml_path,
        schema_path=schema_path,
        allowed_yaml_roots=allowed_yaml_roots,
    )

    if args.json:
        _write_line(json.dumps(payload.as_dict(), ensure_ascii=False))
    else:
        _render_result(
            yaml_path,
            errors=payload.errors,
            warnings=payload.warnings,
            verbose=args.verbose,
            source_lines=source_lines,
        )

    return 0 if payload.ok else 1


def _run_schema_validate(args: argparse.Namespace) -> int:
    schema_path = _resolve_schema_path(args.schema)
    yaml_path = args.yaml_file.resolve()
    schema, exit_code = _load_schema_or_error(schema_path, yaml_path=yaml_path, args=args)
    if exit_code != 0 or schema is None:
        return exit_code

    try:
        yaml_text = yaml_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        _emit_error(
            "YAML 文件读取失败: {}".format(yaml_path),
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="schema-validate",
        )
        return 1
    source_lines: Optional[List[str]] = yaml_text.splitlines()

    try:
        yaml_data_dict, locations, _lines = load_yaml_mapping_text(
            yaml_text,
            source_path=str(yaml_path),
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        return _emit_schema_result(
            yaml_path,
            schema_path,
            list(exc.errors),
            list(exc.warnings),
            args,
            ok=False,
            source_lines=source_lines,
        )

    jsonschema_module = _get_jsonschema_module(args, yaml_path=yaml_path, schema_path=schema_path)
    if jsonschema_module is None:
        return 1

    try:
        if contains_import_syntax(yaml_data_dict) and contains_import_syntax(schema):
            _ = expand_imports_inplace(yaml_data_dict, yaml_path=yaml_path)
    except ScalimYamlImportExpansionError as exc:
        logical_path = str(exc.logical_path or "(root)")
        errors = [
            ErrorEnvelope(
                code="yaml_import_expansion_error",
                message=str(exc),
                source_path=str(yaml_path),
                path=logical_path,
                loc=error_loc_for_yaml_path(logical_path, locations),
            )
        ]
        return _emit_schema_result(yaml_path, schema_path, errors, [], args, ok=False, source_lines=source_lines)

    errors, warnings = _collect_schema_issues(
        yaml_data_dict,
        schema,
        args,
        jsonschema_module,
        source_path=str(yaml_path),
        locations=locations,
    )
    ok = not errors

    return _emit_schema_result(
        yaml_path,
        schema_path,
        errors,
        warnings,
        args,
        ok=ok,
        source_lines=source_lines,
    )


def _load_schema_or_error(
    schema_path: Path,
    *,
    yaml_path: Path,
    args: argparse.Namespace,
) -> Tuple[Optional[Dict[str, Any]], int]:
    if not schema_path.exists():
        _emit_error(
            "Schema 文件不存在: {}".format(schema_path),
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="schema-validate",
        )
        return None, 1

    try:
        return _load_json_schema(schema_path), 0
    except json.JSONDecodeError:
        _emit_error(
            "Schema JSON 无法解析: {}".format(schema_path),
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="schema-validate",
        )
        return None, 1


def _get_jsonschema_module(
    args: argparse.Namespace,
    *,
    yaml_path: Path,
    schema_path: Path,
) -> Optional[Any]:
    if _HAS_JSONSCHEMA and jsonschema is not None:
        return jsonschema
    _emit_error(
        "缺少 jsonschema 依赖,请安装 scalim[cli]",
        json_output=args.json,
        yaml_path=yaml_path,
        schema_path=schema_path,
        mode="schema-validate",
    )
    return None


def _collect_schema_issues(
    yaml_data: Dict[str, Any],
    schema: Dict[str, Any],
    args: argparse.Namespace,
    jsonschema_module: Any,
    *,
    source_path: str,
    locations: YamlLocationIndex,
) -> Tuple[List[ErrorEnvelope], List[ErrorEnvelope]]:
    try:
        issues = collect_jsonschema_validation_issues(
            yaml_data,
            schema,
            jsonschema_module=jsonschema_module,
            include_context=bool(args.verbose),
            filter_additional_properties=True,
        )
    except ScalimJsonSchemaCollectorError as exc:
        errors = [
            ErrorEnvelope(
                code="yaml_schema_validate_error",
                message=str(exc),
                source_path=source_path,
                path="(root)",
                loc=error_loc_for_yaml_path("(root)", locations),
            )
        ]
        return errors, []

    errors = _issues_to_rows(
        issues,
        source_path=source_path,
        locations=locations,
        default_code="yaml_schema_validate_error",
    )
    errors.extend(
        _find_legacy_field_errors(
            yaml_data,
            source_path=source_path,
            locations=locations,
        )
    )
    errors.extend(
        _issues_to_rows(
            find_unknown_fields(yaml_data, schema),
            source_path=source_path,
            locations=locations,
            default_code="yaml_unknown_field",
        )
    )
    demand_book_ids = _extract_demand_book_ids(yaml_data)
    errors.extend(
        _find_removed_outputs_defaults_errors(
            yaml_data,
            source_path=source_path,
            locations=locations,
            default_code="yaml_schema_validate_error",
        )
    )
    errors.extend(
        _find_demand_book_binding_errors(
            yaml_data,
            source_path=source_path,
            locations=locations,
            available_book_ids=demand_book_ids,
            default_code="yaml_schema_validate_error",
        )
    )
    errors.extend(
        _find_retry_enabled_missing_should_retry_errors(
            yaml_data,
            source_path=source_path,
            locations=locations,
            default_code="yaml_schema_validate_error",
        )
    )
    return errors, []


def _emit_schema_result(
    yaml_path: Path,
    schema_path: Path,
    errors: List[ErrorEnvelope],
    warnings: List[ErrorEnvelope],
    args: argparse.Namespace,
    *,
    ok: bool,
    source_lines: Optional[List[str]],
) -> int:
    if args.json:
        payload = ValidationPayload(
            mode="schema-validate",
            ok=ok,
            yaml_path=str(yaml_path),
            schema_path=str(schema_path),
            errors=errors,
            warnings=warnings,
        )
        _write_line(json.dumps(payload.as_dict(), ensure_ascii=False))
    else:
        _render_result(
            yaml_path,
            errors=errors,
            warnings=warnings,
            verbose=args.verbose,
            source_lines=source_lines,
        )
    return 0 if ok else 1


def _run_schema_show(args: argparse.Namespace) -> int:
    args_dict = vars(args)
    schema_type = str(args_dict.get("schema_type", yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE) or yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE)
    try:
        schema_path = _schema_path_for_schema_type(schema_type)
    except ValueError as exc:
        _emit_error(str(exc), json_output=False)
        return 1
    if not schema_path.exists():
        _emit_error("Schema 文件不存在: {}".format(schema_path), json_output=False)
        return 1
    _write_raw(schema_path.read_text(encoding="utf-8"))
    return 0


def _run_schema_path(args: argparse.Namespace) -> int:
    args_dict = vars(args)
    schema_type = str(args_dict.get("schema_type", yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE) or yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE)
    try:
        schema_path = _schema_path_for_schema_type(schema_type)
    except ValueError as exc:
        _emit_error(str(exc), json_output=False)
        return 1
    if not schema_path.exists():
        _emit_error("Schema 文件不存在: {}".format(schema_path), json_output=False)
        return 1
    _write_line(str(schema_path))
    return 0


def _run_upsert_lsp_comment(args: argparse.Namespace) -> int:
    args_dict = vars(args)
    schema_type = str(args_dict.get("schema_type", yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE) or yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE)
    schema_path = str(args_dict.get("schema_path", yaml_dsl_lsp.DEFAULT_SCHEMA_PATH) or yaml_dsl_lsp.DEFAULT_SCHEMA_PATH)
    comment_style = str(args_dict.get("comment_style", yaml_dsl_lsp.DEFAULT_COMMENT_STYLE) or yaml_dsl_lsp.DEFAULT_COMMENT_STYLE).strip()

    try:
        schema_ref = yaml_dsl_lsp.resolve_schema_ref(schema_type, schema_path)
    except ValueError as exc:
        _emit_error(str(exc), json_output=False)
        return 1

    try:
        schema_modelines = yaml_dsl_lsp.make_schema_modelines(schema_ref, comment_style=comment_style)
    except ValueError as exc:
        _emit_error(str(exc), json_output=False)
        return 1

    exit_code = 0
    changed: List[Path] = []
    unchanged: List[Path] = []

    paths = list(args_dict.get("paths", []) or [])
    for raw_path in paths:
        path = raw_path
        if not path.exists():
            _write_line_stderr("错误: YAML 文件不存在: {}".format(path))
            exit_code = 1
            continue
        if not path.is_file():
            _write_line_stderr("错误: 不是文件: {}".format(path))
            exit_code = 1
            continue

        result = yaml_dsl_lsp.upsert_schema_modelines_file(path, schema_modelines=schema_modelines)
        if result.error:
            _write_line_stderr("错误: {} ({})".format(result.error, path))
            exit_code = 1
            continue
        if result.changed:
            changed.append(path)
            _write_line("UPDATED {}".format(path))
        else:
            unchanged.append(path)
            _write_line("OK {}".format(path))

    if changed or unchanged:
        _write_line("")
        _write_line(
            "Summary: {} updated, {} ok".format(
                len(changed),
                len(unchanged),
            )
        )

    return exit_code


__all__ = ()
