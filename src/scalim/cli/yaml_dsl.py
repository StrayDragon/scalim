import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple, cast

from ..vendor.compact.importlibx import import_module, require_optional_dependency
from . import yaml_dsl_lsp

if TYPE_CHECKING:
    import yaml
else:
    yaml = require_optional_dependency(
        "yaml",
        context="scalim.cli.yaml_dsl",
        install_name="pyyaml",
    )

from ..dsl.by_yaml.config_parsing.imports import YamlImportExpansionError, contains_import_syntax, expand_imports_inplace
from ..dsl.by_yaml.config_parsing.unknown_fields import find_unknown_fields
from ..dsl.by_yaml.config_parsing.validator import ConfigValidator, attach_locations, build_yaml_location_index
from ..dsl.by_yaml.config_parsing.validator import YamlValidationIssue as Issue

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

    errors: List[Issue] = field(default_factory=list)
    """错误列表."""

    warnings: List[Issue] = field(default_factory=list)
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
    schema_show_parser.set_defaults(func=_run_schema_show)

    schema_path_parser = schema_subparsers.add_parser("path", help="Print JSON Schema path")
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
    _ = parser.add_argument("--strict", action="store_true", help="严格模式: 将未知字段视为错误")
    _ = parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    _ = parser.add_argument("--verbose", "-v", action="store_true", help="显示详细错误信息")


