import copy
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union, cast

from ....exceptions import ScalimYamlError
from ....vendor.dataclassesx import dataclass
from .allowed_paths import normalize_allowed_yaml_roots, validate_resolved_yaml_path_within_roots
from .presets import load_scalim_preset_yaml_text
from .project_config import YamlDslProjectConfig, load_yaml_dsl_project_config
from .template_precompile import DEFAULT_RENDERED_YAML_MAX_LEN, maybe_precompile_yaml_text
from .yaml_load import load_yaml_mapping_text

IMPORTS_KEY = "imports"
IMPORT_KEY = "$import"

MAX_IMPORT_EXPANSION_DEPTH = 20

_SEGMENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_WINDOWS_DRIVE_RE = re.compile(r"^[a-zA-Z]:")
_RESERVED_ALIAS_PREFIX_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*:/")
_SCALIM_SCHEME_PREFIX = "scalim://"


@dataclass(frozen=True)
class ImportSource:
    kind: str
    key: str
    path: Optional[Path] = None
    preset_id: Optional[str] = None


@dataclass(frozen=True)
class ImportTraceItem:
    source: str
    via: Optional[str] = None


class ScalimYamlImportExpansionError(ScalimYamlError):
    trace: Tuple[ImportTraceItem, ...]
    logical_path: str

    def __init__(
        self,
        message: str,
        *,
        trace: List[ImportTraceItem],
        logical_path: str,
    ) -> None:
        self.trace = tuple(trace)
        self.logical_path = str(logical_path or "")
        super(ScalimYamlImportExpansionError, self).__init__(self._format_message(message))

    def _format_message(self, message: str) -> str:
        parts: List[str] = []
        if self.trace:
            parts.append("import trace: {}".format(_format_trace(self.trace)))
        if self.logical_path:
            parts.append("logical path: {}".format(self.logical_path))
        parts.append(str(message))
        return " | ".join(parts)


def _format_trace(trace: Tuple[ImportTraceItem, ...]) -> str:
    if not trace:
        return ""
    parts: List[str] = [str(trace[0].source)]
    for item in trace[1:]:
        via = str(item.via) if item.via else "import"
        parts.append("--{}--> {}".format(via, item.source))
    return " ".join(parts)


