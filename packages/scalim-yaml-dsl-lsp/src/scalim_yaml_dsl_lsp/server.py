import asyncio
import logging
import os
import re
from dataclasses import dataclass, replace
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Set, Tuple, cast
from urllib.parse import unquote, urlparse

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from scalim.dsl.yaml_dsl._internal.config_parsing.presets import load_scalim_preset_yaml_text
from scalim.vendor.yamlx.ruamel.yaml import YAML

from .core import (
    PythonDefinitionResult,
    YamlDslEditorDiagnosticsResult,
    YamlDslEditorEffectiveView,
    YamlDslEntityCompletionItem,
    YamlDslEntityCompletionResult,
    YamlDslEntityHintDiagnostic,
    YamlDslEntityIndex,
    YamlDslImportPathDefinitionResult,
    YamlDslSugarCompletionResult,
    YamlImportDefinitionResult,
    YamlImportHoverResult,
    build_yaml_dsl_editor_effective_view,
    build_yaml_dsl_entity_index,
    collect_yaml_dsl_editor_diagnostics,
    complete_python_attr_path_segment,
    complete_python_module_segment,
    complete_yaml_dsl_builtin_callable_reference,
    complete_yaml_dsl_entity_reference,
    complete_yaml_dsl_import_path_reference,
    complete_yaml_dsl_output_field_id,
    discover_yaml_dsl_editor_project,
    extract_yaml_dsl_entity_reference_by_cursor,
    extract_yaml_dsl_import_reference_by_cursor,
    extract_yaml_dsl_output_field_reference_by_cursor,
    extract_yaml_dsl_python_reference_by_cursor,
    extract_yaml_dsl_yaml_alias_reference_by_cursor,
    hover_python_reference,
    hover_yaml_dsl_builtin_callable_reference,
    hover_yaml_dsl_entity_reference,
    hover_yaml_dsl_import_path_reference,
    hover_yaml_dsl_output_field_id,
    hover_yaml_dsl_yaml_alias,
    hover_yaml_import_reference,
    is_probably_yaml_dsl_document,
    resolve_python_definition,
    resolve_yaml_dsl_builtin_callable_definition,
    resolve_yaml_dsl_entity_definition,
    resolve_yaml_dsl_import_path_definition,
    resolve_yaml_dsl_output_field_definition,
    resolve_yaml_dsl_yaml_alias_definition,
    resolve_yaml_import_definition,
)
from .cursor_extraction import YamlCursorExtractionResult, extract_yaml_dsl_import_path_reference_by_cursor
from .editor_types import EditorPosition, EditorRange

__all__ = ()

_LOG = logging.getLogger(__name__)

_COMMAND_DUMP_DISCOVERY = "scalim.dumpDiscovery"
_COMMAND_CREATE_MINIMAL_SCALIM_YAML = "scalim.yaml.createMinimal"
_COMMAND_ADD_IMPORT_ROOTS = "scalim.yaml.addImportRoots"
_COMMAND_ADD_IMPORT_ROOT_ALIAS = "scalim.yaml.addImportRootAlias"
_COMMAND_ADD_PYTHON_ROOTS = "scalim.yaml.addPythonRoots"
_COMMAND_EXPLAIN_RESOLUTION_FAILURE = "scalim.python.explainResolutionFailure"
_COMMAND_PRESET_GET_TEXT = "scalim.preset.getText"

_MODE_MINIMAL = "minimal"
_MODE_WIDE = "wide"

_IMPORT_ESCAPES_ALLOWED_ROOTS_MARKER = "YAML path escapes allowed roots:"
_RESOLVED_PATH_RE = re.compile(r"resolved_path='([^']+)'")
_IMPORT_RAW_PATH_RE = re.compile(r"raw='([^']+)'")
_IMPORT_RESERVED_ALIAS_MARKER = "reserved alias prefixes are not allowed"
_IMPORT_ALIAS_TOKEN_RE = re.compile(r"^(?:@/|([a-zA-Z_][a-zA-Z0-9_]*):/)")


@dataclass(frozen=True)
class _DocumentState:
    text: str
    version: int
    report: Optional[YamlDslEditorDiagnosticsResult]
    python_roots: Tuple[Path, ...]
    base_diagnostics: Tuple[types.Diagnostic, ...] = ()
    hint_diagnostics: Tuple[types.Diagnostic, ...] = ()
    entity_index: Optional[YamlDslEntityIndex] = None
    effective_view: Optional[YamlDslEditorEffectiveView] = None


@dataclass(frozen=True)
class _ReferenceCompletionContext:
    kind: str
    module_path: str
    prefix_module_path: str
    segment_prefix: str
    attr_path_prefix: str
    replace_start_offset: int
    replace_end_offset: int


def create_server() -> LanguageServer:
    server = LanguageServer(
        "scalim-yaml-dsl-lsp",
        "0.7.5",
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
        await _update_state_and_publish_diagnostics(
            ls,
            uri,
            state,
            yaml_text=str(params.text_document.text or ""),
            version=int(params.text_document.version or 0),
        )

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    async def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams) -> None:
        uri = str(params.text_document.uri)
        yaml_text = ""
        if params.content_changes:
            yaml_text = str(params.content_changes[-1].text or "")
        await _update_state_and_publish_diagnostics(
            ls,
            uri,
            state,
            yaml_text=yaml_text or None,
            version=int(params.text_document.version or 0),
        )

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    async def did_close(_ls: LanguageServer, params: types.DidCloseTextDocumentParams) -> None:
        uri = str(params.text_document.uri)
        state.pop(uri, None)


def _register_definition_feature(server: LanguageServer, state: Dict[str, _DocumentState]) -> None:
    @server.feature(types.TEXT_DOCUMENT_DEFINITION)
    async def definition(_ls: LanguageServer, params: types.DefinitionParams) -> Optional[List[types.Location]]:
        return await _handle_definition(_ls, params, state=state)


async def _handle_definition(
    ls: LanguageServer,
    params: types.DefinitionParams,
    *,
    state: Dict[str, _DocumentState],
) -> Optional[List[types.Location]]:
    uri = str(params.text_document.uri)
    doc_state = state.get(uri)
    if doc_state is None or doc_state.report is None:
        return None
    anchor_path = _uri_to_path(uri)

    handled, locations = await _try_handle_python_definition(
        doc_state,
        position=params.position,
        anchor_path=anchor_path,
        uri=uri,
    )
    if handled:
        return locations

    if anchor_path is None:
        return None

    locations = await _handle_yaml_import_path_definition(
        doc_state,
        position=params.position,
        anchor_path=anchor_path,
        uri=uri,
    )
    if locations is None:
        locations = await _handle_yaml_import_definition(
            doc_state,
            position=params.position,
            anchor_path=anchor_path,
            uri=uri,
        )

    if locations is None and doc_state.effective_view is not None:
        locations = await _handle_yaml_dsl_yaml_alias_definition(
            doc_state,
            position=params.position,
            anchor_path=anchor_path,
            uri=uri,
        )

    if locations is None and doc_state.effective_view is not None:
        locations = await _handle_yaml_dsl_output_field_definition(
            doc_state,
            position=params.position,
            uri=uri,
        )

    if locations is None:
        locations = await _handle_yaml_dsl_entity_definition(
            ls,
            doc_state,
            position=params.position,
            anchor_path=anchor_path,
            uri=uri,
            state=state,
        )

    return locations


async def _try_handle_python_definition(
    doc_state: _DocumentState,
    *,
    position: types.Position,
    anchor_path: Optional[Path],
    uri: str,
) -> Tuple[bool, Optional[List[types.Location]]]:
    extraction = _safe_extract_reference_for_lsp(doc_state.text, position, uri=uri, op="definition")
    if not extraction.reference:
        return False, None

    ref = str(extraction.reference or "")
    if ref.lstrip().startswith("^"):
        result = await _safe_resolve_yaml_dsl_builtin_callable_definition(
            extraction,
            python_roots=doc_state.python_roots,
            anchor_path=anchor_path,
            uri=uri,
        )
    else:
        result = await _safe_resolve_python_definition(
            extraction,
            python_roots=doc_state.python_roots,
            anchor_path=anchor_path,
            uri=uri,
        )
    if result is None:
        return True, None

    locations: List[types.Location] = []
    for loc in result.locations:
        location = _location_from_definition_location(loc.file_path, loc.range)
        if location is not None:
            locations.append(location)
    return True, locations or None


async def _handle_yaml_import_definition(
    doc_state: _DocumentState,
    *,
    position: types.Position,
    anchor_path: Path,
    uri: str,
) -> Optional[List[types.Location]]:
    if doc_state.report is None:
        return None
    import_extraction = _safe_extract_import_reference_for_lsp(doc_state.text, position, uri=uri, op="definition")
    if not import_extraction.reference:
        return None

    import_result = await _safe_resolve_yaml_import_definition(
        import_extraction,
        anchor_yaml_text=doc_state.text,
        anchor_yaml_path=anchor_path,
        allowed_yaml_roots=doc_state.report.discovery.allowed_yaml_roots,
        scalim_yaml_override=doc_state.report.discovery.scalim_yaml_path,
        project_root_override=doc_state.report.discovery.project_root,
        uri=uri,
    )
    if import_result is None:
        return None

    locations: List[types.Location] = []
    for loc in import_result.locations:
        location = _location_from_definition_location(loc.file_path, loc.range)
        if location is not None:
            locations.append(location)
    return locations or None


_PRESET_VDOC_SCHEME = "scalim-preset"


def _preset_virtual_uri(preset_id: str) -> str:
    # Use an empty authority to keep the id as a simple path segment.
    safe_id = str(preset_id or "").lstrip("/")
    return "{}:///{}".format(_PRESET_VDOC_SCHEME, safe_id)


