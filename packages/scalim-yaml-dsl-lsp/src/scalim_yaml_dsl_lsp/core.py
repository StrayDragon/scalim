import ast
import json
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from functools import lru_cache
from importlib.machinery import PathFinder
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union, cast

try:
    import jsonschema as _jsonschema  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover  # pragma: allow-no-cover optional dependency
    _jsonschema = None  # type: ignore[assignment]

from scalim.dsl import by_yaml
from scalim.dsl.by_yaml._internal.config_parsing.allowed_paths import normalize_allowed_yaml_roots
from scalim.dsl.by_yaml._internal.config_parsing.error_envelope import ErrorEnvelope, ErrorLoc, ScalimYamlValidationError
from scalim.dsl.by_yaml._internal.config_parsing.imports import (
    ScalimYamlImportExpansionError,
    contains_import_syntax,
    expand_imports_inplace,
)
from scalim.dsl.by_yaml._internal.config_parsing.jsonschema_issues import (
    ScalimJsonSchemaCollectorError,
    collect_jsonschema_validation_issues,
)
from scalim.dsl.by_yaml._internal.config_parsing.project_config import YamlDslProjectConfig, load_yaml_dsl_project_config
from scalim.dsl.by_yaml._internal.config_parsing.unknown_fields import find_unknown_fields
from scalim.dsl.by_yaml._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml._internal.config_parsing.validators.issues import VALIDATION_SEVERITY_ERROR, ValidationIssue
from scalim.dsl.by_yaml._internal.config_parsing.yaml_load import (
    envelope_from_validation_issue,
    error_loc_for_yaml_path,
    load_yaml_mapping_text,
)
from scalim.dsl.by_yaml.reference_syntax import (
    ParsedReference,
    ScalimReferenceSyntaxError,
    is_valid_builtin_callable_reference,
    parse_python_reference,
)
from scalim.vendor.yamlx import yaml

from .cursor_extraction import YamlCursorExtractionResult, extract_yaml_dsl_python_reference_by_cursor
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
class PythonDefinitionResult:
    locations: Tuple[PythonDefinitionLocation, ...] = ()
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "locations": [loc.as_dict() for loc in self.locations],
        }
        if self.warnings:
            payload["warnings"] = list(self.warnings)
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
        raw_allowed_roots = cfg.import_allowed_roots
        if cfg.editor is not None and cfg.editor.python_roots:
            raw_python_roots = cfg.editor.python_roots
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


def is_probably_yaml_dsl_document(yaml_path: Optional[Union[str, Path]], yaml_text: str) -> bool:
    """Best-effort heuristic to decide whether a YAML file looks like Scalim YAML DSL.

    This is used to avoid polluting unrelated YAML files with scalim diagnostics/features.
    """
    try:
        path = Path(str(yaml_path)).expanduser().resolve(strict=False) if yaml_path is not None else None
    except Exception:  # noqa: BLE001
        path = None

    if path is not None:
        if path.name == _SCALIM_YAML_FILENAME:
            return False
        # Skip ephemeral generated folders by default.
        if ".tmp" in path.parts:
            return False

    text = str(yaml_text or "")
    if not text.strip():
        return False

    if any(marker in text for marker in _YAML_DSL_SCHEMA_MARKERS):
        return True
    if _YAML_DSL_DOLLAR_HINT_RE.search(text) is not None:
        return True
    if _YAML_DSL_FALLBACK_HINT_RE.search(text) is not None:
        return True

    try:
        loaded = yaml.safe_load(text)
    except Exception:  # noqa: BLE001
        return False

    if isinstance(loaded, dict):
        loaded_dict = cast("Dict[str, Any]", loaded)  # pragma: allow-cast yaml safe_load typed narrowing
        required_kind = _classify_yaml_kind_by_required_keys_loaded(loaded_dict)
        if required_kind:
            return True

        # Permissive fallback for in-progress demand drafts that only contain `imports` + `name`.
        imports_obj = loaded_dict.get("imports")
        if isinstance(imports_obj, dict) and "name" in loaded_dict:
            return True

        return False

    return False


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


def resolve_python_definition(
    reference: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]] = None,
) -> PythonDefinitionResult:
    """静态解析 `Python` 引用并返回定义位置(不执行用户代码)."""
    warnings: List[str] = []
    raw = str(reference or "").strip()
    if not raw:
        return PythonDefinitionResult(locations=(), warnings=("引用不能为空",))

    if is_valid_builtin_callable_reference(raw):
        warnings.append("builtin callable 引用不支持 go-to-definition")
        return PythonDefinitionResult(locations=(), warnings=tuple(warnings))

    try:
        parsed = parse_python_reference(raw)
    except ScalimReferenceSyntaxError as exc:
        warnings.append(str(exc))
        return PythonDefinitionResult(locations=(), warnings=tuple(warnings))

    module_path = _normalize_python_module_path(
        parsed.module_path,
        python_roots=python_roots,
        anchor_path=anchor_path,
        warnings=warnings,
    )
    if not module_path:
        return PythonDefinitionResult(locations=(), warnings=tuple(warnings))

    parsed = ParsedReference(
        reference=parsed.reference,
        module_path=module_path,
        attr_path=parsed.attr_path,
        style=parsed.style,
    )

    location = _resolve_python_definition_location(parsed, python_roots=python_roots, warnings=warnings)
    if location is None:
        return PythonDefinitionResult(locations=(), warnings=tuple(warnings))
    return PythonDefinitionResult(locations=(location,), warnings=tuple(warnings))


