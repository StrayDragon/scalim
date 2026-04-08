import ast
import json
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from functools import lru_cache
from importlib.machinery import PathFinder
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union, cast

try:
    import jsonschema as _jsonschema  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover  # pragma: allow-no-cover optional dependency
    _jsonschema = None  # type: ignore[assignment]

from scalim.dsl import yaml_dsl
from scalim.dsl.yaml_dsl._internal.config_parsing.allowed_paths import (
    normalize_allowed_yaml_roots,
    validate_resolved_yaml_path_within_roots,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.error_envelope import ErrorEnvelope, ErrorLoc, ScalimYamlValidationError
from scalim.dsl.yaml_dsl._internal.config_parsing.imports import (
    ScalimYamlImportExpansionError,
    contains_import_syntax,
    expand_imports_inplace,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.jsonschema_issues import (
    ScalimJsonSchemaCollectorError,
    collect_jsonschema_validation_issues,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.presets import load_scalim_preset_yaml_text
from scalim.dsl.yaml_dsl._internal.config_parsing.project_config import YamlDslProjectConfig, load_yaml_dsl_project_config
from scalim.dsl.yaml_dsl._internal.config_parsing.unknown_fields import find_unknown_fields
from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.yaml_dsl._internal.config_parsing.validators.issues import VALIDATION_SEVERITY_ERROR, ValidationIssue
from scalim.dsl.yaml_dsl._internal.config_parsing.yaml_load import (
    envelope_from_validation_issue,
    error_loc_for_yaml_path,
    load_yaml_mapping_text,
)
from scalim.dsl.yaml_dsl.reference_syntax import (
    ParsedReference,
    ScalimReferenceSyntaxError,
    is_valid_builtin_callable_reference,
    parse_python_reference,
)
from scalim.dsl.yaml_dsl.runtime.builtin_callables import (
    list_public_builtin_callable_ids,
    list_public_builtin_callable_python_references,
)
from scalim.vendor.yamlx import yaml

from .cache import load_yaml_mapping_cached, parse_python_ast_cached
from .cursor_extraction import (
    YamlCursorExtractionResult,
    extract_yaml_dsl_entity_reference_by_cursor,
    extract_yaml_dsl_import_reference_by_cursor,
    extract_yaml_dsl_python_reference_by_cursor,
)
from .editor_types import EditorPosition, EditorRange

YAML_DSL_KIND_DEMAND = "demand"
YAML_DSL_KIND_WORKFLOW = "workflow"

_YAML_DSL_KIND_CHOICES: Tuple[str, ...] = (
    YAML_DSL_KIND_DEMAND,
    YAML_DSL_KIND_WORKFLOW,
)

_SEVERITY_ERROR = "error"
_SEVERITY_WARNING = "warning"

_SCALIM_YAML_FILENAME = "scalim.yaml"
_IMPORTS_KEY = "imports"
_IMPORT_KEY = "$import"

_IMPORT_REF_SEGMENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_IMPORT_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_IMPORT_WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:")
_IMPORT_RESERVED_ALIAS_PREFIX_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*:/")
_IMPORT_SCALIM_SCHEME_PREFIX = "scalim://"


@dataclass(frozen=True)
class EditorDiagnostic:
    """面向编辑器/`LSP` 的结构化诊断输出."""

    severity: str
    message: str
    path: str
    source_path: str
    code: str = ""
    range: Optional[EditorRange] = None
    suggestions: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "severity": str(self.severity),
            "message": str(self.message),
            "path": str(self.path),
            "source_path": str(self.source_path),
        }
        if self.code:
            payload["code"] = str(self.code)
        if self.range is not None:
            payload["range"] = self.range.as_dict()
        if self.suggestions:
            payload["suggestions"] = list(self.suggestions)
        return payload


@dataclass(frozen=True)
class YamlDslEditorProjectDiscovery:
    """编辑器项目发现结果."""

    project_root: Path
    scalim_yaml_path: Optional[Path]
    python_roots: Tuple[Path, ...]
    allowed_yaml_roots: Tuple[Path, ...]

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "project_root": str(self.project_root),
            "python_roots": [str(p) for p in self.python_roots],
            "allowed_yaml_roots": [str(p) for p in self.allowed_yaml_roots],
        }
        if self.scalim_yaml_path is not None:
            payload["scalim_yaml_path"] = str(self.scalim_yaml_path)
        return payload


@dataclass(frozen=True)
class YamlDslEditorDiagnosticsResult:
    yaml_kind: str
    discovery: YamlDslEditorProjectDiscovery
    errors: Tuple[EditorDiagnostic, ...]
    warnings: Tuple[EditorDiagnostic, ...]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "yaml_kind": str(self.yaml_kind),
            "discovery": self.discovery.as_dict(),
            "errors": [d.as_dict() for d in self.errors],
            "warnings": [d.as_dict() for d in self.warnings],
            "ok": not self.errors,
        }


@dataclass(frozen=True)
class PythonDefinitionLocation:
    file_path: str
    range: Optional[EditorRange]
    module_path: str
    symbol_path: str

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "file_path": str(self.file_path),
            "module_path": str(self.module_path),
            "symbol_path": str(self.symbol_path),
        }
        if self.range is not None:
            payload["range"] = self.range.as_dict()
        return payload


@dataclass(frozen=True)
class ResolutionStep:
    action: str
    input: str = ""
    output: str = ""
    rejected: bool = False
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "action": str(self.action),
            "input": str(self.input),
        }
        if self.output:
            payload["output"] = str(self.output)
        if self.rejected:
            payload["rejected"] = True
        if self.reason:
            payload["reason"] = str(self.reason)
        return payload


@dataclass(frozen=True)
class ResolutionTrace:
    query: str
    steps: Tuple[ResolutionStep, ...] = ()
    locations: Tuple[PythonDefinitionLocation, ...] = ()
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "query": str(self.query),
            "steps": [step.as_dict() for step in self.steps],
            "locations": [loc.as_dict() for loc in self.locations],
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class PythonDefinitionResult:
    locations: Tuple[PythonDefinitionLocation, ...] = ()
    warnings: Tuple[str, ...] = ()
    trace: Optional[ResolutionTrace] = None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "locations": [loc.as_dict() for loc in self.locations],
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        if self.trace is not None:
            payload["trace"] = self.trace.as_dict()
        return payload


@dataclass(frozen=True)
class PythonHoverResult:
    text: str = ""
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": str(self.text)}
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class YamlImportDefinitionLocation:
    file_path: str
    range: Optional[EditorRange]
    fragment_path: str

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "file_path": str(self.file_path),
            "fragment_path": str(self.fragment_path),
        }
        if self.range is not None:
            payload["range"] = self.range.as_dict()
        return payload


@dataclass(frozen=True)
class YamlImportDefinitionResult:
    locations: Tuple[YamlImportDefinitionLocation, ...] = ()
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "locations": [loc.as_dict() for loc in self.locations],
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class YamlImportHoverResult:
    text: str = ""
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": str(self.text)}
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class YamlDslSugarCompletionItem:
    label: str
    insert_text: str
    detail: str = ""
    is_snippet: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "label": str(self.label),
            "insert_text": str(self.insert_text),
            "detail": str(self.detail or ""),
            "is_snippet": bool(self.is_snippet),
        }


@dataclass(frozen=True)
class YamlDslSugarCompletionResult:
    items: Tuple[YamlDslSugarCompletionItem, ...] = ()
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"items": [item.as_dict() for item in self.items]}
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class YamlDslSugarHoverResult:
    text: str = ""
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": str(self.text)}
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class YamlDslImportPathDefinitionResult:
    kind: str = ""  # file|preset
    file_path: str = ""
    preset_id: str = ""
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "kind": str(self.kind or ""),
            "file_path": str(self.file_path or ""),
            "preset_id": str(self.preset_id or ""),
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


@dataclass(frozen=True)
class YamlDslEntityHintDiagnostic:
    """实体引用解析失败时的 hint 级诊断(用于 LSP publishDiagnostics)."""

    message: str
    range: Optional[EditorRange] = None
    code: str = "scalim_unknown_entity_id"
    yaml_path: str = ""
    kind: str = ""
    entity_id: str = ""

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "message": str(self.message),
            "code": str(self.code),
        }
        if self.yaml_path:
            payload["yaml_path"] = str(self.yaml_path)
        if self.kind:
            payload["kind"] = str(self.kind)
        if self.entity_id:
            payload["entity_id"] = str(self.entity_id)
        if self.range is not None:
            payload["range"] = self.range.as_dict()
        return payload


@dataclass(frozen=True)
class YamlDslEntityDeclaration:
    kind: str
    entity_id: str
    yaml_path: str
    range: Optional[EditorRange]
    summary: str = ""
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "kind": str(self.kind),
            "entity_id": str(self.entity_id),
            "yaml_path": str(self.yaml_path),
            "summary": str(self.summary or ""),
            "detail": str(self.detail or ""),
        }
        if self.range is not None:
            payload["range"] = self.range.as_dict()
        return payload


@dataclass(frozen=True)
class YamlDslEntityIndex:
    """单文件实体索引(仅基于 YAML 结构,不执行 Python)."""

    sources: Dict[str, YamlDslEntityDeclaration]
    relations: Dict[str, YamlDslEntityDeclaration]
    outputs: Dict[str, YamlDslEntityDeclaration]
    workflow_runs: Dict[str, YamlDslEntityDeclaration]
    source_fields: Dict[Tuple[str, str], YamlDslEntityDeclaration]
    derived_fields: Dict[str, YamlDslEntityDeclaration]
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        return {
            "sources": {k: v.as_dict() for k, v in self.sources.items()},
            "relations": {k: v.as_dict() for k, v in self.relations.items()},
            "outputs": {k: v.as_dict() for k, v in self.outputs.items()},
            "workflow_runs": {k: v.as_dict() for k, v in self.workflow_runs.items()},
            "source_fields": {"{}.{}".format(k[0], k[1]): v.as_dict() for k, v in self.source_fields.items()},
            "derived_fields": {k: v.as_dict() for k, v in self.derived_fields.items()},
            "warnings": list(self.warnings) if self.warnings else [],
        }


@dataclass(frozen=True)
class YamlDslEntityDefinitionLocation:
    file_path: str
    range: Optional[EditorRange]
    entity_kind: str
    entity_id: str
    yaml_path: str = ""

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "file_path": str(self.file_path),
            "entity_kind": str(self.entity_kind),
            "entity_id": str(self.entity_id),
        }
        if self.yaml_path:
            payload["yaml_path"] = str(self.yaml_path)
        if self.range is not None:
            payload["range"] = self.range.as_dict()
        return payload


@dataclass(frozen=True)
class YamlDslEntityDefinitionResult:
    locations: Tuple[YamlDslEntityDefinitionLocation, ...] = ()
    warnings: Tuple[str, ...] = ()
    hint: Optional[YamlDslEntityHintDiagnostic] = None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "locations": [loc.as_dict() for loc in self.locations],
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        if self.hint is not None:
            payload["hint"] = self.hint.as_dict()
        return payload


@dataclass(frozen=True)
class YamlDslEntityHoverResult:
    text: str = ""
    warnings: Tuple[str, ...] = ()
    hint: Optional[YamlDslEntityHintDiagnostic] = None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": str(self.text)}
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        if self.hint is not None:
            payload["hint"] = self.hint.as_dict()
        return payload


@dataclass(frozen=True)
class YamlDslEntityCompletionItem:
    label: str
    insert_text: str
    detail: str = ""
    is_snippet: bool = False
    replace: str = "token"  # token|value

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "label": str(self.label),
            "insert_text": str(self.insert_text),
            "detail": str(self.detail or ""),
            "is_snippet": bool(self.is_snippet),
            "replace": str(self.replace or "token"),
        }
        return payload


@dataclass(frozen=True)
class YamlDslEntityCompletionResult:
    items: Tuple[YamlDslEntityCompletionItem, ...] = ()
    warnings: Tuple[str, ...] = ()
    hint: Optional[YamlDslEntityHintDiagnostic] = None

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "items": [item.as_dict() for item in self.items],
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        if self.hint is not None:
            payload["hint"] = self.hint.as_dict()
        return payload


@dataclass(frozen=True)
class PythonCompletionResult:
    items: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"items": list(self.items)}
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


def discover_yaml_dsl_editor_project(
    yaml_path: Union[str, Path],
    *,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
    workspace_root_override: Optional[Union[str, Path]] = None,
) -> YamlDslEditorProjectDiscovery:
    """执行 `YAML` `DSL` 编辑器项目发现逻辑.

    输出字段:
    - `project_root`
    - `scalim_yaml_path` (可能为空)
    - `python_roots`
    - `allowed_yaml_roots`
    """
    entry_path = Path(str(yaml_path)).expanduser().resolve(strict=False)
    workspace_root = _resolve_workspace_root_override(workspace_root_override)
    cfg = _load_yaml_dsl_project_config_for_editor(
        entry_path,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
        workspace_root=workspace_root,
    )
    return _discover_yaml_dsl_editor_project_from_project_config(entry_path, cfg, workspace_root=workspace_root)


def _resolve_workspace_root_override(raw: Optional[Union[str, Path]]) -> Optional[Path]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        resolved = Path(text).expanduser().resolve(strict=False)
    except Exception:  # noqa: BLE001
        return None
    if not resolved.exists() or not resolved.is_dir():
        return None
    return resolved


def _is_within_dir(path: Path, root: Path) -> bool:
    try:
        _ = path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _locate_scalim_yaml_bounded(*, start_dir: Path, stop_dir: Path) -> Optional[Path]:
    current = start_dir.resolve(strict=False)
    stop = stop_dir.resolve(strict=False)
    if current != stop and not _is_within_dir(current, stop):
        return None

    while True:
        candidate = current / _SCALIM_YAML_FILENAME
        if candidate.exists() and candidate.is_file():
            return candidate.resolve(strict=False)
        if current == stop:
            return None
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _load_yaml_dsl_project_config_for_editor(
    entry_path: Path,
    *,
    scalim_yaml_override: Optional[Union[str, Path]],
    project_root_override: Optional[Union[str, Path]],
    workspace_root: Optional[Path],
) -> Optional[YamlDslProjectConfig]:
    if scalim_yaml_override is not None or project_root_override is not None:
        return load_yaml_dsl_project_config(
            entry_path,
            scalim_yaml_override=scalim_yaml_override,
            project_root_override=project_root_override,
        )

    if workspace_root is not None and _is_within_dir(entry_path, workspace_root):
        scalim_yaml_path = _locate_scalim_yaml_bounded(start_dir=entry_path.parent, stop_dir=workspace_root)
        if scalim_yaml_path is None:
            return None
        return load_yaml_dsl_project_config(entry_path, scalim_yaml_override=scalim_yaml_path)

    return load_yaml_dsl_project_config(entry_path)


def _discover_yaml_dsl_editor_project_from_project_config(
    entry_path: Path,
    cfg: Optional[YamlDslProjectConfig],
    *,
    workspace_root: Optional[Path],
) -> YamlDslEditorProjectDiscovery:
    entry_dir = entry_path.parent
    project_root = entry_dir
    scalim_yaml_path: Optional[Path] = None
    raw_allowed_roots: Optional[Iterable[Union[str, Path]]] = None
    raw_python_roots: Optional[Iterable[Union[str, Path]]] = None

    if cfg is not None:
        project_root = cfg.project_root
        scalim_yaml_path = cfg.scalim_yaml_path
        raw_allowed_roots = tuple(item.path for item in cfg.import_roots)
        if cfg.lsp is not None and cfg.lsp.python_roots:
            raw_python_roots = cfg.lsp.python_roots
        elif workspace_root is not None and _is_within_dir(entry_path, workspace_root):
            # `scalim.yaml` is present but does not declare `yaml_dsl.lsp.python_roots`.
            # For editor features (go-to-definition/hover/completion), prefer a 0-config experience:
            # infer a monorepo-friendly set of python roots from the workspace root, while
            # still including `project_root` to keep relative-module references stable.
            raw_python_roots = (*_infer_default_python_roots(workspace_root), project_root)
    elif workspace_root is not None and _is_within_dir(entry_path, workspace_root):
        project_root = workspace_root
        raw_allowed_roots = (workspace_root,)
        raw_python_roots = _infer_default_python_roots(workspace_root)

    allowed_yaml_roots = normalize_allowed_yaml_roots(raw_allowed_roots, default_root=entry_dir)
    python_roots = _normalize_python_roots(raw_python_roots, default_root=project_root)

    return YamlDslEditorProjectDiscovery(
        project_root=project_root,
        scalim_yaml_path=scalim_yaml_path,
        python_roots=python_roots,
        allowed_yaml_roots=allowed_yaml_roots,
    )