def _normalize_import_path(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        msg = "imports.* path cannot be empty"
        raise ValueError(msg)
    if _URI_SCHEME_RE.match(value):
        msg = "Imports v2 only supports relative .yaml/.yml file paths; URI schemes are not allowed: '{}'".format(value)
        raise ValueError(msg)
    if value.startswith(("/", "\\")):
        msg = "Imports v2 only supports relative .yaml/.yml file paths; absolute paths are not allowed: '{}'".format(value)
        raise ValueError(msg)
    if _WINDOWS_DRIVE_RE.match(value):
        msg = "Imports v2 only supports relative .yaml/.yml file paths; Windows drive paths are not allowed: '{}'".format(value)
        raise ValueError(msg)
    if value.startswith("@") or _RESERVED_ALIAS_PREFIX_RE.match(value):
        msg = "Imports v2 only supports relative .yaml/.yml file paths; reserved alias prefixes are not allowed: '{}'".format(value)
        raise ValueError(msg)
    if "\\" in value:
        msg = "Imports v2 only supports '/' path separators: '{}'".format(value)
        raise ValueError(msg)
    while value.startswith("./"):
        value = value[2:]
    if not value.endswith((".yaml", ".yml")):
        msg = "Imports v2 only supports .yaml/.yml fragment paths: '{}'".format(raw)
        raise ValueError(msg)
    return value


def _parse_scalim_preset_uri(raw: str) -> str:
    uri = str(raw or "").strip()
    if not uri.startswith(_SCALIM_SCHEME_PREFIX):
        msg = "Expected scalim:// preset URI, got: '{}'".format(uri)
        raise ValueError(msg)
    preset_id = uri[len(_SCALIM_SCHEME_PREFIX) :].lstrip("/")
    if not preset_id:
        msg = "scalim:// preset id cannot be empty"
        raise ValueError(msg)
    return preset_id


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


def _parse_import_source(
    alias: str,
    raw_path: str,
    *,
    base_dir: Optional[Path],
    project_config: Optional[YamlDslProjectConfig],
    allowed_yaml_roots: Sequence[Path],
) -> ImportSource:
    if raw_path.startswith(_SCALIM_SCHEME_PREFIX):
        preset_id = _parse_scalim_preset_uri(raw_path)
        return ImportSource(kind="preset", key=str(raw_path), preset_id=preset_id)

    if base_dir is None:
        msg = "imports file paths require base_dir"
        raise ValueError(msg)

    path_for_normalize = raw_path
    resolve_base_dir = base_dir
    rewrite = _apply_import_aliases(raw_path, project_config=project_config)
    if rewrite is not None:
        path_for_normalize, resolve_base_dir = rewrite

    try:
        normalized = _normalize_import_path(path_for_normalize)
    except Exception as exc:
        resolved: Optional[Path] = None
        try:
            resolved = (resolve_base_dir / path_for_normalize).resolve()
        except Exception:  # noqa: BLE001
            resolved = None
        msg = "imports.{} invalid path: raw='{}' | base_dir='{}' | resolved='{}' | {}: {}".format(
            alias,
            raw_path,
            str(resolve_base_dir),
            str(resolved) if resolved is not None else "(unknown)",
            type(exc).__name__,
            exc,
        )
        raise ValueError(msg) from exc

    resolved = (resolve_base_dir / normalized).resolve()
    validate_resolved_yaml_path_within_roots(
        raw_path=raw_path,
        base_dir=resolve_base_dir,
        resolved_path=resolved,
        allowed_yaml_roots=allowed_yaml_roots,
        context_label="imports.{}".format(str(alias)),
    )
    if project_config is not None and project_config.import_allowed_roots:
        validate_resolved_yaml_path_within_roots(
            raw_path=raw_path,
            base_dir=project_config.project_root,
            resolved_path=resolved,
            allowed_yaml_roots=project_config.import_allowed_roots,
            context_label="imports.{}(import_allowed_roots)".format(str(alias)),
        )
    return ImportSource(kind="file", key=str(resolved), path=resolved)


def _parse_imports_mapping(
    raw: Any,
    *,
    base_dir: Optional[Path],
    project_config: Optional[YamlDslProjectConfig],
    allowed_yaml_roots: Sequence[Path],
) -> Dict[str, ImportSource]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        msg = "imports must be a mapping"
        raise TypeError(msg)
    raw_dict = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml imports mapping typed narrowing
    imports: Dict[str, ImportSource] = {}
    for alias, path_raw in raw_dict.items():
        if not isinstance(alias, str) or not alias.strip():
            msg = "imports alias must be a non-empty string"
            raise TypeError(msg)
        if not isinstance(path_raw, str) or not str(path_raw).strip():
            msg = "imports.{} path must be a non-empty string".format(alias)
            raise TypeError(msg)
        raw_path = str(path_raw).strip()
        imports[str(alias)] = _parse_import_source(
            str(alias),
            raw_path,
            base_dir=base_dir,
            project_config=project_config,
            allowed_yaml_roots=allowed_yaml_roots,
        )
    return imports


def _parse_import_ref(raw: str) -> Tuple[str, List[str]]:
    ref = str(raw or "").strip()
    if not ref:
        msg = "$import ref cannot be empty"
        raise ValueError(msg)
    parts = ref.split(".")
    alias = parts[0]
    if not _SEGMENT_RE.match(alias):
        msg = "Invalid $import alias: '{}'".format(alias)
        raise ValueError(msg)
    segments: List[str] = []
    for seg in parts[1:]:
        if not _SEGMENT_RE.match(seg):
            msg = "Invalid $import path segment: '{}'".format(seg)
            raise ValueError(msg)
        segments.append(seg)
    return alias, segments


def _select_mapping_fragment(
    file_data: Dict[str, Any],
    *,
    segments: List[str],
    trace: List[ImportTraceItem],
    logical_path: str,
    ref: str,
) -> Dict[str, Any]:
    current: Any = file_data
    drill_path: List[str] = []
    for seg in segments:
        if not isinstance(current, dict):
            msg = "$import ref '{}' points to a non-mapping value".format(ref)
            raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
        current_dict = cast("Dict[str, Any]", current)  # pragma: allow-cast yaml import fragment typed narrowing
        if seg not in current_dict:
            msg = "$import ref '{}' missing key '{}'".format(ref, seg)
            raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
        drill_path.append(seg)
        current = current_dict[seg]
    if not isinstance(current, dict):
        msg = "$import ref '{}' points to a non-mapping value".format(ref)
        raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
    return cast("Dict[str, Any]", current)  # pragma: allow-cast yaml import fragment typed narrowing


def _deep_merge_override_inplace(
    target: Dict[str, Any],
    source: Dict[str, Any],
    *,
    trace: List[ImportTraceItem],
    logical_path: str,
) -> None:
    for key, value in source.items():
        if key not in target:
            target[key] = value
            continue
        left = target[key]
        right = value
        if isinstance(left, dict) and isinstance(right, dict):
            _deep_merge_override_inplace(
                cast("Dict[str, Any]", left),  # pragma: allow-cast yaml import deep merge typed narrowing
                cast("Dict[str, Any]", right),  # pragma: allow-cast yaml import deep merge typed narrowing
                trace=trace,
                logical_path="{}.{}".format(logical_path, key) if logical_path else str(key),
            )
            continue
        if isinstance(left, list) and isinstance(right, list):
            target[key] = right
            continue
        if isinstance(left, (dict, list)) or isinstance(right, (dict, list)):
            conflict_path = "{}.{}".format(logical_path, key) if logical_path else str(key)
            left_name = "dict" if isinstance(left, dict) else "list" if isinstance(left, list) else type(left).__name__
            right_name = "dict" if isinstance(right, dict) else "list" if isinstance(right, list) else type(right).__name__
            msg = "Type mismatch during import merge at '{}' ({} vs {})".format(
                key,
                left_name,
                right_name,
            )
            raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=conflict_path)
        target[key] = right