async def _handle_yaml_import_path_definition(
    doc_state: _DocumentState,
    *,
    position: types.Position,
    anchor_path: Path,
    uri: str,
) -> Optional[List[types.Location]]:
    if doc_state.report is None:
        return None
    extraction = _safe_extract_import_path_reference_for_lsp(doc_state.text, position, uri=uri, op="definition")
    if not extraction.reference:
        return None

    result = await _safe_resolve_yaml_import_path_definition(
        extraction,
        anchor_yaml_path=anchor_path,
        allowed_yaml_roots=doc_state.report.discovery.allowed_yaml_roots,
        scalim_yaml_override=doc_state.report.discovery.scalim_yaml_path,
        project_root_override=doc_state.report.discovery.project_root,
        uri=uri,
    )
    if result is None:
        return None
    if result.warnings:
        _LOG.info("定义跳转(`imports.*`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, extraction.yaml_path, list(result.warnings))

    locations: List[types.Location] = []
    if result.kind == "file" and result.file_path:
        location = _location_from_definition_location(result.file_path, None)
        if location is not None:
            locations.append(location)
    elif result.kind == "preset" and result.preset_id:
        locations.append(
            types.Location(
                uri=_preset_virtual_uri(result.preset_id),
                range=types.Range(start=types.Position(0, 0), end=types.Position(0, 0)),
            )
        )

    return locations or None


async def _handle_yaml_dsl_yaml_alias_definition(
    doc_state: _DocumentState,
    *,
    position: types.Position,
    anchor_path: Path,
    uri: str,
) -> Optional[List[types.Location]]:
    view = doc_state.effective_view
    if view is None:
        return None
    extraction = _safe_extract_yaml_alias_reference_for_lsp(doc_state.text, position, uri=uri, op="definition")
    if not extraction.reference:
        return None

    try:
        result = await asyncio.to_thread(resolve_yaml_dsl_yaml_alias_definition, extraction.reference, view=view)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "定义跳转(`yaml_alias`) 解析失败 `uri`=%s: %s: %s",
            uri,
            type(exc).__name__,
            exc,
        )
        return None
    if result.warnings:
        _LOG.info("定义跳转(`yaml_alias`) 警告 `uri`=%s `warnings`=%s", uri, list(result.warnings))
    if result.range is None:
        return None

    location = _location_from_definition_location(str(anchor_path), result.range)
    return [location] if location is not None else None


async def _handle_yaml_dsl_output_field_definition(
    doc_state: _DocumentState,
    *,
    position: types.Position,
    uri: str,
) -> Optional[List[types.Location]]:
    view = doc_state.effective_view
    if view is None:
        return None
    extraction = _safe_extract_output_field_reference_for_lsp(doc_state.text, position, uri=uri, op="definition")
    if not extraction.reference:
        return None

    try:
        result = await asyncio.to_thread(resolve_yaml_dsl_output_field_definition, extraction.reference, view=view)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "定义跳转(`outputs.*.fields`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None

    locations: List[types.Location] = []
    for loc in result.locations:
        location = _location_from_definition_location(loc.file_path, loc.range)
        if location is not None:
            locations.append(location)
    return locations or None


