from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, cast

from ....vendor.compact.importlibx import require_optional_dependency
from ..schema_dsl.constants import UTF8_ENCODING
from .error_envelope import ErrorEnvelope, ErrorLoc, ScalimYamlValidationError
from .validators.issues import ValidationIssue

if TYPE_CHECKING:
    import yaml
    from yaml.nodes import MappingNode, SequenceNode
else:
    yaml = require_optional_dependency(
        "yaml",
        context="scalim.dsl.by_yaml.config_parsing.yaml_load",
        install_name="pyyaml",
    )
    _yaml_nodes = require_optional_dependency(
        "yaml.nodes",
        context="scalim.dsl.by_yaml.config_parsing.yaml_load",
        install_name="pyyaml",
    )
    MappingNode = _yaml_nodes.MappingNode
    SequenceNode = _yaml_nodes.SequenceNode


YamlLocationIndex = Dict[str, Tuple[int, int]]


def safe_yaml_parse_error_message(exc: Exception) -> str:
    """构造不回显 YAML 文本正文的 `parse` 错误消息."""
    context = getattr(exc, "context", None)  # pragma: allow-dynattr third-party: pyyaml MarkedYAMLError
    problem = getattr(exc, "problem", None)  # pragma: allow-dynattr third-party: pyyaml MarkedYAMLError

    parts: List[str] = []
    if isinstance(context, str) and context.strip():
        parts.append(context.strip())
    if isinstance(problem, str) and problem.strip() and problem.strip() not in parts:
        parts.append(problem.strip())
    if not parts:
        parts.append(type(exc).__name__)
    return ": ".join(parts)


def _extract_yaml_error_location(exc: Exception) -> Optional[Tuple[int, int]]:
    problem_mark = getattr(exc, "problem_mark", None)  # pragma: allow-dynattr third-party: pyyaml YAMLError mark
    context_mark = getattr(exc, "context_mark", None)  # pragma: allow-dynattr third-party: pyyaml YAMLError mark
    mark = problem_mark or context_mark
    if mark is None:
        return None
    line = getattr(mark, "line", None)  # pragma: allow-dynattr third-party: pyyaml Mark
    column = getattr(mark, "column", None)  # pragma: allow-dynattr third-party: pyyaml Mark
    if not isinstance(line, int) or not isinstance(column, int):
        return None
    return line + 1, column + 1


def _safe_load_yaml_no_duplicates(text: str, *, source_path: str) -> object:
    """对 `yaml.safe_load` 增加重复 `key` 检测(默认启用)."""

    class _Loader(yaml.SafeLoader):  # type: ignore[name-defined]
        pass

    def _construct_mapping(loader: object, node: object, deep: bool = False) -> Dict[object, object]:  # noqa: FBT001, FBT002
        # 说明: `YAML` 合并键(`<<`) 会在 `PyYAML` 的 `construct_mapping` 阶段被展开.
        # 我们希望对“显式声明的键”做重复检测,同时允许合并语义:
        # 1) 扫描显式键是否重复(跳过合并标签键)
        # 2) 委托给 `PyYAML` 做合并展开
        # 3) 采用“后写覆盖前写”的映射构造语义

        explicit_seen: Dict[object, bool] = {}
        pairs = cast("Any", node).value  # pragma: allow-cast pyyaml loader typed narrowing
        for key_node, _value_node in pairs:
            tag = getattr(key_node, "tag", None)  # pragma: allow-dynattr third-party: pyyaml node.tag
            if str(tag) == "tag:yaml.org,2002:merge":
                continue
            key = cast("Any", loader).construct_object(key_node, deep=deep)  # pragma: allow-cast pyyaml loader typed narrowing
            if key in explicit_seen:
                mark = getattr(key_node, "start_mark", None)  # pragma: allow-dynattr third-party: pyyaml node.start_mark
                line_raw = getattr(mark, "line", None)  # pragma: allow-dynattr third-party: pyyaml Mark
                column_raw = getattr(mark, "column", None)  # pragma: allow-dynattr third-party: pyyaml Mark
                loc: Optional[ErrorLoc] = None
                if isinstance(line_raw, int) and isinstance(column_raw, int):
                    loc = ErrorLoc(line=int(line_raw) + 1, column=int(column_raw) + 1)
                error_message = "YAML duplicate key detected"
                raise ScalimYamlValidationError(
                    error_message,
                    errors=[
                        ErrorEnvelope(
                            code="yaml_duplicate_key",
                            message="Duplicate key in YAML mapping: {!r}".format(key),
                            source_path=source_path,
                            path="(root)",
                            loc=loc,
                        )
                    ],
                )
            explicit_seen[key] = True

        cast("Any", loader).flatten_mapping(node)  # pragma: allow-cast pyyaml loader typed narrowing

        mapping: Dict[object, object] = {}
        for key_node, value_node in cast("Any", node).value:  # pragma: allow-cast pyyaml loader typed narrowing
            key = cast("Any", loader).construct_object(key_node, deep=deep)  # pragma: allow-cast pyyaml loader typed narrowing
            value = cast("Any", loader).construct_object(value_node, deep=deep)  # pragma: allow-cast pyyaml loader typed narrowing
            mapping[key] = value
        return mapping

    _Loader.add_constructor(  # type: ignore[attr-defined]
        cast("Any", yaml).resolver.BaseResolver.DEFAULT_MAPPING_TAG,  # pragma: allow-cast pyyaml resolver typed narrowing
        _construct_mapping,
    )
    return cast("Any", yaml).load(text, Loader=_Loader)  # pragma: allow-cast pyyaml loader typed narrowing


