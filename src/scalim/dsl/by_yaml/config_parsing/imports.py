import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast

from ....vendor.compact.importlibx import require_optional_dependency

if TYPE_CHECKING:
    import yaml
else:
    yaml = require_optional_dependency(
        "yaml",
        context="scalim.dsl.by_yaml.config_parsing.imports",
        install_name="pyyaml",
    )

IMPORTS_KEY = "imports"
IMPORT_KEY = "$import"

MAX_IMPORT_EXPANSION_DEPTH = 20

_SEGMENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


@dataclass(frozen=True)
class ImportTraceItem:
    yaml_path: Path
    via: Optional[str] = None


class YamlImportExpansionError(ValueError):
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
        super(YamlImportExpansionError, self).__init__(self._format_message(message))

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
    parts: List[str] = [str(trace[0].yaml_path)]
    for item in trace[1:]:
        via = str(item.via) if item.via else "import"
        parts.append("--{}--> {}".format(via, item.yaml_path))
    return " ".join(parts)


def _normalize_import_path(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        msg = "imports.* path cannot be empty"
        raise ValueError(msg)
    if ":" in value or value.startswith("@"):
        msg = "V1 only supports same-directory import paths: '{}'".format(value)
        raise ValueError(msg)
    if value.startswith(("/", "\\")):
        msg = "V1 only supports same-directory import paths: '{}'".format(value)
        raise ValueError(msg)
    if value.startswith("./"):
        value = value[2:]
    if value.startswith("../"):
        msg = "V1 only supports same-directory import paths: '{}'".format(raw)
        raise ValueError(msg)
    if "/" in value or "\\" in value:
        msg = "V1 only supports same-directory import paths: '{}'".format(raw)
        raise ValueError(msg)
    if not value.endswith((".yaml", ".yml")):
        msg = "V1 only supports .yaml/.yml fragment paths: '{}'".format(raw)
        raise ValueError(msg)
    return value


def _parse_imports_mapping(raw: Any, *, base_dir: Path) -> Dict[str, Path]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        msg = "imports must be a mapping"
        raise TypeError(msg)
    raw_dict = cast("Dict[str, Any]", raw)
    imports: Dict[str, Path] = {}
    for alias, path_raw in raw_dict.items():
        if not isinstance(alias, str) or not alias.strip():
            msg = "imports alias must be a non-empty string"
            raise TypeError(msg)
        if not isinstance(path_raw, str) or not str(path_raw).strip():
            msg = "imports.{} path must be a non-empty string".format(alias)
            raise TypeError(msg)
        normalized = _normalize_import_path(str(path_raw))
        imports[str(alias)] = (base_dir / normalized).resolve()
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
            raise YamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
        current_dict = cast("Dict[str, Any]", current)
        if seg not in current_dict:
            msg = "$import ref '{}' missing key '{}'".format(ref, seg)
            raise YamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
        drill_path.append(seg)
        current = current_dict[seg]
    if not isinstance(current, dict):
        msg = "$import ref '{}' points to a non-mapping value".format(ref)
        raise YamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
    return cast("Dict[str, Any]", current)


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
                cast("Dict[str, Any]", left),
                cast("Dict[str, Any]", right),
                trace=trace,
                logical_path="{}.{}".format(logical_path, key) if logical_path else str(key),
            )
            continue
        if isinstance(left, list) and isinstance(right, list):
            target[key] = right
            continue
        if isinstance(left, (dict, list)) or isinstance(right, (dict, list)):
            conflict_path = "{}.{}".format(logical_path, key) if logical_path else str(key)
            msg = "Type mismatch during import merge at '{}' ({} vs {})".format(
                key,
                type(cast("object", left)).__name__,
                type(cast("object", right)).__name__,
            )
            raise YamlImportExpansionError(msg, trace=trace, logical_path=conflict_path)
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
                cast("Dict[str, Any]", local_value),
                cast("Dict[str, Any]", imported_value),
                trace=trace,
                logical_path="{}.{}".format(logical_path, key) if logical_path else str(key),
            )
            continue
        if isinstance(local_value, list) and isinstance(imported_value, list):
            continue
        if isinstance(local_value, (dict, list)) or isinstance(imported_value, (dict, list)):
            conflict_path = "{}.{}".format(logical_path, key) if logical_path else str(key)
            msg = "Type mismatch during import merge at '{}' ({} vs {})".format(
                key,
                type(cast("object", local_value)).__name__,
                type(cast("object", imported_value)).__name__,
            )
            raise YamlImportExpansionError(msg, trace=trace, logical_path=conflict_path)
        continue


