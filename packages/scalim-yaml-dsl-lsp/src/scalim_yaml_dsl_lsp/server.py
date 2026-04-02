import logging
import os
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote, urlparse

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from scalim.vendor.yamlx.ruamel.yaml import YAML

from .core import (
    PythonDefinitionResult,
    YamlDslEditorDiagnosticsResult,
    collect_yaml_dsl_editor_diagnostics,
    complete_python_reference,
    discover_yaml_dsl_editor_project,
    extract_yaml_dsl_python_reference_by_cursor,
    hover_python_reference,
    resolve_python_definition,
)
from .cursor_extraction import YamlCursorExtractionResult
from .editor_types import EditorPosition, EditorRange

__all__ = ()

_LOG = logging.getLogger(__name__)

_COMMAND_DUMP_DISCOVERY = "scalim.dumpDiscovery"
_COMMAND_CREATE_MINIMAL_SCALIM_YAML = "scalim.yaml.createMinimal"
_COMMAND_ADD_IMPORT_ALLOWED_ROOTS = "scalim.yaml.addImportAllowedRoots"
_COMMAND_ADD_PYTHON_ROOTS = "scalim.yaml.addPythonRoots"
_COMMAND_EXPLAIN_RESOLUTION_FAILURE = "scalim.python.explainResolutionFailure"

_MODE_MINIMAL = "minimal"
_MODE_WIDE = "wide"

_IMPORT_ESCAPES_ALLOWED_ROOTS_MARKER = "YAML path escapes allowed roots:"
_RESOLVED_PATH_RE = re.compile(r"resolved_path='([^']+)'")


@dataclass(frozen=True)
class _DocumentState:
    text: str
    report: Optional[YamlDslEditorDiagnosticsResult]
    python_roots: Tuple[Path, ...]


def create_server() -> LanguageServer:
    server = LanguageServer(
        "scalim-yaml-dsl-lsp",
        "0.7.1",
        text_document_sync_kind=types.TextDocumentSyncKind.Full,
    )
    state: Dict[str, _DocumentState] = {}

    _register_text_document_sync(server, state)
    _register_definition_feature(server, state)
    _register_hover_feature(server, state)
    _register_completion_feature(server, state)
    _register_code_actions(server, state)

    return server


def _register_text_document_sync(server: LanguageServer, state: Dict[str, _DocumentState]) -> None:
    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    async def did_open(ls: LanguageServer, params: types.DidOpenTextDocumentParams) -> None:
        uri = str(params.text_document.uri)
        _update_state_and_publish_diagnostics(ls, uri, state, yaml_text=str(params.text_document.text or ""))

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    async def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams) -> None:
        uri = str(params.text_document.uri)
        yaml_text = ""
        if params.content_changes:
            yaml_text = str(params.content_changes[-1].text or "")
        _update_state_and_publish_diagnostics(ls, uri, state, yaml_text=yaml_text or None)

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    async def did_close(_ls: LanguageServer, params: types.DidCloseTextDocumentParams) -> None:
        uri = str(params.text_document.uri)
        state.pop(uri, None)


def _register_definition_feature(server: LanguageServer, state: Dict[str, _DocumentState]) -> None:
    @server.feature(types.TEXT_DOCUMENT_DEFINITION)
    async def definition(_ls: LanguageServer, params: types.DefinitionParams) -> Optional[List[types.Location]]:
        return _handle_definition(params, state=state)


def _handle_definition(
    params: types.DefinitionParams,
    *,
    state: Dict[str, _DocumentState],
) -> Optional[List[types.Location]]:
    uri = str(params.text_document.uri)
    doc_state = state.get(uri)
    if doc_state is None:
        return None

    extraction = _safe_extract_reference_for_lsp(doc_state.text, params.position, uri=uri, op="definition")
    if not extraction.reference:
        return None

    result = _safe_resolve_python_definition(extraction, python_roots=doc_state.python_roots, uri=uri)
    if result is None:
        return None

    locations: List[types.Location] = []
    for loc in result.locations:
        location = _location_from_definition_location(loc.file_path, loc.range)
        if location is not None:
            locations.append(location)
    return locations or None


