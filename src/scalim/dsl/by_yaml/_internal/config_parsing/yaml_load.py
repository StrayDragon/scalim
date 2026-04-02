# pragma: allow-cast-file yaml parsing boundary typed narrowing
import re
from collections.abc import Hashable
from pathlib import Path
from types import MethodType
from typing import Any, Dict, List, Optional, Tuple, cast

from .....vendor.yamlx.ruamel.yaml import YAML
from ...schema_dsl.constants import UTF8_ENCODING
from .error_envelope import ErrorEnvelope, ErrorLoc, ScalimYamlValidationError
from .validators.issues import ValidationIssue

YamlLocationIndex = Dict[str, Tuple[int, int]]

_BRACKET_INDEX_RE = re.compile(r"\[(\d+)\]")


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


def _normalize_yaml_mapping_key(key: object) -> object:
    if isinstance(key, list):
        return cast("Any", tuple(cast("Any", key)))
    return key


def _raise_yaml_duplicate_key(
    key: object,
    *,
    key_node: object,
    source_path: str,
) -> None:
    mark = getattr(key_node, "start_mark", None)  # pragma: allow-dynattr third-party: ruamel node.start_mark
    line_raw = getattr(mark, "line", None)  # pragma: allow-dynattr third-party: ruamel Mark
    column_raw = getattr(mark, "column", None)  # pragma: allow-dynattr third-party: ruamel Mark
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


def _validate_no_duplicate_yaml_keys(
    pairs: object,
    *,
    constructor: object,
    source_path: str,
) -> None:
    explicit_seen: Dict[object, bool] = {}
    for key_node, _value_node in cast("Any", pairs):
        tag = getattr(key_node, "tag", None)  # pragma: allow-dynattr third-party: ruamel node.tag
        if str(tag) == "tag:yaml.org,2002:merge":
            continue
        key = cast("Any", constructor).construct_object(key_node, deep=True)  # pragma: allow-cast ruamel typed narrowing
        key = _normalize_yaml_mapping_key(key)
        if not isinstance(key, Hashable):
            msg = "found unhashable key"
            raise TypeError(msg)
        if key in explicit_seen:
            _raise_yaml_duplicate_key(key, key_node=key_node, source_path=source_path)
        explicit_seen[key] = True


def _construct_ruamel_mapping(
    constructor: object,
    node: object,
    *,
    deep: bool,
    detect_duplicate_keys: bool,
    source_path: str,
) -> Dict[object, object]:
    node_id = getattr(node, "id", None)  # pragma: allow-dynattr third-party: ruamel node.id
    if str(node_id) != "mapping":
        msg = "expected a mapping node, but found {}".format(str(node_id) if node_id is not None else "(unknown)")
        raise TypeError(msg)

    pairs = cast("Any", node).value  # pragma: allow-cast third-party: ruamel MappingNode.value
    if detect_duplicate_keys:
        _validate_no_duplicate_yaml_keys(pairs, constructor=constructor, source_path=source_path)

    cast("Any", constructor).flatten_mapping(node)  # pragma: allow-cast ruamel constructor typed narrowing

    mapping: Dict[object, object] = cast("Any", constructor).yaml_base_dict_type()  # pragma: allow-cast ruamel typed narrowing
    for key_node, value_node in cast("Any", node).value:
        key = cast("Any", constructor).construct_object(key_node, deep=True)  # pragma: allow-cast ruamel typed narrowing
        key = _normalize_yaml_mapping_key(key)
        value = cast("Any", constructor).construct_object(value_node, deep=deep)  # pragma: allow-cast ruamel typed narrowing
        mapping[key] = value
    return mapping