def _safe_load_yaml(text: str, *, source_path: str, detect_duplicate_keys: bool) -> object:
    if detect_duplicate_keys:
        return _safe_load_yaml_no_duplicates(text, source_path=source_path)
    return yaml.safe_load(text)


def _record_location(locations: YamlLocationIndex, path: List[str], mark: Any) -> None:
    if mark is None:
        return
    path_key = ".".join(path)
    if path_key in locations:
        return
    locations[path_key] = (mark.line + 1, mark.column + 1)


def _index_yaml_node(
    node: Any,
    path: List[str],
    locations: YamlLocationIndex,
    *,
    record_current: bool = True,
) -> None:
    if node is None:
        return
    if record_current:
        _record_location(locations, path, getattr(node, "start_mark", None))  # pragma: allow-dynattr third-party: pyyaml node.start_mark

    if isinstance(node, MappingNode):
        for key_node, value_node in node.value:
            key = str(getattr(key_node, "value", ""))  # pragma: allow-dynattr third-party: pyyaml node.value
            key_path = [*path, key]
            key_mark = getattr(key_node, "start_mark", None)  # pragma: allow-dynattr third-party: pyyaml node.start_mark
            _record_location(
                locations,
                key_path,
                key_mark,
            )
            _index_yaml_node(value_node, key_path, locations, record_current=False)
        return

    if isinstance(node, SequenceNode):
        for idx, item_node in enumerate(node.value):
            idx_path = [*path, str(idx)]
            item_mark = getattr(item_node, "start_mark", None)  # pragma: allow-dynattr third-party: pyyaml node.start_mark
            _record_location(
                locations,
                idx_path,
                item_mark,
            )
            _index_yaml_node(item_node, idx_path, locations, record_current=False)


def _compose_yaml_node(yaml_text: str) -> Optional[object]:
    return cast(
        "Optional[object]",
        yaml.compose(yaml_text, Loader=yaml.SafeLoader),  # pyright: ignore[reportUnknownMemberType]
    )  # pragma: allow-cast pyyaml compose typed narrowing


def build_yaml_location_index(yaml_text: str) -> YamlLocationIndex:
    try:
        root = _compose_yaml_node(yaml_text)
    except Exception:  # noqa: BLE001
        return {}
    if root is None:
        return {}
    locations: YamlLocationIndex = {}
    _index_yaml_node(root, [], locations, record_current=True)
    return locations


def lookup_yaml_location(path: str, locations: YamlLocationIndex) -> Optional[Tuple[int, int]]:
    if path in locations:
        return locations[path]
    if not path:
        return locations.get("")
    parts = path.split(".")
    while parts:
        _ = parts.pop()
        candidate = ".".join(parts)
        if candidate in locations:
            return locations[candidate]
    return locations.get("")


def _normalize_yaml_path_for_location(path: str) -> str:
    cleaned = str(path or "").strip()
    if cleaned.startswith("↳"):
        cleaned = cleaned.lstrip("↳").strip()
    if cleaned == "(root)":
        return ""
    return cleaned