def _deep_merge_fill_inplace(
    local: Dict[str, Any],
    imported: Dict[str, Any],
    *,
    trace: List[ImportTraceItem],
    logical_path: str,
) -> None:
    for key, imported_value in imported.items():
        if key not in local:
            local[key] = imported_value
            continue
        local_value = local[key]
        if isinstance(local_value, dict) and isinstance(imported_value, dict):
            _deep_merge_fill_inplace(
                cast("Dict[str, Any]", local_value),  # pragma: allow-cast yaml import deep merge typed narrowing
                cast("Dict[str, Any]", imported_value),  # pragma: allow-cast yaml import deep merge typed narrowing
                trace=trace,
                logical_path="{}.{}".format(logical_path, key) if logical_path else str(key),
            )
            continue
        if isinstance(local_value, list) and isinstance(imported_value, list):
            continue
        if isinstance(local_value, (dict, list)) or isinstance(imported_value, (dict, list)):
            conflict_path = "{}.{}".format(logical_path, key) if logical_path else str(key)
            local_name = (
                "dict" if isinstance(local_value, dict) else "list" if isinstance(local_value, list) else type(local_value).__name__
            )
            imported_name = (
                "dict"
                if isinstance(imported_value, dict)
                else "list"
                if isinstance(imported_value, list)
                else type(imported_value).__name__
            )
            msg = "Type mismatch during import merge at '{}' ({} vs {})".format(
                key,
                local_name,
                imported_name,
            )
            raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=conflict_path)
        continue