def expand_imports_inplace(
    raw: Dict[str, Any],
    *,
    yaml_path: Path,
    cache: Optional[Dict[Path, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    resolved = yaml_path.resolve()
    if cache is None:
        cache = {}
    trace: List[ImportTraceItem] = [ImportTraceItem(yaml_path=resolved, via=None)]
    return _expand_file_inplace(raw, yaml_path=resolved, cache=cache, trace=trace)


def load_and_expand_imports(yaml_path: Path, *, cache: Optional[Dict[Path, Dict[str, Any]]] = None) -> Dict[str, Any]:
    resolved = yaml_path.resolve()
    if cache is None:
        cache = {}
    trace: List[ImportTraceItem] = [ImportTraceItem(yaml_path=resolved, via=None)]
    return _load_and_expand_file(resolved, cache=cache, trace=trace)


def _load_yaml_mapping(yaml_path: Path) -> Dict[str, Any]:
    with yaml_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        msg = "YAML config must be a mapping"
        raise TypeError(msg)
    return cast("Dict[str, Any]", loaded)


def _load_and_expand_file(
    yaml_path: Path,
    *,
    cache: Dict[Path, Dict[str, Any]],
    trace: List[ImportTraceItem],
) -> Dict[str, Any]:
    if any(item.yaml_path == yaml_path for item in trace[:-1]):
        msg = "Import cycle detected"
        raise YamlImportExpansionError(msg, trace=trace, logical_path="")
    if len(trace) > MAX_IMPORT_EXPANSION_DEPTH:
        msg = "Import expansion exceeded max depth {}".format(MAX_IMPORT_EXPANSION_DEPTH)
        raise YamlImportExpansionError(msg, trace=trace, logical_path="")
    if yaml_path in cache:
        return cache[yaml_path]

    try:
        data = _load_yaml_mapping(yaml_path)
    except Exception as exc:
        msg = "Failed to load fragment YAML: {}: {}".format(type(exc).__name__, exc)
        raise YamlImportExpansionError(msg, trace=trace, logical_path="") from exc
    expanded = _expand_file_inplace(data, yaml_path=yaml_path, cache=cache, trace=trace)
    cache[yaml_path] = expanded
    return expanded


def _expand_file_inplace(
    raw: Dict[str, Any],
    *,
    yaml_path: Path,
    cache: Dict[Path, Dict[str, Any]],
    trace: List[ImportTraceItem],
) -> Dict[str, Any]:
    base_dir = yaml_path.parent
    try:
        imports = _parse_imports_mapping(raw.get(IMPORTS_KEY), base_dir=base_dir)
    except Exception as exc:
        msg = "Invalid imports mapping: {}: {}".format(type(exc).__name__, exc)
        raise YamlImportExpansionError(msg, trace=trace, logical_path=IMPORTS_KEY) from exc
    _ = raw.pop(IMPORTS_KEY, None)

    _expand_node_inplace(
        raw,
        yaml_path=yaml_path,
        imports=imports,
        cache=cache,
        trace=trace,
        logical_path="",
    )
    return raw


def _expand_node_inplace(
    node: Any,
    *,
    yaml_path: Path,
    imports: Dict[str, Path],
    cache: Dict[Path, Dict[str, Any]],
    trace: List[ImportTraceItem],
    logical_path: str,
) -> None:
    if isinstance(node, dict):
        _expand_mapping_inplace(
            cast("Dict[str, Any]", node),
            imports=imports,
            cache=cache,
            trace=trace,
            logical_path=logical_path,
        )
        for key, value in list(cast("Dict[str, Any]", node).items()):
            next_path = "{}.{}".format(logical_path, key) if logical_path else str(key)
            _expand_node_inplace(
                value,
                yaml_path=yaml_path,
                imports=imports,
                cache=cache,
                trace=trace,
                logical_path=next_path,
            )
        return
    if isinstance(node, list):
        for idx, item in enumerate(cast("List[Any]", node)):
            next_path = "{}.{}".format(logical_path, idx) if logical_path else str(idx)
            _expand_node_inplace(
                item,
                yaml_path=yaml_path,
                imports=imports,
                cache=cache,
                trace=trace,
                logical_path=next_path,
            )
        return


def _expand_mapping_inplace(
    mapping: Dict[str, Any],
    *,
    imports: Dict[str, Path],
    cache: Dict[Path, Dict[str, Any]],
    trace: List[ImportTraceItem],
    logical_path: str,
) -> None:
    if IMPORT_KEY not in mapping:
        return

    import_raw = mapping.get(IMPORT_KEY)
    import_refs: List[str] = []
    if isinstance(import_raw, str):
        import_refs = [import_raw]
    elif isinstance(import_raw, list):
        for item in cast("List[Any]", import_raw):
            if not isinstance(item, str):
                msg = "$import list entries must be strings"
                raise YamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
            import_refs.append(item)
    else:
        msg = "$import must be a string or list of strings"
        raise YamlImportExpansionError(msg, trace=trace, logical_path=logical_path)

    merged: Dict[str, Any] = {}
    for ref in import_refs:
        try:
            alias, segments = _parse_import_ref(ref)
        except Exception as exc:
            msg = "Invalid $import ref '{}': {}: {}".format(ref, type(exc).__name__, exc)
            raise YamlImportExpansionError(msg, trace=trace, logical_path=logical_path) from exc
        if alias not in imports:
            msg = "Unknown $import alias '{}'".format(alias)
            raise YamlImportExpansionError(msg, trace=trace, logical_path=logical_path)
        fragment_path = imports[alias]
        next_trace = [*trace, ImportTraceItem(yaml_path=fragment_path, via="$import {}".format(ref))]
        imported_file = _load_and_expand_file(fragment_path, cache=cache, trace=next_trace)
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
        raw_dict = cast("Dict[str, Any]", raw)
        if IMPORTS_KEY in raw_dict or IMPORT_KEY in raw_dict:
            return True
        return any(contains_import_syntax(value) for value in raw_dict.values())
    if isinstance(raw, list):
        return any(contains_import_syntax(item) for item in cast("List[Any]", raw))
    return False