async def _handle_yaml_dsl_entity_definition(
    ls: LanguageServer,
    doc_state: _DocumentState,
    *,
    position: types.Position,
    anchor_path: Path,
    uri: str,
    state: Dict[str, _DocumentState],
) -> Optional[List[types.Location]]:
    entity_index = doc_state.entity_index
    if entity_index is None:
        return None

    extraction = _safe_extract_entity_reference_for_lsp(doc_state.text, position, uri=uri, op="definition")
    if not extraction.kind or not extraction.reference:
        return None

    try:
        result = await asyncio.to_thread(
            resolve_yaml_dsl_entity_definition,
            extraction,
            entity_index=entity_index,
            anchor_yaml_path=anchor_path,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "定义跳转解析失败(`entity`) `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None

    if result.warnings:
        _LOG.info("定义跳转(`entity`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, extraction.yaml_path, list(result.warnings))

    _maybe_publish_entity_hint_diagnostic(ls, uri, state=state, hint=result.hint)

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


async def _safe_resolve_python_definition(
    extraction: YamlCursorExtractionResult,
    *,
    python_roots: Tuple[Path, ...],
    anchor_path: Optional[Path],
    uri: str,
) -> Optional[PythonDefinitionResult]:
    try:
        result = await asyncio.to_thread(
            resolve_python_definition,
            extraction.reference,
            python_roots=list(python_roots),
            anchor_path=anchor_path,
        )
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
    if result.trace is not None and (not result.locations or result.warnings):
        _LOG.debug(
            "定义跳转解析链路 `uri`=%s `yaml_path`=%s `steps`=%s",
            uri,
            extraction.yaml_path,
            len(result.trace.steps),
        )
    return result


async def _safe_resolve_yaml_dsl_builtin_callable_definition(
    extraction: YamlCursorExtractionResult,
    *,
    python_roots: Tuple[Path, ...],
    anchor_path: Optional[Path],
    uri: str,
) -> Optional[PythonDefinitionResult]:
    try:
        result = await asyncio.to_thread(
            resolve_yaml_dsl_builtin_callable_definition,
            extraction.reference,
            python_roots=list(python_roots),
            anchor_path=anchor_path,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "定义跳转解析失败(`builtin`) `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None
    if result.warnings:
        _LOG.info("定义跳转(`builtin`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, extraction.yaml_path, list(result.warnings))
    return result


def _safe_extract_import_reference_for_lsp(
    yaml_text: str,
    position: types.Position,
    *,
    uri: str,
    op: str,
) -> YamlCursorExtractionResult:
    try:
        extraction = _extract_import_reference_for_lsp(yaml_text, position)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("%s(`$import`) 光标抽取失败 `uri`=%s: %s: %s", op, uri, type(exc).__name__, exc)
        return YamlCursorExtractionResult(warnings=("{}(`$import`) 光标抽取失败".format(op),))
    if extraction.warnings:
        _LOG.debug(
            "%s(`$import`) 光标抽取警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
            op,
            uri,
            extraction.yaml_path,
            list(extraction.warnings),
        )
    return extraction


def _safe_extract_import_path_reference_for_lsp(
    yaml_text: str,
    position: types.Position,
    *,
    uri: str,
    op: str,
) -> YamlCursorExtractionResult:
    try:
        extraction = _extract_import_path_reference_for_lsp(yaml_text, position)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("%s(`imports.*`) 光标抽取失败 `uri`=%s: %s: %s", op, uri, type(exc).__name__, exc)
        return YamlCursorExtractionResult(warnings=("{}(`imports.*`) 光标抽取失败".format(op),))
    if extraction.warnings:
        _LOG.debug(
            "%s(`imports.*`) 光标抽取警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
            op,
            uri,
            extraction.yaml_path,
            list(extraction.warnings),
        )
    return extraction


def _safe_extract_output_field_reference_for_lsp(
    yaml_text: str,
    position: types.Position,
    *,
    uri: str,
    op: str,
) -> YamlCursorExtractionResult:
    try:
        extraction = _extract_output_field_reference_for_lsp(yaml_text, position)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("%s(`outputs.*.fields`) 光标抽取失败 `uri`=%s: %s: %s", op, uri, type(exc).__name__, exc)
        return YamlCursorExtractionResult(warnings=("{}(`outputs.*.fields`) 光标抽取失败".format(op),))
    if extraction.warnings:
        _LOG.debug(
            "%s(`outputs.*.fields`) 光标抽取警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
            op,
            uri,
            extraction.yaml_path,
            list(extraction.warnings),
        )
    return extraction


def _safe_extract_yaml_alias_reference_for_lsp(
    yaml_text: str,
    position: types.Position,
    *,
    uri: str,
    op: str,
) -> YamlCursorExtractionResult:
    try:
        extraction = _extract_yaml_alias_reference_for_lsp(yaml_text, position)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("%s(`yaml_alias`) 光标抽取失败 `uri`=%s: %s: %s", op, uri, type(exc).__name__, exc)
        return YamlCursorExtractionResult(warnings=("{}(`yaml_alias`) 光标抽取失败".format(op),))
    if extraction.warnings:
        _LOG.debug(
            "%s(`yaml_alias`) 光标抽取警告 `uri`=%s `warnings`=%s",
            op,
            uri,
            list(extraction.warnings),
        )
    return extraction


def _safe_extract_entity_reference_for_lsp(
    yaml_text: str,
    position: types.Position,
    *,
    uri: str,
    op: str,
) -> YamlCursorExtractionResult:
    try:
        extraction = _extract_entity_reference_for_lsp(yaml_text, position)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("%s(`entity`) 光标抽取失败 `uri`=%s: %s: %s", op, uri, type(exc).__name__, exc)
        return YamlCursorExtractionResult(warnings=("{}(`entity`) 光标抽取失败".format(op),))
    if extraction.warnings:
        _LOG.debug(
            "%s(`entity`) 光标抽取警告 `uri`=%s `yaml_path`=%s `kind`=%s `warnings`=%s",
            op,
            uri,
            extraction.yaml_path,
            extraction.kind,
            list(extraction.warnings),
        )
    return extraction


def _diagnostic_key(diag: types.Diagnostic) -> Tuple[str, str, int, int, int, int]:
    rng = diag.range
    return (
        str(diag.code or ""),
        str(diag.message or ""),
        int(rng.start.line),
        int(rng.start.character),
        int(rng.end.line),
        int(rng.end.character),
    )


def _lsp_diagnostic_from_entity_hint(hint: YamlDslEntityHintDiagnostic) -> types.Diagnostic:
    rng = types.Range(start=types.Position(0, 0), end=types.Position(0, 0))
    if hint.range is not None:
        rng = _to_lsp_range(hint.range)
    return types.Diagnostic(
        range=rng,
        severity=types.DiagnosticSeverity.Hint,
        source="scalim",
        message=str(hint.message),
        code=str(hint.code or "scalim_unknown_entity_id"),
        data=hint.as_dict(),
    )


def _maybe_publish_entity_hint_diagnostic(
    ls: LanguageServer,
    uri: str,
    *,
    state: Dict[str, _DocumentState],
    hint: Optional[YamlDslEntityHintDiagnostic],
) -> None:
    if hint is None:
        return

    doc_state = state.get(uri)
    if doc_state is None:
        return

    diag = _lsp_diagnostic_from_entity_hint(hint)
    diag_key = _diagnostic_key(diag)
    existing_keys = {_diagnostic_key(d) for d in doc_state.hint_diagnostics}
    if diag_key in existing_keys:
        return

    new_hints = (*doc_state.hint_diagnostics, diag)
    state[uri] = replace(doc_state, hint_diagnostics=new_hints)
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=uri,
            diagnostics=list(doc_state.base_diagnostics) + list(new_hints),
        )
    )


async def _safe_resolve_yaml_import_definition(
    extraction: YamlCursorExtractionResult,
    *,
    anchor_yaml_text: str,
    anchor_yaml_path: Path,
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Path],
    project_root_override: Path,
    uri: str,
) -> Optional[YamlImportDefinitionResult]:
    try:
        result = await asyncio.to_thread(
            resolve_yaml_import_definition,
            extraction.reference,
            anchor_yaml_text=anchor_yaml_text,
            anchor_yaml_path=anchor_yaml_path,
            allowed_yaml_roots=allowed_yaml_roots,
            scalim_yaml_override=scalim_yaml_override,
            project_root_override=project_root_override,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "定义跳转(`$import`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None
    if result.warnings:
        _LOG.info("定义跳转(`$import`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, extraction.yaml_path, list(result.warnings))
    return result


async def _safe_resolve_yaml_import_path_definition(
    extraction: YamlCursorExtractionResult,
    *,
    anchor_yaml_path: Path,
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Path],
    project_root_override: Path,
    uri: str,
) -> Optional[YamlDslImportPathDefinitionResult]:
    try:
        result = await asyncio.to_thread(
            resolve_yaml_dsl_import_path_definition,
            extraction,
            anchor_yaml_path=anchor_yaml_path,
            allowed_yaml_roots=allowed_yaml_roots,
            scalim_yaml_override=scalim_yaml_override,
            project_root_override=project_root_override,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "定义跳转(`imports.*`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None
    return result


def _register_hover_feature(server: LanguageServer, state: Dict[str, _DocumentState]) -> None:
    @server.feature(types.TEXT_DOCUMENT_HOVER)
    async def hover(_ls: LanguageServer, params: types.HoverParams) -> Optional[types.Hover]:
        return await _handle_hover(_ls, params, state=state)


async def _try_handle_python_hover(
    doc_state: _DocumentState,
    position: types.Position,
    *,
    anchor_path: Optional[Path],
    uri: str,
) -> Tuple[bool, Optional[types.Hover]]:
    extraction = _safe_extract_reference_for_lsp(doc_state.text, position, uri=uri, op="悬浮提示(`hover`)")
    if not extraction.reference:
        return False, None

    ref = str(extraction.reference or "")
    if ref.lstrip().startswith("^"):
        hover = await _hover_builtin_callable_extraction(
            extraction,
            python_roots=doc_state.python_roots,
            anchor_path=anchor_path,
            uri=uri,
        )
    else:
        hover = await _hover_python_extraction(
            extraction,
            python_roots=doc_state.python_roots,
            anchor_path=anchor_path,
            uri=uri,
        )
    return True, hover


async def _try_handle_yaml_import_path_hover(
    doc_state: _DocumentState,
    position: types.Position,
    *,
    anchor_yaml_path: Path,
    uri: str,
) -> Tuple[bool, Optional[types.Hover]]:
    extraction = _safe_extract_import_path_reference_for_lsp(doc_state.text, position, uri=uri, op="悬浮提示(`hover`)")
    if not extraction.reference:
        return False, None

    report = doc_state.report
    if report is None:
        return True, None

    hover = await _hover_yaml_import_path_extraction(
        extraction,
        anchor_yaml_path=anchor_yaml_path,
        allowed_yaml_roots=report.discovery.allowed_yaml_roots,
        scalim_yaml_override=report.discovery.scalim_yaml_path,
        project_root_override=report.discovery.project_root,
        uri=uri,
    )
    return True, hover


async def _try_handle_effective_view_hover(
    doc_state: _DocumentState,
    position: types.Position,
    *,
    uri: str,
) -> Optional[types.Hover]:
    if doc_state.effective_view is None:
        return None
    view = doc_state.effective_view

    alias_extraction = _safe_extract_yaml_alias_reference_for_lsp(doc_state.text, position, uri=uri, op="悬浮提示(`hover`)")
    if alias_extraction.reference:
        alias_hover = await _hover_yaml_alias_extraction(alias_extraction, view=view, uri=uri)
        if alias_hover is not None:
            return alias_hover

    output_field_extraction = _safe_extract_output_field_reference_for_lsp(doc_state.text, position, uri=uri, op="悬浮提示(`hover`)")
    if output_field_extraction.reference:
        out_hover = await _hover_output_field_extraction(output_field_extraction, view=view, uri=uri)
        if out_hover is not None:
            return out_hover

    return None


async def _handle_yaml_import_or_entity_hover(
    ls: LanguageServer,
    doc_state: _DocumentState,
    position: types.Position,
    *,
    anchor_yaml_path: Path,
    uri: str,
    state: Dict[str, _DocumentState],
) -> Optional[types.Hover]:
    report = doc_state.report
    if report is None:
        return None

    import_extraction = _safe_extract_import_reference_for_lsp(doc_state.text, position, uri=uri, op="悬浮提示(`hover`)")
    if not import_extraction.reference:
        return await _handle_yaml_dsl_entity_hover(
            ls,
            doc_state,
            position=position,
            anchor_path=anchor_yaml_path,
            uri=uri,
            state=state,
        )

    return await _hover_yaml_import_extraction(
        import_extraction,
        anchor_yaml_text=doc_state.text,
        anchor_yaml_path=anchor_yaml_path,
        allowed_yaml_roots=report.discovery.allowed_yaml_roots,
        scalim_yaml_override=report.discovery.scalim_yaml_path,
        project_root_override=report.discovery.project_root,
        uri=uri,
    )


async def _handle_hover(ls: LanguageServer, params: types.HoverParams, *, state: Dict[str, _DocumentState]) -> Optional[types.Hover]:
    uri = str(params.text_document.uri)
    doc_state = state.get(uri)
    if doc_state is None or doc_state.report is None:
        return None
    anchor_path = _uri_to_path(uri)

    handled, hover = await _try_handle_python_hover(doc_state, params.position, anchor_path=anchor_path, uri=uri)
    if handled:
        return hover

    if anchor_path is None:
        return None

    handled, hover = await _try_handle_yaml_import_path_hover(doc_state, params.position, anchor_yaml_path=anchor_path, uri=uri)
    if handled:
        return hover

    hover = await _try_handle_effective_view_hover(doc_state, params.position, uri=uri)
    if hover is not None:
        return hover

    return await _handle_yaml_import_or_entity_hover(
        ls,
        doc_state,
        params.position,
        anchor_yaml_path=anchor_path,
        uri=uri,
        state=state,
    )


async def _hover_builtin_callable_extraction(
    extraction: YamlCursorExtractionResult,
    *,
    python_roots: Tuple[Path, ...],
    anchor_path: Optional[Path],
    uri: str,
) -> Optional[types.Hover]:
    try:
        result = await asyncio.to_thread(
            hover_yaml_dsl_builtin_callable_reference,
            extraction.reference,
            python_roots=list(python_roots),
            anchor_path=anchor_path,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "悬浮提示(`hover`, `builtin`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None
    if result.warnings:
        _LOG.info(
            "悬浮提示(`hover`, `builtin`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
            uri,
            extraction.yaml_path,
            list(result.warnings),
        )
    if not str(result.text or "").strip():
        return None
    return types.Hover(contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=str(result.text)))


async def _hover_python_extraction(
    extraction: YamlCursorExtractionResult,
    *,
    python_roots: Tuple[Path, ...],
    anchor_path: Optional[Path],
    uri: str,
) -> Optional[types.Hover]:
    try:
        result = await asyncio.to_thread(
            hover_python_reference,
            extraction.reference,
            python_roots=list(python_roots),
            anchor_path=anchor_path,
        )
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


async def _hover_yaml_import_extraction(
    extraction: YamlCursorExtractionResult,
    *,
    anchor_yaml_text: str,
    anchor_yaml_path: Path,
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Path],
    project_root_override: Path,
    uri: str,
) -> Optional[types.Hover]:
    import_result = await _safe_hover_yaml_import_reference(
        extraction,
        anchor_yaml_text=anchor_yaml_text,
        anchor_yaml_path=anchor_yaml_path,
        allowed_yaml_roots=allowed_yaml_roots,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
        uri=uri,
    )
    if import_result is None or not import_result.text.strip():
        return None
    return types.Hover(contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=str(import_result.text)))


async def _hover_yaml_import_path_extraction(
    extraction: YamlCursorExtractionResult,
    *,
    anchor_yaml_path: Path,
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Path],
    project_root_override: Path,
    uri: str,
) -> Optional[types.Hover]:
    try:
        result = await asyncio.to_thread(
            hover_yaml_dsl_import_path_reference,
            extraction,
            anchor_yaml_path=anchor_yaml_path,
            allowed_yaml_roots=allowed_yaml_roots,
            scalim_yaml_override=scalim_yaml_override,
            project_root_override=project_root_override,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "悬浮提示(`hover`, `imports.*`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None
    if result.warnings:
        _LOG.info(
            "悬浮提示(`hover`, `imports.*`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
            uri,
            extraction.yaml_path,
            list(result.warnings),
        )
    if not str(result.text or "").strip():
        return None
    return types.Hover(contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=str(result.text)))


async def _hover_yaml_alias_extraction(
    extraction: YamlCursorExtractionResult,
    *,
    view: YamlDslEditorEffectiveView,
    uri: str,
) -> Optional[types.Hover]:
    try:
        result = await asyncio.to_thread(hover_yaml_dsl_yaml_alias, extraction.reference, view=view)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "悬浮提示(`hover`, `yaml_alias`) 解析失败 `uri`=%s: %s: %s",
            uri,
            type(exc).__name__,
            exc,
        )
        return None
    if result.warnings:
        _LOG.info("悬浮提示(`hover`, `yaml_alias`) 警告 `uri`=%s `warnings`=%s", uri, list(result.warnings))
    if not str(result.text or "").strip():
        return None
    return types.Hover(contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=str(result.text)))