def error_loc_for_yaml_path(
    path: str,
    locations: YamlLocationIndex,
    *,
    default: Optional[Tuple[int, int]] = (1, 1),
) -> Optional[ErrorLoc]:
    normalized = _normalize_yaml_path_for_location(path)
    loc_raw = lookup_yaml_location(normalized, locations)
    if loc_raw is None:
        if default is None:
            return None
        line, column = default
    else:
        line, column = loc_raw
    return ErrorLoc(line=int(line), column=int(column))


def envelope_from_validation_issue(
    issue: ValidationIssue,
    *,
    source_path: str,
    locations: YamlLocationIndex,
    default_code: str,
) -> ErrorEnvelope:
    path = str(issue.path or "(root)")
    return ErrorEnvelope(
        code=str(issue.code) if issue.code else str(default_code),
        message=str(issue.message),
        source_path=str(source_path),
        path=path,
        loc=error_loc_for_yaml_path(path, locations),
        suggestions=tuple(issue.suggestions),
    )


def load_yaml_mapping_text(
    yaml_text: str,
    *,
    source_path: str,
    detect_duplicate_keys: bool = True,
) -> Tuple[Dict[str, Any], YamlLocationIndex, List[str]]:
    lines: List[str] = yaml_text.splitlines()

    try:
        loaded = _safe_load_yaml(yaml_text, source_path=source_path, detect_duplicate_keys=bool(detect_duplicate_keys))
    except ScalimYamlValidationError:
        raise
    except yaml.YAMLError as exc:
        loc_raw = _extract_yaml_error_location(exc)
        loc = ErrorLoc(*loc_raw) if loc_raw is not None else None
        error_message = "YAML parse error"
        raise ScalimYamlValidationError(
            error_message,
            errors=[
                ErrorEnvelope(
                    code="yaml_parse_error",
                    message="YAML parse error: {}".format(safe_yaml_parse_error_message(exc)),
                    source_path=source_path,
                    path="(root)",
                    loc=loc,
                )
            ],
        ) from None
    except Exception as exc:  # noqa: BLE001
        error_message = "YAML parse error"
        raise ScalimYamlValidationError(
            error_message,
            errors=[
                ErrorEnvelope(
                    code="yaml_parse_error",
                    message="YAML parse error: {}".format(type(exc).__name__),
                    source_path=source_path,
                    path="(root)",
                    loc=None,
                )
            ],
        ) from None

    if loaded is None:
        error_message = "YAML document is empty"
        raise ScalimYamlValidationError(
            error_message,
            errors=[
                ErrorEnvelope(
                    code="yaml_empty_document",
                    message="YAML document is empty",
                    source_path=source_path,
                    path="(root)",
                    loc=ErrorLoc(1, 1),
                )
            ],
        )

    if not isinstance(loaded, dict):
        error_message = "YAML root must be a mapping"
        raise ScalimYamlValidationError(
            error_message,
            errors=[
                ErrorEnvelope(
                    code="yaml_root_not_mapping",
                    message="YAML root must be a mapping",
                    source_path=source_path,
                    path="(root)",
                    loc=ErrorLoc(1, 1),
                )
            ],
        )

    locations = build_yaml_location_index(yaml_text)
    return (
        cast("Dict[str, Any]", loaded),  # pragma: allow-cast yaml.safe_load mapping typed narrowing
        locations,
        lines,
    )


def load_yaml_mapping_file(
    yaml_path: Path,
    *,
    detect_duplicate_keys: bool = True,
) -> Tuple[Dict[str, Any], YamlLocationIndex, List[str]]:
    try:
        yaml_text = yaml_path.read_text(encoding=UTF8_ENCODING)
    except Exception as exc:  # noqa: BLE001
        error_message = "YAML file read error"
        raise ScalimYamlValidationError(
            error_message,
            errors=[
                ErrorEnvelope(
                    code="yaml_file_read_error",
                    message="Failed to read YAML file: {}: {}".format(type(exc).__name__, exc),
                    source_path=str(yaml_path),
                    path="(file)",
                    loc=None,
                )
            ],
        ) from None

    return load_yaml_mapping_text(
        yaml_text,
        source_path=str(yaml_path),
        detect_duplicate_keys=bool(detect_duplicate_keys),
    )


__all__ = [
    "YamlLocationIndex",
    "build_yaml_location_index",
    "envelope_from_validation_issue",
    "error_loc_for_yaml_path",
    "load_yaml_mapping_file",
    "load_yaml_mapping_text",
    "lookup_yaml_location",
    "safe_yaml_parse_error_message",
]