_YAML_DSL_SCHEMA_MARKERS: Tuple[str, ...] = (
    "demand.gen.json",
    "workflow.gen.json",
    "scalim_yaml.gen.json",
)

_YAML_DSL_FALLBACK_HINT_RE = re.compile(r"(?m)^\s*(loader|call_by)\s*:")
_YAML_DSL_DOLLAR_HINT_RE = re.compile(r"\$(import|init_var)\b")


def _try_resolve_yaml_path(raw: Optional[Union[str, Path]]) -> Optional[Path]:
    if raw is None:
        return None
    try:
        return Path(str(raw)).expanduser().resolve(strict=False)
    except Exception:  # noqa: BLE001
        return None


def _is_yaml_dsl_path_excluded(path: Optional[Path]) -> bool:
    if path is None:
        return False
    if path.name == _SCALIM_YAML_FILENAME:
        return True
    # Skip ephemeral generated folders by default.
    return ".tmp" in path.parts


def _has_yaml_dsl_text_hints(text: str) -> bool:
    if any(marker in text for marker in _YAML_DSL_SCHEMA_MARKERS):
        return True
    if _YAML_DSL_DOLLAR_HINT_RE.search(text) is not None:
        return True
    return _YAML_DSL_FALLBACK_HINT_RE.search(text) is not None


def _try_load_yaml_mapping(text: str) -> Optional[Dict[str, Any]]:
    try:
        loaded = yaml.safe_load(text)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(loaded, dict):
        return None
    return cast("Dict[str, Any]", loaded)  # pragma: allow-cast yaml safe_load typed narrowing


def is_probably_yaml_dsl_document(yaml_path: Optional[Union[str, Path]], yaml_text: str) -> bool:
    """Best-effort heuristic to decide whether a YAML file looks like Scalim YAML DSL.

    This is used to avoid polluting unrelated YAML files with scalim diagnostics/features.
    """
    path = _try_resolve_yaml_path(yaml_path)
    if _is_yaml_dsl_path_excluded(path):
        return False

    text = str(yaml_text or "")
    if not text.strip():
        return False

    if _has_yaml_dsl_text_hints(text):
        return True

    loaded_dict = _try_load_yaml_mapping(text)
    if loaded_dict is None:
        return False

    required_kind = _classify_yaml_kind_by_required_keys_loaded(loaded_dict)
    if required_kind:
        return True

    # Permissive fallback for in-progress demand drafts that only contain `imports` + `name`.
    imports_obj = loaded_dict.get("imports")
    return isinstance(imports_obj, dict) and "name" in loaded_dict


def classify_yaml_dsl_kind(
    yaml_path: Union[str, Path],
    yaml_text: str,
    *,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
    workspace_root_override: Optional[Union[str, Path]] = None,
) -> str:
    """对单个 `YAML` 文件执行类型分类(`demand`/`workflow`)."""
    path = Path(str(yaml_path)).expanduser().resolve(strict=False)
    workspace_root = _resolve_workspace_root_override(workspace_root_override)
    cfg = _load_yaml_dsl_project_config_for_editor(
        path,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
        workspace_root=workspace_root,
    )
    kind = _classify_yaml_kind_from_overrides(path, cfg)
    if kind:
        return kind
    kind = _classify_yaml_kind_by_required_keys(yaml_text)
    if kind:
        return kind
    return _classify_yaml_kind_by_heuristic(yaml_text)


def collect_yaml_dsl_editor_diagnostics(
    yaml_path: Union[str, Path],
    *,
    yaml_text: Optional[str] = None,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
    workspace_root_override: Optional[Union[str, Path]] = None,
) -> YamlDslEditorDiagnosticsResult:
    """收集编辑器/`LSP` 侧 `diagnostics`(不调用 `CLI`)."""
    path = Path(str(yaml_path)).expanduser().resolve(strict=False)
    if yaml_text is None:
        yaml_text = path.read_text(encoding="utf-8")

    workspace_root = _resolve_workspace_root_override(workspace_root_override)
    cfg = _load_yaml_dsl_project_config_for_editor(
        path,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
        workspace_root=workspace_root,
    )
    discovery = _discover_yaml_dsl_editor_project_from_project_config(path, cfg, workspace_root=workspace_root)

    yaml_kind = (
        _classify_yaml_kind_from_overrides(path, cfg)
        or _classify_yaml_kind_by_required_keys(yaml_text)
        or _classify_yaml_kind_by_heuristic(yaml_text)
    )

    if yaml_kind == YAML_DSL_KIND_WORKFLOW:
        errors, warnings = _collect_workflow_diagnostics(yaml_text, yaml_path=path)
        return YamlDslEditorDiagnosticsResult(
            yaml_kind=yaml_kind,
            discovery=discovery,
            errors=errors,
            warnings=warnings,
        )

    errors, warnings = _collect_demand_diagnostics(
        yaml_text,
        yaml_path=path,
        allowed_yaml_roots=discovery.allowed_yaml_roots,
    )
    return YamlDslEditorDiagnosticsResult(
        yaml_kind=YAML_DSL_KIND_DEMAND,
        discovery=discovery,
        errors=errors,
        warnings=warnings,
    )


def build_yaml_dsl_entity_index(
    yaml_text: str,
    *,
    yaml_kind: str,
    source_path: str,
) -> YamlDslEntityIndex:
    """从单个 YAML 文档构建实体索引(单文件,静态,无副作用)."""
    warnings: List[str] = []
    store = _EntityIndexStore(
        sources={},
        relations={},
        outputs={},
        workflow_runs={},
        source_fields={},
        derived_fields={},
    )

    parsed = _load_yaml_mapping_for_entity_index(yaml_text, source_path=source_path, warnings=warnings)
    if parsed is not None:
        demand, locations = parsed
        _index_main_source_entities(demand, locations, store)
        _index_lookup_sources_entities(demand, locations, store)
        _index_derived_fields_entities(demand, locations, store)
        _index_relations_entities(demand, locations, store)
        _index_outputs_entities(demand, locations, store)
        _index_workflow_runs_entities(demand, locations, store)

    if yaml_kind not in _YAML_DSL_KIND_CHOICES:
        warnings.append("Unknown yaml_kind: {}".format(str(yaml_kind)))

    return YamlDslEntityIndex(
        sources=store.sources,
        relations=store.relations,
        outputs=store.outputs,
        workflow_runs=store.workflow_runs,
        source_fields=store.source_fields,
        derived_fields=store.derived_fields,
        warnings=tuple(warnings),
    )


@dataclass
class _EntityIndexStore:
    sources: Dict[str, YamlDslEntityDeclaration]
    relations: Dict[str, YamlDslEntityDeclaration]
    outputs: Dict[str, YamlDslEntityDeclaration]
    workflow_runs: Dict[str, YamlDslEntityDeclaration]
    source_fields: Dict[Tuple[str, str], YamlDslEntityDeclaration]
    derived_fields: Dict[str, YamlDslEntityDeclaration]


def _load_yaml_mapping_for_entity_index(
    yaml_text: str,
    *,
    source_path: str,
    warnings: List[str],
) -> Optional[Tuple[Dict[str, Any], Dict[str, Tuple[int, int]]]]:
    try:
        loaded, locations, _lines = load_yaml_mapping_text(yaml_text, source_path=str(source_path))
    except ScalimYamlValidationError as exc:
        msg = exc.errors[0].message if exc.errors else str(exc)
        warnings.append("YAML parse failed: {}".format(msg))
        return None
    except Exception as exc:  # noqa: BLE001
        warnings.append("YAML parse failed: {}: {}".format(type(exc).__name__, exc))
        return None
    if not isinstance(loaded, dict):
        warnings.append("YAML root must be a mapping")
        return None
    return loaded, locations


def _index_main_source_entities(demand: Dict[str, Any], locations: Dict[str, Tuple[int, int]], store: _EntityIndexStore) -> None:
    main_source = demand.get("main_source")
    if not isinstance(main_source, dict):
        return
    main_source_id = _safe_str(main_source.get("source_id"))
    if not main_source_id:
        return
    decl = _build_source_declaration(
        main_source_id,
        yaml_path="main_source.source_id",
        range_key_text="source_id",
        locations=locations,
        spec=main_source,
    )
    if decl is not None:
        store.sources[main_source_id] = decl
    _index_source_fields(main_source_id, main_source.get("fields"), base_yaml_path="main_source.fields", locations=locations, store=store)


def _index_lookup_sources_entities(demand: Dict[str, Any], locations: Dict[str, Tuple[int, int]], store: _EntityIndexStore) -> None:
    sources_map = demand.get("sources")
    if not isinstance(sources_map, dict):
        return
    for source_id, spec in sources_map.items():
        sid = _safe_str(source_id)
        if not sid:
            continue
        decl = _build_source_declaration(
            sid,
            yaml_path="sources.{}".format(sid),
            range_key_text=sid,
            locations=locations,
            spec=spec,
        )
        if decl is not None:
            store.sources[sid] = decl
        fields_map = spec.get("fields") if isinstance(spec, dict) else None
        _index_source_fields(sid, fields_map, base_yaml_path="sources.{}.fields".format(sid), locations=locations, store=store)


def _index_source_fields(
    source_id: str,
    fields_map: object,
    *,
    base_yaml_path: str,
    locations: Dict[str, Tuple[int, int]],
    store: _EntityIndexStore,
) -> None:
    if not source_id or not isinstance(fields_map, dict):
        return
    for field_id, spec in fields_map.items():
        fid = _safe_str(field_id)
        if not fid:
            continue
        yaml_path = "{}.{}".format(base_yaml_path, fid)
        rng = _range_for_yaml_key_path(yaml_path, key_text=fid, locations=locations)
        store.source_fields[(source_id, fid)] = YamlDslEntityDeclaration(
            kind="source_field",
            entity_id=fid,
            yaml_path=yaml_path,
            range=rng,
            summary=_field_summary(spec),
            detail=_field_detail(spec),
        )


def _index_derived_fields_entities(demand: Dict[str, Any], locations: Dict[str, Tuple[int, int]], store: _EntityIndexStore) -> None:
    derived_map = demand.get("fields")
    if not isinstance(derived_map, dict):
        return
    for field_id, spec in derived_map.items():
        fid = _safe_str(field_id)
        if not fid:
            continue
        yaml_path = "fields.{}".format(fid)
        rng = _range_for_yaml_key_path(yaml_path, key_text=fid, locations=locations)
        store.derived_fields[fid] = YamlDslEntityDeclaration(
            kind="derived_field",
            entity_id=fid,
            yaml_path=yaml_path,
            range=rng,
            summary=_field_summary(spec),
            detail=_field_detail(spec),
        )


def _index_relations_entities(demand: Dict[str, Any], locations: Dict[str, Tuple[int, int]], store: _EntityIndexStore) -> None:
    relations_map = demand.get("relations")
    if not isinstance(relations_map, dict):
        return
    for rel_id, spec in relations_map.items():
        rid = _safe_str(rel_id)
        if not rid:
            continue
        yaml_path = "relations.{}".format(rid)
        rng = _range_for_yaml_key_path(yaml_path, key_text=rid, locations=locations)
        store.relations[rid] = YamlDslEntityDeclaration(
            kind="relation",
            entity_id=rid,
            yaml_path=yaml_path,
            range=rng,
            summary=_relation_summary(spec),
            detail=_relation_detail(spec),
        )


def _index_outputs_entities(demand: Dict[str, Any], locations: Dict[str, Tuple[int, int]], store: _EntityIndexStore) -> None:
    outputs_seq = demand.get("outputs")
    if not isinstance(outputs_seq, list):
        return
    for idx, spec in enumerate(outputs_seq):
        if not isinstance(spec, dict):
            continue
        name = _safe_str(spec.get("name"))
        if not name:
            continue
        yaml_path = "outputs.{}.name".format(idx)
        rng = _range_for_yaml_key_path(yaml_path, key_text="name", locations=locations)
        store.outputs[name] = YamlDslEntityDeclaration(
            kind="output",
            entity_id=name,
            yaml_path=yaml_path,
            range=rng,
            summary=_output_summary(spec),
            detail=_output_detail(spec),
        )


def _index_workflow_runs_entities(demand: Dict[str, Any], locations: Dict[str, Tuple[int, int]], store: _EntityIndexStore) -> None:
    workflow = demand.get("workflow")
    if not isinstance(workflow, dict):
        return
    runs = workflow.get("runs")
    if not isinstance(runs, list):
        return
    for idx, spec in enumerate(runs):
        if not isinstance(spec, dict):
            continue
        run_id = _safe_str(spec.get("id"))
        if not run_id:
            continue
        yaml_path = "workflow.runs.{}.id".format(idx)
        rng = _range_for_yaml_key_path(yaml_path, key_text="id", locations=locations)
        store.workflow_runs[run_id] = YamlDslEntityDeclaration(
            kind="workflow_run",
            entity_id=run_id,
            yaml_path=yaml_path,
            range=rng,
            summary=_workflow_run_summary(spec),
            detail=_workflow_run_detail(spec),
        )


def resolve_yaml_dsl_entity_definition(
    extraction: YamlCursorExtractionResult,
    *,
    entity_index: YamlDslEntityIndex,
    anchor_yaml_path: Union[str, Path],
) -> YamlDslEntityDefinitionResult:
    """解析实体引用并返回定义位置(同文件)."""
    kind = str(getattr(extraction, "kind", "") or "").strip()
    ref = str(extraction.reference or "").strip()
    if not kind or not ref:
        return YamlDslEntityDefinitionResult()

    file_path = str(Path(str(anchor_yaml_path)).expanduser().resolve(strict=False))

    if kind == "relation_step_field_id":
        return _resolve_relation_step_field_definition(extraction, entity_index=entity_index, file_path=file_path)

    kind_label, decl = _simple_decl_for_entity_reference(kind, ref, entity_index=entity_index)
    if not kind_label:
        return YamlDslEntityDefinitionResult(warnings=("Unknown extraction kind: {}".format(kind),))
    if decl is None:
        return YamlDslEntityDefinitionResult(hint=_unknown_hint(kind_label, ref, extraction))
    return _definition_result_for_decl(decl, file_path=file_path)


def _definition_result_for_decl(decl: YamlDslEntityDeclaration, *, file_path: str) -> YamlDslEntityDefinitionResult:
    loc = YamlDslEntityDefinitionLocation(
        file_path=str(file_path),
        range=decl.range,
        entity_kind=str(decl.kind),
        entity_id=str(decl.entity_id),
        yaml_path=str(decl.yaml_path),
    )
    return YamlDslEntityDefinitionResult(locations=(loc,))


def _simple_decl_for_entity_reference(
    kind: str,
    ref: str,
    *,
    entity_index: YamlDslEntityIndex,
) -> Tuple[str, Optional[YamlDslEntityDeclaration]]:
    if kind in ("source_id", "relation_step_source_id"):
        return "source id", entity_index.sources.get(ref)
    if kind == "relation_id":
        return "relation id", entity_index.relations.get(ref)
    if kind == "output_name":
        return "output name", entity_index.outputs.get(ref)
    if kind == "workflow_run_id":
        return "workflow run id", entity_index.workflow_runs.get(ref)
    return "", None