def _safe_load_yaml_ruamel(text: str, *, source_path: str, detect_duplicate_keys: bool) -> object:
    """统一 `YAML` 解析入口(仓库内置 `ruamel.yaml` 的 `safe loader`, `YAML 1.2` 语义).

    约束:
    - `YAML 1.2` 语义
    - 默认 `detect_duplicate_keys=True` 时,重复键 `fail-fast` 并产出结构化错误(含 `loc`)
    - `detect_duplicate_keys=False` 时,允许重复键且采用 `last-wins` 语义
    - 允许 `merge key`(`<<`) 语义;仅对“显式声明的键”做重复检测(不包含合并展开得到的键)
    """

    yaml_rt = YAML(typ="safe")
    cast("Any", yaml_rt).version = (1, 2)

    def _construct_mapping(self: object, node: object, deep: bool = False) -> Dict[object, object]:  # noqa: FBT001, FBT002
        return _construct_ruamel_mapping(
            self,
            node,
            deep=bool(deep),
            detect_duplicate_keys=bool(detect_duplicate_keys),
            source_path=str(source_path),
        )

    cast("Any", yaml_rt).constructor.construct_mapping = MethodType(  # pragma: allow-cast ruamel typed narrowing
        _construct_mapping,
        cast("Any", yaml_rt).constructor,  # pragma: allow-cast ruamel typed narrowing
    )

    return cast("Any", yaml_rt).load(text)  # pragma: allow-cast ruamel YAML.load typed narrowing


def _safe_load_yaml(text: str, *, source_path: str, detect_duplicate_keys: bool) -> object:
    return _safe_load_yaml_ruamel(text, source_path=source_path, detect_duplicate_keys=bool(detect_duplicate_keys))


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

    node_id = getattr(node, "id", None)  # pragma: allow-dynattr third-party: ruamel node.id
    if str(node_id) == "mapping":
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

    if str(node_id) == "sequence":
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
    yaml_safe = YAML(typ="safe")
    cast("Any", yaml_safe).version = (1, 2)
    return cast("Optional[object]", yaml_safe.compose(yaml_text))  # pragma: allow-cast ruamel compose typed narrowing


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


def normalize_yaml_diagnostic_path(path: str) -> str:
    """归一化用于诊断/定位的 `YAML` 逻辑路径.

    说明: 该函数仅用于 `ValidationIssue.path` / `ErrorEnvelope.path` 等诊断路径与 `YAML` `AST` 位置索引的匹配与展示.

    归一化规则:
    - 去除嵌套诊断使用的前缀 `↳`(例如 `↳ outputs[0]` -> `outputs[0]`)
    - 将根路径标记 `(root)` 映射为 ``(即位置索引的根键)
    - 将数字索引的 `[]` 形态转换为点号段: `foo[0].bar[12]` -> `foo.0.bar.12`

    注意:
    - 仅处理形如 `[0]` 的数字索引段; 其他 `[]` 原样保留.
    - 禁止用于 `DSL` 表达式字符串,例如 `extract: \"[1].x\"`.
    """

    cleaned = str(path or "").strip()
    if not cleaned:
        return ""
    if cleaned.startswith("↳"):
        cleaned = cleaned.lstrip("↳").strip()
    if cleaned == "(root)":
        return ""
    cleaned = _BRACKET_INDEX_RE.sub(r".\1", cleaned)
    return cleaned.lstrip(".")


def lookup_yaml_location(path: str, locations: YamlLocationIndex) -> Optional[Tuple[int, int]]:
    normalized = normalize_yaml_diagnostic_path(path)
    if normalized in locations:
        return locations[normalized]
    if not normalized:
        return locations.get("")
    parts = normalized.split(".")
    while parts:
        _ = parts.pop()
        candidate = ".".join(parts)
        if candidate in locations:
            return locations[candidate]
    return locations.get("")


def error_loc_for_yaml_path(
    path: str,
    locations: YamlLocationIndex,
    *,
    default: Optional[Tuple[int, int]] = (1, 1),
) -> Optional[ErrorLoc]:
    loc_raw = lookup_yaml_location(path, locations)
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
    raw_path = str(issue.path or "(root)")
    normalized = normalize_yaml_diagnostic_path(raw_path)
    path = normalized or "(root)"
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
    except Exception as exc:  # noqa: BLE001
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


__all__ = ()