def expand_imports_inplace(
    raw: Dict[str, Any],
    *,
    yaml_path: Path,
    cache: Optional[Dict[str, Dict[str, Any]]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Sequence[Union[str, Path]]] = None,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    resolved = yaml_path.resolve()
    if cache is None:
        cache = {}
    project_config = load_yaml_dsl_project_config(
        resolved,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
    )
    roots = _compute_allowed_yaml_roots(
        entry_yaml_path=resolved,
        project_config=project_config,
        allowed_yaml_roots=allowed_yaml_roots,
    )
    trace: List[ImportTraceItem] = [ImportTraceItem(source=str(resolved), via=None)]
    source = ImportSource(kind="file", key=str(resolved), path=resolved)
    return _expand_file_inplace(
        raw,
        source=source,
        cache=cache,
        trace=trace,
        logical_path="",
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=roots,
        project_config=project_config,
    )


def load_and_expand_imports(
    yaml_path: Path,
    *,
    cache: Optional[Dict[str, Dict[str, Any]]] = None,
    template_vars: Optional[Mapping[str, object]] = None,
    template_sandbox: str = "safe",
    rendered_yaml_max_len: int = DEFAULT_RENDERED_YAML_MAX_LEN,
    allowed_yaml_roots: Optional[Sequence[Union[str, Path]]] = None,
    scalim_yaml_override: Optional[Union[str, Path]] = None,
    project_root_override: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    resolved = yaml_path.resolve()
    if cache is None:
        cache = {}
    project_config = load_yaml_dsl_project_config(
        resolved,
        scalim_yaml_override=scalim_yaml_override,
        project_root_override=project_root_override,
    )
    roots = _compute_allowed_yaml_roots(
        entry_yaml_path=resolved,
        project_config=project_config,
        allowed_yaml_roots=allowed_yaml_roots,
    )
    trace: List[ImportTraceItem] = [ImportTraceItem(source=str(resolved), via=None)]
    source = ImportSource(kind="file", key=str(resolved), path=resolved)
    return _load_and_expand_source(
        source,
        cache=cache,
        trace=trace,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=roots,
        project_config=project_config,
    )


def _compute_allowed_yaml_roots(
    *,
    entry_yaml_path: Path,
    project_config: Optional[YamlDslProjectConfig],
    allowed_yaml_roots: Optional[Sequence[Union[str, Path]]],
) -> Tuple[Path, ...]:
    """计算 `imports` 展开所使用的 `allowed_yaml_roots`.

    规则:
    - 若调用方显式提供 `allowed_yaml_roots`,则以调用方为准(并强制包含入口 `YAML` 的目录).
    - 若未显式提供,则允许 `scalim.yaml` 通过 `import_aliases`/`import_allowed_roots` 显式扩展允许范围.
    """
    base_dir = entry_yaml_path.resolve(strict=False).parent
    if allowed_yaml_roots is not None:
        return normalize_allowed_yaml_roots(allowed_yaml_roots, default_root=base_dir)

    extras: List[Path] = []
    if project_config is not None:
        extras = list(project_config.import_aliases.values())
        extras.extend(project_config.import_allowed_roots)
    return normalize_allowed_yaml_roots(extras, default_root=base_dir)


def _load_yaml_mapping(
    yaml_path: Path,
    *,
    template_vars: Optional[Mapping[str, object]],
    template_sandbox: str,
    rendered_yaml_max_len: int,
) -> Dict[str, Any]:
    text = yaml_path.read_text(encoding="utf-8")
    text = maybe_precompile_yaml_text(
        text,
        template_vars=template_vars,
        context_label="导入片段 `YAML` 文件 `{}`".format(str(yaml_path)),
        context_kind="fragment",
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
    )
    loaded, _locations, _lines = load_yaml_mapping_text(
        text,
        source_path=str(yaml_path),
        detect_duplicate_keys=True,
    )
    return loaded


def _load_and_expand_source(
    source: ImportSource,
    *,
    cache: Dict[str, Dict[str, Any]],
    trace: List[ImportTraceItem],
    template_vars: Optional[Mapping[str, object]],
    template_sandbox: str,
    rendered_yaml_max_len: int,
    allowed_yaml_roots: Sequence[Path],
    project_config: Optional[YamlDslProjectConfig],
) -> Dict[str, Any]:
    if any(item.source == source.key for item in trace[:-1]):
        msg = "Import cycle detected"
        raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path="")
    if len(trace) > MAX_IMPORT_EXPANSION_DEPTH:
        msg = "Import expansion exceeded max depth {}".format(MAX_IMPORT_EXPANSION_DEPTH)
        raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path="")
    if source.key in cache:
        return cache[source.key]

    try:
        data = _load_yaml_mapping_from_source(
            source,
            template_vars=template_vars,
            template_sandbox=template_sandbox,
            rendered_yaml_max_len=rendered_yaml_max_len,
        )
    except Exception as exc:
        msg = "Failed to load fragment YAML: {}: {}".format(type(exc).__name__, exc)
        raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path="") from exc
    expanded = _expand_file_inplace(
        data,
        source=source,
        cache=cache,
        trace=trace,
        logical_path="",
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
        project_config=project_config,
    )
    cache[source.key] = expanded
    return expanded