def _resolve_relation_step_field_definition(
    extraction: YamlCursorExtractionResult,
    *,
    entity_index: YamlDslEntityIndex,
    file_path: str,
) -> YamlDslEntityDefinitionResult:
    source_id, field_id = _split_source_field_ref(extraction.value or "")
    if not source_id:
        return YamlDslEntityDefinitionResult(hint=_unknown_hint("source id", source_id, extraction))
    if not field_id:
        return YamlDslEntityDefinitionResult()

    decl = entity_index.source_fields.get((source_id, field_id)) or entity_index.derived_fields.get(field_id)
    if decl is None:
        return YamlDslEntityDefinitionResult(hint=_unknown_hint("field id", field_id, extraction, extra="source={}".format(source_id)))
    return _definition_result_for_decl(decl, file_path=file_path)


def hover_yaml_dsl_entity_reference(
    extraction: YamlCursorExtractionResult,
    *,
    entity_index: YamlDslEntityIndex,
) -> YamlDslEntityHoverResult:
    kind = str(getattr(extraction, "kind", "") or "").strip()
    ref = str(extraction.reference or "").strip()
    if not kind or not ref:
        return YamlDslEntityHoverResult(text="")

    if kind == "relation_step_field_id":
        return _hover_relation_step_field(extraction, entity_index=entity_index)

    title, kind_label, decl = _simple_hover_decl_for_entity_reference(kind, ref, entity_index=entity_index)
    if not title:
        return YamlDslEntityHoverResult(text="")
    if decl is None:
        return YamlDslEntityHoverResult(text="", hint=_unknown_hint(kind_label, ref, extraction))
    return YamlDslEntityHoverResult(text=_hover_card(title, decl))


def _simple_hover_decl_for_entity_reference(
    kind: str,
    ref: str,
    *,
    entity_index: YamlDslEntityIndex,
) -> Tuple[str, str, Optional[YamlDslEntityDeclaration]]:
    if kind in ("source_id", "relation_step_source_id"):
        return "Source", "source id", entity_index.sources.get(ref)
    if kind == "relation_id":
        return "Relation", "relation id", entity_index.relations.get(ref)
    if kind == "output_name":
        return "Output", "output name", entity_index.outputs.get(ref)
    if kind == "workflow_run_id":
        return "Workflow Run", "workflow run id", entity_index.workflow_runs.get(ref)
    return "", "", None


def _hover_relation_step_field(extraction: YamlCursorExtractionResult, *, entity_index: YamlDslEntityIndex) -> YamlDslEntityHoverResult:
    source_id, field_id = _split_source_field_ref(extraction.value or "")
    if not source_id or not field_id:
        return YamlDslEntityHoverResult(text="")

    decl = entity_index.source_fields.get((source_id, field_id)) or entity_index.derived_fields.get(field_id)
    if decl is None:
        return YamlDslEntityHoverResult(
            text="",
            hint=_unknown_hint("field id", field_id, extraction, extra="source={}".format(source_id)),
        )

    title = "Field ({})".format(source_id) if decl.kind == "source_field" else "Field"
    return YamlDslEntityHoverResult(text=_hover_card(title, decl))


def complete_yaml_dsl_entity_reference(
    extraction: YamlCursorExtractionResult,
    *,
    entity_index: YamlDslEntityIndex,
) -> YamlDslEntityCompletionResult:
    kind = str(getattr(extraction, "kind", "") or "").strip()
    if not kind:
        return YamlDslEntityCompletionResult(items=())

    if kind == "relation_step_source_id":
        return _complete_relation_step_source_id(entity_index=entity_index)

    if kind == "relation_step_field_id":
        return _complete_relation_step_field_id(extraction, entity_index=entity_index)

    decls = _decls_for_simple_completion_kind(kind, entity_index=entity_index)
    if decls is None:
        return YamlDslEntityCompletionResult(items=(), warnings=("Unknown extraction kind: {}".format(kind),))

    items = _completion_items_for_decls(sorted(decls, key=lambda d: d.entity_id), replace="token")
    return YamlDslEntityCompletionResult(items=items)


def _decls_for_simple_completion_kind(kind: str, *, entity_index: YamlDslEntityIndex) -> Optional[Sequence[YamlDslEntityDeclaration]]:
    if kind == "source_id":
        return list(entity_index.sources.values())
    if kind == "relation_id":
        return list(entity_index.relations.values())
    if kind == "output_name":
        return list(entity_index.outputs.values())
    if kind == "workflow_run_id":
        return list(entity_index.workflow_runs.values())
    return None


def _complete_relation_step_source_id(*, entity_index: YamlDslEntityIndex) -> YamlDslEntityCompletionResult:
    decls = sorted(entity_index.sources.values(), key=lambda d: d.entity_id)
    snippet = YamlDslEntityCompletionItem(
        label="source_id.field_id",
        insert_text="${1:source_id}.${2:field_id}",
        detail="snippet",
        is_snippet=True,
        replace="value",
    )
    items = (snippet, *_completion_items_for_decls(decls, replace="token"))
    return YamlDslEntityCompletionResult(items=items)


def _complete_relation_step_field_id(
    extraction: YamlCursorExtractionResult,
    *,
    entity_index: YamlDslEntityIndex,
) -> YamlDslEntityCompletionResult:
    source_id, _field_id = _split_source_field_ref(extraction.value or "")
    if not source_id:
        return YamlDslEntityCompletionResult(items=())
    if source_id not in entity_index.sources:
        return YamlDslEntityCompletionResult(items=(), hint=_unknown_hint("source id", source_id, extraction))

    fields = [decl for (sid, _fid), decl in entity_index.source_fields.items() if sid == source_id]
    fields_sorted = sorted(fields, key=lambda d: d.entity_id)
    items = _completion_items_for_decls(fields_sorted, replace="token")
    return YamlDslEntityCompletionResult(items=items)


def _safe_str(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    return str(raw).strip()


def _range_for_yaml_key_path(
    yaml_path: str,
    *,
    key_text: str,
    locations: Dict[str, Tuple[int, int]],
) -> Optional[EditorRange]:
    loc = locations.get(str(yaml_path))
    if loc is None:
        return None
    line, column = loc
    end_col = int(column) + max(1, len(str(key_text)))
    return EditorRange(
        start=EditorPosition(line=int(line), column=int(column)),
        end=EditorPosition(line=int(line), column=int(end_col)),
    )


def _build_source_declaration(
    source_id: str,
    *,
    yaml_path: str,
    range_key_text: str,
    locations: Dict[str, Tuple[int, int]],
    spec: object,
) -> Optional[YamlDslEntityDeclaration]:
    rng = _range_for_yaml_key_path(yaml_path, key_text=str(range_key_text), locations=locations)
    loader = ""
    key = ""
    fields_cnt = 0
    if isinstance(spec, dict):
        loader = _safe_str(spec.get("loader"))
        key_raw = spec.get("key")
        if isinstance(key_raw, list):
            key = "[" + ", ".join([_safe_str(k) for k in key_raw if _safe_str(k)]) + "]"
        else:
            key = _safe_str(key_raw)
        fields_raw = spec.get("fields")
        if isinstance(fields_raw, dict):
            fields_cnt = len(fields_raw)

    summary = "loader: {}".format(loader) if loader else ""
    detail_lines: List[str] = ["id: {}".format(source_id)]
    if loader:
        detail_lines.append("loader: {}".format(loader))
    if key:
        detail_lines.append("key: {}".format(key))
    if fields_cnt:
        detail_lines.append("fields: {}".format(int(fields_cnt)))

    return YamlDslEntityDeclaration(
        kind="source",
        entity_id=str(source_id),
        yaml_path=str(yaml_path),
        range=rng,
        summary=summary,
        detail="\n".join(detail_lines),
    )


def _field_summary(spec: object) -> str:
    if isinstance(spec, dict):
        name = _safe_str(spec.get("name"))
        if name:
            return "name: {}".format(name)
    return ""


def _field_detail(spec: object) -> str:
    if isinstance(spec, dict):
        name = _safe_str(spec.get("name"))
        if name:
            return "name: {}".format(name)
    return ""


def _relation_sources_involved(rel_spec: object) -> Tuple[str, ...]:
    if not isinstance(rel_spec, dict):
        return ()
    steps = rel_spec.get("steps")
    if not isinstance(steps, list):
        return ()
    names: Dict[str, None] = {}
    for step in steps:
        if not isinstance(step, dict):
            continue
        for key in ("from", "to"):
            val = step.get(key)
            for src in _iter_source_ids_from_step_value(val):
                if src:
                    names[src] = None
    return tuple(sorted(names.keys()))


def _iter_source_ids_from_step_value(val: object) -> Iterable[str]:
    if isinstance(val, str):
        src, _field = _split_source_field_ref(val)
        if src:
            yield src
        return
    if isinstance(val, list):
        for item in val:
            if isinstance(item, str):
                src, _field = _split_source_field_ref(item)
                if src:
                    yield src


def _relation_summary(rel_spec: object) -> str:
    if not isinstance(rel_spec, dict):
        return ""
    steps = rel_spec.get("steps")
    step_cnt = len(steps) if isinstance(steps, list) else 0
    sources = _relation_sources_involved(rel_spec)
    if sources:
        return "steps: {} | sources: {}".format(int(step_cnt), ", ".join(sources))
    return "steps: {}".format(int(step_cnt))


def _relation_detail(rel_spec: object) -> str:
    if not isinstance(rel_spec, dict):
        return ""
    steps = rel_spec.get("steps")
    step_cnt = len(steps) if isinstance(steps, list) else 0
    sources = _relation_sources_involved(rel_spec)
    lines = ["steps: {}".format(int(step_cnt))]
    if sources:
        lines.append("sources: {}".format(", ".join(sources)))
    return "\n".join(lines)


def _output_summary(out_spec: object) -> str:
    if not isinstance(out_spec, dict):
        return ""
    parent = _safe_str(out_spec.get("from"))
    if parent:
        return "from: {}".format(parent)
    return ""


def _output_detail(out_spec: object) -> str:
    if not isinstance(out_spec, dict):
        return ""
    lines: List[str] = []
    parent = _safe_str(out_spec.get("from"))
    if parent:
        lines.append("from: {}".format(parent))
    fields_raw = out_spec.get("fields")
    if isinstance(fields_raw, list):
        lines.append("fields: {}".format(len(fields_raw)))
    if isinstance(out_spec.get("aggregate"), dict):
        lines.append("aggregate: true")
    return "\n".join(lines)


def _workflow_run_summary(run_spec: object) -> str:
    if not isinstance(run_spec, dict):
        return ""
    deps_raw = run_spec.get("depends_on")
    if isinstance(deps_raw, list):
        deps = [d for d in [_safe_str(x) for x in deps_raw] if d]
        if deps:
            return "depends_on: {}".format(", ".join(deps))
    return ""


def _workflow_run_detail(run_spec: object) -> str:
    if not isinstance(run_spec, dict):
        return ""
    lines: List[str] = []
    deps_raw = run_spec.get("depends_on")
    if isinstance(deps_raw, list):
        deps = [d for d in [_safe_str(x) for x in deps_raw] if d]
        if deps:
            lines.append("depends_on: {}".format(", ".join(deps)))
    return "\n".join(lines)


def _split_source_field_ref(text: str) -> Tuple[str, str]:
    raw = _safe_str(text)
    if not raw:
        return "", ""
    if "." not in raw:
        return raw, ""
    left, right = raw.split(".", 1)
    return _safe_str(left), _safe_str(right)


def _unknown_hint(
    kind_label: str, entity_id: str, extraction: YamlCursorExtractionResult, *, extra: str = ""
) -> YamlDslEntityHintDiagnostic:
    suffix = " ({})".format(extra) if extra else ""
    msg = "Unknown {}: {}{}".format(str(kind_label), str(entity_id), suffix)
    return YamlDslEntityHintDiagnostic(
        message=msg,
        range=extraction.range,
        yaml_path=str(extraction.yaml_path or ""),
        kind=str(getattr(extraction, "kind", "") or ""),
        entity_id=str(entity_id or ""),
    )


def _hover_card(title: str, decl: YamlDslEntityDeclaration) -> str:
    lines = ["{}: {}".format(title, decl.entity_id)]
    detail = str(decl.detail or "").strip()
    if detail:
        for ln in detail.splitlines():
            # avoid duplicating "id:" line in Source card
            if title == "Source" and ln.startswith("id:"):
                continue
            lines.append(str(ln))
    return "\n".join(lines).strip()


def _completion_items_for_decls(
    decls: Sequence[YamlDslEntityDeclaration],
    *,
    replace: str,
) -> Tuple[YamlDslEntityCompletionItem, ...]:
    items: List[YamlDslEntityCompletionItem] = []
    for decl in decls:
        detail = str(decl.summary or "")
        items.append(
            YamlDslEntityCompletionItem(
                label=str(decl.entity_id),
                insert_text=str(decl.entity_id),
                detail=detail,
                is_snippet=False,
                replace=str(replace or "token"),
            )
        )
    return tuple(items)


def resolve_python_definition(
    reference: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]] = None,
) -> PythonDefinitionResult:
    """静态解析 `Python` 引用并返回定义位置(不执行用户代码)."""
    warnings: List[str] = []
    steps: List[ResolutionStep] = []
    raw = str(reference or "").strip()
    if not raw:
        msg = "引用不能为空"
        warnings.append(msg)
        _trace_add_step(steps, action="validate_reference", input_text=str(reference or ""), rejected=True, reason=msg)
        trace = ResolutionTrace(query=str(reference or ""), steps=tuple(steps), locations=(), warnings=tuple(warnings))
        return PythonDefinitionResult(locations=(), warnings=tuple(warnings), trace=trace)

    if is_valid_builtin_callable_reference(raw):
        msg = "builtin callable 引用不支持 go-to-definition"
        warnings.append(msg)
        _trace_add_step(steps, action="validate_reference", input_text=raw, rejected=True, reason=msg)
        trace = ResolutionTrace(query=raw, steps=tuple(steps), locations=(), warnings=tuple(warnings))
        return PythonDefinitionResult(locations=(), warnings=tuple(warnings), trace=trace)

    try:
        parsed = parse_python_reference(raw)
    except ScalimReferenceSyntaxError as exc:
        msg = str(exc)
        warnings.append(msg)
        _trace_add_step(steps, action="parse_reference", input_text=raw, rejected=True, reason=msg)
        trace = ResolutionTrace(query=raw, steps=tuple(steps), locations=(), warnings=tuple(warnings))
        return PythonDefinitionResult(locations=(), warnings=tuple(warnings), trace=trace)
    _trace_add_step(
        steps,
        action="parse_reference",
        input_text=raw,
        output="module_path='{}' attr_path='{}'".format(parsed.module_path, ".".join(parsed.attr_path)),
    )

    before_warnings = len(warnings)
    module_path = _normalize_python_module_path(
        parsed.module_path,
        python_roots=python_roots,
        anchor_path=anchor_path,
        warnings=warnings,
    )
    if not module_path:
        reason = "; ".join(warnings[before_warnings:]) if len(warnings) > before_warnings else "无法解析 module_path"
        _trace_add_step(steps, action="normalize_module_path", input_text=str(parsed.module_path), rejected=True, reason=reason)
        trace = ResolutionTrace(query=raw, steps=tuple(steps), locations=(), warnings=tuple(warnings))
        return PythonDefinitionResult(locations=(), warnings=tuple(warnings), trace=trace)
    _trace_add_step(steps, action="normalize_module_path", input_text=str(parsed.module_path), output=str(module_path))

    parsed = ParsedReference(
        reference=parsed.reference,
        module_path=module_path,
        attr_path=parsed.attr_path,
        style=parsed.style,
    )

    locations = _resolve_python_definition_locations(parsed, python_roots=python_roots, warnings=warnings, trace_steps=steps)
    if not locations:
        if any(("模块语法解析失败" in w or "读取模块文件失败" in w) for w in warnings) and not any(
            "无法解析符号定义" in w for w in warnings
        ):
            warnings.append("无法解析符号定义: {}".format(parsed.reference))
        _trace_add_step(steps, action="finalize_locations", input_text=str(parsed.reference), rejected=True, reason="no locations")
        trace = ResolutionTrace(query=raw, steps=tuple(steps), locations=(), warnings=tuple(warnings))
        return PythonDefinitionResult(locations=(), warnings=tuple(warnings), trace=trace)

    trace = ResolutionTrace(query=raw, steps=tuple(steps), locations=locations, warnings=tuple(warnings))
    return PythonDefinitionResult(locations=locations, warnings=tuple(warnings), trace=trace)


