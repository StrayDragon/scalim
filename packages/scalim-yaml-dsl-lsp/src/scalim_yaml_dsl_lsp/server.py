import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from .core import (
    PythonDefinitionResult,
    collect_yaml_dsl_editor_diagnostics,
    complete_python_reference,
    extract_yaml_dsl_python_reference_by_cursor,
    hover_python_reference,
    resolve_python_definition,
)
from .cursor_extraction import YamlCursorExtractionResult
from .editor_types import EditorPosition, EditorRange

__all__ = ()

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class _DocumentState:
    text: str
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
            state[uri] = _DocumentState(text="", python_roots=())
            ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=[]))
            return

    yaml_path = _uri_to_path(uri)
    diagnostics, python_roots = _compute_diagnostics_and_roots(yaml_path=yaml_path, yaml_text=str(yaml_text))
    state[uri] = _DocumentState(text=str(yaml_text), python_roots=python_roots)
    ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=diagnostics))


def _compute_diagnostics_and_roots(*, yaml_path: Optional[Path], yaml_text: str) -> Tuple[List[types.Diagnostic], Tuple[Path, ...]]:
    if yaml_path is None:
        return [], ()
    try:
        report = collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("诊断计算失败 `path`=%s: %s: %s", yaml_path, type(exc).__name__, exc)
        return [], ()

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
    return diagnostics, tuple(report.discovery.python_roots)


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
