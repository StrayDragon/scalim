from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from scalim.vendor.yamlx.ruamel.yaml import YAML

from .editor_types import EditorPosition, EditorRange

__all__ = ()

_MIN_QUOTED_TOKEN_LEN = 2
_RETRY_SHOULD_RETRY_PATH_MIN_LEN = 2
_IMPORT_LIST_PATH_MIN_LEN = 2
_IMPORT_KEY = "$import"


@dataclass(frozen=True)
class YamlCursorExtractionResult:
    """YAML DSL 光标抽取结果(以 1-based 表示,供 server 转换为 LSP range)."""

    yaml_path: str = ""
    reference: str = ""
    range: Optional[EditorRange] = None
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "yaml_path": str(self.yaml_path or ""),
            "reference": str(self.reference or ""),
        }
        if self.range is not None:
            payload["range"] = self.range.as_dict()
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        return payload


def extract_yaml_dsl_python_reference_by_cursor(
    yaml_text: str,
    position: EditorPosition,
) -> YamlCursorExtractionResult:
    """基于 `yaml_text + position` 抽取 YAML DSL 内的 Python 引用字段.

    约束:
    - 仅做静态解析,无副作用
    - 失败时降级为“空结果 + warnings”,不得 crash
    - v1 只覆盖单行 scalar string (`loader`/`call_by`/`retry.should_retry`)
    """

    return _extract_yaml_dsl_reference_by_cursor(
        yaml_text,
        position,
        allowed_kinds=("loader", "call_by", "retry.should_retry"),
    )


def extract_yaml_dsl_import_reference_by_cursor(
    yaml_text: str,
    position: EditorPosition,
) -> YamlCursorExtractionResult:
    """基于 `yaml_text + position` 抽取 YAML DSL 内的 `$import` 引用字段.

    约束:
    - 仅做静态解析,无副作用
    - 失败时降级为“空结果 + warnings”,不得 crash
    - v1 覆盖 `$import: <ref>` 与 `$import: [<ref>, ...]` 形态
    """

    return _extract_yaml_dsl_reference_by_cursor(yaml_text, position, allowed_kinds=(_IMPORT_KEY,))


def _extract_yaml_dsl_reference_by_cursor(
    yaml_text: str,
    position: EditorPosition,
    *,
    allowed_kinds: Tuple[str, ...],
) -> YamlCursorExtractionResult:
    warnings: List[str] = []

    try:
        root = _compose_yaml_node(yaml_text)
    except Exception as exc:  # noqa: BLE001
        warnings.append("YAML parse failed: {}: {}".format(type(exc).__name__, exc))
        return YamlCursorExtractionResult(warnings=tuple(warnings))

    if root is None:
        warnings.append("YAML document is empty")
        return YamlCursorExtractionResult(warnings=tuple(warnings))

    lines = yaml_text.splitlines()

    try:
        result = _extract_from_node(root, lines=lines, path=[], position=position, warnings=warnings, allowed_kinds=allowed_kinds)
    except Exception as exc:  # noqa: BLE001
        warnings.append("cursor extraction failed: {}: {}".format(type(exc).__name__, exc))
        return YamlCursorExtractionResult(warnings=tuple(warnings))

    if result is None:
        return YamlCursorExtractionResult(warnings=tuple(warnings))
    return YamlCursorExtractionResult(
        yaml_path=result.yaml_path,
        reference=result.reference,
        range=result.range,
        warnings=tuple(warnings) + tuple(result.warnings),
    )


def _compose_yaml_node(yaml_text: str) -> Optional[object]:
    yaml_safe = YAML(typ="safe")
    yaml_safe.version = (1, 2)
    return yaml_safe.compose(yaml_text)


def _extract_from_node(
    node: object,
    *,
    lines: List[str],
    path: List[str],
    position: EditorPosition,
    warnings: List[str],
    allowed_kinds: Tuple[str, ...],
) -> Optional[YamlCursorExtractionResult]:
    node_id = str(getattr(node, "id", ""))

    if node_id == "scalar":
        yaml_path = ".".join(path)
        return _extract_from_scalar_value(
            node,
            lines=lines,
            yaml_path=yaml_path,
            path=path,
            position=position,
            allowed_kinds=allowed_kinds,
        )

    if node_id == "mapping":
        for key_node, value_node in cast_value(node):
            key = str(getattr(key_node, "value", ""))
            if not key:
                continue
            key_path = [*path, key]

            nested = _extract_from_node(
                value_node,
                lines=lines,
                path=key_path,
                position=position,
                warnings=warnings,
                allowed_kinds=allowed_kinds,
            )
            if nested is not None:
                return nested
        return None

    if node_id == "sequence":
        for idx, item_node in enumerate(cast_value(node)):
            idx_path = [*path, str(idx)]
            nested = _extract_from_node(
                item_node,
                lines=lines,
                path=idx_path,
                position=position,
                warnings=warnings,
                allowed_kinds=allowed_kinds,
            )
            if nested is not None:
                return nested
        return None

    return None


def cast_value(node: object) -> Any:
    return getattr(node, "value", [])