def _scalim_editor_python_roots() -> Tuple[Path, ...]:
    """为 editor 侧 builtin callables 提供可解析 scalim 自身源码的 roots.

    说明:
    - builtin callable 属于 scalim runtime 的保守词表,其 definition/hover 需要能跳到 scalim 源码,
      即使 workspace 本身不包含 scalim 包源码(例如用户只安装了 scalim 依赖)。
    - 这里仅用于静态定位符号定义,不执行用户代码。
    """
    raw = getattr(yaml_dsl, "__file__", None)
    if not isinstance(raw, str) or not raw.strip():
        return ()
    try:
        module_file = Path(raw).expanduser().resolve(strict=False)
    except Exception:  # noqa: BLE001
        return ()

    pkg_dir: Optional[Path] = None
    for parent in module_file.parents:
        if parent.name == "scalim":
            pkg_dir = parent
            break
    if pkg_dir is None:
        return ()
    root = pkg_dir.parent
    if not root.exists() or not root.is_dir():
        return ()
    return (root,)


def _dedupe_python_roots(raw: Sequence[Union[str, Path]]) -> Tuple[Path, ...]:
    seen: Dict[str, None] = {}
    out: List[Path] = []
    for item in raw:
        p: Optional[Path]
        try:
            p = Path(str(item)).expanduser().resolve(strict=False)
        except Exception:  # noqa: BLE001
            p = None
        if p is None:
            continue
        key = str(p)
        if key in seen:
            continue
        seen[key] = None
        out.append(p)
    return tuple(out)


def complete_yaml_dsl_builtin_callable_reference(
    reference_prefix: str,
    *,
    call_by: bool,
) -> YamlDslSugarCompletionResult:
    """为 `^<id>` builtin callable 提供 completion(保守词表)."""
    warnings: List[str] = []
    raw = str(reference_prefix or "")
    if not raw.strip():
        return YamlDslSugarCompletionResult(items=(), warnings=())

    prefix = raw.lstrip()
    if not prefix.startswith("^"):
        return YamlDslSugarCompletionResult(items=(), warnings=())

    id_prefix = prefix[1:]
    ids = list_public_builtin_callable_ids()
    python_refs = list_public_builtin_callable_python_references()

    matched = [builtin_id for builtin_id in ids if builtin_id.startswith(id_prefix)]
    if not matched and id_prefix:
        warnings.append("Unknown builtin callable id prefix: {!r}".format(id_prefix))

    items: List[YamlDslSugarCompletionItem] = []
    for builtin_id in matched:
        py_ref = python_refs.get(builtin_id, "")
        detail = "python: {}".format(py_ref) if py_ref else ""
        insert_text = "^{}".format(builtin_id)
        is_snippet = False
        if call_by:
            insert_text = "^{}(${{1:arg}}=${{2:value}})".format(builtin_id)
            is_snippet = True
        items.append(
            YamlDslSugarCompletionItem(
                label=str(builtin_id),
                insert_text=str(insert_text),
                detail=detail,
                is_snippet=is_snippet,
            )
        )

    return YamlDslSugarCompletionResult(items=tuple(items), warnings=tuple(warnings))


def resolve_yaml_dsl_builtin_callable_definition(
    reference: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]] = None,
) -> PythonDefinitionResult:
    """静态解析 builtin callable 引用并尽可能跳转到 scalim 源码实现."""
    raw = str(reference or "").strip()
    if not raw.startswith("^"):
        return PythonDefinitionResult(locations=(), warnings=())
    builtin_id = raw[1:]
    python_refs = list_public_builtin_callable_python_references()
    py_ref = python_refs.get(builtin_id, "")
    if not py_ref:
        msg = "Unknown builtin callable id: {!r}".format(builtin_id)
        return PythonDefinitionResult(locations=(), warnings=(msg,))

    combined = _dedupe_python_roots([*python_roots, *_scalim_editor_python_roots()])
    return resolve_python_definition(py_ref, python_roots=combined, anchor_path=anchor_path)


def hover_yaml_dsl_builtin_callable_reference(
    reference: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]] = None,
) -> YamlDslSugarHoverResult:
    """返回 builtin callable 的 hover 文本(静态)."""
    warnings: List[str] = []
    raw = str(reference or "").strip()
    if not raw.startswith("^"):
        return YamlDslSugarHoverResult(text="", warnings=())
    builtin_id = raw[1:]

    python_refs = list_public_builtin_callable_python_references()
    py_ref = python_refs.get(builtin_id, "")
    if not py_ref:
        warnings.append("Unknown builtin callable id: {!r}".format(builtin_id))

    lines: List[str] = ["builtin: ^{}".format(builtin_id)]
    if py_ref:
        lines.append("python: {}".format(py_ref))

        combined = _dedupe_python_roots([*python_roots, *_scalim_editor_python_roots()])
        doc = hover_python_reference(py_ref, python_roots=combined, anchor_path=anchor_path)
        if doc.warnings:
            warnings.extend(list(doc.warnings))
        doc_text = str(doc.text or "").strip()
        if doc_text:
            lines.append("")
            lines.append(doc_text)

    return YamlDslSugarHoverResult(text="\n".join(lines).strip(), warnings=tuple(warnings))


_IMPORT_ALIAS_TOKEN_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_]*)")


def _split_import_path_alias_token(prefix: str) -> Tuple[str, str, str]:
    """拆分 `@/x` / `ALIAS:/x` 的 token.

    返回 `(alias, token, remainder)`; 不匹配返回空元组。
    """
    value = str(prefix or "")
    if value.startswith("@/"):
        return "@", "@/", value[2:]

    if ":/" not in value:
        return "", "", ""
    head, _sep, tail = value.partition(":/")
    if not head:
        return "", "", ""
    if _IMPORT_ALIAS_TOKEN_RE.fullmatch(head) is None:
        return "", "", ""
    return head, "{}:/".format(head), tail


def _iter_yaml_files_in_dir(dir_path: Path, *, name_prefix: str) -> Iterable[Path]:
    try:
        items = list(dir_path.iterdir())
    except Exception:  # noqa: BLE001
        return ()
    for item in items:
        if not item.is_file():
            continue
        if item.suffix not in (".yaml", ".yml"):
            continue
        if name_prefix and not item.name.startswith(name_prefix):
            continue
        yield item


def _is_within_any_dir(path: Path, roots: Sequence[Path]) -> bool:
    resolved = path.resolve(strict=False)
    for root in roots:
        try:
            _ = resolved.relative_to(root.resolve(strict=False))
        except ValueError:
            continue
        return True
    return False


def _complete_yaml_files_under_dir(
    raw_prefix: str,
    *,
    base_dir: Path,
    token_prefix: str,
    allowed_roots: Sequence[Path],
    warnings: List[str],
) -> List["YamlDslSugarCompletionItem"]:
    dir_part, _sep, name_part = str(raw_prefix or "").rpartition("/")
    search_dir = base_dir / dir_part if dir_part else base_dir
    if not search_dir.exists() or not search_dir.is_dir():
        return []
    if not _is_within_any_dir(search_dir, allowed_roots):
        warnings.append("Import path completion rejected (escapes allowed roots): {}".format(str(search_dir)))
        return []

    items: List[YamlDslSugarCompletionItem] = []
    for f in _iter_yaml_files_in_dir(search_dir, name_prefix=name_part):
        rel = f.relative_to(base_dir).as_posix()
        insert_text = "{}{}".format(token_prefix, rel) if token_prefix else rel
        items.append(YamlDslSugarCompletionItem(label=rel, insert_text=insert_text, detail=str(f)))
    return items


def _complete_yaml_dsl_import_path_alias_tokens(
    raw_prefix: str, *, project_config: Optional[YamlDslProjectConfig]
) -> List["YamlDslSugarCompletionItem"]:
    if project_config is None:
        return []
    prefix = str(raw_prefix or "")
    items: List[YamlDslSugarCompletionItem] = []
    for alias in sorted(project_config.import_aliases):
        token = "{}{}".format(alias, "/") if alias.startswith("@") else "{}{}".format(alias, ":/")
        if prefix and not token.startswith(prefix):
            continue
        items.append(YamlDslSugarCompletionItem(label=token, insert_text=token, detail="import root alias"))
    return items


def _complete_yaml_dsl_import_path_starters(raw_prefix: str) -> List["YamlDslSugarCompletionItem"]:
    prefix = str(raw_prefix or "")
    out: List[YamlDslSugarCompletionItem] = []
    for token in ("./", "../"):
        if prefix and not token.startswith(prefix):
            continue
        out.append(YamlDslSugarCompletionItem(label=token, insert_text=token, detail="relative path"))
    return out


def _complete_yaml_dsl_import_path_files(
    raw_prefix: str,
    *,
    anchor_dir: Path,
    allowed_roots: Sequence[Path],
    project_config: Optional[YamlDslProjectConfig],
    warnings: List[str],
) -> List["YamlDslSugarCompletionItem"]:
    alias, token, remainder = _split_import_path_alias_token(raw_prefix)
    if alias and project_config is not None:
        base_dir = project_config.import_aliases.get(alias)
        if base_dir is None:
            warnings.append("Unknown import root alias: {!r}".format(alias))
            return []
        return _complete_yaml_files_under_dir(
            remainder,
            base_dir=base_dir,
            token_prefix=token,
            allowed_roots=allowed_roots,
            warnings=warnings,
        )

    return _complete_yaml_files_under_dir(
        raw_prefix,
        base_dir=anchor_dir,
        token_prefix="",
        allowed_roots=allowed_roots,
        warnings=warnings,
    )


def _dedupe_sugar_completion_items(items: Sequence["YamlDslSugarCompletionItem"]) -> Tuple["YamlDslSugarCompletionItem", ...]:
    # Keep output stable.
    unique: Dict[Tuple[str, str], None] = {}
    deduped: List[YamlDslSugarCompletionItem] = []
    for item in items:
        key = (str(item.label), str(item.insert_text))
        if key in unique:
            continue
        unique[key] = None
        deduped.append(item)
    return tuple(deduped)