def _normalize_python_module_path(
    module_path: str,
    *,
    python_roots: Sequence[Union[str, Path]],
    anchor_path: Optional[Union[str, Path]],
    warnings: List[str],
) -> str:
    raw_module_path = str(module_path or "").strip()
    if not raw_module_path:
        warnings.append("无法解析 module_path")
        return ""

    if not raw_module_path.startswith("."):
        return raw_module_path

    if anchor_path is None:
        warnings.append("相对模块引用 '{}' 需要 anchor_path 才能解析".format(raw_module_path))
        return ""

    roots = _normalize_python_roots(python_roots, default_root=Path().resolve(strict=False))
    base = _derive_base_module_path_from_anchor(anchor_path, roots=roots, warnings=warnings)
    if base is None:
        return ""

    dot_count = 0
    for ch in raw_module_path:
        if ch != ".":
            break
        dot_count += 1

    rest = raw_module_path[dot_count:]
    base_parts = [p for p in str(base).split(".") if p] if base else []
    up_levels = dot_count - 1
    if up_levels > len(base_parts):
        warnings.append("相对模块引用 '{}' 超出了根包范围(`base_module_path='{}'`)".format(raw_module_path, base))
        return ""

    prefix_parts = base_parts[: len(base_parts) - up_levels] if up_levels else base_parts
    rest_parts = [p for p in rest.split(".") if p]
    absolute_parts = prefix_parts + rest_parts
    if not absolute_parts:
        warnings.append("相对模块引用 '{}' 解析为空模块路径".format(raw_module_path))
        return ""
    return ".".join(absolute_parts)


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
    for root in roots:
        try:
            if yaml_dir != root and root not in yaml_dir.parents:
                continue
            rel_path = yaml_dir.relative_to(root)
        except Exception:  # noqa: BLE001
            continue

        if rel_path == Path():
            candidates.append(((), root))
            continue

        parts = tuple(p for p in rel_path.parts if p and p != ".")
        if not parts:
            candidates.append(((), root))
            continue

        if any(not p.isidentifier() for p in parts):
            continue

        candidates.append((parts, root))

    if not candidates:
        warnings.append(
            "无法推导相对模块引用的 base_module_path: yaml_dir='{}' 不在任何 python_roots 下. "
            "修复: 补充 `yaml_dsl.editor.python_roots` 或改用绝对模块引用.".format(str(yaml_dir))
        )
        return None

    parts, _root = min(candidates, key=lambda item: (len(item[0]), -len(item[1].parts), str(item[1])))
    return ".".join(parts)


def _resolve_python_definition_location(
    parsed: ParsedReference,
    *,
    python_roots: Sequence[Union[str, Path]],
    warnings: List[str],
) -> Optional[PythonDefinitionLocation]:
    roots = _normalize_python_roots(python_roots, default_root=Path().resolve(strict=False))
    spec = _find_spec(parsed.module_path, roots=roots)
    origin = None
    if spec is not None:
        origin = spec.origin
    if not isinstance(origin, str) or not origin or origin in ("built-in", "frozen"):
        warnings.append("无法定位模块文件: {}".format(parsed.module_path))
        return None

    file_path = Path(origin).expanduser().resolve(strict=False)
    if not file_path.exists() or not file_path.is_file():
        warnings.append("模块文件不存在: {}".format(file_path))
        return None

    node, tree_warning = _resolve_attr_path_node(file_path, parsed)
    if tree_warning:
        warnings.append(tree_warning)
    if node is None:
        warnings.append("无法解析符号定义: {}".format(parsed.reference))
        return None

    return PythonDefinitionLocation(
        file_path=str(file_path),
        range=_node_range(node),
        module_path=str(parsed.module_path),
        symbol_path=".".join(parsed.attr_path),
    )


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
    try:
        path = Path(loc.file_path)
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except Exception as exc:  # noqa: BLE001
        warnings.append("hover 解析失败: {}: {}".format(type(exc).__name__, exc))
        return PythonHoverResult(text="", warnings=tuple(warnings))

    try:
        parsed = parse_python_reference(reference)
    except ScalimReferenceSyntaxError as exc:
        warnings.append(str(exc))
        return PythonHoverResult(text="", warnings=tuple(warnings))

    node = _find_symbol_in_module(tree, parsed.attr_path)
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
            for candidate in sorted(packages_dir.glob("*/src")):
                if candidate.exists() and candidate.is_dir():
                    roots.append(candidate)
        except Exception:  # noqa: BLE001
            pass

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
    if cfg is None or cfg.editor is None or not cfg.editor.kind_overrides:
        return ""
    rel = ""
    try:
        rel = path.resolve(strict=False).relative_to(cfg.project_root).as_posix()
    except Exception:  # noqa: BLE001
        rel = ""
    if not rel:
        return ""
    for item in cfg.editor.kind_overrides:
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
    return Path(by_yaml.__file__).resolve().parent / "schema"


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
        text = file_path.read_text(encoding="utf-8")
        tree = ast.parse(text)
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
    "classify_yaml_dsl_kind",
    "collect_yaml_dsl_editor_diagnostics",
    "complete_python_reference",
    "discover_yaml_dsl_editor_project",
    "extract_yaml_dsl_python_reference_by_cursor",
    "hover_python_reference",
    "resolve_python_definition",
)