async def _hover_output_field_extraction(
    extraction: YamlCursorExtractionResult,
    *,
    view: YamlDslEditorEffectiveView,
    uri: str,
) -> Optional[types.Hover]:
    try:
        result = await asyncio.to_thread(hover_yaml_dsl_output_field_id, extraction.reference, view=view)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "悬浮提示(`hover`, `outputs.*.fields`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None
    if result.warnings:
        _LOG.info(
            "悬浮提示(`hover`, `outputs.*.fields`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
            uri,
            extraction.yaml_path,
            list(result.warnings),
        )
    if not str(result.text or "").strip():
        return None
    return types.Hover(contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=str(result.text)))


async def _safe_hover_yaml_import_reference(
    extraction: YamlCursorExtractionResult,
    *,
    anchor_yaml_text: str,
    anchor_yaml_path: Path,
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Path],
    project_root_override: Path,
    uri: str,
) -> Optional[YamlImportHoverResult]:
    try:
        result = await asyncio.to_thread(
            hover_yaml_import_reference,
            extraction.reference,
            anchor_yaml_text=anchor_yaml_text,
            anchor_yaml_path=anchor_yaml_path,
            allowed_yaml_roots=allowed_yaml_roots,
            scalim_yaml_override=scalim_yaml_override,
            project_root_override=project_root_override,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "悬浮提示(`hover`, `$import`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None
    if result.warnings:
        _LOG.info(
            "悬浮提示(`hover`, `$import`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, extraction.yaml_path, list(result.warnings)
        )
    return result


async def _handle_yaml_dsl_entity_hover(
    ls: LanguageServer,
    doc_state: _DocumentState,
    *,
    position: types.Position,
    anchor_path: Path,
    uri: str,
    state: Dict[str, _DocumentState],
) -> Optional[types.Hover]:
    _ = anchor_path
    entity_index = doc_state.entity_index
    if entity_index is None:
        return None

    extraction = _safe_extract_entity_reference_for_lsp(doc_state.text, position, uri=uri, op="悬浮提示(`hover`)")
    if not extraction.kind or not extraction.reference:
        return None

    try:
        result = await asyncio.to_thread(
            hover_yaml_dsl_entity_reference,
            extraction,
            entity_index=entity_index,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "悬浮提示(`hover`, `entity`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return None

    if result.warnings:
        _LOG.info(
            "悬浮提示(`hover`, `entity`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
            uri,
            extraction.yaml_path,
            list(result.warnings),
        )

    _maybe_publish_entity_hint_diagnostic(ls, uri, state=state, hint=result.hint)

    if not str(result.text or "").strip():
        return None
    return types.Hover(contents=types.MarkupContent(kind=types.MarkupKind.PlainText, value=str(result.text)))


def _cursor_offset_for_completion(position: types.Position, extraction_range: EditorRange, *, reference_len: int) -> Optional[int]:
    cursor_col1 = int(position.character) + 1
    if cursor_col1 < int(extraction_range.start.column) or cursor_col1 > int(extraction_range.end.column):
        return None
    cursor_offset = int(cursor_col1) - int(extraction_range.start.column)
    if cursor_offset < 0:
        return None
    return min(int(cursor_offset), int(reference_len))


def _completion_segment_bounds(text: str, offset: int) -> Tuple[int, int]:
    o = max(0, min(int(offset), len(text)))
    start = text.rfind(".", 0, o)
    start = start + 1 if start != -1 else 0
    end = text.find(".", o)
    end = end if end != -1 else len(text)
    return int(start), int(end)


def _strip_trailing_separator(prefix_slice: str) -> str:
    prefix = str(prefix_slice or "")
    if prefix.endswith(".") and set(prefix) != {"."}:
        return prefix[:-1]
    return prefix


def _completion_context_colon(reference: str, cursor_offset: int) -> _ReferenceCompletionContext:
    colon_idx = reference.find(":")
    module_text = reference[:colon_idx]
    attr_start = colon_idx + 1
    if cursor_offset <= colon_idx:
        seg_start, seg_end = _completion_segment_bounds(module_text, cursor_offset)
        prefix_slice = module_text[:seg_start]
        return _ReferenceCompletionContext(
            kind="module",
            module_path=module_text,
            prefix_module_path=_strip_trailing_separator(prefix_slice),
            segment_prefix=module_text[seg_start:cursor_offset],
            attr_path_prefix="",
            replace_start_offset=seg_start,
            replace_end_offset=seg_end,
        )

    attr_text = reference[attr_start:]
    attr_cursor = cursor_offset - attr_start
    seg_start, seg_end = _completion_segment_bounds(attr_text, attr_cursor)
    return _ReferenceCompletionContext(
        kind="attr",
        module_path=module_text,
        prefix_module_path="",
        segment_prefix="",
        attr_path_prefix=attr_text[:attr_cursor],
        replace_start_offset=attr_start + seg_start,
        replace_end_offset=attr_start + seg_end,
    )


def _completion_context_dotted(reference: str, cursor_offset: int) -> _ReferenceCompletionContext:
    dot_idx = reference.rfind(".")
    if dot_idx == -1:
        seg_start, seg_end = _completion_segment_bounds(reference, cursor_offset)
        prefix_slice = reference[:seg_start]
        return _ReferenceCompletionContext(
            kind="module",
            module_path=reference,
            prefix_module_path=_strip_trailing_separator(prefix_slice),
            segment_prefix=reference[seg_start:cursor_offset],
            attr_path_prefix="",
            replace_start_offset=seg_start,
            replace_end_offset=seg_end,
        )

    module_text = reference[:dot_idx]
    attr_start = dot_idx + 1
    if cursor_offset <= dot_idx:
        module_cursor = min(int(cursor_offset), len(module_text))
        seg_start, seg_end = _completion_segment_bounds(module_text, module_cursor)
        prefix_slice = module_text[:seg_start]
        return _ReferenceCompletionContext(
            kind="module",
            module_path=module_text,
            prefix_module_path=_strip_trailing_separator(prefix_slice),
            segment_prefix=module_text[seg_start:module_cursor],
            attr_path_prefix="",
            replace_start_offset=seg_start,
            replace_end_offset=seg_end,
        )

    attr_text = reference[attr_start:]
    attr_cursor = cursor_offset - attr_start
    seg_start, seg_end = _completion_segment_bounds(attr_text, attr_cursor)
    return _ReferenceCompletionContext(
        kind="attr",
        module_path=module_text,
        prefix_module_path="",
        segment_prefix="",
        attr_path_prefix=attr_text[:attr_cursor],
        replace_start_offset=attr_start + seg_start,
        replace_end_offset=attr_start + seg_end,
    )


def _completion_context(reference: str, cursor_offset: int) -> Optional[_ReferenceCompletionContext]:
    raw = str(reference or "")
    cursor = max(0, min(int(cursor_offset), len(raw)))
    if ":" in raw:
        return _completion_context_colon(raw, cursor)
    if not raw:
        return None
    return _completion_context_dotted(raw, cursor)


def _lsp_range_for_reference_offsets(extraction_range: EditorRange, start_offset: int, end_offset: int) -> types.Range:
    line0 = int(extraction_range.start.line) - 1
    col0_base = int(extraction_range.start.column) - 1
    start_char0 = col0_base + int(start_offset)
    end_char0 = col0_base + int(end_offset)
    return types.Range(
        start=types.Position(line=line0, character=int(start_char0)),
        end=types.Position(line=line0, character=int(end_char0)),
    )


async def _completion_items_for_context(
    ctx: _ReferenceCompletionContext,
    *,
    extraction_range: EditorRange,
    python_roots: Tuple[Path, ...],
    anchor_path: Optional[Path],
    uri: str,
    yaml_path: str,
) -> List[types.CompletionItem]:
    replace_range = _lsp_range_for_reference_offsets(extraction_range, ctx.replace_start_offset, ctx.replace_end_offset)
    if ctx.kind == "module":
        result = await asyncio.to_thread(
            complete_python_module_segment,
            ctx.prefix_module_path,
            segment_prefix=ctx.segment_prefix,
            python_roots=list(python_roots),
            anchor_path=anchor_path,
        )
        if result.warnings:
            _LOG.info("补全(`completion`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, yaml_path, list(result.warnings))

        return [
            types.CompletionItem(
                label=str(name),
                kind=types.CompletionItemKind.Module,
                text_edit=types.TextEdit(range=replace_range, new_text=str(name)),
            )
            for name in result.items
        ]

    result = await asyncio.to_thread(
        complete_python_attr_path_segment,
        ctx.module_path,
        attr_path_prefix=ctx.attr_path_prefix,
        python_roots=list(python_roots),
        anchor_path=anchor_path,
    )
    if result.warnings:
        _LOG.info("补全(`completion`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, yaml_path, list(result.warnings))

    return [
        types.CompletionItem(
            label=str(name),
            kind=types.CompletionItemKind.Function,
            text_edit=types.TextEdit(range=replace_range, new_text=str(name)),
        )
        for name in result.items
    ]


def _completion_item_kind_for_entity_item(item: YamlDslEntityCompletionItem, *, extraction_kind: str) -> types.CompletionItemKind:
    if item.is_snippet:
        return types.CompletionItemKind.Snippet
    if extraction_kind == "relation_step_field_id":
        return types.CompletionItemKind.Field
    if extraction_kind in ("source_id", "relation_step_source_id"):
        return types.CompletionItemKind.Reference
    if extraction_kind == "relation_id":
        return types.CompletionItemKind.Reference
    if extraction_kind in ("output_name", "workflow_run_id"):
        return types.CompletionItemKind.Value
    return types.CompletionItemKind.Value


def _lsp_completion_items_from_entity_result(
    result: YamlDslEntityCompletionResult,
    *,
    extraction: YamlCursorExtractionResult,
) -> List[types.CompletionItem]:
    extraction_kind = str(extraction.kind or "").strip()
    items: List[types.CompletionItem] = []
    for item in result.items:
        rng = extraction.range
        if item.replace == "value":
            rng = extraction.value_range
        if rng is None:
            continue
        replace_range = _to_lsp_range(rng)
        completion = types.CompletionItem(
            label=str(item.label),
            kind=_completion_item_kind_for_entity_item(item, extraction_kind=extraction_kind),
            detail=str(item.detail or ""),
            text_edit=types.TextEdit(range=replace_range, new_text=str(item.insert_text)),
        )
        if item.is_snippet:
            completion.insert_text_format = types.InsertTextFormat.Snippet
        items.append(completion)
    return items


def _completion_item_kind_for_sugar_item(label: str, insert_text: str, *, is_snippet: bool) -> types.CompletionItemKind:
    if is_snippet:
        return types.CompletionItemKind.Snippet
    if str(insert_text).endswith((".yaml", ".yml")):
        return types.CompletionItemKind.File
    if str(label).endswith(("/", ":/")) or str(insert_text).endswith(("/", ":/")):
        return types.CompletionItemKind.Folder
    return types.CompletionItemKind.Value


def _lsp_completion_items_from_sugar_result(
    result: YamlDslSugarCompletionResult,
    *,
    replace_range: types.Range,
) -> List[types.CompletionItem]:
    items: List[types.CompletionItem] = []
    for item in result.items:
        completion = types.CompletionItem(
            label=str(item.label),
            kind=_completion_item_kind_for_sugar_item(str(item.label), str(item.insert_text), is_snippet=bool(item.is_snippet)),
            detail=str(item.detail or ""),
            text_edit=types.TextEdit(range=replace_range, new_text=str(item.insert_text)),
        )
        if item.is_snippet:
            completion.insert_text_format = types.InsertTextFormat.Snippet
        items.append(completion)
    return items


async def _handle_yaml_dsl_builtin_callable_completion(
    params: types.CompletionParams,
    *,
    extraction: YamlCursorExtractionResult,
    uri: str,
) -> types.CompletionList:
    if extraction.reference is None or extraction.range is None:
        return types.CompletionList(is_incomplete=False, items=[])
    reference = str(extraction.reference)
    cursor_offset = _cursor_offset_for_completion(params.position, extraction.range, reference_len=len(reference))
    if cursor_offset is None:
        return types.CompletionList(is_incomplete=False, items=[])

    prefix = reference[:cursor_offset]
    leaf = str(extraction.yaml_path or "").split(".")[-1]
    call_by = leaf == "call_by"

    try:
        result = await asyncio.to_thread(complete_yaml_dsl_builtin_callable_reference, prefix, call_by=call_by)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "补全(`completion`, `builtin`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return types.CompletionList(is_incomplete=False, items=[])
    if result.warnings:
        _LOG.info(
            "补全(`completion`, `builtin`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, extraction.yaml_path, list(result.warnings)
        )

    replace_range = _to_lsp_range(extraction.range)
    items = _lsp_completion_items_from_sugar_result(result, replace_range=replace_range)
    return types.CompletionList(is_incomplete=False, items=items)


async def _handle_yaml_dsl_import_path_completion(
    params: types.CompletionParams,
    *,
    extraction: YamlCursorExtractionResult,
    anchor_yaml_path: Path,
    doc_state: _DocumentState,
    uri: str,
) -> types.CompletionList:
    if doc_state.report is None:
        return types.CompletionList(is_incomplete=False, items=[])
    if extraction.value_range is None:
        return types.CompletionList(is_incomplete=False, items=[])

    value = str(extraction.value or extraction.reference or "")
    cursor_offset = _cursor_offset_for_completion(params.position, extraction.value_range, reference_len=len(value))
    if cursor_offset is None:
        return types.CompletionList(is_incomplete=False, items=[])

    prefix = value[:cursor_offset]
    try:
        result = await asyncio.to_thread(
            complete_yaml_dsl_import_path_reference,
            prefix,
            anchor_yaml_path=anchor_yaml_path,
            allowed_yaml_roots=doc_state.report.discovery.allowed_yaml_roots,
            scalim_yaml_override=doc_state.report.discovery.scalim_yaml_path,
            project_root_override=doc_state.report.discovery.project_root,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "补全(`completion`, `imports.*`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return types.CompletionList(is_incomplete=False, items=[])
    if result.warnings:
        _LOG.info(
            "补全(`completion`, `imports.*`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s",
            uri,
            extraction.yaml_path,
            list(result.warnings),
        )

    replace_range = _to_lsp_range(extraction.value_range)
    items = _lsp_completion_items_from_sugar_result(result, replace_range=replace_range)
    return types.CompletionList(is_incomplete=False, items=items)


async def _handle_yaml_dsl_output_field_completion(
    params: types.CompletionParams,
    *,
    extraction: YamlCursorExtractionResult,
    view: YamlDslEditorEffectiveView,
    uri: str,
) -> types.CompletionList:
    if extraction.value_range is None:
        return types.CompletionList(is_incomplete=False, items=[])

    value = str(extraction.value or extraction.reference or "")
    cursor_offset = _cursor_offset_for_completion(params.position, extraction.value_range, reference_len=len(value))
    if cursor_offset is None:
        return types.CompletionList(is_incomplete=False, items=[])
    prefix = value[:cursor_offset]

    try:
        result = await asyncio.to_thread(complete_yaml_dsl_output_field_id, prefix, view=view)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "补全(`completion`, `outputs.*.fields`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return types.CompletionList(is_incomplete=False, items=[])

    replace_range = _to_lsp_range(extraction.value_range)
    items = _lsp_completion_items_from_sugar_result(result, replace_range=replace_range)
    return types.CompletionList(is_incomplete=False, items=items)


async def _handle_yaml_dsl_entity_completion(
    ls: LanguageServer,
    params: types.CompletionParams,
    *,
    doc_state: _DocumentState,
    anchor_path: Optional[Path],
    uri: str,
    state: Dict[str, _DocumentState],
) -> types.CompletionList:
    _ = anchor_path
    entity_index = doc_state.entity_index
    if entity_index is None:
        return types.CompletionList(is_incomplete=False, items=[])

    extraction = _safe_extract_entity_reference_for_lsp(doc_state.text, params.position, uri=uri, op="completion")
    if not extraction.kind or extraction.range is None or extraction.value_range is None:
        return types.CompletionList(is_incomplete=False, items=[])

    try:
        result = await asyncio.to_thread(
            complete_yaml_dsl_entity_reference,
            extraction,
            entity_index=entity_index,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception(
            "补全(`completion`, `entity`) 解析失败 `uri`=%s `yaml_path`=%s: %s: %s",
            uri,
            extraction.yaml_path,
            type(exc).__name__,
            exc,
        )
        return types.CompletionList(is_incomplete=False, items=[])

    if result.warnings:
        _LOG.info(
            "补全(`completion`, `entity`) 警告 `uri`=%s `yaml_path`=%s `warnings`=%s", uri, extraction.yaml_path, list(result.warnings)
        )

    _maybe_publish_entity_hint_diagnostic(ls, uri, state=state, hint=result.hint)

    lsp_items = _lsp_completion_items_from_entity_result(result, extraction=extraction)
    return types.CompletionList(is_incomplete=False, items=lsp_items)


async def _handle_completion(
    ls: LanguageServer, params: types.CompletionParams, *, state: Dict[str, _DocumentState]
) -> types.CompletionList:
    uri = str(params.text_document.uri)
    doc_state = state.get(uri)
    if doc_state is None or doc_state.report is None:
        return types.CompletionList(is_incomplete=False, items=[])
    anchor_path = _uri_to_path(uri)

    extraction = _safe_extract_reference_for_lsp(doc_state.text, params.position, uri=uri, op="completion")
    reference_completion = await _handle_reference_completion(
        params,
        extraction=extraction,
        python_roots=doc_state.python_roots,
        anchor_path=anchor_path,
        uri=uri,
    )
    if reference_completion is not None:
        return reference_completion

    # imports.* path completion (separate from $import refs)
    if anchor_path is not None:
        import_path_extraction = _safe_extract_import_path_reference_for_lsp(doc_state.text, params.position, uri=uri, op="completion")
        if import_path_extraction.reference and import_path_extraction.value_range is not None:
            return await _handle_yaml_dsl_import_path_completion(
                params,
                extraction=import_path_extraction,
                anchor_yaml_path=anchor_path,
                doc_state=doc_state,
                uri=uri,
            )

    if doc_state.effective_view is not None and anchor_path is not None:
        output_field_extraction = _safe_extract_output_field_reference_for_lsp(
            doc_state.text,
            params.position,
            uri=uri,
            op="completion",
        )
        if output_field_extraction.reference and output_field_extraction.value_range is not None:
            return await _handle_yaml_dsl_output_field_completion(
                params,
                extraction=output_field_extraction,
                view=doc_state.effective_view,
                uri=uri,
            )

    return await _handle_yaml_dsl_entity_completion(
        ls,
        params,
        doc_state=doc_state,
        anchor_path=anchor_path,
        uri=uri,
        state=state,
    )


async def _handle_reference_completion(
    params: types.CompletionParams,
    *,
    extraction: YamlCursorExtractionResult,
    python_roots: Tuple[Path, ...],
    anchor_path: Optional[Path],
    uri: str,
) -> Optional[types.CompletionList]:
    if not extraction.reference or extraction.range is None:
        return None

    reference = str(extraction.reference)
    if reference.lstrip().startswith("^"):
        return await _handle_yaml_dsl_builtin_callable_completion(
            params,
            extraction=extraction,
            uri=uri,
        )

    cursor_offset = _cursor_offset_for_completion(params.position, extraction.range, reference_len=len(reference))
    if cursor_offset is None:
        return types.CompletionList(is_incomplete=False, items=[])

    ctx = _completion_context(reference, cursor_offset)
    if ctx is None:
        return types.CompletionList(is_incomplete=False, items=[])

    items = await _completion_items_for_context(
        ctx,
        extraction_range=extraction.range,
        python_roots=python_roots,
        anchor_path=anchor_path,
        uri=uri,
        yaml_path=extraction.yaml_path,
    )
    return types.CompletionList(is_incomplete=False, items=items)


def _register_completion_feature(server: LanguageServer, state: Dict[str, _DocumentState]) -> None:
    @server.feature(types.TEXT_DOCUMENT_COMPLETION, types.CompletionOptions(trigger_characters=[".", ":"]))
    async def completion(_ls: LanguageServer, params: types.CompletionParams) -> types.CompletionList:
        return await _handle_completion(_ls, params, state=state)


_DIAG_CODE_MISSING_SCALIM_YAML = "scalim_missing_scalim_yaml"
_DIAG_CODE_MISSING_PYTHON_ROOTS = "scalim_missing_python_roots"
_DIAG_CODE_PYTHON_RESOLUTION_FAILED = "scalim_python_resolution_failed"


@dataclass(frozen=True)
class _QuickFixContext:
    uri: str
    doc_state: _DocumentState
    report: YamlDslEditorDiagnosticsResult
    anchor_path: Optional[Path]
    params: types.CodeActionParams


class _QuickFixProvider(Protocol):
    def can_fix(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> bool: ...

    def provide(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> List[types.CodeAction]: ...


class _QuickFixRegistry:
    def __init__(self) -> None:
        self._providers_by_code: Dict[str, List[_QuickFixProvider]] = {}

    def register(self, code: str, provider: _QuickFixProvider) -> None:
        self._providers_by_code.setdefault(str(code), []).append(provider)

    def providers_for(self, code: str) -> Sequence[_QuickFixProvider]:
        return tuple(self._providers_by_code.get(str(code), []))


class _CreateMinimalScalimYamlProvider:
    def can_fix(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> bool:
        _ = diagnostic
        return ctx.report.discovery.scalim_yaml_path is None

    def provide(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> List[types.CodeAction]:
        _ = diagnostic
        return [
            types.CodeAction(
                title="创建最小 `scalim.yaml`",
                kind=types.CodeActionKind.QuickFix,
                is_preferred=True,
                command=types.Command(
                    title="创建最小 `scalim.yaml`",
                    command=_COMMAND_CREATE_MINIMAL_SCALIM_YAML,
                    arguments=[ctx.uri],
                ),
            )
        ]


class _FixImportRootsProvider:
    def can_fix(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> bool:
        _ = diagnostic
        return bool(_first_import_escape_dir_rel(ctx.report))

    def provide(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> List[types.CodeAction]:
        _ = diagnostic
        import_dir_rel = _first_import_escape_dir_rel(ctx.report)
        if not import_dir_rel:
            return []
        return [
            types.CodeAction(
                title="修复: 将 `{}` 注册到 `yaml_dsl.import_roots` (最小)".format(import_dir_rel),
                kind=types.CodeActionKind.QuickFix,
                is_preferred=True,
                command=types.Command(
                    title="修复 import_roots (最小)",
                    command=_COMMAND_ADD_IMPORT_ROOTS,
                    arguments=[ctx.uri, _MODE_MINIMAL],
                ),
            ),
            types.CodeAction(
                title="修复: 将 `.` 注册到 `yaml_dsl.import_roots` (宽松)",
                kind=types.CodeActionKind.QuickFix,
                command=types.Command(
                    title="修复 import_roots (宽松)",
                    command=_COMMAND_ADD_IMPORT_ROOTS,
                    arguments=[ctx.uri, _MODE_WIDE],
                ),
            ),
        ]


class _FixImportRootAliasProvider:
    def can_fix(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> bool:
        _ = diagnostic
        if ctx.report.discovery.scalim_yaml_path is None:
            return False
        return bool(_first_import_missing_alias(ctx.report))

    def provide(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> List[types.CodeAction]:
        _ = diagnostic
        alias = _first_import_missing_alias(ctx.report)
        if not alias:
            return []
        return [
            types.CodeAction(
                title="修复: 将 alias `{}` 注册到 `yaml_dsl.import_roots`".format(alias),
                kind=types.CodeActionKind.QuickFix,
                is_preferred=not bool(_first_import_escape_dir_rel(ctx.report)),
                command=types.Command(
                    title="修复 import alias",
                    command=_COMMAND_ADD_IMPORT_ROOT_ALIAS,
                    arguments=[ctx.uri, alias],
                ),
            )
        ]


class _FixPythonRootsProvider:
    def can_fix(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> bool:
        _ = diagnostic
        python_root_candidates = _infer_python_roots_candidates(ctx.report.discovery.project_root)
        missing_py_roots = _missing_roots(ctx.report.discovery.project_root, ctx.report.discovery.python_roots, python_root_candidates)
        return bool(missing_py_roots)

    def provide(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> List[types.CodeAction]:
        _ = diagnostic
        python_root_candidates = _infer_python_roots_candidates(ctx.report.discovery.project_root)
        missing_py_roots = _missing_roots(ctx.report.discovery.project_root, ctx.report.discovery.python_roots, python_root_candidates)
        if not missing_py_roots:
            return []

        missing_py_roots_display = ", ".join(["`{}`".format(p) for p in missing_py_roots])
        return [
            types.CodeAction(
                title="修复: 将 `{}` 加入 `yaml_dsl.lsp.python_roots` (最小)".format(missing_py_roots[0]),
                kind=types.CodeActionKind.QuickFix,
                is_preferred=not bool(_first_import_escape_dir_rel(ctx.report)),
                command=types.Command(
                    title="修复 python_roots (最小)",
                    command=_COMMAND_ADD_PYTHON_ROOTS,
                    arguments=[ctx.uri, _MODE_MINIMAL],
                ),
            ),
            types.CodeAction(
                title="修复: 将 {} 加入 `yaml_dsl.lsp.python_roots` (宽松)".format(missing_py_roots_display),
                kind=types.CodeActionKind.QuickFix,
                command=types.Command(
                    title="修复 python_roots (宽松)",
                    command=_COMMAND_ADD_PYTHON_ROOTS,
                    arguments=[ctx.uri, _MODE_WIDE],
                ),
            ),
        ]


class _ExplainPythonResolutionFailureProvider:
    def can_fix(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> bool:
        _ = ctx
        data = getattr(diagnostic, "data", None)
        if not isinstance(data, dict):
            return False
        ref = data.get("reference")
        return bool(str(ref or "").strip())

    def provide(self, ctx: _QuickFixContext, diagnostic: types.Diagnostic) -> List[types.CodeAction]:
        data = getattr(diagnostic, "data", None)
        reference = ""
        if isinstance(data, dict):
            reference = str(data.get("reference") or "")

        reference = str(reference or "").strip()
        if not reference:
            return []

        return [
            types.CodeAction(
                title="解释: Python 引用解析失败",
                kind=types.CodeActionKind.QuickFix,
                command=types.Command(
                    title="解释 Python 引用解析失败",
                    command=_COMMAND_EXPLAIN_RESOLUTION_FAILURE,
                    arguments=[ctx.uri, reference],
                ),
            )
        ]


_QUICK_FIX_REGISTRY = _QuickFixRegistry()
_QUICK_FIX_REGISTRY.register(_DIAG_CODE_MISSING_SCALIM_YAML, _CreateMinimalScalimYamlProvider())
_QUICK_FIX_REGISTRY.register("yaml_import_expansion_error", _FixImportRootsProvider())
_QUICK_FIX_REGISTRY.register("yaml_import_expansion_error", _FixImportRootAliasProvider())
_QUICK_FIX_REGISTRY.register(_DIAG_CODE_MISSING_PYTHON_ROOTS, _FixPythonRootsProvider())
_QUICK_FIX_REGISTRY.register(_DIAG_CODE_PYTHON_RESOLUTION_FAILED, _ExplainPythonResolutionFailureProvider())


def _quick_fix_registry() -> _QuickFixRegistry:
    return _QUICK_FIX_REGISTRY


def _register_code_actions(server: LanguageServer, state: Dict[str, _DocumentState]) -> None:
    @server.feature(types.TEXT_DOCUMENT_CODE_ACTION)
    async def code_action(ls: LanguageServer, params: types.CodeActionParams) -> List[types.CodeAction]:
        return await _handle_code_actions(ls, params, state=state)

    @server.command(_COMMAND_DUMP_DISCOVERY)
    def dump_discovery(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        return _dump_discovery_payload(ls, document_uri)

    @server.command(_COMMAND_CREATE_MINIMAL_SCALIM_YAML)
    async def create_minimal_scalim_yaml(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        return await _cmd_create_minimal_scalim_yaml(ls, document_uri, state=state)

    @server.command(_COMMAND_ADD_IMPORT_ROOTS)
    async def add_import_roots(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        mode = str(args[1]) if len(args) > 1 else ""
        return await _cmd_add_import_roots(ls, document_uri, mode, state=state)

    @server.command(_COMMAND_ADD_IMPORT_ROOT_ALIAS)
    async def add_import_root_alias(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        alias = str(args[1]) if len(args) > 1 else ""
        return await _cmd_add_import_root_alias(ls, document_uri, alias, state=state)

    @server.command(_COMMAND_ADD_PYTHON_ROOTS)
    async def add_python_roots(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        mode = str(args[1]) if len(args) > 1 else ""
        return await _cmd_add_python_roots(ls, document_uri, mode, state=state)

    @server.command(_COMMAND_EXPLAIN_RESOLUTION_FAILURE)
    async def explain_resolution_failure(ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        document_uri = str(args[0]) if args else ""
        reference = str(args[1]) if len(args) > 1 else ""
        return await _cmd_explain_resolution_failure(ls, document_uri, reference, state=state)

    @server.command(_COMMAND_PRESET_GET_TEXT)
    def preset_get_text(_ls: LanguageServer, *args: Any) -> Dict[str, Any]:
        preset_id = str(args[0]) if args else ""
        return _cmd_preset_get_text(preset_id)


def _dedupe_code_actions(actions: Sequence[types.CodeAction]) -> List[types.CodeAction]:
    out: List[types.CodeAction] = []
    seen: Set[Tuple[str, str, Tuple[str, ...]]] = set()
    for action in actions:
        cmd = action.command
        command = str(cmd.command) if cmd is not None else ""
        args = tuple([str(a) for a in (cmd.arguments or [])]) if cmd is not None else ()
        key = (str(action.title), command, args)
        if key in seen:
            continue
        seen.add(key)
        out.append(action)
    return out


def _add_diagnostic_by_code(store: Dict[str, types.Diagnostic], diag: types.Diagnostic) -> None:
    code = str(diag.code or "").strip()
    if not code:
        return
    store.setdefault(code, diag)


def _context_diagnostics_by_code(params: types.CodeActionParams) -> Dict[str, types.Diagnostic]:
    out: Dict[str, types.Diagnostic] = {}
    for diag in list(getattr(getattr(params, "context", None), "diagnostics", None) or []):
        if not isinstance(diag, types.Diagnostic):
            continue
        _add_diagnostic_by_code(out, diag)
    return out


def _synthetic_project_quick_fix_diagnostics(ctx: _QuickFixContext) -> List[types.Diagnostic]:
    report = ctx.report

    if report.discovery.scalim_yaml_path is None:
        return [
            types.Diagnostic(
                range=ctx.params.range,
                severity=types.DiagnosticSeverity.Hint,
                source="scalim",
                message="missing scalim.yaml",
                code=_DIAG_CODE_MISSING_SCALIM_YAML,
            )
        ]

    diags: List[types.Diagnostic] = []
    if _has_import_expansion_error(report):
        diags.append(
            types.Diagnostic(
                range=ctx.params.range,
                severity=types.DiagnosticSeverity.Warning,
                source="scalim",
                message="YAML path escapes allowed roots",
                code="yaml_import_expansion_error",
            )
        )

    python_root_candidates = _infer_python_roots_candidates(report.discovery.project_root)
    missing_py_roots = _missing_roots(report.discovery.project_root, report.discovery.python_roots, python_root_candidates)
    if missing_py_roots:
        diags.append(
            types.Diagnostic(
                range=ctx.params.range,
                severity=types.DiagnosticSeverity.Hint,
                source="scalim",
                message="missing python_roots: {}".format(", ".join(missing_py_roots)),
                code=_DIAG_CODE_MISSING_PYTHON_ROOTS,
            )
        )

    return diags


async def _synthetic_python_resolution_failure_diagnostic(ctx: _QuickFixContext) -> Optional[types.Diagnostic]:
    report = ctx.report
    if report.discovery.scalim_yaml_path is None:
        return None

    extraction = _safe_extract_reference_for_lsp(ctx.doc_state.text, ctx.params.range.start, uri=ctx.uri, op="codeAction")
    if not extraction.reference:
        return None

    result = await _safe_resolve_python_definition(
        extraction,
        python_roots=ctx.doc_state.python_roots,
        anchor_path=ctx.anchor_path,
        uri=ctx.uri,
    )
    if result is None or result.locations or not result.warnings:
        return None

    return types.Diagnostic(
        range=ctx.params.range,
        severity=types.DiagnosticSeverity.Hint,
        source="scalim",
        message="python resolution failed",
        code=_DIAG_CODE_PYTHON_RESOLUTION_FAILED,
        data={"reference": str(extraction.reference)},
    )


def _quick_fix_actions_for_diagnostics(
    ctx: _QuickFixContext,
    *,
    diagnostics_by_code: Dict[str, types.Diagnostic],
    registry: _QuickFixRegistry,
) -> List[types.CodeAction]:
    ordered_codes = [
        _DIAG_CODE_MISSING_SCALIM_YAML,
        "yaml_import_expansion_error",
        _DIAG_CODE_MISSING_PYTHON_ROOTS,
        _DIAG_CODE_PYTHON_RESOLUTION_FAILED,
    ]

    actions: List[types.CodeAction] = []
    for code in ordered_codes:
        diag = diagnostics_by_code.get(code)
        if diag is None:
            continue
        for provider in registry.providers_for(code):
            if provider.can_fix(ctx, diag):
                actions.extend(provider.provide(ctx, diag))

    for code in sorted(diagnostics_by_code):
        if code in ordered_codes:
            continue
        diag = diagnostics_by_code[code]
        for provider in registry.providers_for(code):
            if provider.can_fix(ctx, diag):
                actions.extend(provider.provide(ctx, diag))

    return actions


async def _handle_code_actions(
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
    anchor_path = _uri_to_path(uri)
    ctx = _QuickFixContext(uri=uri, doc_state=doc_state, report=report, anchor_path=anchor_path, params=params)

    diagnostics_by_code = _context_diagnostics_by_code(params)
    for diag in _synthetic_project_quick_fix_diagnostics(ctx):
        _add_diagnostic_by_code(diagnostics_by_code, diag)

    if report.discovery.scalim_yaml_path is None:
        actions = _quick_fix_actions_for_diagnostics(ctx, diagnostics_by_code=diagnostics_by_code, registry=_quick_fix_registry())
        return _dedupe_code_actions(actions)

    resolution_diag = await _synthetic_python_resolution_failure_diagnostic(ctx)
    if resolution_diag is not None:
        _add_diagnostic_by_code(diagnostics_by_code, resolution_diag)

    actions = _quick_fix_actions_for_diagnostics(ctx, diagnostics_by_code=diagnostics_by_code, registry=_quick_fix_registry())
    return _dedupe_code_actions(actions)


def _dump_discovery_payload(ls: LanguageServer, document_uri: str) -> Dict[str, Any]:
    path = _uri_to_path(str(document_uri or ""))
    if path is None:
        return {
            "project_root": "",
            "scalim_yaml_path": None,
            "python_roots": [],
            "allowed_yaml_roots": [],
            "error": "仅支持 file:// URI",
        }
    workspace_root = _workspace_root_path(ls)
    try:
        discovery = discover_yaml_dsl_editor_project(path, workspace_root_override=workspace_root)
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


def _cmd_preset_get_text(preset_id: str) -> Dict[str, Any]:
    pid = str(preset_id or "").strip().lstrip("/")
    if not pid:
        return {"ok": False, "kind": "explain_only", "message": "preset_id 不能为空", "hints": []}
    try:
        content = load_scalim_preset_yaml_text(pid)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "kind": "explain_only",
            "message": "加载 preset 失败: {}: {}".format(type(exc).__name__, exc),
            "hints": [pid],
        }

    return {
        "ok": True,
        "kind": "preset_text",
        "preset_id": pid,
        "title": "scalim preset: {}".format(pid),
        "languageId": "yaml",
        "content": str(content or ""),
    }


async def _cmd_explain_resolution_failure(
    _ls: LanguageServer,
    document_uri: str,
    reference: str,
    *,
    state: Dict[str, _DocumentState],
) -> Dict[str, Any]:
    uri = str(document_uri or "")
    doc_state = state.get(uri)
    if doc_state is None or doc_state.report is None:
        return {"ok": False, "kind": "explain_only", "message": "文档未打开或未同步 `state`", "hints": [uri]}
    anchor_path = _uri_to_path(uri)
    try:
        result = await asyncio.to_thread(
            resolve_python_definition,
            str(reference or ""),
            python_roots=list(doc_state.python_roots),
            anchor_path=anchor_path,
        )
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
        import_roots=[{"path": ".", "alias": "@"}],
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


async def _cmd_add_import_roots(  # noqa: C901, PLR0911
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
        root_paths_to_add = [minimal_root]
    elif mode_text == _MODE_WIDE:
        root_paths_to_add = ["."]
    else:
        return {"ok": False, "kind": "explain_only", "message": "未知 mode: {}".format(mode_text), "hints": []}
    new_text = _update_scalim_yaml_text(
        scalim_yaml_path.read_text(encoding="utf-8"),
        import_root_paths_to_add=root_paths_to_add,
        python_roots_to_add=(),
    )
    if new_text is None:
        return {"ok": False, "kind": "explain_only", "message": "无法解析/更新 `scalim.yaml`", "hints": [str(scalim_yaml_path)]}

    edit = _workspace_edit_replace_entire_file(scalim_yaml_path, new_text)
    try:
        result = await ls.workspace_apply_edit_async(types.ApplyWorkspaceEditParams(edit=edit, label="更新 import_roots"))
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("更新 import_roots 失败: %s: %s", type(exc).__name__, exc)
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


async def _cmd_add_import_root_alias(  # noqa: PLR0911
    ls: LanguageServer,
    document_uri: str,
    alias: str,
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

    alias_text = str(alias or "").strip()
    if not alias_text:
        return {"ok": False, "kind": "explain_only", "message": "alias 不能为空", "hints": []}
    if alias_text != "@" and not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", alias_text):
        return {"ok": False, "kind": "explain_only", "message": "alias 格式非法: {!r}".format(alias_text), "hints": []}

    new_text = _update_scalim_yaml_text(
        scalim_yaml_path.read_text(encoding="utf-8"),
        import_root_paths_to_add=(),
        python_roots_to_add=(),
        import_root_aliases_to_add=((".", alias_text),),
    )
    if new_text is None:
        return {"ok": False, "kind": "explain_only", "message": "无法解析/更新 `scalim.yaml`", "hints": [str(scalim_yaml_path)]}

    edit = _workspace_edit_replace_entire_file(scalim_yaml_path, new_text)
    try:
        result = await ls.workspace_apply_edit_async(types.ApplyWorkspaceEditParams(edit=edit, label="更新 `import_roots` 的 `alias`"))
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("更新 `import_roots` 的 `alias` 失败: %s: %s", type(exc).__name__, exc)
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
        import_root_paths_to_add=(),
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


def _has_import_expansion_error(report: YamlDslEditorDiagnosticsResult) -> bool:
    return any(str(item.code) == "yaml_import_expansion_error" for item in list(report.errors) + list(report.warnings))


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


def _first_import_missing_alias(report: YamlDslEditorDiagnosticsResult) -> str:
    """尝试从 import expansion error 中推断缺失的 import root alias(例如 `@`/`COMMON`)."""
    for item in list(report.errors) + list(report.warnings):
        if str(item.code) != "yaml_import_expansion_error":
            continue
        msg = str(item.message or "")
        if _IMPORT_RESERVED_ALIAS_MARKER not in msg:
            continue
        match = _IMPORT_RAW_PATH_RE.search(msg)
        raw_path = match.group(1) if match is not None else ""
        raw_path = str(raw_path or "")
        if raw_path.startswith("@/"):
            return "@"
        token_match = _IMPORT_ALIAS_TOKEN_RE.match(raw_path)
        if token_match is None:
            continue
        alias = token_match.group(1)
        if isinstance(alias, str) and alias.strip():
            return alias.strip()
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


def _render_scalim_yaml_content(*, import_roots: Sequence[Dict[str, str]], python_roots: Sequence[str]) -> str:
    lines: List[str] = ["yaml_dsl:"]
    if import_roots:
        lines.append("  import_roots:")
        for root in import_roots:
            path = str(root.get("path") or "").strip()
            if not path:
                continue
            lines.append("    - path: {}".format(path))
            alias = root.get("alias")
            alias_text = str(alias or "").strip() if alias is not None else ""
            if alias_text:
                # Always quote to keep YAML valid for special tokens like `@`.
                lines.append('      alias: "{}"'.format(alias_text))
    if python_roots:
        lines.append("  lsp:")
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


def _update_scalim_yaml_text(  # noqa: C901, PLR0911, PLR0912, PLR0915
    raw_text: str,
    *,
    import_root_paths_to_add: Sequence[str],
    python_roots_to_add: Sequence[str],
    import_root_aliases_to_add: Sequence[Tuple[str, str]] = (),
) -> Optional[str]:
    yaml_rt = _yaml_rt()
    try:
        loaded_obj: Any = yaml_rt.load(str(raw_text or "")) or {}
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(loaded_obj, dict):
        return None
    loaded: Any = loaded_obj

    yaml_dsl_obj = loaded.get("yaml_dsl")
    if yaml_dsl_obj is None:
        yaml_dsl_obj = {}
        loaded["yaml_dsl"] = yaml_dsl_obj
    if not isinstance(yaml_dsl_obj, dict):
        return None
    yaml_dsl: Any = yaml_dsl_obj

    if import_root_paths_to_add or import_root_aliases_to_add:
        roots_obj = yaml_dsl.get("import_roots")
        if roots_obj is None:
            roots_obj = []
            yaml_dsl["import_roots"] = roots_obj
        if not isinstance(roots_obj, list):
            return None
        import_roots: List[Any] = roots_obj

        existing_by_path: Dict[str, Dict[str, Any]] = {}
        existing_aliases: Dict[str, None] = {}
        for item in import_roots:
            if not isinstance(item, dict):
                return None
            item_dict = cast("Dict[str, Any]", item)
            raw_path = item_dict.get("path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                continue
            normalized = _normalize_rel_path_text(str(raw_path))
            existing_by_path[normalized] = item_dict
            raw_alias = item_dict.get("alias")
            if isinstance(raw_alias, str) and raw_alias.strip():
                existing_aliases[str(raw_alias).strip()] = None

        for raw in import_root_paths_to_add:
            normalized = _normalize_rel_path_text(raw)
            if normalized in existing_by_path:
                continue
            import_roots.append({"path": normalized})
            existing_by_path[normalized] = cast("Dict[str, Any]", import_roots[-1])

        for raw_path, raw_alias in import_root_aliases_to_add:
            normalized_path = _normalize_rel_path_text(raw_path)
            alias = str(raw_alias or "").strip()
            if not alias:
                continue
            if alias in existing_aliases:
                continue

            existing_item = existing_by_path.get(normalized_path)
            if existing_item is not None:
                existing_alias = existing_item.get("alias")
                if not isinstance(existing_alias, str) or not existing_alias.strip():
                    existing_item["alias"] = alias
                else:
                    # Path already has a different alias; append a new entry.
                    import_roots.append({"path": normalized_path, "alias": alias})
                    existing_by_path[normalized_path] = cast("Dict[str, Any]", import_roots[-1])
            else:
                import_roots.append({"path": normalized_path, "alias": alias})
                existing_by_path[normalized_path] = cast("Dict[str, Any]", import_roots[-1])

            existing_aliases[alias] = None

    if python_roots_to_add:
        lsp_obj = yaml_dsl.get("lsp")
        if lsp_obj is None:
            lsp_obj = {}
            yaml_dsl["lsp"] = lsp_obj
        if not isinstance(lsp_obj, dict):
            return None
        lsp: Any = lsp_obj
        roots_obj = lsp.get("python_roots")
        if roots_obj is None:
            roots_obj = []
            lsp["python_roots"] = roots_obj
        if not isinstance(roots_obj, list):
            return None
        python_roots: List[Any] = roots_obj
        _extend_unique(python_roots, python_roots_to_add)

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


def _normalize_rel_path_text(raw: str) -> str:
    text = str(raw or "").strip()
    return text.strip("/") or "."


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


async def _update_state_and_publish_diagnostics(
    ls: LanguageServer,
    uri: str,
    state: Dict[str, _DocumentState],
    *,
    yaml_text: Optional[str],
    version: int,
) -> None:
    if yaml_text is None:
        try:
            text_doc = ls.workspace.get_text_document(uri)
            yaml_text = str(text_doc.source)
        except Exception as exc:  # noqa: BLE001
            _LOG.exception("工作区获取文档失败 `uri`=%s: %s: %s", uri, type(exc).__name__, exc)
            state[uri] = _DocumentState(
                text="",
                version=int(version),
                report=None,
                python_roots=(),
                base_diagnostics=(),
                hint_diagnostics=(),
                entity_index=None,
                effective_view=None,
            )
            ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=[]))
            return

    yaml_path = _uri_to_path(uri)
    workspace_root = _workspace_root_path(ls)
    diagnostics, report, entity_index, effective_view = await asyncio.to_thread(
        _compute_diagnostics_report_and_entity_index,
        yaml_path=yaml_path,
        yaml_text=str(yaml_text),
        workspace_root=workspace_root,
    )
    python_roots = tuple(report.discovery.python_roots) if report is not None else ()
    base_diagnostics = tuple(diagnostics)
    state[uri] = _DocumentState(
        text=str(yaml_text),
        version=int(version),
        report=report,
        python_roots=python_roots,
        base_diagnostics=base_diagnostics,
        hint_diagnostics=(),
        entity_index=entity_index,
        effective_view=effective_view,
    )
    ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=uri, diagnostics=list(base_diagnostics)))


def _compute_diagnostics_report_and_entity_index(
    *,
    yaml_path: Optional[Path],
    yaml_text: str,
    workspace_root: Optional[Path],
) -> Tuple[
    List[types.Diagnostic], Optional[YamlDslEditorDiagnosticsResult], Optional[YamlDslEntityIndex], Optional[YamlDslEditorEffectiveView]
]:
    if yaml_path is None:
        return [], None, None, None
    if not is_probably_yaml_dsl_document(yaml_path, yaml_text):
        return [], None, None, None
    try:
        report = collect_yaml_dsl_editor_diagnostics(yaml_path, yaml_text=yaml_text, workspace_root_override=workspace_root)
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("诊断计算失败 `path`=%s: %s: %s", yaml_path, type(exc).__name__, exc)
        return [], None, None, None

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
    entity_index: Optional[YamlDslEntityIndex] = None
    try:
        entity_index = build_yaml_dsl_entity_index(
            yaml_text,
            yaml_kind=str(report.yaml_kind or ""),
            source_path=str(yaml_path),
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("实体索引构建失败 `path`=%s: %s: %s", yaml_path, type(exc).__name__, exc)
        entity_index = None

    effective_view: Optional[YamlDslEditorEffectiveView] = None
    try:
        effective_view = build_yaml_dsl_editor_effective_view(
            yaml_text,
            yaml_path=yaml_path,
            yaml_kind=str(report.yaml_kind or ""),
            allowed_yaml_roots=report.discovery.allowed_yaml_roots,
            scalim_yaml_override=report.discovery.scalim_yaml_path,
            project_root_override=report.discovery.project_root,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.exception("`effective view` 构建失败 `path`=%s: %s: %s", yaml_path, type(exc).__name__, exc)
        effective_view = None

    return diagnostics, report, entity_index, effective_view


def _extract_reference_for_lsp(yaml_text: str, position: types.Position) -> YamlCursorExtractionResult:
    editor_pos = EditorPosition(line=int(position.line) + 1, column=int(position.character) + 1)
    return extract_yaml_dsl_python_reference_by_cursor(yaml_text, editor_pos)


def _extract_import_reference_for_lsp(yaml_text: str, position: types.Position) -> YamlCursorExtractionResult:
    editor_pos = EditorPosition(line=int(position.line) + 1, column=int(position.character) + 1)
    return extract_yaml_dsl_import_reference_by_cursor(yaml_text, editor_pos)


def _extract_import_path_reference_for_lsp(yaml_text: str, position: types.Position) -> YamlCursorExtractionResult:
    editor_pos = EditorPosition(line=int(position.line) + 1, column=int(position.character) + 1)
    return extract_yaml_dsl_import_path_reference_by_cursor(yaml_text, editor_pos)


def _extract_entity_reference_for_lsp(yaml_text: str, position: types.Position) -> YamlCursorExtractionResult:
    editor_pos = EditorPosition(line=int(position.line) + 1, column=int(position.character) + 1)
    return extract_yaml_dsl_entity_reference_by_cursor(yaml_text, editor_pos)


def _extract_output_field_reference_for_lsp(yaml_text: str, position: types.Position) -> YamlCursorExtractionResult:
    editor_pos = EditorPosition(line=int(position.line) + 1, column=int(position.character) + 1)
    return extract_yaml_dsl_output_field_reference_by_cursor(yaml_text, editor_pos)


def _extract_yaml_alias_reference_for_lsp(yaml_text: str, position: types.Position) -> YamlCursorExtractionResult:
    editor_pos = EditorPosition(line=int(position.line) + 1, column=int(position.character) + 1)
    return extract_yaml_dsl_yaml_alias_reference_by_cursor(yaml_text, editor_pos)


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