def _extract_from_scalar_value(
    node: object,
    *,
    lines: List[str],
    yaml_path: str,
    path: List[str],
    position: EditorPosition,
    allowed_kinds: Tuple[str, ...],
) -> Optional[YamlCursorExtractionResult]:
    if not _is_supported_reference_path(path, allowed_kinds=allowed_kinds):
        return None

    reference_raw = str(getattr(node, "value", "") or "")
    bounds = _scalar_content_bounds(node, lines)
    if not reference_raw.strip() or bounds is None:
        return None

    line, content_start0, content_end0 = bounds

    if not _position_in_slice(position, line=line, start_col0=content_start0, end_col0=content_end0):
        return None

    cursor_result = _extract_reference_and_range(
        reference_raw,
        line=line,
        content_start_col0=content_start0,
        yaml_path=yaml_path,
        path=path,
    )
    if cursor_result is None or cursor_result.range is None:
        return None

    if not _position_in_range(position, cursor_result.range):
        return None
    return cursor_result


def _scalar_content_bounds(node: object, lines: List[str]) -> Optional[Tuple[int, int, int]]:  # noqa: PLR0911
    start_mark = getattr(node, "start_mark", None)
    end_mark = getattr(node, "end_mark", None)
    start_line0 = getattr(start_mark, "line", None)
    start_col0 = getattr(start_mark, "column", None)
    end_line0 = getattr(end_mark, "line", None)
    end_col0 = getattr(end_mark, "column", None)
    if not isinstance(start_line0, int):
        return None
    if not isinstance(start_col0, int):
        return None
    if not isinstance(end_line0, int):
        return None
    if not isinstance(end_col0, int):
        return None
    if int(start_line0) != int(end_line0):
        return None

    line_index = int(start_line0)
    if not (0 <= line_index < len(lines)):
        return None
    line_text = lines[line_index]
    token_start0 = int(start_col0)
    token_end0 = int(end_col0)
    if not (0 <= token_start0 <= token_end0 <= len(line_text)):
        return None

    content_start0, content_end0 = _strip_scalar_quotes(line_text, token_start0, token_end0)
    if content_start0 > content_end0:
        return None
    return line_index + 1, content_start0, content_end0


def _strip_scalar_quotes(line_text: str, token_start0: int, token_end0: int) -> Tuple[int, int]:
    token = line_text[token_start0:token_end0]
    if len(token) >= _MIN_QUOTED_TOKEN_LEN and token[0] in ("'", '"') and token[-1] == token[0]:
        return token_start0 + 1, token_end0 - 1
    return token_start0, token_end0


def _position_in_slice(position: EditorPosition, *, line: int, start_col0: int, end_col0: int) -> bool:
    if int(position.line) != int(line):
        return False
    cursor_col0 = int(position.column) - 1
    return int(start_col0) <= cursor_col0 <= int(end_col0)


def _position_in_range(position: EditorPosition, rng: EditorRange) -> bool:
    if int(position.line) != int(rng.start.line) or int(position.line) != int(rng.end.line):
        return False
    return int(rng.start.column) <= int(position.column) <= int(rng.end.column)


def _extract_reference_and_range(
    raw_value: str,
    *,
    line: int,
    content_start_col0: int,
    yaml_path: str,
    path: List[str],
) -> Optional[YamlCursorExtractionResult]:
    kind = _reference_kind(path)
    if kind == "call_by":
        head, start_offset, end_offset = _parse_call_by_head(raw_value)
        if not head:
            return None
        return YamlCursorExtractionResult(
            yaml_path=yaml_path,
            reference=head,
            range=_range_for_offsets(line, content_start_col0, start_offset, end_offset),
        )

    trimmed, start_offset, end_offset = _trim_value(raw_value)
    if not trimmed:
        return None
    return YamlCursorExtractionResult(
        yaml_path=yaml_path,
        reference=trimmed,
        range=_range_for_offsets(line, content_start_col0, start_offset, end_offset),
    )


def _range_for_offsets(line: int, content_start_col0: int, start_offset: int, end_offset: int) -> EditorRange:
    start_col1 = int(content_start_col0) + int(start_offset) + 1
    end_col1 = int(content_start_col0) + int(end_offset) + 1
    return EditorRange(
        start=EditorPosition(line=int(line), column=int(start_col1)),
        end=EditorPosition(line=int(line), column=int(end_col1)),
    )


def _trim_value(raw: str) -> Tuple[str, int, int]:
    left_trimmed = str(raw).lstrip()
    start_offset = len(raw) - len(left_trimmed)
    right_trimmed = left_trimmed.rstrip()
    value = right_trimmed
    end_offset = start_offset + len(value)
    return value, start_offset, end_offset


def _parse_call_by_head(raw: str) -> Tuple[str, int, int]:
    prefix = str(raw)
    paren_idx = prefix.find("(")
    if paren_idx != -1:
        prefix = prefix[:paren_idx]
    return _trim_value(prefix)


def _reference_kind(path: List[str]) -> str:
    if not path:
        return ""
    leaf = str(path[-1])
    if leaf in ("loader", "call_by"):
        return leaf
    if leaf == _IMPORT_KEY:
        return _IMPORT_KEY
    if len(path) >= _IMPORT_LIST_PATH_MIN_LEN and str(path[-2]) == _IMPORT_KEY:
        return _IMPORT_KEY
    if len(path) >= _RETRY_SHOULD_RETRY_PATH_MIN_LEN and str(path[-2]) == "retry" and leaf == "should_retry":
        return "retry.should_retry"
    return ""


def _is_supported_reference_path(path: List[str], *, allowed_kinds: Tuple[str, ...]) -> bool:
    kind = _reference_kind(path)
    return bool(kind and kind in allowed_kinds)