def complete_yaml_dsl_import_path_reference(
    prefix: str,
    *,
    anchor_yaml_path: Union[str, Path],
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> YamlDslSugarCompletionResult:
    """为 `imports.*` 的 path 值提供 completion(别名前缀 + 相对路径)."""
    warnings: List[str] = []
    raw_prefix = str(prefix or "")

    anchor_path = Path(str(anchor_yaml_path)).expanduser().resolve(strict=False)
    project_config = _safe_load_yaml_dsl_project_config(
        anchor_path,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
        warnings=warnings,
    )

    roots = _compute_allowed_yaml_roots_for_imports(
        base_dir=anchor_path.parent,
        discovery_allowed_roots=allowed_yaml_roots,
        project_config=project_config,
        warnings=warnings,
    )
    items = [
        *_complete_yaml_dsl_import_path_starters(raw_prefix),
        *_complete_yaml_dsl_import_path_alias_tokens(raw_prefix, project_config=project_config),
        *_complete_yaml_dsl_import_path_files(
            raw_prefix,
            anchor_dir=anchor_path.parent,
            allowed_roots=roots,
            project_config=project_config,
            warnings=warnings,
        ),
    ]
    return YamlDslSugarCompletionResult(items=_dedupe_sugar_completion_items(items), warnings=tuple(warnings))


def resolve_yaml_dsl_import_path_definition(
    extraction: YamlCursorExtractionResult,
    *,
    anchor_yaml_path: Union[str, Path],
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> YamlDslImportPathDefinitionResult:
    """解析 `imports.*` 的 path 值,返回 file 或 preset 信息."""
    warnings: List[str] = []
    raw_path = str(extraction.reference or "").strip()
    if not raw_path:
        return YamlDslImportPathDefinitionResult(kind="", warnings=("引用不能为空",))

    if raw_path.startswith(_IMPORT_SCALIM_SCHEME_PREFIX):
        preset_id = ""
        try:
            preset_id = _parse_scalim_preset_uri(raw_path)
            _ = load_scalim_preset_yaml_text(preset_id)
        except Exception as exc:  # noqa: BLE001
            warnings.append("invalid preset: {}: {}".format(type(exc).__name__, exc))
        return YamlDslImportPathDefinitionResult(kind="preset", preset_id=preset_id, warnings=tuple(warnings))

    anchor_path = Path(str(anchor_yaml_path)).expanduser().resolve(strict=False)
    project_config = _safe_load_yaml_dsl_project_config(
        anchor_path,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
        warnings=warnings,
    )

    resolved = _resolve_import_source_file(
        alias=str(extraction.yaml_path or "imports"),
        raw_path=raw_path,
        base_dir=anchor_path.parent,
        allowed_yaml_roots=allowed_yaml_roots,
        project_config=project_config,
        warnings=warnings,
    )
    if resolved is None or resolved.path is None:
        return YamlDslImportPathDefinitionResult(kind="", warnings=tuple(warnings))

    return YamlDslImportPathDefinitionResult(kind="file", file_path=str(resolved.path), warnings=tuple(warnings))


def hover_yaml_dsl_import_path_reference(
    extraction: YamlCursorExtractionResult,
    *,
    anchor_yaml_path: Union[str, Path],
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> YamlDslSugarHoverResult:
    """返回 `imports.*` path 的 hover 文本."""
    warnings: List[str] = []
    raw_path = str(extraction.reference or "").strip()
    if not raw_path:
        return YamlDslSugarHoverResult(text="", warnings=("引用不能为空",))

    title = str(extraction.yaml_path or "imports").strip() or "imports"
    lines: List[str] = ["{}: {}".format(title, raw_path)]

    definition = resolve_yaml_dsl_import_path_definition(
        extraction,
        anchor_yaml_path=anchor_yaml_path,
        allowed_yaml_roots=allowed_yaml_roots,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
    )
    if definition.warnings:
        warnings.extend(list(definition.warnings))

    if definition.kind == "file" and definition.file_path:
        lines.append("resolved: {}".format(definition.file_path))
        lines.append("allowed_roots: ok")
    elif definition.kind == "preset" and definition.preset_id:
        lines.append("preset_id: {}".format(definition.preset_id))
        lines.append("readonly: true")
    else:
        lines.append("allowed_roots: unknown")

    return YamlDslSugarHoverResult(text="\n".join(lines).strip(), warnings=tuple(warnings))


def resolve_yaml_import_definition(
    reference: str,
    *,
    anchor_yaml_text: str,
    anchor_yaml_path: Union[str, Path],
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> YamlImportDefinitionResult:
    """静态解析 `$import` 引用并返回 fragment key 的定义位置(不执行用户代码)."""
    warnings: List[str] = []
    locations: Tuple[YamlImportDefinitionLocation, ...] = ()
    raw_ref = str(reference or "").strip()
    if not raw_ref:
        return YamlImportDefinitionResult(locations=(), warnings=("引用不能为空",))

    parsed_ref = _parse_yaml_import_ref(raw_ref, warnings=warnings)
    if parsed_ref is not None:
        alias, segments = parsed_ref

        anchor_path = Path(str(anchor_yaml_path)).expanduser().resolve(strict=False)
        project_config = _safe_load_yaml_dsl_project_config(
            anchor_path,
            scalim_yaml_override=scalim_yaml_override,
            project_root_override=project_root_override,
            warnings=warnings,
        )

        imports = _extract_imports_mapping(anchor_yaml_text, warnings=warnings)
        raw_import_path = imports.get(alias)
        if raw_import_path is None:
            warnings.append("Unknown $import alias: '{}' (missing top-level imports.{})".format(alias, alias))
        else:
            resolved_source = _resolve_import_source(
                alias=alias,
                raw_import_path=raw_import_path,
                base_dir=anchor_path.parent,
                allowed_yaml_roots=allowed_yaml_roots,
                project_config=project_config,
                warnings=warnings,
            )
            if resolved_source is None:
                pass
            elif resolved_source.kind != "file" or resolved_source.path is None:
                warnings.append("imports.{} is not a local file path; go-to-definition is not supported".format(alias))
            else:
                fragment_loc = _locate_fragment_key_location(
                    resolved_source.path,
                    segments=segments,
                    ref=raw_ref,
                    warnings=warnings,
                )
                if fragment_loc is not None:
                    locations = (fragment_loc,)

    return YamlImportDefinitionResult(locations=locations, warnings=tuple(warnings))


def hover_yaml_import_reference(
    reference: str,
    *,
    anchor_yaml_text: str,
    anchor_yaml_path: Union[str, Path],
    allowed_yaml_roots: Sequence[Path],
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> YamlImportHoverResult:
    """返回 `$import` 引用的 hover 文本(若可解析)."""
    warnings: List[str] = []
    text = ""
    raw_ref = str(reference or "").strip()
    if not raw_ref:
        return YamlImportHoverResult(text="", warnings=("引用不能为空",))

    parsed_ref = _parse_yaml_import_ref(raw_ref, warnings=warnings)
    if parsed_ref is not None:
        alias, segments = parsed_ref

        anchor_path = Path(str(anchor_yaml_path)).expanduser().resolve(strict=False)
        project_config = _safe_load_yaml_dsl_project_config(
            anchor_path,
            scalim_yaml_override=scalim_yaml_override,
            project_root_override=project_root_override,
            warnings=warnings,
        )

        imports = _extract_imports_mapping(anchor_yaml_text, warnings=warnings)
        raw_import_path = imports.get(alias)
        if raw_import_path is None:
            warnings.append("Unknown $import alias: '{}' (missing top-level imports.{})".format(alias, alias))
        else:
            resolved_source = _resolve_import_source(
                alias=alias,
                raw_import_path=raw_import_path,
                base_dir=anchor_path.parent,
                allowed_yaml_roots=allowed_yaml_roots,
                project_config=project_config,
                warnings=warnings,
            )

            if resolved_source is None:
                pass
            elif resolved_source.kind != "file" or resolved_source.path is None:
                warnings.append("imports.{} is not a local file path; hover is not supported".format(alias))
            elif _is_fragment_mapping_resolvable(resolved_source.path, segments=segments, ref=raw_ref, warnings=warnings):
                fragment_path = ".".join(segments) if segments else "(root)"
                text = "\n".join(
                    [
                        "$import {}".format(raw_ref),
                        "imports.{}: {}".format(alias, raw_import_path),
                        "resolved: {}".format(str(resolved_source.path)),
                        "fragment: {}".format(fragment_path),
                    ]
                )

    return YamlImportHoverResult(text=text, warnings=tuple(warnings))


@dataclass(frozen=True)
class _ResolvedImportSource:
    kind: str
    key: str
    path: Optional[Path] = None
    preset_id: Optional[str] = None


def _safe_load_yaml_dsl_project_config(
    anchor_path: Path,
    *,
    scalim_yaml_override: Optional[Union[str, Path]],
    project_root_override: Optional[Union[str, Path]],
    warnings: List[str],
) -> Optional[YamlDslProjectConfig]:
    try:
        return load_yaml_dsl_project_config(
            anchor_path,
            scalim_yaml_override=scalim_yaml_override,
            project_root_override=project_root_override,
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append("加载 scalim.yaml 失败: {}: {}".format(type(exc).__name__, exc))
        return None


def _parse_yaml_import_ref(raw_ref: str, *, warnings: List[str]) -> Optional[Tuple[str, List[str]]]:
    ref = str(raw_ref or "").strip()
    if not ref:
        warnings.append("$import ref 不能为空")
        return None
    parts = ref.split(".")
    alias = parts[0]
    if not _IMPORT_REF_SEGMENT_RE.match(alias):
        warnings.append("Invalid $import alias: '{}'".format(alias))
        return None
    segments: List[str] = []
    for seg in parts[1:]:
        if not _IMPORT_REF_SEGMENT_RE.match(seg):
            warnings.append("Invalid $import path segment: '{}'".format(seg))
            return None
        segments.append(seg)
    return alias, segments


def _extract_imports_mapping(yaml_text: str, *, warnings: List[str]) -> Dict[str, str]:
    try:
        loaded, _locations, _lines = load_yaml_mapping_text(yaml_text, source_path="(in-memory)", detect_duplicate_keys=False)
    except ScalimYamlValidationError as exc:
        msg = exc.errors[0].message if exc.errors else str(exc)
        warnings.append("解析 YAML imports 失败: {}".format(msg))
        return {}
    except Exception as exc:  # noqa: BLE001
        warnings.append("解析 YAML imports 失败: {}: {}".format(type(exc).__name__, exc))
        return {}

    raw_imports = loaded.get(_IMPORTS_KEY)
    if raw_imports is None:
        return {}
    if not isinstance(raw_imports, dict):
        warnings.append("imports 必须是 mapping")
        return {}

    out: Dict[str, str] = {}
    for key, value in cast("Dict[Any, Any]", raw_imports).items():  # pragma: allow-cast yaml mapping typed narrowing
        if not isinstance(key, str):
            continue
        stripped_key = key.strip()
        if not stripped_key:
            continue
        if not isinstance(value, str):
            continue
        stripped_value = value.strip()
        if not stripped_value:
            continue
        out[stripped_key] = stripped_value
    return out


def _compute_allowed_yaml_roots_for_imports(
    *,
    base_dir: Path,
    discovery_allowed_roots: Sequence[Path],
    project_config: Optional[YamlDslProjectConfig],
    warnings: List[str],
) -> Tuple[Path, ...]:
    extras: List[Path] = list(discovery_allowed_roots)
    if project_config is not None:
        extras.extend([item.path for item in project_config.import_roots])
    try:
        return normalize_allowed_yaml_roots(extras, default_root=base_dir)
    except Exception as exc:  # noqa: BLE001
        warnings.append("allowed_yaml_roots 归一化失败: {}: {}".format(type(exc).__name__, exc))
        return normalize_allowed_yaml_roots(None, default_root=base_dir)


def _apply_import_aliases(raw_path: str, *, project_config: Optional[YamlDslProjectConfig]) -> Optional[Tuple[str, Path]]:
    if project_config is None:
        return None
    aliases = dict(project_config.import_aliases)
    if not aliases:
        return None

    value = str(raw_path or "")
    matches: List[Tuple[int, str, Path]] = []
    for alias, dir_path in aliases.items():
        alias_text = str(alias or "").strip()
        if not alias_text:
            continue
        if alias_text.startswith("@"):
            token = "{}{}".format(alias_text, "/")
        else:
            token = "{}{}".format(alias_text, ":/")
        if value.startswith(token):
            matches.append((len(token), token, dir_path))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1]))
    _, token, dir_path = matches[0]
    remainder = value[len(token) :].lstrip("/")
    return remainder, dir_path


def _normalize_import_path(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        msg = "imports.* path cannot be empty"
        raise ValueError(msg)
    if _IMPORT_URI_SCHEME_RE.match(value):
        msg = "Imports only supports relative .yaml/.yml file paths; URI schemes are not allowed: '{}'".format(value)
        raise ValueError(msg)
    if value.startswith(("/", "\\")):
        msg = "Imports only supports relative .yaml/.yml file paths; absolute paths are not allowed: '{}'".format(value)
        raise ValueError(msg)
    if _IMPORT_WINDOWS_DRIVE_RE.match(value):
        msg = "Imports only supports relative .yaml/.yml file paths; Windows drive paths are not allowed: '{}'".format(value)
        raise ValueError(msg)
    if value.startswith("@") or _IMPORT_RESERVED_ALIAS_PREFIX_RE.match(value):
        msg = "Imports only supports relative .yaml/.yml file paths; reserved alias prefixes are not allowed: '{}'".format(value)
        raise ValueError(msg)
    if "\\" in value:
        msg = "Imports only supports '/' path separators: '{}'".format(value)
        raise ValueError(msg)
    while value.startswith("./"):
        value = value[2:]
    if not value.endswith((".yaml", ".yml")):
        msg = "Imports only supports .yaml/.yml fragment paths: '{}'".format(raw)
        raise ValueError(msg)
    return value


def _parse_scalim_preset_uri(raw: str) -> str:
    uri = str(raw or "").strip()
    if not uri.startswith(_IMPORT_SCALIM_SCHEME_PREFIX):
        msg = "Expected scalim:// preset URI, got: '{}'".format(uri)
        raise ValueError(msg)
    preset_id = uri[len(_IMPORT_SCALIM_SCHEME_PREFIX) :].lstrip("/")
    if not preset_id:
        msg = "scalim:// preset id cannot be empty"
        raise ValueError(msg)
    return preset_id


def _resolve_import_source(
    *,
    alias: str,
    raw_import_path: str,
    base_dir: Path,
    allowed_yaml_roots: Sequence[Path],
    project_config: Optional[YamlDslProjectConfig],
    warnings: List[str],
) -> Optional[_ResolvedImportSource]:
    raw_path = str(raw_import_path or "").strip()
    if not raw_path:
        warnings.append("imports.{} path cannot be empty".format(alias))
        return None

    if raw_path.startswith(_IMPORT_SCALIM_SCHEME_PREFIX):
        return _resolve_import_source_preset(alias=alias, raw_path=raw_path, warnings=warnings)

    return _resolve_import_source_file(
        alias=alias,
        raw_path=raw_path,
        base_dir=base_dir,
        allowed_yaml_roots=allowed_yaml_roots,
        project_config=project_config,
        warnings=warnings,
    )


def _resolve_import_source_preset(*, alias: str, raw_path: str, warnings: List[str]) -> Optional[_ResolvedImportSource]:
    try:
        preset_id = _parse_scalim_preset_uri(raw_path)
    except Exception as exc:  # noqa: BLE001
        warnings.append("imports.{} invalid preset uri: {}: {}".format(alias, type(exc).__name__, exc))
        return None
    return _ResolvedImportSource(kind="preset", key=raw_path, preset_id=preset_id)


def _resolve_import_source_file(
    *,
    alias: str,
    raw_path: str,
    base_dir: Path,
    allowed_yaml_roots: Sequence[Path],
    project_config: Optional[YamlDslProjectConfig],
    warnings: List[str],
) -> Optional[_ResolvedImportSource]:
    resolve_base_dir = base_dir
    path_for_normalize = raw_path
    rewrite = _apply_import_aliases(raw_path, project_config=project_config)
    if rewrite is not None:
        path_for_normalize, resolve_base_dir = rewrite

    roots = _compute_allowed_yaml_roots_for_imports(
        base_dir=base_dir,
        discovery_allowed_roots=allowed_yaml_roots,
        project_config=project_config,
        warnings=warnings,
    )

    normalized = _try_normalize_import_path(
        alias=alias,
        raw_path=raw_path,
        resolve_base_dir=resolve_base_dir,
        path_for_normalize=path_for_normalize,
        warnings=warnings,
    )
    if normalized is None:
        return None

    resolved_path = (resolve_base_dir / normalized).resolve()

    if not _validate_import_resolved_path(
        alias=alias,
        raw_path=raw_path,
        resolve_base_dir=resolve_base_dir,
        resolved_path=resolved_path,
        allowed_yaml_roots=roots,
        warnings=warnings,
    ):
        return None

    if not resolved_path.exists() or not resolved_path.is_file():
        warnings.append("imports.{} fragment 文件不存在: {}".format(alias, str(resolved_path)))
        return None

    return _ResolvedImportSource(kind="file", key=str(resolved_path), path=resolved_path)


def _try_normalize_import_path(
    *,
    alias: str,
    raw_path: str,
    resolve_base_dir: Path,
    path_for_normalize: str,
    warnings: List[str],
) -> Optional[str]:
    try:
        return _normalize_import_path(path_for_normalize)
    except Exception as exc:  # noqa: BLE001
        resolved = None
        try:
            resolved = (resolve_base_dir / path_for_normalize).resolve()
        except Exception:  # noqa: BLE001
            resolved = None
        warnings.append(
            "imports.{} invalid path: raw='{}' | base_dir='{}' | resolved='{}' | {}: {}".format(
                alias,
                raw_path,
                str(resolve_base_dir),
                str(resolved) if resolved is not None else "(unknown)",
                type(exc).__name__,
                exc,
            )
        )
        return None


def _validate_import_resolved_path(
    *,
    alias: str,
    raw_path: str,
    resolve_base_dir: Path,
    resolved_path: Path,
    allowed_yaml_roots: Sequence[Path],
    warnings: List[str],
) -> bool:
    try:
        validate_resolved_yaml_path_within_roots(
            raw_path=raw_path,
            base_dir=resolve_base_dir,
            resolved_path=resolved_path,
            allowed_yaml_roots=allowed_yaml_roots,
            context_label="imports.{}".format(alias),
        )
    except Exception as exc:  # noqa: BLE001
        warnings.append(str(exc))
        return False

    return True


def _select_mapping_fragment(
    file_data: Dict[str, Any],
    *,
    segments: List[str],
    ref: str,
    warnings: List[str],
) -> Optional[Dict[str, Any]]:
    current: Any = file_data
    for seg in segments:
        if not isinstance(current, dict):
            warnings.append("$import ref '{}' points to a non-mapping value".format(ref))
            return None
        current_dict = cast("Dict[str, Any]", current)  # pragma: allow-cast yaml import fragment typed narrowing
        if seg not in current_dict:
            warnings.append("$import ref '{}' missing key '{}'".format(ref, seg))
            return None
        current = current_dict[seg]
    if not isinstance(current, dict):
        warnings.append("$import ref '{}' points to a non-mapping value".format(ref))
        return None
    return cast("Dict[str, Any]", current)  # pragma: allow-cast yaml import fragment typed narrowing


def _is_fragment_mapping_resolvable(
    fragment_yaml_path: Path,
    *,
    segments: List[str],
    ref: str,
    warnings: List[str],
) -> bool:
    try:
        loaded, _locations, _lines = load_yaml_mapping_cached(fragment_yaml_path)
    except ScalimYamlValidationError as exc:
        msg = exc.errors[0].message if exc.errors else str(exc)
        warnings.append("fragment YAML 解析失败: {}".format(msg))
        return False
    except Exception as exc:  # noqa: BLE001
        warnings.append("fragment YAML 解析失败: {}: {}".format(type(exc).__name__, exc))
        return False

    return _select_mapping_fragment(loaded, segments=segments, ref=ref, warnings=warnings) is not None


def _locate_fragment_key_location(
    fragment_yaml_path: Path,
    *,
    segments: List[str],
    ref: str,
    warnings: List[str],
) -> Optional[YamlImportDefinitionLocation]:
    try:
        loaded, locations, _lines = load_yaml_mapping_cached(fragment_yaml_path)
    except ScalimYamlValidationError as exc:
        msg = exc.errors[0].message if exc.errors else str(exc)
        warnings.append("fragment YAML 解析失败: {}".format(msg))
        return None
    except Exception as exc:  # noqa: BLE001
        warnings.append("fragment YAML 解析失败: {}: {}".format(type(exc).__name__, exc))
        return None

    if _select_mapping_fragment(loaded, segments=segments, ref=ref, warnings=warnings) is None:
        return None

    fragment_path = ".".join(segments)
    if segments:
        loc = locations.get(fragment_path)
        if loc is None:
            warnings.append("$import ref '{}' missing key '{}'".format(ref, segments[-1]))
            return None
        line, column = loc
        end_col = int(column) + max(1, len(str(segments[-1])))
        rng = EditorRange(
            start=EditorPosition(line=int(line), column=int(column)),
            end=EditorPosition(line=int(line), column=int(end_col)),
        )
    else:
        root_loc = locations.get("") or (1, 1)
        line, column = root_loc
        rng = EditorRange(
            start=EditorPosition(line=int(line), column=int(column)),
            end=EditorPosition(line=int(line), column=int(column) + 1),
        )

    return YamlImportDefinitionLocation(
        file_path=str(fragment_yaml_path),
        range=rng,
        fragment_path=fragment_path or "(root)",
    )


def _normalize_python_module_path(
    module_path: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]],
    warnings: List[str],
) -> str:
    raw_module_path = str(module_path or "").strip()
    result = ""
    if not raw_module_path:
        warnings.append("无法解析 module_path")
    elif not raw_module_path.startswith("."):
        result = raw_module_path
    elif anchor_path is None:
        warnings.append("相对模块引用 '{}' 需要 anchor_path 才能解析".format(raw_module_path))
    else:
        roots = _normalize_python_roots(python_roots, default_root=Path().resolve(strict=False))
        base = _derive_base_module_path_from_anchor(anchor_path, roots=roots, warnings=warnings)
        if base is not None:
            dot_count = len(raw_module_path) - len(raw_module_path.lstrip("."))
            rest = raw_module_path[dot_count:]
            base_parts = [p for p in str(base).split(".") if p] if base else []
            up_levels = dot_count - 1
            if up_levels > len(base_parts):
                warnings.append("相对模块引用 '{}' 超出了根包范围(`base_module_path='{}'`)".format(raw_module_path, base))
            else:
                prefix_parts = base_parts[: len(base_parts) - up_levels] if up_levels else base_parts
                rest_parts = [p for p in rest.split(".") if p]
                absolute_parts = prefix_parts + rest_parts
                if not absolute_parts:
                    warnings.append("相对模块引用 '{}' 解析为空模块路径".format(raw_module_path))
                else:
                    result = ".".join(absolute_parts)
    return result


def _derive_base_module_path_from_anchor(
    anchor_path: Union[str, Path],
    *,
    roots: Sequence[Path],
    warnings: List[str],
) -> Optional[str]:
    try:
        yaml_dir = Path(str(anchor_path)).expanduser().resolve(strict=False).parent
    except Exception as exc:  # noqa: BLE001
        warnings.append("无法解析 anchor_path: {}: {}".format(type(exc).__name__, exc))
        return None

    candidates: List[Tuple[Tuple[str, ...], Path]] = []
    yaml_dir_resolved = yaml_dir.resolve(strict=False)
    for root in roots:
        root_resolved = root.resolve(strict=False)
        if yaml_dir_resolved != root_resolved and root_resolved not in yaml_dir_resolved.parents:
            continue

        try:
            rel_path: Optional[Path] = yaml_dir_resolved.relative_to(root_resolved)
        except ValueError:
            rel_path = None
        if rel_path is None:
            continue

        if rel_path == Path():
            candidates.append(((), root_resolved))
            continue

        parts = tuple(p for p in rel_path.parts if p and p != ".")
        if not parts:
            candidates.append(((), root_resolved))
            continue

        if any(not p.isidentifier() for p in parts):
            continue

        candidates.append((parts, root_resolved))

    if not candidates:
        warnings.append(
            "无法推导相对模块引用的 base_module_path: yaml_dir='{}' 不在任何 python_roots 下. ".format(str(yaml_dir))
            + "修复: 补充 `yaml_dsl.lsp.python_roots` 或改用绝对模块引用."
        )
        return None

    parts, _root = min(candidates, key=lambda item: (len(item[0]), -len(item[1].parts), str(item[1])))
    return ".".join(parts)


@dataclass(frozen=True)
class _ModuleBinding:
    kind: str
    node: ast.AST
    import_module: Optional[str] = None
    import_name: Optional[str] = None


@dataclass(frozen=True)
class _ResolvedClassDef:
    module_path: str
    file_path: Path
    node: ast.ClassDef


_P0_IMPL = 0
_P1_BINDING = 1
_P2_FALLBACK = 2


@dataclass(frozen=True)
class _LocationCandidate:
    priority: int
    location: PythonDefinitionLocation
    label: str = ""


def _trace_add_step(
    trace_steps: Optional[List[ResolutionStep]],
    *,
    action: str,
    input_text: str,
    output: str = "",
    rejected: bool = False,
    reason: str = "",
) -> None:
    if trace_steps is None:
        return
    trace_steps.append(
        ResolutionStep(
            action=str(action),
            input=str(input_text),
            output=str(output or ""),
            rejected=bool(rejected),
            reason=str(reason or ""),
        )
    )


def _candidate_from_node(
    *,
    priority: int,
    file_path: str,
    module_path: str,
    symbol_path: str,
    node: ast.AST,
    label: str = "",
) -> _LocationCandidate:
    return _LocationCandidate(
        priority=int(priority),
        location=_definition_location_from_node(
            file_path=file_path,
            module_path=module_path,
            symbol_path=symbol_path,
            node=node,
        ),
        label=str(label or ""),
    )


def _candidate_sort_key(candidate: _LocationCandidate) -> Tuple[int, str, int, int]:
    rng = candidate.location.range
    start_line = int(rng.start.line) if rng is not None else 0
    start_col = int(rng.start.column) if rng is not None else 0
    return (int(candidate.priority), str(candidate.location.file_path), start_line, start_col)


def _location_dedupe_key(location: PythonDefinitionLocation) -> Tuple[Any, ...]:
    rng = location.range
    if rng is None:
        return (str(location.file_path), None, str(location.symbol_path or ""))
    return (
        str(location.file_path),
        int(rng.start.line),
        int(rng.start.column),
        int(rng.end.line),
        int(rng.end.column),
    )


def _finalize_location_candidates(candidates: Sequence[_LocationCandidate]) -> Tuple[PythonDefinitionLocation, ...]:
    out: List[PythonDefinitionLocation] = []
    seen: Set[Tuple[Any, ...]] = set()
    for candidate in sorted(candidates, key=_candidate_sort_key):
        key = _location_dedupe_key(candidate.location)
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate.location)
    return tuple(out)


def _resolve_python_definition_locations(
    parsed: ParsedReference,
    *,
    python_roots: Sequence[Union[str, Path]],
    warnings: List[str],
    trace_steps: Optional[List[ResolutionStep]] = None,
) -> Tuple[PythonDefinitionLocation, ...]:
    roots = _normalize_python_roots(python_roots, default_root=Path().resolve(strict=False))
    candidates = _resolve_locations_for_module_attr_path(
        parsed.module_path,
        parsed.attr_path,
        roots=roots,
        warnings=warnings,
        max_obj_import_hops=1,
        max_class_import_hops=1,
        visited=set(),
        trace_steps=trace_steps,
    )
    return _finalize_location_candidates(candidates)


def _resolve_locations_for_module_attr_path(
    module_path: str,
    attr_path: Tuple[str, ...],
    *,
    roots: Sequence[Path],
    warnings: List[str],
    max_obj_import_hops: int,
    max_class_import_hops: int,
    visited: Set[str],
    trace_steps: Optional[List[ResolutionStep]],
) -> List[_LocationCandidate]:
    if not module_path:
        return []

    if module_path in visited:
        msg = "import 跟随遇到循环依赖: {}".format(module_path)
        warnings.append(msg)
        _trace_add_step(trace_steps, action="follow_import", input_text=module_path, rejected=True, reason=msg)
        return []

    visited.add(module_path)
    try:
        before_warnings = len(warnings)
        file_path = _resolve_module_file_path(module_path, roots=roots, warnings=warnings)
        if file_path is None:
            reason = "; ".join(warnings[before_warnings:]) if len(warnings) > before_warnings else "无法定位模块文件"
            _trace_add_step(trace_steps, action="resolve_module_file", input_text=module_path, rejected=True, reason=reason)
            return []
        _trace_add_step(trace_steps, action="resolve_module_file", input_text=module_path, output=str(file_path))
        tree, tree_warning = _load_module_ast(file_path)
        if tree_warning:
            warnings.append(tree_warning)
        _trace_add_step(
            trace_steps,
            action="load_module_ast",
            input_text=str(file_path),
            output="ok" if tree is not None else "",
            rejected=tree is None,
            reason=str(tree_warning or ""),
        )
        if tree is None:
            return []

        return _resolve_locations_for_attr_path_in_module_tree(
            tree,
            file_path=file_path,
            module_path=module_path,
            attr_path=attr_path,
            roots=roots,
            warnings=warnings,
            max_obj_import_hops=max_obj_import_hops,
            max_class_import_hops=max_class_import_hops,
            visited=visited,
            trace_steps=trace_steps,
        )
    finally:
        visited.remove(module_path)


def _resolve_locations_for_attr_path_in_module_tree(  # noqa: C901,PLR0911,PLR0912,PLR0915
    tree: ast.Module,
    *,
    file_path: Path,
    module_path: str,
    attr_path: Tuple[str, ...],
    roots: Sequence[Path],
    warnings: List[str],
    max_obj_import_hops: int,
    max_class_import_hops: int,
    visited: Set[str],
    trace_steps: Optional[List[ResolutionStep]],
) -> List[_LocationCandidate]:
    if not attr_path:
        return []

    bindings = _index_module_bindings(tree, module_path=module_path, file_path=file_path)
    head = attr_path[0]
    tail = attr_path[1:]
    binding = bindings.get(head)
    if binding is None:
        msg = "无法解析符号定义: {}".format("{}.{}".format(module_path, ".".join(attr_path)))
        warnings.append(msg)
        _trace_add_step(trace_steps, action="resolve_binding", input_text=str(head), rejected=True, reason=msg)
        return []

    if binding.kind in ("def", "class"):
        fallback_priority = _P0_IMPL
    elif binding.kind in ("assign", "ann_assign", "import_from", "import_module"):
        fallback_priority = _P1_BINDING
    else:
        fallback_priority = _P2_FALLBACK

    fallback = _candidate_from_node(
        priority=fallback_priority,
        file_path=str(file_path),
        module_path=module_path,
        symbol_path=head,
        node=binding.node,
        label="fallback",
    )

    if not tail:
        return [fallback]

    if binding.kind == "class":
        node = _find_symbol_in_module(tree, attr_path)
        if node is None:
            msg = "无法解析符号定义: {}".format("{}.{}".format(module_path, ".".join(attr_path)))
            warnings.append(msg)
            _trace_add_step(trace_steps, action="find_attribute", input_text=".".join(attr_path), rejected=True, reason=msg)
            return []
        return [
            _candidate_from_node(
                priority=_P0_IMPL,
                file_path=str(file_path),
                module_path=module_path,
                symbol_path=".".join(attr_path),
                node=node,
                label="impl",
            )
        ]

    if binding.kind in ("assign", "ann_assign"):
        if len(tail) != 1:
            warnings.append("obj.method 解析仅支持单段属性: {}".format(".".join(attr_path)))
            return [fallback]

        resolved_class = _infer_assignment_class_def(
            binding.node,
            bindings=bindings,
            module_path=module_path,
            file_path=file_path,
            roots=roots,
            warnings=warnings,
            max_class_import_hops=max_class_import_hops,
            visited=visited,
        )
        if resolved_class is None:
            msg = "无法静态推断 obj 的 class: {}".format(head)
            warnings.append(msg)
            _trace_add_step(trace_steps, action="infer_assignment_class", input_text=str(head), rejected=True, reason=msg)
            return [fallback]

        method_name = tail[0]
        method_node = _index_class_symbols(resolved_class.node).get(method_name)
        if isinstance(method_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return [
                _candidate_from_node(
                    priority=_P0_IMPL,
                    file_path=str(resolved_class.file_path),
                    module_path=resolved_class.module_path,
                    symbol_path="{}.{}".format(resolved_class.node.name, method_name),
                    node=method_node,
                    label="impl",
                ),
                fallback,
            ]

        warnings.append(
            "在 class '{}' 中未找到方法 '{}' (可能为继承/动态注入): {}".format(resolved_class.node.name, method_name, ".".join(attr_path))
        )
        _trace_add_step(
            trace_steps,
            action="find_method",
            input_text="{}.{}".format(resolved_class.node.name, method_name),
            rejected=True,
            reason="missing method (maybe inheritance/dynamic)",
        )
        return [
            _candidate_from_node(
                priority=_P0_IMPL,
                file_path=str(resolved_class.file_path),
                module_path=resolved_class.module_path,
                symbol_path=str(resolved_class.node.name),
                node=resolved_class.node,
                label="impl",
            ),
            fallback,
        ]

    if binding.kind == "import_from":
        if binding.import_module is None or binding.import_name is None:
            warnings.append("import 解析失败: {}".format(head))
            return [fallback]
        if max_obj_import_hops <= 0:
            warnings.append("import 跟随超出限制(仅允许单跳): {}".format(head))
            return [fallback]

        remote_attr_path = (binding.import_name, *tail)
        remote_locs = _resolve_locations_for_module_attr_path(
            binding.import_module,
            remote_attr_path,
            roots=roots,
            warnings=warnings,
            max_obj_import_hops=max_obj_import_hops - 1,
            max_class_import_hops=max_class_import_hops,
            visited=visited,
            trace_steps=trace_steps,
        )
        if not remote_locs:
            msg = "import 跟随后仍无法解析符号定义: {}".format(head)
            warnings.append(msg)
            _trace_add_step(trace_steps, action="follow_import", input_text=str(head), rejected=True, reason=msg)
            return [fallback]
        return [*remote_locs, fallback]

    if binding.kind == "import_module":
        if binding.import_module is None:
            warnings.append("import 解析失败: {}".format(head))
            return [fallback]
        if max_class_import_hops <= 0:
            warnings.append("import 跟随超出限制: {}".format(head))
            return [fallback]
        remote_locs = _resolve_locations_for_module_attr_path(
            binding.import_module,
            tail,
            roots=roots,
            warnings=warnings,
            max_obj_import_hops=max_obj_import_hops,
            max_class_import_hops=max_class_import_hops - 1,
            visited=visited,
            trace_steps=trace_steps,
        )
        if not remote_locs:
            msg = "import 跟随后仍无法解析符号定义: {}".format(head)
            warnings.append(msg)
            _trace_add_step(trace_steps, action="follow_import", input_text=str(head), rejected=True, reason=msg)
            return [fallback]
        return [*remote_locs, fallback]

    return [fallback]


def _definition_location_from_node(
    *,
    file_path: str,
    module_path: str,
    symbol_path: str,
    node: ast.AST,
) -> PythonDefinitionLocation:
    return PythonDefinitionLocation(
        file_path=str(file_path),
        range=_node_range(node),
        module_path=str(module_path),
        symbol_path=str(symbol_path),
    )


def _resolve_module_file_path(
    module_path: str,
    *,
    roots: Sequence[Path],
    warnings: List[str],
) -> Optional[Path]:
    spec = _find_spec(str(module_path), roots=list(roots))
    origin = None
    if spec is not None:
        origin = spec.origin
    if not isinstance(origin, str) or not origin or origin in ("built-in", "frozen"):
        warnings.append("无法定位模块文件: {}".format(module_path))
        return None

    file_path = Path(origin).expanduser().resolve(strict=False)
    if not file_path.exists() or not file_path.is_file():
        warnings.append("模块文件不存在: {}".format(file_path))
        return None
    return file_path


def _load_module_ast(file_path: Path) -> Tuple[Optional[ast.Module], str]:
    try:
        tree = parse_python_ast_cached(file_path)
    except SyntaxError as exc:
        return None, "模块语法解析失败: {}: {}".format(type(exc).__name__, exc)
    except Exception as exc:  # noqa: BLE001
        return None, "读取模块文件失败: {}: {}".format(type(exc).__name__, exc)
    return tree, ""


def _index_module_bindings(  # noqa: C901,PLR0912
    tree: ast.Module,
    *,
    module_path: str,
    file_path: Path,
) -> Dict[str, _ModuleBinding]:
    out: Dict[str, _ModuleBinding] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[str(node.name)] = _ModuleBinding(kind="def", node=node)
            continue
        if isinstance(node, ast.ClassDef):
            out[str(node.name)] = _ModuleBinding(kind="class", node=node)
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[str(target.id)] = _ModuleBinding(kind="assign", node=node)
            continue
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name):
                out[str(target.id)] = _ModuleBinding(kind="ann_assign", node=node)
            continue
        if isinstance(node, ast.ImportFrom):
            import_module = _resolve_import_from_module_path(module_path, file_path=file_path, node=node)
            if not import_module:
                continue
            for alias in node.names:
                bound_name = alias.asname or alias.name
                out[str(bound_name)] = _ModuleBinding(
                    kind="import_from",
                    node=node,
                    import_module=str(import_module),
                    import_name=str(alias.name),
                )
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                bound_module = alias.name if alias.asname else alias.name.split(".", 1)[0]
                out[str(bound_name)] = _ModuleBinding(
                    kind="import_module",
                    node=node,
                    import_module=str(bound_module),
                )
            continue
    return out


def _resolve_import_from_module_path(
    current_module_path: str,
    *,
    file_path: Path,
    node: ast.ImportFrom,
) -> Optional[str]:
    mod = getattr(node, "module", None)
    level = getattr(node, "level", 0)
    if not isinstance(level, int) or level < 0:
        level = 0
    mod_str = str(mod) if isinstance(mod, str) else ""

    if level == 0:
        return mod_str or None

    parts = [p for p in str(current_module_path or "").split(".") if p]
    is_package = file_path.name == "__init__.py"
    base_parts = parts if is_package else parts[:-1]

    up = level - 1
    if up > len(base_parts):
        return None
    prefix = base_parts[: len(base_parts) - up] if up else base_parts
    if mod_str:
        prefix.extend([p for p in mod_str.split(".") if p])
    return ".".join(prefix) if prefix else None


def _infer_assignment_class_def(
    node: ast.AST,
    *,
    bindings: Dict[str, _ModuleBinding],
    module_path: str,
    file_path: Path,
    roots: Sequence[Path],
    warnings: List[str],
    max_class_import_hops: int,
    visited: Set[str],
) -> Optional[_ResolvedClassDef]:
    annotation_expr: Optional[ast.AST] = None
    value_expr: Optional[ast.AST] = None
    if isinstance(node, ast.AnnAssign):
        annotation_expr = node.annotation
        value_expr = node.value
    elif isinstance(node, ast.Assign):
        value_expr = node.value

    if annotation_expr is not None:
        segments = _expr_to_qualname_segments(annotation_expr)
        if segments:
            resolved = _resolve_class_def_from_qualname(
                segments,
                bindings=bindings,
                module_path=module_path,
                file_path=file_path,
                roots=roots,
                warnings=warnings,
                max_class_import_hops=max_class_import_hops,
                visited=visited,
            )
            if resolved is not None:
                return resolved

    if isinstance(value_expr, ast.Call):
        segments = _expr_to_qualname_segments(value_expr.func)
    else:
        segments = _expr_to_qualname_segments(value_expr) if value_expr is not None else None
    if not segments:
        return None
    return _resolve_class_def_from_qualname(
        segments,
        bindings=bindings,
        module_path=module_path,
        file_path=file_path,
        roots=roots,
        warnings=warnings,
        max_class_import_hops=max_class_import_hops,
        visited=visited,
    )


def _expr_to_qualname_segments(expr: Optional[ast.AST]) -> Optional[Tuple[str, ...]]:
    if expr is None:
        return None
    if isinstance(expr, ast.Name):
        return (str(expr.id),)
    if isinstance(expr, ast.Attribute):
        parts: List[str] = []
        current: Optional[ast.AST] = expr
        while isinstance(current, ast.Attribute):
            parts.append(str(current.attr))
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(str(current.id))
        else:
            return None
        return tuple(reversed(parts))
    return None


def _resolve_class_def_from_qualname(  # noqa: C901,PLR0911
    segments: Tuple[str, ...],
    *,
    bindings: Dict[str, _ModuleBinding],
    module_path: str,
    file_path: Path,
    roots: Sequence[Path],
    warnings: List[str],
    max_class_import_hops: int,
    visited: Set[str],
) -> Optional[_ResolvedClassDef]:
    if not segments:
        return None

    head = segments[0]
    tail = segments[1:]
    binding = bindings.get(head)
    if binding is None:
        return None

    tail_parts = list(tail)
    if not tail_parts:
        if binding.kind == "class" and isinstance(binding.node, ast.ClassDef):
            return _ResolvedClassDef(module_path=module_path, file_path=file_path, node=binding.node)
        if binding.kind == "import_from" and binding.import_module and binding.import_name:
            if max_class_import_hops <= 0:
                return None
            return _resolve_class_def_in_module(
                binding.import_module,
                class_name=binding.import_name,
                roots=roots,
                warnings=warnings,
                max_class_import_hops=max_class_import_hops - 1,
                visited=visited,
            )
        return None

    if binding.kind == "import_module" and binding.import_module:
        if max_class_import_hops <= 0:
            return None
        target_module = binding.import_module
        if len(tail_parts) > 1:
            target_module = "{}.{}".format(target_module, ".".join(tail_parts[:-1]))
        class_name = tail_parts[-1]
        return _resolve_class_def_in_module(
            target_module,
            class_name=class_name,
            roots=roots,
            warnings=warnings,
            max_class_import_hops=max_class_import_hops - 1,
            visited=visited,
        )

    if binding.kind == "import_from" and binding.import_module and binding.import_name:
        if max_class_import_hops <= 0:
            return None
        target_module = "{}.{}".format(binding.import_module, binding.import_name)
        if len(tail_parts) > 1:
            target_module = "{}.{}".format(target_module, ".".join(tail_parts[:-1]))
        class_name = tail_parts[-1]
        return _resolve_class_def_in_module(
            target_module,
            class_name=class_name,
            roots=roots,
            warnings=warnings,
            max_class_import_hops=max_class_import_hops - 1,
            visited=visited,
        )

    return None


def _resolve_class_def_in_module(
    module_path: str,
    *,
    class_name: str,
    roots: Sequence[Path],
    warnings: List[str],
    max_class_import_hops: int,
    visited: Set[str],
) -> Optional[_ResolvedClassDef]:
    _ = max_class_import_hops  # reserved for future recursive extensions
    if module_path in visited:
        return None
    file_path = _resolve_module_file_path(module_path, roots=roots, warnings=warnings)
    if file_path is None:
        return None

    tree, tree_warning = _load_module_ast(file_path)
    if tree_warning:
        warnings.append(tree_warning)
    if tree is None:
        return None

    bindings = _index_module_bindings(tree, module_path=module_path, file_path=file_path)
    binding = bindings.get(str(class_name))
    if binding is None or binding.kind != "class" or not isinstance(binding.node, ast.ClassDef):
        return None
    return _ResolvedClassDef(module_path=str(module_path), file_path=file_path, node=binding.node)


def hover_python_reference(
    reference: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]] = None,
) -> PythonHoverResult:
    """返回 `Python` 引用的 `docstring`(若可解析)."""
    warnings: List[str] = []
    result = resolve_python_definition(reference, python_roots=python_roots, anchor_path=anchor_path)
    if result.warnings:
        warnings.extend(list(result.warnings))
    if not result.locations:
        return PythonHoverResult(text="", warnings=tuple(warnings))

    loc = result.locations[0]
    path = Path(loc.file_path)
    tree, warn = _load_module_ast(path)
    if tree is None:
        warnings.append("hover 解析失败: {}".format(warn or "unknown error"))
        return PythonHoverResult(text="", warnings=tuple(warnings))

    symbol_path = str(loc.symbol_path or "").strip()
    target_attr_path: Tuple[str, ...] = tuple([p for p in symbol_path.split(".") if p]) if symbol_path else ()
    if not target_attr_path:
        return PythonHoverResult(text="", warnings=tuple(warnings))

    node = _find_symbol_in_module(tree, target_attr_path)
    if node is None:
        return PythonHoverResult(text="", warnings=tuple(warnings))

    doc = ast.get_docstring(node) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) else None
    return PythonHoverResult(text=str(doc or ""), warnings=tuple(warnings))