def _location_from_definition_location(file_path: str, rng: Optional[EditorRange]) -> Optional[types.Location]:
    try:
        file_uri = Path(file_path).as_uri()
    except ValueError as exc:
        _LOG.info("定义跳转位置无效 `file_path`=%r: %s: %s", file_path, type(exc).__name__, exc)
        return None

    lsp_range = types.Range(start=types.Position(0, 0), end=types.Position(0, 0))
    if rng is not None:
        lsp_range = _to_lsp_range(rng)
    return types.Location(uri=file_uri, range=lsp_range)


def _safe_extract_reference_for_lsp(
    yaml_text: str,
    position: types.Position,
    *,
    uri: str,
    op: str,
) -> YamlCursorExtractionResult:
    try:
        extraction = _extract_reference_for_lsp(yaml_text, position)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("%s 光标抽取失败 `uri`=%s: %s: %s", op, uri, type(exc).__name__, exc)
        return YamlCursorExtractionResult(warnings=("{} 光标抽取失败".format(op),))
    if extraction.warnings:
        _LOG.debug("%s 光标抽取警告 `uri`=%s `yaml_path`=%s `warnings`=%s", op, uri, extraction.yaml_path, list(extraction.warnings))
    return extraction


def _safe_resolve_python_definition(
    extraction: YamlCursorExtractionResult,
    *,
    python_roots: Tuple[Path, ...],
    uri: str,
) -> Optional[PythonDefinitionResult]:
    try:
        result = resolve_python_definition(extraction.reference, python_roots=list(python_roots))
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "定义跳转解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None
    if result.warnings:
        _LOG.info("定义跳转警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, extraction.yaml_path, list(result.warnings))
    return result


def _register_hover_feature(server: LanguageServer, state: Dict[str, _DocumentState]) -> None:
    @server.feature(types.TEXT_DOCUMENT_HOVER)
    async def hover(_ls: LanguageServer, params: types.HoverParams) -> Optional[types.Hover]:
        uri = str(params.text_document.uri)
        doc_state = state.get(uri)
        if doc_state is None:
            return None

        try:
            extraction = _extract_reference_for_lsp(doc_state.text, params.position)
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("悬浮提示(`hover`) 光标抽取失败 `uri`=%s: %s: %s", uri, type(exc).__name__, exc)
            return None
        if extraction.warnings:
            _LOG.debug(
                "悬浮提示(`hover`) 光标抽取警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
                uri,
                extraction.yaml_path,
                list(extraction.warnings),
            )
        if not extraction.reference:
            return None

        try:
            result = hover_python_reference(extraction.reference, python_roots=list(doc_state.python_roots))
        except Exception as exc:  # noqa: BLE001
            _LOG.exception(
                "悬浮提示(`hover`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
                uri,
                extraction.yaml_path,
                type(exc).__name__,
                exc,
            )
            return None
        if result.warnings:
            _LOG.info("悬浮提示(`hover`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, extraction.yaml_path, list(result.warnings))
        if not result.text.strip():
            return None
        return types.Hover(contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=str(result.text)))


def _register_completion_feature(server: LanguageServer, state: Dict[str, _DocumentState]) -> None:
    @server.feature(types.TEXT_DOCUMENT_COMPLETION)
    async def completion(_ls: LanguageServer, params: types.CompletionParams) -> types.CompletionList:
        uri = str(params.text_document.uri)
        doc_state = state.get(uri)
        if doc_state is None:
            return types.CompletionList(is_incomplete=False, items=[])

        try:
            extraction = _extract_reference_for_lsp(doc_state.text, params.position)
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("补全(`completion`) 光标抽取失败 `uri`=%s: %s: %s", uri, type(exc).__name__, exc)
            return types.CompletionList(is_incomplete=False, items=[])
        if extraction.warnings:
            _LOG.debug(
                "补全(`completion`) 光标抽取警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
                uri,
                extraction.yaml_path,
                list(extraction.warnings),
            )
        if not extraction.reference:
            return types.CompletionList(is_incomplete=False, items=[])

        try:
            result = complete_python_reference(extraction.reference, python_roots=list(doc_state.python_roots))
        except Exception as exc:  # noqa: BLE001
            _LOG.exception(
                "补全(`completion`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
                uri,
                extraction.yaml_path,
                type(exc).__name__,
                exc,
            )
            return types.CompletionList(is_incomplete=False, items=[])
        if result.warnings:
            _LOG.info(
                "补全(`completion`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
                uri,
                extraction.yaml_path,
                list(result.warnings),
            )

        items = [types.CompletionItem(label=str(item)) for item in result.items]
        return types.CompletionList(is_incomplete=False, items=items)


def _register_code_actions(server: LanguageServer, state: Dict[str, _DocumentState]) -> None:
    @server.feature(types.TEXT_DOCUMENT_CODE_ACTION)
    async def code_action(ls: LanguageServer, params: types.CodeActionParams) -> List[types.CodeAction]:
        return _handle_code_actions(ls, params, state=state)

    @server.command(_COMMAND_DUMP_DISCOVERY)
    def dump_discovery(_ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        return _dump_discovery_payload(document_uri)

    @server.command(_COMMAND_CREATE_MINIMAL_SCALIM_YAML)
    async def create_minimal_scalim_yaml(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        return await _cmd_create_minimal_scalim_yaml(ls, document_uri, state=state)

    @server.command(_COMMAND_ADD_IMPORT_ALLOWED_ROOTS)
    async def add_import_allowed_roots(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        mode = str(args[1]) if len(args) > 1 else ""
        return await _cmd_add_import_allowed_roots(ls, document_uri, mode, state=state)

    @server.command(_COMMAND_ADD_PYTHON_ROOTS)
    async def add_python_roots(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        mode = str(args[1]) if len(args) > 1 else ""
        return await _cmd_add_python_roots(ls, document_uri, mode, state=state)

    @server.command(_COMMAND_EXPLAIN_RESOLUTION_FAILURE)
    def explain_resolution_failure(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        reference = str(args[1]) if len(args) > 1 else ""
        return _cmd_explain_resolution_failure(ls, document_uri, reference, state=state)


def _handle_code_actions(
    _ls: LanguageServer,
    params: types.CodeActionParams,
    *,
    state: Dict[str, _DocumentState],
) -> List[types.CodeAction]:
    uri = str(params.text_document.uri)
    doc_state = state.get(uri)
    if doc_state is None or doc_state.report is None:
        return []

    report = doc_state.report
    actions: List[types.CodeAction] = []

    if report.discovery.scalim_yaml_path is None:
        actions.append(
            types.CodeAction(
                title="创建最小 `scalim.yaml`",
                kind=types.CodeActionKind.QuickFix,
                is_preferred=True,
                command=types.Command(
                    title="创建最小 `scalim.yaml`",
                    command=_COMMAND_CREATE_MINIMAL_SCALIM_YAML,
                    arguments=[uri],
                ),
            )
        )
        return actions

    import_dir_rel = _first_import_escape_dir_rel(report)
    if import_dir_rel:
        actions.append(
            types.CodeAction(
                title="修复: 将 `{}` 加入 `yaml_dsl.import_allowed_roots` (最小)".format(import_dir_rel),
                kind=types.CodeActionKind.QuickFix,
                is_preferred=True,
                command=types.Command(
                    title="修复 import_allowed_roots (最小)",
                    command=_COMMAND_ADD_IMPORT_ALLOWED_ROOTS,
                    arguments=[uri, _MODE_MINIMAL],
                ),
            )
        )
        actions.append(
            types.CodeAction(
                title="修复: 将 `.` 加入 `yaml_dsl.import_allowed_roots` (宽松)",
                kind=types.CodeActionKind.QuickFix,
                command=types.Command(
                    title="修复 import_allowed_roots (宽松)",
                    command=_COMMAND_ADD_IMPORT_ALLOWED_ROOTS,
                    arguments=[uri, _MODE_WIDE],
                ),
            )
        )

    python_root_candidates = _infer_python_roots_candidates(report.discovery.project_root)
    missing_py_roots = _missing_roots(report.discovery.project_root, report.discovery.python_roots, python_root_candidates)
    if missing_py_roots:
        missing_py_roots_display = ", ".join(["`{}`".format(p) for p in missing_py_roots])
        actions.append(
            types.CodeAction(
                title="修复: 将 `{}` 加入 `yaml_dsl.editor.python_roots` (最小)".format(missing_py_roots[0]),
                kind=types.CodeActionKind.QuickFix,
                is_preferred=not bool(import_dir_rel),
                command=types.Command(
                    title="修复 python_roots (最小)",
                    command=_COMMAND_ADD_PYTHON_ROOTS,
                    arguments=[uri, _MODE_MINIMAL],
                ),
            )
        )
        actions.append(
            types.CodeAction(
                title="修复: 将 {} 加入 `yaml_dsl.editor.python_roots` (宽松)".format(missing_py_roots_display),
                kind=types.CodeActionKind.QuickFix,
                command=types.Command(
                    title="修复 python_roots (宽松)",
                    command=_COMMAND_ADD_PYTHON_ROOTS,
                    arguments=[uri, _MODE_WIDE],
                ),
            )
        )

    extraction = _safe_extract_reference_for_lsp(doc_state.text, params.range.start, uri=uri, op="codeAction")
    if extraction.reference:
        result = _safe_resolve_python_definition(extraction, python_roots=doc_state.python_roots, uri=uri)
        if result is not None and not result.locations and result.warnings:
            actions.append(
                types.CodeAction(
                    title="解释: Python 引用解析失败",
                    kind=types.CodeActionKind.QuickFix,
                    command=types.Command(
                        title="解释 Python 引用解析失败",
                        command=_COMMAND_EXPLAIN_RESOLUTION_FAILURE,
                        arguments=[uri, extraction.reference],
                    ),
                )
            )

    return actions


def _dump_discovery_payload(document_uri: str) -> Dict[str, Any]:
    path = _uri_to_path(str(document_uri or ""))
    if path is None:
        return {
            "project_root": "",
            "scalim_yaml_path": None,
            "python_roots": [],
            "allowed_yaml_roots": [],
            "error": "仅支持 file:// URI",
        }
    try:
        discovery = discover_yaml_dsl_editor_project(path)
    except Exception as exc:  # noqa: BLE001
        return {
            "project_root": str(path.parent),
            "scalim_yaml_path": None,
            "python_roots": [str(path.parent)],
            "allowed_yaml_roots": [str(path.parent)],
            "error": "{}: {}".format(type(exc).__name__, exc),
        }
    payload = discovery.as_dict()
    if "scalim_yaml_path" not in payload:
        payload["scalim_yaml_path"] = None
    return payload


def _cmd_explain_resolution_failure(
    _ls: LanguageServer,
    document_uri: str,
    reference: str,
    *,
    state: Dict[str, _DocumentState],
) -> Dict[str, Any]:
    uri = str(document_uri or "")
    doc_state = state.get(uri)
    if doc_state is None:
        return {"ok": False, "kind": "explain_only", "message": "文档未打开或未同步 `state`", "hints": [uri]}
    try:
        result = resolve_python_definition(str(reference or ""), python_roots=list(doc_state.python_roots))
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("解释 `Python` 引用解析失败 `uri`=%s: %s: %s", uri, type(exc).__name__, exc)
        return {
            "ok": False,
            "kind": "explain_only",
            "message": "解析失败: {}: {}".format(type(exc).__name__, exc),
            "hints": [str(reference or "")],
        }
    payload = result.as_dict()
    payload["ok"] = bool(result.locations)
    payload["kind"] = "definition_result"
    payload["reference"] = str(reference or "")
    return payload


async def _cmd_create_minimal_scalim_yaml(  # noqa: PLR0911
    ls: LanguageServer,
    document_uri: str,
    *,
    state: Dict[str, _DocumentState],
) -> Dict[str, Any]:
    uri = str(document_uri or "")
    doc_state = state.get(uri)
    if doc_state is None or doc_state.report is None:
        return {"ok": False, "kind": "explain_only", "message": "文档未打开或未同步 diagnostics", "hints": [uri]}

    report = doc_state.report
    if report.discovery.scalim_yaml_path is not None:
        return {
            "ok": False,
            "kind": "explain_only",
            "message": "`scalim.yaml` 已存在,无需创建",
            "hints": [str(report.discovery.scalim_yaml_path)],
        }

    workspace_root = _workspace_root_path(ls)
    if workspace_root is None:
        return {"ok": False, "kind": "explain_only", "message": "无法确定 workspace root,拒绝写入", "hints": []}

    project_root = report.discovery.project_root
    scalim_yaml_path = project_root / "scalim.yaml"
    if not _is_within_dir(scalim_yaml_path, workspace_root):
        return {"ok": False, "kind": "explain_only", "message": "目标不在 workspace 内,拒绝写入", "hints": [str(scalim_yaml_path)]}
    if not os.access(str(project_root), os.W_OK):
        return {"ok": False, "kind": "explain_only", "message": "目标目录不可写,拒绝写入", "hints": [str(project_root)]}

    python_roots = _infer_python_roots_candidates(project_root)
    content = _render_scalim_yaml_content(
        import_allowed_roots=["."],
        python_roots=[python_roots[0]] if python_roots else [],
    )
    edit = _workspace_edit_create_file_with_text(scalim_yaml_path, content)
    try:
        result = await ls.workspace_apply_edit_async(types.ApplyWorkspaceEditParams(edit=edit, label="创建最小 scalim.yaml"))
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("创建 `scalim.yaml` 失败: %s: %s", type(exc).__name__, exc)
        return {
            "ok": False,
            "kind": "explain_only",
            "message": "创建失败: {}: {}".format(type(exc).__name__, exc),
            "hints": [str(scalim_yaml_path)],
        }

    return {
        "ok": bool(result.applied),
        "kind": "workspace_edit",
        "applied": bool(result.applied),
        "failure_reason": str(result.failure_reason or ""),
    }


async def _cmd_add_import_allowed_roots(  # noqa: C901, PLR0911
    ls: LanguageServer,
    document_uri: str,
    mode: str,
    *,
    state: Dict[str, _DocumentState],
) -> Dict[str, Any]:
    uri = str(document_uri or "")
    doc_state = state.get(uri)
    if doc_state is None or doc_state.report is None:
        return {"ok": False, "kind": "explain_only", "message": "文档未打开或未同步 diagnostics", "hints": [uri]}

    report = doc_state.report
    scalim_yaml_path = report.discovery.scalim_yaml_path
    if scalim_yaml_path is None:
        return {"ok": False, "kind": "explain_only", "message": "缺少 `scalim.yaml`,请先创建", "hints": []}

    workspace_root = _workspace_root_path(ls)
    if workspace_root is None:
        return {"ok": False, "kind": "explain_only", "message": "无法确定 workspace root,拒绝写入", "hints": []}
    if not _is_within_dir(scalim_yaml_path, workspace_root):
        return {"ok": False, "kind": "explain_only", "message": "目标不在 workspace 内,拒绝写入", "hints": [str(scalim_yaml_path)]}
    if not os.access(str(scalim_yaml_path), os.W_OK):
        return {"ok": False, "kind": "explain_only", "message": "目标文件不可写,拒绝写入", "hints": [str(scalim_yaml_path)]}

    minimal_root = _first_import_escape_dir_rel(report)
    if not minimal_root:
        return {"ok": False, "kind": "explain_only", "message": "未找到可修复的 imports 越界错误", "hints": []}

    mode_text = str(mode or "")
    if mode_text == _MODE_MINIMAL:
        roots_to_add = [minimal_root]
    elif mode_text == _MODE_WIDE:
        roots_to_add = ["."]
    else:
        return {"ok": False, "kind": "explain_only", "message": "未知 mode: {}".format(mode_text), "hints": []}
    new_text = _update_scalim_yaml_text(
        scalim_yaml_path.read_text(encoding="utf-8"),
        import_allowed_roots_to_add=roots_to_add,
        python_roots_to_add=(),
    )
    if new_text is None:
        return {"ok": False, "kind": "explain_only", "message": "无法解析/更新 `scalim.yaml`", "hints": [str(scalim_yaml_path)]}

    edit = _workspace_edit_replace_entire_file(scalim_yaml_path, new_text)
    try:
        result = await ls.workspace_apply_edit_async(types.ApplyWorkspaceEditParams(edit=edit, label="更新 import_allowed_roots"))
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("更新 import_allowed_roots 失败: %s: %s", type(exc).__name__, exc)
        return {
            "ok": False,
            "kind": "explain_only",
            "message": "更新失败: {}: {}".format(type(exc).__name__, exc),
            "hints": [str(scalim_yaml_path)],
        }

    return {
        "ok": bool(result.applied),
        "kind": "workspace_edit",
        "applied": bool(result.applied),
        "failure_reason": str(result.failure_reason or ""),
    }


async def _cmd_add_python_roots(  # noqa: C901, PLR0911
    ls: LanguageServer,
    document_uri: str,
    mode: str,
    *,
    state: Dict[str, _DocumentState],
) -> Dict[str, Any]:
    uri = str(document_uri or "")
    doc_state = state.get(uri)
    if doc_state is None or doc_state.report is None:
        return {"ok": False, "kind": "explain_only", "message": "文档未打开或未同步 diagnostics", "hints": [uri]}

    report = doc_state.report
    scalim_yaml_path = report.discovery.scalim_yaml_path
    if scalim_yaml_path is None:
        return {"ok": False, "kind": "explain_only", "message": "缺少 `scalim.yaml`,请先创建", "hints": []}

    workspace_root = _workspace_root_path(ls)
    if workspace_root is None:
        return {"ok": False, "kind": "explain_only", "message": "无法确定 workspace root,拒绝写入", "hints": []}
    if not _is_within_dir(scalim_yaml_path, workspace_root):
        return {"ok": False, "kind": "explain_only", "message": "目标不在 workspace 内,拒绝写入", "hints": [str(scalim_yaml_path)]}
    if not os.access(str(scalim_yaml_path), os.W_OK):
        return {"ok": False, "kind": "explain_only", "message": "目标文件不可写,拒绝写入", "hints": [str(scalim_yaml_path)]}

    candidates = _infer_python_roots_candidates(report.discovery.project_root)
    missing = _missing_roots(report.discovery.project_root, report.discovery.python_roots, candidates)
    if not missing:
        return {"ok": False, "kind": "explain_only", "message": "未发现可补充的 python_roots", "hints": []}

    mode_text = str(mode or "")
    if mode_text == _MODE_MINIMAL:
        roots_to_add = [missing[0]]
    elif mode_text == _MODE_WIDE:
        roots_to_add = list(missing)
    else:
        return {"ok": False, "kind": "explain_only", "message": "未知 mode: {}".format(mode_text), "hints": []}
    new_text = _update_scalim_yaml_text(
        scalim_yaml_path.read_text(encoding="utf-8"),
        import_allowed_roots_to_add=(),
        python_roots_to_add=roots_to_add,
    )
    if new_text is None:
        return {"ok": False, "kind": "explain_only", "message": "无法解析/更新 `scalim.yaml`", "hints": [str(scalim_yaml_path)]}

    edit = _workspace_edit_replace_entire_file(scalim_yaml_path, new_text)
    try:
        result = await ls.workspace_apply_edit_async(types.ApplyWorkspaceEditParams(edit=edit, label="更新 python_roots"))
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("更新 python_roots 失败: %s: %s", type(exc).__name__, exc)
        return {
            "ok": False,
            "kind": "explain_only",
            "message": "更新失败: {}: {}".format(type(exc).__name__, exc),
            "hints": [str(scalim_yaml_path)],
        }

    return {
        "ok": bool(result.applied),
        "kind": "workspace_edit",
        "applied": bool(result.applied),
        "failure_reason": str(result.failure_reason or ""),
    }


def _workspace_root_path(ls: LanguageServer) -> Optional[Path]:
    raw = getattr(ls.workspace, "root_path", None)
    if not raw:
        return None
    return Path(str(raw)).expanduser().resolve(strict=False)


def _is_within_dir(path: Path, root: Path) -> bool:
    try:
        _ = path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _first_import_escape_dir_rel(report: YamlDslEditorDiagnosticsResult) -> str:
    for item in list(report.errors) + list(report.warnings):
        if str(item.code) != "yaml_import_expansion_error":
            continue
        msg = str(item.message or "")
        if _IMPORT_ESCAPES_ALLOWED_ROOTS_MARKER not in msg:
            continue
        match = _RESOLVED_PATH_RE.search(msg)
        if match is None:
            continue
        resolved = Path(match.group(1)).expanduser().resolve(strict=False)
        try:
            rel = resolved.parent.relative_to(report.discovery.project_root)
        except ValueError:
            return ""
        rel_text = rel.as_posix().strip("/")
        return rel_text or "."
    return ""


def _infer_python_roots_candidates(project_root: Path) -> List[str]:
    candidates: List[str] = []
    src_dir = project_root / "src"
    if src_dir.exists() and src_dir.is_dir():
        candidates.append("src")
    return candidates


def _missing_roots(project_root: Path, existing: Sequence[Path], candidates: Sequence[str]) -> List[str]:
    existing_rel: Dict[str, None] = {}
    for p in existing:
        try:
            rel = p.resolve(strict=False).relative_to(project_root.resolve(strict=False)).as_posix()
        except ValueError:
            continue
        rel_text = rel.strip("/") or "."
        existing_rel[rel_text] = None

    missing: List[str] = []
    for rel in candidates:
        rel_text = str(rel or "").strip("/") or "."
        if not rel_text:
            continue
        if rel_text in existing_rel:
            continue
        missing.append(rel_text)
    return missing


def _render_scalim_yaml_content(*, import_allowed_roots: Sequence[str], python_roots: Sequence[str]) -> str:
    lines: List[str] = ["yaml_dsl:"]
    if import_allowed_roots:
        lines.append("  import_allowed_roots:")
        for root in import_allowed_roots:
            lines.append("    - {}".format(str(root)))
    if python_roots:
        lines.append("  editor:")
        lines.append("    python_roots:")
        for root in python_roots:
            lines.append("      - {}".format(str(root)))
    return "\n".join(lines) + "\n"


def _yaml_rt() -> YAML:
    yaml_rt = YAML(typ="rt")
    yaml_rt.version = (1, 2)
    yaml_rt.default_flow_style = False
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    return yaml_rt


def _update_scalim_yaml_text(  # noqa: C901, PLR0911, PLR0912
    raw_text: str,
    *,
    import_allowed_roots_to_add: Sequence[str],
    python_roots_to_add: Sequence[str],
) -> Optional[str]:
    yaml_rt = _yaml_rt()
    try:
        loaded = yaml_rt.load(str(raw_text or "")) or {}
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(loaded, dict):
        return None

    yaml_dsl = loaded.get("yaml_dsl")
    if yaml_dsl is None:
        yaml_dsl = {}
        loaded["yaml_dsl"] = yaml_dsl
    if not isinstance(yaml_dsl, dict):
        return None

    if import_allowed_roots_to_add:
        roots = yaml_dsl.get("import_allowed_roots")
        if roots is None:
            roots = []
            yaml_dsl["import_allowed_roots"] = roots
        if not isinstance(roots, list):
            return None
        _extend_unique(roots, import_allowed_roots_to_add)

    if python_roots_to_add:
        editor = yaml_dsl.get("editor")
        if editor is None:
            editor = {}
            yaml_dsl["editor"] = editor
        if not isinstance(editor, dict):
            return None
        roots = editor.get("python_roots")
        if roots is None:
            roots = []
            editor["python_roots"] = roots
        if not isinstance(roots, list):
            return None
        _extend_unique(roots, python_roots_to_add)

    buf = StringIO()
    yaml_rt.dump(loaded, buf)
    text = buf.getvalue()
    if not text.endswith("\n"):
        text += "\n"
    return text


def _extend_unique(seq: List[Any], values: Sequence[str]) -> None:
    existing = {str(v) for v in seq}
    for value in values:
        v = str(value or "").strip()
        if not v or v in existing:
            continue
        seq.append(v)
        existing.add(v)


def _workspace_edit_create_file_with_text(path: Path, content: str) -> types.WorkspaceEdit:
    uri = path.as_uri()
    create = types.CreateFile(uri=uri, options=types.CreateFileOptions(overwrite=False, ignore_if_exists=True))
    doc = types.OptionalVersionedTextDocumentIdentifier(uri=uri, version=None)
    edit = types.TextEdit(range=types.Range(start=types.Position(0, 0), end=types.Position(0, 0)), new_text=str(content))
    return types.WorkspaceEdit(document_changes=[create, types.TextDocumentEdit(text_document=doc, edits=[edit])])


def _workspace_edit_replace_entire_file(path: Path, new_text: str) -> types.WorkspaceEdit:
    uri = path.as_uri()
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    end = _lsp_end_position(old)
    edit = types.TextEdit(range=types.Range(start=types.Position(0, 0), end=end), new_text=str(new_text))
    return types.WorkspaceEdit(changes={uri: [edit]})


def _lsp_end_position(text: str) -> types.Position:
    raw = str(text or "")
    if not raw:
        return types.Position(0, 0)
    line = raw.count("\n")
    col = len(raw.rsplit("\n", 1)[-1])
    return types.Position(int(line), int(col))


def _update_state_and_publish_diagnostics(
    ls: LanguageServer,
    uri: str,
    state: Dict[str, _DocumentState],
    *,
    yaml_text: Optional[str],
) -> None:
    if yaml_text is None:
        try:
            text_doc = ls.workspace.get_text_document(uri)
            yaml_text = str(text_doc.source)
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("工作区获取文档失败 `uri`=%s: %s: %s", uri, type(exc).__name__, exc)
            state[uri] = _DocumentState(text="", report=None, python_roots=())
            ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=[]))
            return

    yaml_path = _uri_to_path(uri)
    diagnostics, report = _compute_diagnostics_and_report(yaml_path=yaml_path, yaml_text=str(yaml_text))
    python_roots = tuple(report.discovery.python_roots) if report is not None else ()
    state[uri] = _DocumentState(text=str(yaml_text), report=report, python_roots=python_roots)
    ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics))


def _compute_diagnostics_and_report(
    *,
    yaml_path: Optional[Path],
    yaml_text: str,
) -> Tuple[List[types.Diagnostic], Optional[YamlDslEditorDiagnosticsResult]]:
    if yaml_path is None:
        return [], None
    try:
        report = collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("诊断计算失败 `path`=%s: %s: %s", yaml_path, type(exc).__name__, exc)
        return [], None

    diagnostics: List[types.Diagnostic] = []
    for item in list(report.errors) + list(report.warnings):
        rng = _to_lsp_range(item.range) if item.range is not None else types.Range(start=types.Position(0, 0), end=types.Position(0, 0))
        severity = types.DiagnosticSeverity.Error if item.severity == "error" else types.DiagnosticSeverity.Warning
        diagnostics.append(
            types.Diagnostic(
                range=rng,
                severity=severity,
                source="scalim",
                message=str(item.message),
                code=str(item.code or ""),
            )
        )
    return diagnostics, report


def _extract_reference_for_lsp(yaml_text: str, position: types.Position) -> YamlCursorExtractionResult:
    editor_pos = EditorPosition(line=int(position.line) + 1, column=int(position.character) + 1)
    return extract_yaml_dsl_python_reference_by_cursor(yaml_text, editor_pos)


def _to_lsp_range(rng: EditorRange) -> types.Range:
    return types.Range(
        start=types.Position(line=int(rng.start.line) - 1, character=int(rng.start.column) - 1),
        end=types.Position(line=int(rng.end.line) - 1, character=int(rng.end.column) - 1),
    )


def _uri_to_path(uri: str) -> Optional[Path]:
    parsed = urlparse(str(uri or ""))
    if parsed.scheme != "file":
        return None
    raw_path = unquote(parsed.path or "")
    if not raw_path:
        return None
    return Path(raw_path).expanduser().resolve(strict=False)