def _load_yaml_mapping_from_source(
    source: ImportSource,
    *,
    template_vars: Optional[Mapping[str, object]],
    template_sandbox: str,
    rendered_yaml_max_len: int,
) -> Dict[str, Any]:
    if source.kind == "file":
        if source.path is None:
            msg = "ImportSource(kind='file') requires path"
            raise ValueError(msg)
        return _load_yaml_mapping(
            source.path,
            template_vars=template_vars,
            template_sandbox=template_sandbox,
            rendered_yaml_max_len=rendered_yaml_max_len,
        )
    if source.kind == "preset":
        if source.preset_id is None:
            msg = "ImportSource(kind='preset') requires preset_id"
            raise ValueError(msg)
        text = load_scalim_preset_yaml_text(source.preset_id)
        text = maybe_precompile_yaml_text(
            text,
            template_vars=template_vars,
            context_label="导入片段 `YAML` preset `{}`".format(source.key),
            context_kind="fragment",
            template_sandbox=template_sandbox,
            rendered_yaml_max_len=rendered_yaml_max_len,
        )
        loaded, _locations, _lines = load_yaml_mapping_text(
            text,
            source_path=str(source.key),
            detect_duplicate_keys=True,
        )
        return loaded
    msg = "Unknown ImportSource.kind: '{}'".format(source.kind)
    raise ValueError(msg)


def _expand_file_inplace(
    raw: Dict[str, Any],
    *,
    source: ImportSource,
    cache: Dict[str, Dict[str, Any]],
    trace: List[ImportTraceItem],
    logical_path: str,
    template_vars: Optional[Mapping[str, object]],
    template_sandbox: str,
    rendered_yaml_max_len: int,
    allowed_yaml_roots: Sequence[Path],
    project_config: Optional[YamlDslProjectConfig],
) -> Dict[str, Any]:
    base_dir = source.path.parent if source.path is not None else None
    try:
        imports = _parse_imports_mapping(
            raw.get(IMPORTS_KEY),
            base_dir=base_dir,
            project_config=project_config,
            allowed_yaml_roots=allowed_yaml_roots,
        )
    except Exception as exc:
        msg = "Invalid imports mapping: {}: {}".format(type(exc).__name__, exc)
        raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=IMPORTS_KEY) from exc
    _ = raw.pop(IMPORTS_KEY, None)

    _expand_node_inplace(
        raw,
        imports=imports,
        cache=cache,
        trace=trace,
        logical_path=logical_path,
        template_vars=template_vars,
        template_sandbox=template_sandbox,
        rendered_yaml_max_len=rendered_yaml_max_len,
        allowed_yaml_roots=allowed_yaml_roots,
        project_config=project_config,
    )
    return raw