def complete_python_reference(
    reference: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]] = None,
) -> PythonCompletionResult:
    """在 `Python` 引用字符串内提供最小 `completion`."""
    raw = str(reference or "")
    warnings: List[str] = []

    module_path_raw, attr_prefix, style = _split_reference_for_completion(raw)
    if not module_path_raw:
        return PythonCompletionResult(items=(), warnings=("无法解析 module_path",))

    module_path_resolved = _normalize_python_module_path(
        module_path_raw,
        python_roots=python_roots,
        anchor_path=anchor_path,
        warnings=warnings,
    )
    if not module_path_resolved:
        return PythonCompletionResult(items=(), warnings=tuple(warnings))

    roots = _normalize_python_roots(python_roots, default_root=Path().resolve(strict=False))
    spec = _find_spec(module_path_resolved, roots=roots)
    origin = None
    if spec is not None:
        origin = spec.origin
    if not isinstance(origin, str) or not origin or origin in ("built-in", "frozen"):
        warnings.append("无法定位模块文件: {}".format(module_path_resolved))
        return PythonCompletionResult(items=(), warnings=tuple(warnings))

    file_path = Path(origin).expanduser().resolve(strict=False)
    symbols, warn = _list_module_symbols(file_path)
    if warn:
        warnings.append(warn)
    if not symbols:
        return PythonCompletionResult(items=(), warnings=tuple(warnings))

    matched = sorted([name for name in symbols if name.startswith(attr_prefix or "")])
    if style == "class":
        items = tuple(["{}:{}".format(module_path_raw, name) for name in matched])
    else:
        items = tuple(["{}.{}".format(module_path_raw, name) for name in matched])
    return PythonCompletionResult(items=items, warnings=tuple(warnings))


