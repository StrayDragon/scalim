import argparse
import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ErrorEnvelope, ScalimYamlValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.imports import (
    ScalimYamlImportExpansionError,
    contains_import_syntax,
    expand_imports_inplace,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.jsonschema_issues import (
    ScalimJsonSchemaCollectorError,
    collect_jsonschema_validation_issues,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.unknown_fields import find_unknown_fields
from scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load import (
    YamlLocationIndex,
    error_loc_for_yaml_path,
    load_yaml_mapping_text,
)
from scalim.dsl.yaml_dsl.validation_service import (
    DemandValidationResult,
    ValidationPayload,
    WorkflowValidationResult,
    extract_demand_book_ids,
    extract_demand_file_ids,
    find_demand_output_destination_binding_errors,
    find_legacy_field_errors,
    find_removed_outputs_defaults_errors,
    find_retry_enabled_missing_should_retry_errors,
    issues_to_rows,
    load_workflow_resource_ids_from_file,
    validate_demand_text,
    validate_workflow_text,
)
from scalim.vendor.compact.importlibx import import_module

from . import yaml_dsl_authoring, yaml_dsl_lsp, yaml_dsl_viz

try:
    jsonschema = import_module("jsonschema")
except ImportError:
    jsonschema = None  # type: ignore[assignment]
    _HAS_JSONSCHEMA = False  # pyright: ignore[reportConstantRedefinition]
else:
    _HAS_JSONSCHEMA = True


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser("yaml-dsl", help="YAML DSL utilities")
    _set_help_default(parser)
    yaml_subparsers = parser.add_subparsers(dest="yaml_dsl_command")

    validate_parser = yaml_subparsers.add_parser("validate", help="Validate YAML DSL via internal validator")
    _add_validate_args(validate_parser)
    validate_parser.set_defaults(func=_run_validate)

    lint_parser = yaml_subparsers.add_parser("lint", help="Lint YAML DSL authoring style (ruff-like)")
    _add_lint_args(lint_parser)
    lint_parser.set_defaults(func=_run_lint)

    format_parser = yaml_subparsers.add_parser("format", help="Format YAML DSL authoring style (idempotent)")
    _add_format_args(format_parser)
    format_parser.set_defaults(func=_run_format)

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

    viz_parser = yaml_subparsers.add_parser("viz", help="Viz helpers")
    _set_help_default(viz_parser)
    viz_subparsers = viz_parser.add_subparsers(dest="yaml_dsl_viz_command")

    viz_compile_parser = viz_subparsers.add_parser("compile", help="Export static viz artifacts (snapshot + schedule)")
    _add_viz_compile_args(viz_compile_parser)
    viz_compile_parser.set_defaults(func=_run_viz_compile)


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
        "--workflow",
        dest="workflow",
        type=Path,
        default=None,
        help="仅 demand validate: workflow YAML 上下文(用于 outputs→resources 绑定校验)",
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
        default=None,
        help="允许读取 YAML 的根目录(可重复);默认仅允许入口 YAML 所在目录",
    )
    _ = parser.add_argument("--json", action="store_true", help="输出 JSON 结果")
    _ = parser.add_argument("--verbose", "-v", action="store_true", help="显示详细错误信息")


def _add_lint_args(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "paths",
        type=Path,
        nargs="+",
        help="一个或多个 YAML 文件/目录 (递归扫描 .yaml/.yml; 默认排除 .tmp/ 与 dist/)",
    )
    _ = parser.add_argument("--fix", action="store_true", help="应用 safe fixes (仅确定性且语义安全的修复)")
    _ = parser.add_argument("--json", action="store_true", help="输出 JSON payload (机器可消费)")


def _add_format_args(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "paths",
        type=Path,
        nargs="+",
        help="一个或多个 YAML 文件/目录 (递归扫描 .yaml/.yml; 默认排除 .tmp/ 与 dist/)",
    )
    _ = parser.add_argument("--check", action="store_true", help="只检查是否需要改动 (不写回文件)")
    _ = parser.add_argument("--diff", action="store_true", help="输出 unified diff (不写回文件)")


def _add_schema_validate_args(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("yaml_file", type=Path, help="YAML 文件路径")
    _ = parser.add_argument("--schema", "-s", type=Path, default=None, help="JSON Schema 文件路径")
    _ = parser.add_argument(
        "--workflow",
        dest="workflow",
        type=Path,
        default=None,
        help="仅 demand schema validate: workflow YAML 上下文(用于 outputs→resources 绑定校验)",
    )
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


def _add_viz_compile_args(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "--type",
        dest="viz_type",
        type=str,
        choices=["demand", "workflow"],
        required=True,
        help="入口 YAML 类型: demand/workflow",
    )
    _ = parser.add_argument("yaml_file", type=Path, help="入口 YAML 文件路径(demand/workflow)")
    _ = parser.add_argument(
        "--output-dir",
        dest="output_dir",
        type=Path,
        required=True,
        help="输出目录(demand: run dir; workflow: bundle root, will create a scalim-viz/ folder inside)",
    )


def _default_schema_path() -> Path:
    return yaml_dsl_lsp.schema_dir() / "demand.gen.json"


def _resolve_schema_path(arg: Path | None) -> Path:
    return arg.resolve() if arg is not None else _default_schema_path()


_SCHEMA_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def _schema_path_for_schema_type(schema_type: str) -> Path:
    schema_type = (schema_type or "").strip() or yaml_dsl_lsp.DEFAULT_SCHEMA_TYPE
    if not _SCHEMA_TYPE_PATTERN.match(schema_type):
        msg = f"Invalid schema type: {schema_type}"
        raise ValueError(msg)
    return yaml_dsl_lsp.schema_dir() / f"{schema_type}.gen.json"


def _load_json_schema(schema_path: Path) -> dict[str, Any]:
    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
        return f"{yaml_path}:{issue.line}:{issue.column}"
    return f"{yaml_path}:{issue.line}"


def _emit_source_snippet(issue: ErrorEnvelope, source_lines: list[str] | None, *, verbose: bool) -> None:
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
        _write_line(f"{current:>4} | {text}")
        if current == line_no:
            column = issue.column or 1
            pointer = " " * max(column - 1, 0)
            _write_line(f"  | {pointer}^")


def _print_linter_result(
    yaml_path: Path,
    *,
    errors: list[ErrorEnvelope],
    warnings: list[ErrorEnvelope],
    verbose: bool,
    source_lines: list[str] | None,
) -> None:
    if not errors and not warnings:
        _write_line(f"OK {yaml_path.name}")
        return

    for issue in errors:
        path_suffix = _display_issue_path(issue.path)
        message = issue.message
        if path_suffix != "(root)":
            message = f"{message} [{path_suffix}]"
        _write_line(f"ERROR {message} --> {_format_issue_location(yaml_path, issue)}")
        _emit_source_snippet(issue, source_lines, verbose=verbose)
        if issue.suggestions:
            _write_line("help: {}".format(", ".join(issue.suggestions)))
        _write_line("")

    for issue in warnings:
        path_suffix = _display_issue_path(issue.path)
        message = issue.message
        if path_suffix != "(root)":
            message = f"{message} [{path_suffix}]"
        _write_line(f"WARN {message} --> {_format_issue_location(yaml_path, issue)}")
        _emit_source_snippet(issue, source_lines, verbose=verbose)
        if issue.suggestions:
            _write_line("help: {}".format(", ".join(issue.suggestions)))
        _write_line("")

    summary_parts: list[str] = []
    if errors:
        summary_parts.append("{} error{}".format(len(errors), "" if len(errors) == 1 else "s"))
    if warnings:
        summary_parts.append("{} warning{}".format(len(warnings), "" if len(warnings) == 1 else "s"))
    summary = ", ".join(summary_parts) if summary_parts else "no issues"
    _write_line(f"Found {summary}.")


def _render_result(
    yaml_path: Path,
    *,
    errors: list[ErrorEnvelope],
    warnings: list[ErrorEnvelope],
    verbose: bool,
    source_lines: list[str] | None,
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
    yaml_path: Path | None = None,
    schema_path: Path | None = None,
    mode: str | None = None,
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
    _write_line_stderr(f"错误: {message}")


def _emit_workflow_context_errors(
    *,
    mode: str,
    args: argparse.Namespace,
    yaml_path: Path,
    schema_path: Path,
    workflow_path: Path,
    workflow_source_lines: list[str] | None,
    errors: list[ErrorEnvelope],
    warnings: list[ErrorEnvelope],
) -> int:
    if args.json:
        payload = ValidationPayload(
            mode=str(mode),
            ok=False,
            yaml_path=str(yaml_path),
            schema_path=str(schema_path),
            errors=errors,
            warnings=warnings,
        )
        _write_line(json.dumps(payload.as_dict(), ensure_ascii=False))
        return 1

    _render_result(
        workflow_path,
        errors=errors,
        warnings=warnings,
        verbose=args.verbose,
        source_lines=workflow_source_lines,
    )
    return 1


def _infer_yaml_type(yaml_text: str) -> str:
    try:
        yaml_data, _locations, _lines = load_yaml_mapping_text(
            yaml_text,
            source_path="(memory)",
            detect_duplicate_keys=False,
        )
    except Exception:  # noqa: BLE001
        return "demand"
    if "workflow" in yaml_data:
        return "workflow"
    return "demand"


def _parse_path_aliases(raw_values: Iterable[str]) -> tuple[dict[str, str] | None, str | None]:
    output: dict[str, str] = {}
    for raw in raw_values:
        item = str(raw or "").strip()
        if not item:
            continue
        if "=" not in item:
            return None, f"Invalid --path-alias value: {item!r} (expected <alias>=<path>)"
        alias, base = item.split("=", 1)
        alias = str(alias or "").strip()
        base = str(base or "").strip()
        if not alias:
            return None, f"Invalid --path-alias value: {item!r} (alias must be non-empty)"
        if not base:
            return None, f"Invalid --path-alias value: {item!r} (path must be non-empty)"
        output[alias] = base
    return output, None


def _run_validate_workflow(
    yaml_path: Path,
    *,
    schema_path: Path,
    path_aliases: dict[str, str] | None,
    allowed_yaml_roots: list[Path] | None,
    args: argparse.Namespace,
) -> int:
    try:
        workflow_text = yaml_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        _emit_error(
            f"YAML 文件读取失败: {yaml_path}",
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="workflow-validate",
        )
        return 1

    workflow_result: WorkflowValidationResult = validate_workflow_text(
        workflow_text,
        yaml_path=yaml_path,
        schema_path=schema_path,
        path_aliases=path_aliases,
        allowed_yaml_roots=allowed_yaml_roots,
    )

    if args.json:
        _write_line(json.dumps(workflow_result.payload.as_dict(), ensure_ascii=False))
    else:
        _render_result(
            yaml_path,
            errors=workflow_result.workflow_payload.errors,
            warnings=workflow_result.workflow_payload.warnings,
            verbose=args.verbose,
            source_lines=workflow_result.workflow_source_lines,
        )
        for demand_result in workflow_result.demand_results:
            demand_path_str = demand_result.payload.yaml_path or ""
            demand_path = Path(demand_path_str) if demand_path_str else Path("demand.yaml")
            _render_result(
                demand_path,
                errors=demand_result.payload.errors,
                warnings=demand_result.payload.warnings,
                verbose=args.verbose,
                source_lines=demand_result.source_lines,
            )

    return 0 if workflow_result.payload.ok else 1


def _run_validate_demand(
    yaml_path: Path,
    *,
    yaml_text: str | None,
    schema_path: Path,
    allowed_yaml_roots: list[Path] | None,
    available_book_ids: set[str] | None,
    available_file_ids: set[str] | None,
    args: argparse.Namespace,
) -> int:
    try:
        text = str(yaml_text or "") or yaml_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        _emit_error(
            f"YAML 文件读取失败: {yaml_path}",
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="validate",
        )
        return 1

    demand_result: DemandValidationResult = validate_demand_text(
        text,
        yaml_path=yaml_path,
        schema_path=schema_path,
        allowed_yaml_roots=allowed_yaml_roots,
        available_book_ids=available_book_ids,
        available_file_ids=available_file_ids,
    )
    payload = demand_result.payload

    if args.json:
        _write_line(json.dumps(payload.as_dict(), ensure_ascii=False))
    else:
        _render_result(
            yaml_path,
            errors=payload.errors,
            warnings=payload.warnings,
            verbose=args.verbose,
            source_lines=demand_result.source_lines,
        )

    return 0 if payload.ok else 1


def _run_validate(args: argparse.Namespace) -> int:
    yaml_path = args.yaml_file.resolve()
    schema_path = _resolve_schema_path(args.schema)
    args_dict = vars(args)
    yaml_type = str(args_dict.get("yaml_type", "auto") or "auto").strip()
    inferred_yaml_text = ""
    if yaml_type == "auto":
        try:
            inferred_yaml_text = yaml_path.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            inferred_yaml_text = ""
        yaml_type = _infer_yaml_type(inferred_yaml_text)
    raw_aliases = list(args_dict.get("path_aliases", []) or [])
    path_aliases, alias_error = _parse_path_aliases(raw_aliases)
    if alias_error is not None:
        _emit_error(alias_error, json_output=bool(args.json), yaml_path=yaml_path, schema_path=schema_path, mode="validate")
        return 1
    raw_allowed_yaml_roots = args_dict.get("allowed_yaml_roots")
    allowed_yaml_roots = list(raw_allowed_yaml_roots) if raw_allowed_yaml_roots else None

    workflow_book_ids: set[str] | None = None
    workflow_file_ids: set[str] | None = None
    raw_workflow_path = args_dict.get("workflow")
    workflow_path = None
    if raw_workflow_path:
        workflow_path = raw_workflow_path.resolve() if isinstance(raw_workflow_path, Path) else Path(str(raw_workflow_path)).resolve()
    if workflow_path is not None:
        if yaml_type == "workflow":
            _emit_error(
                "--workflow is only supported for demand validation",
                json_output=bool(args.json),
                yaml_path=yaml_path,
                schema_path=schema_path,
                mode="validate",
            )
            return 1
        wf_books, wf_files, wf_lines, wf_errors, wf_warnings = load_workflow_resource_ids_from_file(workflow_path)
        if wf_errors:
            return _emit_workflow_context_errors(
                mode="validate",
                args=args,
                yaml_path=yaml_path,
                schema_path=schema_path,
                workflow_path=workflow_path,
                workflow_source_lines=wf_lines,
                errors=wf_errors,
                warnings=wf_warnings,
            )
        workflow_book_ids = wf_books
        workflow_file_ids = wf_files

    if not schema_path.exists():
        _emit_error(
            f"Schema 文件不存在: {schema_path}",
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="validate",
        )
        return 1

    if yaml_type == "workflow":
        return _run_validate_workflow(
            yaml_path,
            schema_path=schema_path,
            path_aliases=path_aliases,
            allowed_yaml_roots=allowed_yaml_roots,
            args=args,
        )

    return _run_validate_demand(
        yaml_path,
        yaml_text=inferred_yaml_text,
        schema_path=schema_path,
        allowed_yaml_roots=allowed_yaml_roots,
        available_book_ids=workflow_book_ids,
        available_file_ids=workflow_file_ids,
        args=args,
    )


def _run_viz_compile_demand(yaml_path: Path, *, output_dir: Path) -> int:
    try:
        snapshot_path, schedule_path = yaml_dsl_viz.compile_demand_viz(yaml_path, output_dir=output_dir)
    except Exception as exc:  # noqa: BLE001
        _write_line_stderr(f"[错误] viz compile 失败: {yaml_path!s}: {type(exc).__name__}: {exc}")
        return 1
    _write_line(f"OK {output_dir!s}")
    _write_line(f"snapshot: {snapshot_path!s}")
    _write_line(f"schedule: {schedule_path!s}")
    return 0


def _run_viz_compile_workflow(yaml_path: Path, *, output_dir: Path) -> int:
    try:
        out_paths = yaml_dsl_viz.compile_workflow_viz(yaml_path, output_dir=output_dir)
    except Exception as exc:  # noqa: BLE001
        _write_line_stderr(f"[错误] viz compile 失败: {yaml_path!s}: {type(exc).__name__}: {exc}")
        return 1
    manifest_path = out_paths.get("bundle:manifest")
    _write_line(f"OK {output_dir!s}")
    if manifest_path is not None:
        _write_line(f"manifest: {manifest_path!s}")
    return 0


def _run_viz_compile(args: argparse.Namespace) -> int:
    yaml_path = args.yaml_file.expanduser().resolve(strict=False)
    output_dir = args.output_dir.expanduser().resolve(strict=False)
    viz_type = str(getattr(args, "viz_type", "") or "").strip()

    if not yaml_path.exists() or not yaml_path.is_file():
        _write_line_stderr(f"[错误] YAML 文件不存在: {yaml_path!s}")
        return 2
    if output_dir.exists() and not output_dir.is_dir():
        _write_line_stderr(f"[错误] --output-dir 必须是目录: {output_dir!s}")
        return 2

    if viz_type == "demand":
        return _run_viz_compile_demand(yaml_path, output_dir=output_dir)
    if viz_type == "workflow":
        return _run_viz_compile_workflow(yaml_path, output_dir=output_dir)

    _write_line_stderr(f"[错误] Unknown --type: {viz_type!r}")
    return 2


def _run_lint(args: argparse.Namespace) -> int:  # noqa: C901, PLR0912
    args_dict = vars(args)
    fix = bool(args_dict.get("fix"))
    json_output = bool(args_dict.get("json"))

    raw_paths = list(args_dict.get("paths", []) or [])
    yaml_paths, discovery_errors = yaml_dsl_authoring.discover_yaml_files(raw_paths)
    if discovery_errors:
        for err in discovery_errors:
            _write_line_stderr(f"error: {err}")
        return 2

    issues: list[yaml_dsl_authoring.LintIssue] = []
    had_fatal_error = False

    for path in yaml_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            issues.append(
                yaml_dsl_authoring.LintIssue(
                    code="YDL000",
                    severity="error",
                    message=f"Failed to read: {type(exc).__name__}: {exc}",
                    path=str(path),
                    range=yaml_dsl_authoring.TextRange(
                        start=yaml_dsl_authoring.TextPosition(line=1, character=1),
                        end=yaml_dsl_authoring.TextPosition(line=1, character=1),
                    ),
                )
            )
            had_fatal_error = True
            continue

        if fix:
            new_text, changed, error = yaml_dsl_authoring.format_yaml_dsl_text(text)
            if error is not None:
                issues.append(
                    yaml_dsl_authoring.LintIssue(
                        code="YDL000",
                        severity="error",
                        message=error,
                        path=str(path),
                        range=yaml_dsl_authoring.TextRange(
                            start=yaml_dsl_authoring.TextPosition(line=1, character=1),
                            end=yaml_dsl_authoring.TextPosition(line=1, character=1),
                        ),
                    )
                )
                had_fatal_error = True
                continue
            if changed:
                try:
                    _ = path.write_text(new_text, encoding="utf-8")
                except Exception as exc:  # noqa: BLE001
                    issues.append(
                        yaml_dsl_authoring.LintIssue(
                            code="YDL000",
                            severity="error",
                            message=f"Failed to write: {type(exc).__name__}: {exc}",
                            path=str(path),
                            range=yaml_dsl_authoring.TextRange(
                                start=yaml_dsl_authoring.TextPosition(line=1, character=1),
                                end=yaml_dsl_authoring.TextPosition(line=1, character=1),
                            ),
                        )
                    )
                    had_fatal_error = True
                    continue
                text = new_text

        file_issues, error = yaml_dsl_authoring.lint_yaml_dsl_text(text, source_path=str(path))
        if error is not None:
            issues.append(
                yaml_dsl_authoring.LintIssue(
                    code="YDL000",
                    severity="error",
                    message=error,
                    path=str(path),
                    range=yaml_dsl_authoring.TextRange(
                        start=yaml_dsl_authoring.TextPosition(line=1, character=1),
                        end=yaml_dsl_authoring.TextPosition(line=1, character=1),
                    ),
                )
            )
            had_fatal_error = True
            continue
        issues.extend(file_issues)

    if json_output:
        payload = {
            "ok": not issues and not had_fatal_error,
            "issues": [item.as_dict() for item in issues],
        }
        _write_line(json.dumps(payload, ensure_ascii=False))
    else:
        for issue in issues:
            start = issue.range.start
            _write_line(f"{issue.path}:{start.line}:{start.character}: {issue.severity.upper()} {issue.code} {issue.message}")
        if not issues:
            _write_line("OK")

    if had_fatal_error:
        return 2
    return 0 if not issues else 1


def _run_format(args: argparse.Namespace) -> int:  # noqa: C901, PLR0912
    args_dict = vars(args)
    check = bool(args_dict.get("check"))
    diff = bool(args_dict.get("diff"))
    if diff:
        check = True

    raw_paths = list(args_dict.get("paths", []) or [])
    yaml_paths, discovery_errors = yaml_dsl_authoring.discover_yaml_files(raw_paths)
    if discovery_errors:
        for err in discovery_errors:
            _write_line_stderr(f"error: {err}")
        return 2

    had_fatal_error = False
    had_changes = False

    for path in yaml_paths:
        try:
            old_text = path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            _write_line_stderr(f"error: Failed to read {path}: {type(exc).__name__}: {exc}")
            had_fatal_error = True
            continue

        new_text, changed, error = yaml_dsl_authoring.format_yaml_dsl_text(old_text)
        if error is not None:
            _write_line_stderr(f"error: {path}: {error}")
            had_fatal_error = True
            continue
        if not changed:
            if not check and not diff:
                _write_line(f"OK {path}")
            continue

        had_changes = True

        if diff:
            _write_raw(yaml_dsl_authoring.diff_text(old_text=old_text, new_text=new_text, path=path))
            continue

        if check:
            _write_line(f"WOULD_FORMAT {path}")
            continue

        try:
            _ = path.write_text(new_text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            _write_line_stderr(f"error: Failed to write {path}: {type(exc).__name__}: {exc}")
            had_fatal_error = True
            continue
        _write_line(f"FORMATTED {path}")

    if had_fatal_error:
        return 2
    if check and had_changes:
        return 1
    return 0


def _load_workflow_context_for_schema_validate(
    *,
    args: argparse.Namespace,
    yaml_path: Path,
    schema_path: Path,
    yaml_data_dict: dict[str, Any],
) -> tuple[set[str] | None, set[str] | None, bool]:
    args_dict = vars(args)
    raw_workflow_path = args_dict.get("workflow")
    if not raw_workflow_path:
        return None, None, False

    workflow_path = raw_workflow_path.resolve() if isinstance(raw_workflow_path, Path) else Path(str(raw_workflow_path)).resolve()
    if "workflow" in yaml_data_dict:
        _emit_error(
            "--workflow is only supported for demand schema validation",
            json_output=bool(args.json),
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="schema-validate",
        )
        return None, None, True

    wf_books, wf_files, wf_lines, wf_errors, wf_warnings = load_workflow_resource_ids_from_file(workflow_path)
    if wf_errors:
        _ = _emit_workflow_context_errors(
            mode="schema-validate",
            args=args,
            yaml_path=yaml_path,
            schema_path=schema_path,
            workflow_path=workflow_path,
            workflow_source_lines=wf_lines,
            errors=wf_errors,
            warnings=wf_warnings,
        )
        return None, None, True

    return wf_books, wf_files, False


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
            f"YAML 文件读取失败: {yaml_path}",
            json_output=args.json,
            yaml_path=yaml_path,
            schema_path=schema_path,
            mode="schema-validate",
        )
        return 1
    source_lines: list[str] | None = yaml_text.splitlines()

    errors: list[ErrorEnvelope] = []
    warnings: list[ErrorEnvelope] = []
    ok = False

    try:
        yaml_data_dict, locations, _lines = load_yaml_mapping_text(
            yaml_text,
            source_path=str(yaml_path),
            detect_duplicate_keys=True,
        )
    except ScalimYamlValidationError as exc:
        errors = list(exc.errors)
        warnings = list(exc.warnings)
    else:
        workflow_book_ids, workflow_file_ids, emitted = _load_workflow_context_for_schema_validate(
            args=args,
            yaml_path=yaml_path,
            schema_path=schema_path,
            yaml_data_dict=yaml_data_dict,
        )
        if emitted:
            return 1

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
            warnings = []
        else:
            errors, warnings = _collect_schema_issues(
                yaml_data_dict,
                schema,
                args,
                jsonschema_module,
                workflow_book_ids=workflow_book_ids,
                workflow_file_ids=workflow_file_ids,
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
) -> tuple[dict[str, Any] | None, int]:
    if not schema_path.exists():
        _emit_error(
            f"Schema 文件不存在: {schema_path}",
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
            f"Schema JSON 无法解析: {schema_path}",
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
) -> Any | None:
    if _HAS_JSONSCHEMA and jsonschema is not None:
        return jsonschema
    _emit_error(
        "缺少 jsonschema 依赖,请安装 scalim-cli",
        json_output=args.json,
        yaml_path=yaml_path,
        schema_path=schema_path,
        mode="schema-validate",
    )
    return None


def _collect_schema_issues(
    yaml_data: dict[str, Any],
    schema: dict[str, Any],
    args: argparse.Namespace,
    jsonschema_module: Any,
    *,
    workflow_book_ids: set[str] | None,
    workflow_file_ids: set[str] | None,
    source_path: str,
    locations: YamlLocationIndex,
) -> tuple[list[ErrorEnvelope], list[ErrorEnvelope]]:
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

    errors = issues_to_rows(
        issues,
        source_path=source_path,
        locations=locations,
        default_code="yaml_schema_validate_error",
    )
    errors.extend(
        find_legacy_field_errors(
            yaml_data,
            source_path=source_path,
            locations=locations,
        )
    )
    errors.extend(
        issues_to_rows(
            find_unknown_fields(yaml_data, schema),
            source_path=source_path,
            locations=locations,
            default_code="yaml_unknown_field",
        )
    )
    demand_book_ids = extract_demand_book_ids(yaml_data)
    demand_file_ids = extract_demand_file_ids(yaml_data)
    visible_book_ids = set(demand_book_ids)
    visible_file_ids = set(demand_file_ids)
    if workflow_book_ids is not None:
        visible_book_ids.update(workflow_book_ids)
    if workflow_file_ids is not None:
        visible_file_ids.update(workflow_file_ids)
    errors.extend(
        find_removed_outputs_defaults_errors(
            yaml_data,
            source_path=source_path,
            locations=locations,
            default_code="yaml_schema_validate_error",
        )
    )
    errors.extend(
        find_demand_output_destination_binding_errors(
            yaml_data,
            source_path=source_path,
            locations=locations,
            available_book_ids=visible_book_ids,
            available_file_ids=visible_file_ids,
            default_code="yaml_schema_validate_error",
        )
    )
    errors.extend(
        find_retry_enabled_missing_should_retry_errors(
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
    errors: list[ErrorEnvelope],
    warnings: list[ErrorEnvelope],
    args: argparse.Namespace,
    *,
    ok: bool,
    source_lines: list[str] | None,
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
        _emit_error(f"Schema 文件不存在: {schema_path}", json_output=False)
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
        _emit_error(f"Schema 文件不存在: {schema_path}", json_output=False)
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
    changed: list[Path] = []
    unchanged: list[Path] = []

    paths = list(args_dict.get("paths", []) or [])
    for raw_path in paths:
        path = raw_path
        if not path.exists():
            _write_line_stderr(f"错误: YAML 文件不存在: {path}")
            exit_code = 1
            continue
        if not path.is_file():
            _write_line_stderr(f"错误: 不是文件: {path}")
            exit_code = 1
            continue

        result = yaml_dsl_lsp.upsert_schema_modelines_file(path, schema_modelines=schema_modelines)
        if result.error:
            _write_line_stderr(f"错误: {result.error} ({path})")
            exit_code = 1
            continue
        if result.changed:
            changed.append(path)
            _write_line(f"UPDATED {path}")
        else:
            unchanged.append(path)
            _write_line(f"OK {path}")

    if changed or unchanged:
        _write_line("")
        _write_line(f"Summary: {len(changed)} updated, {len(unchanged)} ok")

    return exit_code


__all__ = ()