def _expand_node_inplace(
    node: Any,
    *,
    imports: Dict[str, ImportSource],
    cache: Dict[str, Dict[str, Any]],
    trace: List[ImportTraceItem],
    logical_path: str,
    template_vars: Optional[Mapping[str, object]],
    template_sandbox: str,
    rendered_yaml_max_len: int,
    allowed_yaml_roots: Sequence[Path],
    project_config: Optional[YamlDslProjectConfig],
) -> None:
    if isinstance(node, dict):
        _expand_mapping_inplace(
            cast("Dict[str, Any]", node),  # pragma: allow-cast yaml import expansion typed narrowing
            imports=imports,
            cache=cache,
            trace=trace,
            logical_path=logical_path,
            template_vars=template_vars,
            template_sandbox=template_sandbox,
            rendered_yaml_max_len=rendered_yaml_max_len,
            allowed_yaml_roots=allowed_yaml_roots,
            project_config=project_config,
        )
        for key, value in list(cast("Dict[str, Any]", node).items()):  # pragma: allow-cast yaml import expansion typed narrowing
            next_path = "{}.{}".format(logical_path, key) if logical_path else str(key)
            _expand_node_inplace(
                value,
                imports=imports,
                cache=cache,
                trace=trace,
                logical_path=next_path,
                template_vars=template_vars,
                template_sandbox=template_sandbox,
                rendered_yaml_max_len=rendered_yaml_max_len,
                allowed_yaml_roots=allowed_yaml_roots,
                project_config=project_config,
            )
        return
    if isinstance(node, list):
        for idx, item in enumerate(cast("List[Any]", node)):  # pragma: allow-cast yaml import expansion typed narrowing
            next_path = "{}.{}".format(logical_path, idx) if logical_path else str(idx)
            _expand_node_inplace(
                item,
                imports=imports,
                cache=cache,
                trace=trace,
                logical_path=next_path,
                template_vars=template_vars,
                template_sandbox=template_sandbox,
                rendered_yaml_max_len=rendered_yaml_max_len,
                allowed_yaml_roots=allowed_yaml_roots,
                project_config=project_config,
            )
        return


def _expand_mapping_inplace(
    mapping: Dict[str, Any],
    *,
    imports: Dict[str, ImportSource],
    cache: Dict[str, Dict[str, Any]],
    trace: List[ImportTraceItem],
    logical_path: str,
    template_vars: Optional[Mapping[str, object]],
    template_sandbox: str,
    rendered_yaml_max_len: int,
    allowed_yaml_roots: Sequence[Path],
    project_config: Optional[YamlDslProjectConfig],
) -> None:
    if IMPORT_KEY not in mapping:
        return

    import_raw = mapping.get(IMPORT_KEY)
    import_refs: List[str] = []
    if isinstance(import_raw, str):
        import_refs = [import_raw]
    elif isinstance(import_raw, list):
        for item in cast("List[Any]", import_raw):  # pragma: allow-cast yaml $import list typed narrowing
            if not isinstance(item, str):
                msg = "$import list entries must be strings"
                raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
            import_refs.append(item)
    else:
        msg = "$import must be a string or list of strings"
        raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=logical_path)

    merged: Dict[str, Any] = {}
    for ref in import_refs:
        try:
            alias, segments = _parse_import_ref(ref)
        except Exception as exc:
            msg = "Invalid $import ref '{}': {}: {}".format(ref, type(exc).__name__, exc)
            raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=logical_path) from exc
        if alias not in imports:
            msg = "Unknown $import alias '{}'".format(alias)
            raise ScalimYamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
        fragment_source = imports[alias]
        next_trace = [*trace, ImportTraceItem(source=fragment_source.key, via="$import {}".format(ref))]
        imported_file = _load_and_expand_source(
            fragment_source,
            cache=cache,
            trace=next_trace,
            template_vars=template_vars,
            template_sandbox=template_sandbox,
            rendered_yaml_max_len=rendered_yaml_max_len,
            allowed_yaml_roots=allowed_yaml_roots,
            project_config=project_config,
        )
        fragment = _select_mapping_fragment(
            imported_file,
            segments=segments,
            trace=next_trace,
            logical_path=logical_path,
            ref=ref,
        )
        fragment_copy = copy.deepcopy(fragment)
        _deep_merge_override_inplace(merged, fragment_copy, trace=next_trace, logical_path=logical_path)

    del mapping[IMPORT_KEY]
    _deep_merge_fill_inplace(mapping, merged, trace=trace, logical_path=logical_path)


def contains_import_syntax(raw: Any) -> bool:
    if isinstance(raw, dict):
        raw_dict = cast("Dict[str, Any]", raw)  # pragma: allow-cast yaml import syntax scan typed narrowing
        if IMPORTS_KEY in raw_dict or IMPORT_KEY in raw_dict:
            return True
        return any(contains_import_syntax(value) for value in raw_dict.values())
    if isinstance(raw, list):
        raw_list = cast("List[Any]", raw)  # pragma: allow-cast yaml import syntax scan typed narrowing
        return any(contains_import_syntax(item) for item in raw_list)
    return False


__all__ = []