def complete_python_module_segment(
    prefix_module_path: str,
    *,
    segment_prefix: str,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]] = None,
) -> PythonCompletionResult:
    """提供 module path 的 segment 补全.

    例:
    - prefix_module_path="pkg" + segment_prefix="mo" -> ["mod", "more"]
    - prefix_module_path="" + segment_prefix="pkg" -> ["pkg"]
    """
    warnings: List[str] = []
    prefix_raw = str(prefix_module_path or "").strip()
    seg_prefix = str(segment_prefix or "")
    search_locations = _python_module_search_locations(
        prefix_raw,
        python_roots=python_roots,
        anchor_path=anchor_path,
        warnings=warnings,
    )

    names: Dict[str, None] = {}
    for base in search_locations:
        for name in _iter_python_module_child_names(base):
            if name.startswith(seg_prefix):
                names[name] = None

    return PythonCompletionResult(items=tuple(sorted(names)), warnings=tuple(warnings))


def complete_python_attr_path_segment(
    module_path: str,
    *,
    attr_path_prefix: str,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]] = None,
) -> PythonCompletionResult:
    """提供 `module_path + attr_path` 的补全(支持 class 内符号)."""
    raw_module_path = str(module_path or "").strip()
    warnings: List[str] = []
    if not raw_module_path:
        return PythonCompletionResult(items=(), warnings=("无法解析 module_path",))

    parsed = _split_attr_path_prefix(str(attr_path_prefix or ""))
    if parsed is None:
        return PythonCompletionResult(items=(), warnings=tuple(warnings))
    base_parts, seg_prefix = parsed

    tree = _resolve_module_ast(raw_module_path, python_roots=python_roots, anchor_path=anchor_path, warnings=warnings)
    if tree is None:
        return PythonCompletionResult(items=(), warnings=tuple(warnings))

    current_symbols: Dict[str, ast.AST] = _index_module_symbols(tree)
    for part in base_parts:
        node = current_symbols.get(part)
        if node is None:
            return PythonCompletionResult(items=(), warnings=tuple(warnings))
        if not isinstance(node, ast.ClassDef):
            return PythonCompletionResult(items=(), warnings=tuple(warnings))
        current_symbols = _index_class_symbols(node)

    matched = sorted([name for name in current_symbols if name.startswith(seg_prefix)])
    return PythonCompletionResult(items=tuple(matched), warnings=tuple(warnings))


def _safe_path(raw: object) -> Optional[Path]:
    try:
        return Path(str(raw)).expanduser().resolve(strict=False)
    except Exception:  # noqa: BLE001
        return None


def _python_module_search_locations(
    prefix_module_path: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]],
    warnings: List[str],
) -> Tuple[Path, ...]:
    roots = _normalize_python_roots(python_roots, default_root=Path().resolve(strict=False))
    prefix = str(prefix_module_path or "").strip()
    if not prefix:
        return roots

    resolved_prefix = _normalize_python_module_path(
        prefix,
        python_roots=python_roots,
        anchor_path=anchor_path,
        warnings=warnings,
    )
    if not resolved_prefix:
        return ()

    spec = _find_spec(resolved_prefix, roots=roots)
    locs = getattr(spec, "submodule_search_locations", None) if spec is not None else None
    if not locs:
        warnings.append("无法定位模块包路径: {}".format(resolved_prefix))
        return ()

    out: List[Path] = []
    for loc in list(locs):
        p = _safe_path(loc)
        if p is None or not p.exists() or not p.is_dir():
            continue
        out.append(p)
    return tuple(out)


def _looks_like_package_dir(path: Path) -> bool:
    try:
        if (path / "__init__.py").exists():
            return True
    except OSError:
        return False

    try:
        return any(path.glob("*.py")) or any(path.glob("*.pyi"))
    except OSError:
        return False


def _iter_python_module_child_names(base: Path) -> Iterable[str]:
    if not base.exists() or not base.is_dir():
        return ()
    try:
        children = list(base.iterdir())
    except OSError:
        return ()

    for child in children:
        name = str(child.name)
        if not name or name.startswith("."):
            continue

        if child.is_file():
            suffix = str(child.suffix)
            if suffix not in (".py", ".pyi"):
                continue
            stem = str(child.stem)
            if stem and stem != "__init__" and stem.isidentifier():
                yield stem
            continue

        if child.is_dir() and name.isidentifier() and _looks_like_package_dir(child):
            yield name


def _split_attr_path_prefix(prefix_full: str) -> Optional[Tuple[Tuple[str, ...], str]]:
    parts = [p.strip() for p in str(prefix_full or "").split(".")]
    if not parts:
        return ((), "")
    if any(p == "" for p in parts[:-1]):
        return None
    base_parts = tuple([p for p in parts[:-1] if p])
    seg_prefix = str(parts[-1] or "")
    return base_parts, seg_prefix


def _resolve_module_ast(
    raw_module_path: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]],
    warnings: List[str],
) -> Optional[ast.Module]:
    module_path_resolved = _normalize_python_module_path(
        str(raw_module_path or ""),
        python_roots=python_roots,
        anchor_path=anchor_path,
        warnings=warnings,
    )
    if not module_path_resolved:
        return None

    roots = _normalize_python_roots(python_roots, default_root=Path().resolve(strict=False))
    spec = _find_spec(module_path_resolved, roots=roots)
    origin = spec.origin if spec is not None else None
    if not isinstance(origin, str) or not origin or origin in ("built-in", "frozen"):
        warnings.append("无法定位模块文件: {}".format(module_path_resolved))
        return None

    file_path = Path(origin).expanduser().resolve(strict=False)
    if not file_path.exists() or not file_path.is_file():
        warnings.append("模块文件不存在: {}".format(file_path))
        return None

    try:
        text = file_path.read_text(encoding="utf-8")
        return ast.parse(text)
    except Exception as exc:  # noqa: BLE001
        warnings.append("completion 解析失败: {}: {}".format(type(exc).__name__, exc))
        return None


def _normalize_python_roots(
    raw_roots: Optional[Iterable[Union[str, Path]]],
    *,
    default_root: Path,
) -> Tuple[Path, ...]:
    roots: List[Path] = []
    if raw_roots is not None:
        for raw in raw_roots:
            p = Path(str(raw)).expanduser().resolve(strict=False)
            if p.exists() and p.is_dir():
                roots.append(p)

    if not roots:
        roots.append(default_root)

    seen: Dict[str, None] = {}
    unique: List[Path] = []
    for p in roots:
        key = str(p)
        if key in seen:
            continue
        seen[key] = None
        unique.append(p)
    return tuple(unique)