def _add_schema_validate_args(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("yaml_file", type=Path, help="YAML 文件路径")
    _ = parser.add_argument("--schema", "-s", type=Path, default=None, help="JSON Schema 文件路径")
    _ = parser.add_argument("--strict", action="store_true", help="严格模式: 将未知字段视为错误")
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


def _load_json_schema(schema_path: Path) -> Dict[str, Any]:
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml_file(yaml_path: Path) -> Any:
    with yaml_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _find_legacy_field_errors(yaml_data: Dict[str, Any]) -> List[Issue]:
    errors: List[Issue] = []

    _collect_legacy_fields(errors, yaml_data, None)

    sources = yaml_data.get("sources", {})
    if isinstance(sources, dict):
        sources_dict = cast("Dict[str, Any]", sources)
        for source_id, source_data in sources_dict.items():
            if not isinstance(source_data, dict):
                continue
            _collect_legacy_fields(errors, cast("Dict[str, Any]", source_data), "sources.{}".format(source_id))

    fields = yaml_data.get("fields", {})
    if isinstance(fields, dict):
        fields_dict = cast("Dict[str, Any]", fields)
        for field_id, field_data in fields_dict.items():
            if not isinstance(field_data, dict):
                continue
            _collect_legacy_fields(errors, cast("Dict[str, Any]", field_data), "fields.{}".format(field_id))

    return errors


def _collect_legacy_fields(errors: List[Issue], data: Dict[str, Any], prefix: Optional[str]) -> None:
    for key in data:
        if key not in LEGACY_FIELDS:
            continue
        path = "{}.{}".format(prefix, key) if prefix else str(key)
        errors.append(Issue(path=path, message="Legacy field '{}' is not allowed".format(key)))


def _issues_to_rows(issues: Iterable[Any]) -> List[Issue]:
    rows: List[Issue] = []
    for issue in issues:
        path = getattr(issue, "path", "") or ""
        message = getattr(issue, "message", str(issue))
        suggestions = list(getattr(issue, "suggestions", []) or [])
        rows.append(Issue(path=path, message=message, suggestions=suggestions))
    return rows


def _format_error_path(error: Any) -> str:
    absolute_path = getattr(error, "absolute_path", None)
    if absolute_path:
        return ".".join(str(p) for p in absolute_path)
    return "(root)"


def _write_line(text: str) -> None:
    _ = sys.stdout.write(text + "\n")


def _write_line_stderr(text: str) -> None:
    _ = sys.stderr.write(text + "\n")


def _write_raw(text: str) -> None:
    _ = sys.stdout.write(text)


def _display_issue_path(path: str) -> str:
    return path or "(root)"


def _format_issue_location(yaml_path: Path, issue: Issue) -> str:
    if issue.line is None:
        return str(yaml_path)
    if issue.column is not None:
        return "{}:{}:{}".format(yaml_path, issue.line, issue.column)
    return "{}:{}".format(yaml_path, issue.line)


def _emit_source_snippet(issue: Issue, source_lines: Optional[List[str]], *, verbose: bool) -> None:
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
    errors: List[Issue],
    warnings: List[Issue],
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
    errors: List[Issue],
    warnings: List[Issue],
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


def _read_yaml_or_error(
    yaml_path: Path,
    *,
    json_output: bool,
    mode: Optional[str] = None,
    schema_path: Optional[Path] = None,
) -> Tuple[Optional[Any], int]:
    if not yaml_path.exists():
        _emit_error(
            "YAML 文件不存在: {}".format(yaml_path),
            json_output=json_output,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode=mode,
        )
        return None, 1
    try:
        yaml_data = _load_yaml_file(yaml_path)
    except yaml.YAMLError as exc:
        _emit_error(
            "YAML 文件解析失败: {}".format(exc),
            json_output=json_output,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode=mode,
        )
        return None, 1
    if yaml_data is None:
        _emit_error(
            "YAML 文件内容为空",
            json_output=json_output,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode=mode,
        )
        return None, 1
    return yaml_data, 0


def _extract_yaml_error_location(exc: Exception) -> Optional[Tuple[int, int]]:
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    if mark is None:
        return None
    line = getattr(mark, "line", None)
    column = getattr(mark, "column", None)
    if not isinstance(line, int) or not isinstance(column, int):
        return None
    return line + 1, column + 1


def _emit_error(
    message: str,
    *,
    json_output: bool,
    yaml_path: Optional[Path] = None,
    schema_path: Optional[Path] = None,
    mode: Optional[str] = None,
) -> None:
    if json_output:
        payload = ValidationPayload(
            mode=mode or "error",
            ok=False,
            yaml_path=str(yaml_path) if yaml_path is not None else None,
            schema_path=str(schema_path) if schema_path is not None else None,
            errors=[Issue(path="(root)", message=message)],
        )
        _write_line(json.dumps(payload.as_dict(), ensure_ascii=False))
        return
    _write_line_stderr("错误: {}".format(message))


def _run_validate(args: argparse.Namespace) -> int:  # noqa: C901, PLR0911, PLR0912, PLR0915
    yaml_path = args.yaml_file.resolve()
    schema_path = _resolve_schema_path(args.schema)

    if not schema_path.exists():
        _emit_error(
            "Schema 文件不存在: {}".format(schema_path),
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="validate",
        )
        return 1

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

    source_lines: List[str] = yaml_text.splitlines()

    try:
        yaml_data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        loc = _extract_yaml_error_location(exc)
        line = loc[0] if loc is not None else None
        column = loc[1] if loc is not None else None
        errors = [Issue(path="(root)", message="YAML parse error: {}".format(exc), line=line, column=column)]
        warnings: List[Issue] = []
        ok = False
        if args.json:
            payload = ValidationPayload(
                mode="validate",
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
        return 1

    if yaml_data is None:
        errors = [Issue(path="(root)", message="YAML document is empty", line=1, column=1)]
        warnings = []
        ok = False
        if args.json:
            payload = ValidationPayload(
                mode="validate",
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
        return 1

    if not isinstance(yaml_data, dict):
        errors = [Issue(path="(root)", message="YAML root must be a mapping", line=1, column=1)]
        warnings = []
        ok = False
        if args.json:
            payload = ValidationPayload(
                mode="validate",
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
        return 1

    yaml_data_dict = cast("Dict[str, Any]", yaml_data)
    locations = build_yaml_location_index(yaml_text)
    try:
        if contains_import_syntax(yaml_data_dict):
            _ = expand_imports_inplace(yaml_data_dict, yaml_path=yaml_path)
    except YamlImportExpansionError as exc:
        errors = [Issue(path=exc.logical_path or "(root)", message=str(exc))]
        warnings = []
        errors = attach_locations(errors, locations)
        ok = False
        if args.json:
            payload = ValidationPayload(
                mode="validate",
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
        return 1

    validator = ConfigValidator(schema_path=str(schema_path))
    report = validator.validate_report(
        yaml_data_dict,
        strict_unknown_fields=bool(args.strict),
        enable_jsonschema_validation=False,
    )
    errors = _issues_to_rows(report.errors())
    warnings = _issues_to_rows(report.warnings())

    errors = attach_locations(errors, locations)
    warnings = attach_locations(warnings, locations)

    ok = (not errors) and (not (bool(args.strict) and warnings))

    if args.json:
        payload = ValidationPayload(
            mode="validate",
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


def _run_schema_validate(args: argparse.Namespace) -> int:
    schema_path = _resolve_schema_path(args.schema)
    yaml_path = args.yaml_file.resolve()
    schema, exit_code = _load_schema_or_error(schema_path, yaml_path=yaml_path, args=args)
    if exit_code != 0 or schema is None:
        return exit_code

    yaml_data, exit_code = _read_yaml_or_error(
        yaml_path,
        json_output=args.json,
        mode="schema-validate",
        schema_path=schema_path,
    )
    if exit_code != 0 or yaml_data is None:
        return exit_code

    jsonschema_module = _get_jsonschema_module(args, yaml_path=yaml_path, schema_path=schema_path)
    if jsonschema_module is None:
        return 1

    if not isinstance(yaml_data, dict):
        errors = [Issue(path="(root)", message="YAML root must be a mapping")]
        return _emit_schema_result(yaml_path, schema_path, errors, [], args, ok=False, source_lines=None)

    yaml_data_dict = cast("Dict[str, Any]", yaml_data)
    try:
        if contains_import_syntax(yaml_data_dict):
            _ = expand_imports_inplace(yaml_data_dict, yaml_path=yaml_path)
    except YamlImportExpansionError as exc:
        errors = [Issue(path=exc.logical_path or "(root)", message=str(exc))]
        return _emit_schema_result(yaml_path, schema_path, errors, [], args, ok=False, source_lines=None)
    errors, warnings = _collect_schema_issues(yaml_data_dict, schema, args, jsonschema_module)
    ok = not errors and not (args.strict and warnings)
    source_lines: Optional[List[str]] = None
    locations: Dict[str, Tuple[int, int]] = {}
    try:
        yaml_text = yaml_path.read_text(encoding="utf-8")
        source_lines = yaml_text.splitlines()
        locations = build_yaml_location_index(yaml_text)
    except Exception:  # noqa: BLE001
        source_lines = None
        locations = {}

    errors = attach_locations(errors, locations)
    warnings = attach_locations(warnings, locations)

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
) -> Tuple[List[Issue], List[Issue]]:
    validator_factory = getattr(jsonschema_module, "Draft7Validator", None)
    if not callable(validator_factory):
        errors = [Issue(path="(root)", message="jsonschema Draft7Validator unavailable")]
        return errors, []
    validator = validator_factory(schema)
    iter_errors = getattr(validator, "iter_errors", None)
    if not callable(iter_errors):
        errors = [Issue(path="(root)", message="jsonschema validator missing iter_errors")]
        return errors, []
    errors_iter = iter_errors(yaml_data)
    errors_raw = list(cast("Iterable[Any]", errors_iter))

    errors: List[Issue] = []
    for error in sorted(errors_raw, key=lambda err: str(list(getattr(err, "absolute_path", [])))):
        path = _format_error_path(error)
        message = getattr(error, "message", str(error))
        errors.append(Issue(path=path, message=message))

        context = getattr(error, "context", None)
        if args.verbose and context:
            for ctx in context:
                ctx_path = _format_error_path(ctx)
                ctx_message = getattr(ctx, "message", str(ctx))
                errors.append(Issue(path=ctx_path, message="↳ {}".format(ctx_message)))

    errors.extend(_find_legacy_field_errors(yaml_data))

    unknowns = _issues_to_rows(find_unknown_fields(yaml_data, schema))
    warnings: List[Issue] = []
    if args.strict and unknowns:
        errors.extend(unknowns)
    else:
        warnings.extend(unknowns)

    return errors, warnings


def _emit_schema_result(
    yaml_path: Path,
    schema_path: Path,
    errors: List[Issue],
    warnings: List[Issue],
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


def _run_schema_show(_args: argparse.Namespace) -> int:
    schema_path = _default_schema_path()
    if not schema_path.exists():
        _emit_error("Schema 文件不存在: {}".format(schema_path), json_output=False)
        return 1
    _write_raw(schema_path.read_text(encoding="utf-8"))
    return 0


def _run_schema_path(_args: argparse.Namespace) -> int:
    schema_path = _default_schema_path()
    if not schema_path.exists():
        _emit_error("Schema 文件不存在: {}".format(schema_path), json_output=False)
        return 1
    _write_line(str(schema_path))
    return 0


def _run_upsert_lsp_comment(args: argparse.Namespace) -> int:
    schema_type = str(getattr(args, "schema_type", yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE) or yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE)
    schema_path = str(getattr(args, "schema_path", yaml_dsl_lsp.DEFAULT_SCHEMA_PATH) or yaml_dsl_lsp.DEFAULT_SCHEMA_PATH)
    comment_style = str(getattr(args, "comment_style", yaml_dsl_lsp.DEFAULT_COMMENT_STYLE) or yaml_dsl_lsp.DEFAULT_COMMENT_STYLE).strip()

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

    paths = cast("List[Path]", list(getattr(args, "paths", []) or []))
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