def _infer_default_python_roots(project_root: Path) -> Tuple[Path, ...]:
    roots: List[Path] = []

    src_dir = project_root / "src"
    if src_dir.exists() and src_dir.is_dir():
        roots.append(src_dir)

    packages_dir = project_root / "packages"
    if packages_dir.exists() and packages_dir.is_dir():
        try:
            candidates = sorted(packages_dir.glob("*/src"))
        except Exception:  # noqa: BLE001
            candidates = []
        for candidate in candidates:
            if candidate.exists() and candidate.is_dir():
                roots.append(candidate)

    # Include project_root itself as a fallback sys.path entry:
    # - supports monorepos / ad-hoc modules (e.g. notebooks/)
    roots.append(project_root)

    seen: Dict[str, None] = {}
    unique: List[Path] = []
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen[key] = None
        unique.append(root)
    return tuple(unique)


def _classify_yaml_kind_from_overrides(path: Path, cfg: Optional[YamlDslProjectConfig]) -> str:
    if cfg is None or cfg.lsp is None or not cfg.lsp.kind_overrides:
        return ""
    rel = ""
    try:
        rel = path.resolve(strict=False).relative_to(cfg.project_root).as_posix()
    except Exception:  # noqa: BLE001
        rel = ""
    if not rel:
        return ""
    for item in cfg.lsp.kind_overrides:
        if fnmatch(rel, str(item.glob)):
            return str(item.kind)
    return ""


def _classify_yaml_kind_by_heuristic(yaml_text: str) -> str:
    try:
        loaded = yaml.safe_load(str(yaml_text or ""))
    except Exception:  # noqa: BLE001
        return YAML_DSL_KIND_DEMAND
    if isinstance(loaded, dict):
        wf = cast("Dict[str, Any]", loaded).get("workflow")  # pragma: allow-cast yaml safe_load typed narrowing
        if isinstance(wf, dict):
            return YAML_DSL_KIND_WORKFLOW
    return YAML_DSL_KIND_DEMAND


def _schema_dir() -> Path:
    return Path(yaml_dsl.__file__).resolve().parent / "schema"


def _load_json_schema(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return cast("Dict[str, Any]", json.load(f))  # pragma: allow-cast json schema typed boundary


_SCHEMA_REQUIRED_FILENAMES: Dict[str, str] = {
    YAML_DSL_KIND_DEMAND: "demand.gen.json",
    YAML_DSL_KIND_WORKFLOW: "workflow.gen.json",
}


@lru_cache(maxsize=None)
def _schema_required_keys(kind: str) -> Tuple[str, ...]:
    filename = _SCHEMA_REQUIRED_FILENAMES.get(str(kind))
    if not filename:
        return ()

    try:
        schema = _load_json_schema(_schema_dir() / filename)
    except Exception:  # noqa: BLE001
        return ()

    raw_required = schema.get("required")
    if not isinstance(raw_required, list):
        return ()

    keys: List[str] = []
    seen: Dict[str, None] = {}
    for item in raw_required:
        if not isinstance(item, str):
            continue
        key = item.strip()
        if not key or key in seen:
            continue
        keys.append(key)
        seen[key] = None
    return tuple(keys)


def _classify_yaml_kind_by_required_keys_loaded(loaded: Dict[str, Any]) -> str:
    required_workflow = _schema_required_keys(YAML_DSL_KIND_WORKFLOW)
    if required_workflow and all(key in loaded for key in required_workflow):
        wf = loaded.get("workflow")
        if isinstance(wf, dict):
            return YAML_DSL_KIND_WORKFLOW

    required_demand = _schema_required_keys(YAML_DSL_KIND_DEMAND)
    if required_demand and all(key in loaded for key in required_demand):
        return YAML_DSL_KIND_DEMAND

    return ""


def _classify_yaml_kind_by_required_keys(yaml_text: str) -> str:
    try:
        loaded = yaml.safe_load(str(yaml_text or ""))
    except Exception:  # noqa: BLE001
        return ""
    if isinstance(loaded, dict):
        loaded_dict = cast("Dict[str, Any]", loaded)  # pragma: allow-cast yaml safe_load typed narrowing
        return _classify_yaml_kind_by_required_keys_loaded(loaded_dict)
    return ""


def _collect_demand_diagnostics(
    yaml_text: str,
    *,
    yaml_path: Path,
    allowed_yaml_roots: Sequence[Path],
) -> Tuple[Tuple[EditorDiagnostic, ...], Tuple[EditorDiagnostic, ...]]:
    try:
        yaml_data, locations, _lines = load_yaml_mapping_text(yaml_text, source_path=str(yaml_path), detect_duplicate_keys=True)
    except ScalimYamlValidationError as exc:
        return (
            tuple(_envelopes_to_diagnostics(exc.errors, severity=_SEVERITY_ERROR)),
            tuple(_envelopes_to_diagnostics(exc.warnings, severity=_SEVERITY_WARNING)),
        )

    try:
        if contains_import_syntax(yaml_data):
            _ = expand_imports_inplace(yaml_data, yaml_path=yaml_path, allowed_yaml_roots=allowed_yaml_roots)
    except ScalimYamlImportExpansionError as exc:
        logical_path = str(exc.logical_path or "(root)")
        env = ErrorEnvelope(
            code="yaml_import_expansion_error",
            message=str(exc),
            source_path=str(yaml_path),
            path=logical_path,
            loc=error_loc_for_yaml_path(logical_path, locations),
        )
        return (tuple(_envelopes_to_diagnostics((env,), severity=_SEVERITY_ERROR)), ())

    report = ConfigValidator(schema_path=str(_schema_dir() / "demand.gen.json")).validate_report(
        yaml_data,
        strict_unknown_fields=True,
        enable_jsonschema_validation=True,
    )

    errors: List[EditorDiagnostic] = []
    warnings: List[EditorDiagnostic] = []

    for issue in report.errors():
        env = envelope_from_validation_issue(
            issue,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_error",
        )
        errors.append(_envelope_to_diagnostic(env, severity=_SEVERITY_ERROR))

    for issue in report.warnings():
        env = envelope_from_validation_issue(
            issue,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_validate_warning",
        )
        warnings.append(_envelope_to_diagnostic(env, severity=_SEVERITY_WARNING))

    return tuple(errors), tuple(warnings)


def _collect_workflow_diagnostics(
    yaml_text: str,
    *,
    yaml_path: Path,
) -> Tuple[Tuple[EditorDiagnostic, ...], Tuple[EditorDiagnostic, ...]]:
    try:
        yaml_data, locations, _lines = load_yaml_mapping_text(yaml_text, source_path=str(yaml_path), detect_duplicate_keys=True)
    except ScalimYamlValidationError as exc:
        return (
            tuple(_envelopes_to_diagnostics(exc.errors, severity=_SEVERITY_ERROR)),
            tuple(_envelopes_to_diagnostics(exc.warnings, severity=_SEVERITY_WARNING)),
        )

    schema_path = _schema_dir() / "workflow.gen.json"
    schema = _load_json_schema(schema_path)

    errors: List[EditorDiagnostic] = []
    warnings: List[EditorDiagnostic] = []

    jsonschema_module = import_jsonschema_module()
    if jsonschema_module is None:
        env = ErrorEnvelope(
            code="yaml_schema_validate_warning",
            message="jsonschema 不可用, 已跳过 workflow schema 校验",
            source_path=str(yaml_path),
            path="(schema)",
            loc=ErrorLoc(1, 1),
        )
        warnings.append(_envelope_to_diagnostic(env, severity=_SEVERITY_WARNING))
    else:
        try:
            issues = collect_jsonschema_validation_issues(
                yaml_data,
                schema,
                jsonschema_module=jsonschema_module,
                include_context=False,
                filter_additional_properties=True,
            )
        except ScalimJsonSchemaCollectorError as exc:
            env = ErrorEnvelope(
                code="yaml_schema_validate_warning",
                message=str(exc),
                source_path=str(yaml_path),
                path="(schema)",
                loc=ErrorLoc(1, 1),
            )
            warnings.append(_envelope_to_diagnostic(env, severity=_SEVERITY_WARNING))
            issues = []
        except Exception as exc:  # noqa: BLE001
            env = ErrorEnvelope(
                code="yaml_schema_validate_warning",
                message="Schema validation failed unexpectedly: {}: {}".format(type(exc).__name__, exc),
                source_path=str(yaml_path),
                path="(schema)",
                loc=ErrorLoc(1, 1),
            )
            warnings.append(_envelope_to_diagnostic(env, severity=_SEVERITY_WARNING))
            issues = []

        for issue in issues:
            env = envelope_from_validation_issue(
                issue,
                source_path=str(yaml_path),
                locations=locations,
                default_code="yaml_schema_validate_error",
            )
            errors.append(_envelope_to_diagnostic(env, severity=_SEVERITY_ERROR))

    for unknown in find_unknown_fields(yaml_data, schema):
        issue = ValidationIssue(
            severity=VALIDATION_SEVERITY_ERROR,
            message=unknown.message,
            path=unknown.path,
            suggestions=unknown.suggestions,
        )
        env = envelope_from_validation_issue(
            issue,
            source_path=str(yaml_path),
            locations=locations,
            default_code="yaml_unknown_field",
        )
        errors.append(_envelope_to_diagnostic(env, severity=_SEVERITY_ERROR))

    return tuple(errors), tuple(warnings)


def _envelopes_to_diagnostics(
    envelopes: Sequence[ErrorEnvelope],
    *,
    severity: str,
) -> List[EditorDiagnostic]:
    return [_envelope_to_diagnostic(env, severity=severity) for env in envelopes]


def _envelope_to_diagnostic(env: ErrorEnvelope, *, severity: str) -> EditorDiagnostic:
    rng = None
    if env.loc is not None:
        rng = EditorRange(
            start=EditorPosition(line=int(env.loc.line), column=int(env.loc.column)),
            end=EditorPosition(line=int(env.loc.line), column=int(env.loc.column) + 1),
        )
    return EditorDiagnostic(
        severity=severity,
        message=str(env.message),
        path=str(env.path),
        source_path=str(env.source_path),
        code=str(env.code or ""),
        range=rng,
        suggestions=tuple(env.suggestions),
    )


def import_jsonschema_module() -> Optional[Any]:
    return _jsonschema


def _find_spec(module_path: str, *, roots: Sequence[Path]) -> Optional[Any]:
    roots_str = [str(r) for r in roots]
    spec: Optional[Any] = None
    try:
        parts = [p for p in str(module_path or "").split(".") if p]
        if not parts:
            spec = None
        elif len(parts) == 1:
            spec = PathFinder.find_spec(parts[0], roots_str)
        else:
            prefix = parts[0]
            spec = PathFinder.find_spec(prefix, roots_str)
            for part in parts[1:]:
                if spec is None:
                    break
                search_locations = spec.submodule_search_locations
                if not search_locations:
                    spec = None
                    break
                prefix = "{}.{}".format(prefix, part)
                spec = PathFinder.find_spec(prefix, list(search_locations))
    except Exception:  # noqa: BLE001
        spec = None

    return spec


def _resolve_attr_path_node(file_path: Path, parsed: ParsedReference) -> Tuple[Optional[ast.AST], str]:
    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return None, "读取模块文件失败: {}: {}".format(type(exc).__name__, exc)

    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return None, "模块语法解析失败: {}: {}".format(type(exc).__name__, exc)

    node: Optional[ast.AST] = _find_symbol_in_module(tree, parsed.attr_path)
    return node, ""


def _find_symbol_in_module(tree: ast.Module, attr_path: Tuple[str, ...]) -> Optional[ast.AST]:
    if not attr_path:
        return None

    symbols = _index_module_symbols(tree)
    current = symbols.get(attr_path[0])
    if current is None:
        return None
    if len(attr_path) == 1:
        return current

    for part in attr_path[1:]:
        if not isinstance(current, ast.ClassDef):
            return current
        current = _index_class_symbols(current).get(part)
        if current is None:
            return None
    return current


def _index_module_symbols(tree: ast.Module) -> Dict[str, ast.AST]:
    out: Dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[str(node.name)] = node
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[str(target.id)] = node
            continue
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name):
                out[str(target.id)] = node
    return out


def _index_class_symbols(node: ast.ClassDef) -> Dict[str, ast.AST]:
    out: Dict[str, ast.AST] = {}
    for child in node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[str(child.name)] = child
            continue
        if isinstance(child, ast.Assign):
            for target in child.targets:
                if isinstance(target, ast.Name):
                    out[str(target.id)] = child
            continue
        if isinstance(child, ast.AnnAssign):
            target = child.target
            if isinstance(target, ast.Name):
                out[str(target.id)] = child
    return out


def _node_range(node: ast.AST) -> Optional[EditorRange]:
    node_any = cast("Any", node)  # pragma: allow-cast ast node dynamic position fields
    try:
        lineno = node_any.lineno
        col = node_any.col_offset
    except AttributeError:
        return None
    if not isinstance(lineno, int) or not isinstance(col, int):
        return None
    start = EditorPosition(line=int(lineno), column=int(col) + 1)

    try:
        end_line = node_any.end_lineno
        end_col = node_any.end_col_offset
    except AttributeError:
        end_line = None
        end_col = None
    if isinstance(end_line, int) and isinstance(end_col, int):
        end = EditorPosition(line=int(end_line), column=int(end_col) + 1)
    else:
        end = EditorPosition(line=int(lineno), column=int(col) + 2)
    return EditorRange(start=start, end=end)


def _split_reference_for_completion(reference: str) -> Tuple[str, str, str]:
    raw = str(reference or "").strip()
    if ":" in raw:
        module, attr = raw.split(":", 1)
        return module.strip(), attr.strip(), "class"
    if "." in raw:
        module, attr = raw.rsplit(".", 1)
        return module.strip(), attr.strip(), "dotted"
    return "", "", ""


def _list_module_symbols(file_path: Path) -> Tuple[Tuple[str, ...], str]:
    try:
        tree = parse_python_ast_cached(file_path)
    except Exception as exc:  # noqa: BLE001
        return (), "completion 解析失败: {}: {}".format(type(exc).__name__, exc)
    symbols = _index_module_symbols(tree)
    return tuple(sorted(symbols.keys())), ""


__all__ = (
    "YAML_DSL_KIND_DEMAND",
    "YAML_DSL_KIND_WORKFLOW",
    "EditorDiagnostic",
    "EditorPosition",
    "EditorRange",
    "PythonCompletionResult",
    "PythonDefinitionLocation",
    "PythonDefinitionResult",
    "PythonHoverResult",
    "YamlCursorExtractionResult",
    "YamlDslEditorDiagnosticsResult",
    "YamlDslEditorProjectDiscovery",
    "YamlDslEntityCompletionItem",
    "YamlDslEntityCompletionResult",
    "YamlDslEntityDeclaration",
    "YamlDslEntityDefinitionLocation",
    "YamlDslEntityDefinitionResult",
    "YamlDslEntityHintDiagnostic",
    "YamlDslEntityHoverResult",
    "YamlDslEntityIndex",
    "YamlImportDefinitionLocation",
    "YamlImportDefinitionResult",
    "YamlImportHoverResult",
    "build_yaml_dsl_entity_index",
    "classify_yaml_dsl_kind",
    "collect_yaml_dsl_editor_diagnostics",
    "complete_python_reference",
    "complete_yaml_dsl_entity_reference",
    "discover_yaml_dsl_editor_project",
    "extract_yaml_dsl_entity_reference_by_cursor",
    "extract_yaml_dsl_import_reference_by_cursor",
    "extract_yaml_dsl_python_reference_by_cursor",
    "hover_python_reference",
    "hover_yaml_dsl_entity_reference",
    "hover_yaml_import_reference",
    "resolve_python_definition",
    "resolve_yaml_dsl_entity_definition",
    "resolve_yaml_import_definition",
)
