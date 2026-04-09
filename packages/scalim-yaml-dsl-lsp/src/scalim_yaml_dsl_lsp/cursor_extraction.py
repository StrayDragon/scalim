import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from scalim.vendor.yamlx.ruamel.yaml import YAML

from .editor_types import EditorPosition, EditorRange

__all__ = ()

_MIN_QUOTED_TOKEN_LEN = 2
_RETRY_SHOULD_RETRY_PATH_MIN_LEN = 2
_IMPORT_LIST_PATH_MIN_LEN = 2
_IMPORTS_PATH_MIN_LEN = 2
_IMPORT_KEY = "$import"
_FIELDS_REF_PATH_MIN_LEN = 3
_RELATION_STEP_PARENT_PATH_MIN_LEN = 2
_RELATION_STEP_INLINE_PARENT_PATH_MIN_LEN = 3
_RELATION_STEP_SCALAR_PATH_MIN_LEN = 3
_RELATION_STEP_LIST_PATH_MIN_LEN = 4
_WORKFLOW_PATH_PREFIX_MIN_LEN = 2
_WORKFLOW_RUN_REF_PATH_MIN_LEN = 5
_OUTPUTS_FIELDS_PATH_MIN_LEN = 4
_OUTPUTS_AGGREGATE_REF_PATH_MIN_LEN = 4
_OUTPUTS_AGGREGATE_FIELDS_FIELD_PATH_MIN_LEN = 7
_OUTPUTS_AGGREGATE_FIELDS_FIELDS_ITEM_PATH_MIN_LEN = 8
_OUTPUTS_AGGREGATE_FIELDS_RANK_BY_PATH_MIN_LEN = 7
_OUTPUTS_AGGREGATE_FIELDS_RANK_LIST_ITEM_PATH_MIN_LEN = 8
_OUTPUTS_AGGREGATE_FIELDS_SCORE_BY_RANK_PATH_MIN_LEN = 7
_EXPR_FIELDS_COMPUTE_PATH_MIN_LEN = 3
_EXPR_OUTPUTS_WHERE_PATH_MIN_LEN = 3
_EXPR_OUTPUTS_AGGREGATE_COMPUTE_PATH_MIN_LEN = 6
_EXPR_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SIMPLE_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_IMPORTS_KEY_VALUE_LINE_RE = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
_DOLLAR_IMPORT_KEY_VALUE_LINE_RE = re.compile(r"^(\s*)\$import\s*:\s*(.*)$")
_AGGREGATE_RANK_KINDS = ("row_number", "rank", "dense_rank")


@dataclass(frozen=True)
class YamlCursorExtractionResult:
    """YAML DSL 光标抽取结果(以 1-based 表示,供 server 转换为 LSP range)."""

    yaml_path: str = ""
    kind: str = ""
    reference: str = ""
    range: Optional[EditorRange] = None
    value: str = ""
    value_range: Optional[EditorRange] = None
    warnings: Tuple[str, ...] = ()

    def as_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "yaml_path": str(self.yaml_path or ""),
            "kind": str(self.kind or ""),
            "reference": str(self.reference or ""),
            "value": str(self.value or ""),
        }
        if self.range is not None:
            payload["range"] = self.range.as_dict()
        if self.value_range is not None:
            payload["value_range"] = self.value_range.as_dict()
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

    base = _extract_yaml_dsl_reference_by_cursor(yaml_text, position, allowed_kinds=(_IMPORT_KEY,))
    if base.range is None:
        fallback = _fallback_extract_import_ref_value_by_cursor(yaml_text, position)
        if fallback is not None:
            return fallback
        return base
    return YamlCursorExtractionResult(
        yaml_path=base.yaml_path,
        kind=_IMPORT_KEY,
        reference=base.reference,
        range=base.range,
        value=str(base.reference or ""),
        value_range=base.range,
        warnings=base.warnings,
    )


def _fallback_extract_import_ref_value_by_cursor(
    yaml_text: str,
    position: EditorPosition,
) -> Optional[YamlCursorExtractionResult]:
    """Fallback for `$import: <empty>` where YAML parser marks null values on the next line.

    Similar to imports.* fallback, but `$import` can appear anywhere (not only under `imports:`).
    """

    lines = str(yaml_text or "").splitlines()
    line_idx0 = int(position.line) - 1
    if not (0 <= line_idx0 < len(lines)):
        return None
    line_text = str(lines[line_idx0])
    if not line_text.strip() or line_text.lstrip().startswith("#"):
        return None

    m = _DOLLAR_IMPORT_KEY_VALUE_LINE_RE.match(line_text)
    if not m:
        return None

    cursor_col0 = int(position.column) - 1
    value_start0 = int(m.start(2))
    colon_idx0 = line_text.rfind(":", 0, int(value_start0))
    if colon_idx0 == -1:
        return None
    after_colon0 = int(colon_idx0) + 1
    if cursor_col0 < after_colon0:
        return None

    prefix = ""
    if cursor_col0 >= value_start0:
        prefix = str(line_text[int(value_start0) : int(cursor_col0)] or "")

    rng = EditorRange(start=position, end=position)
    if prefix.strip():
        rng = EditorRange(
            start=EditorPosition(line=int(position.line), column=int(value_start0) + 1),
            end=EditorPosition(line=int(position.line), column=int(cursor_col0) + 1),
        )

    return YamlCursorExtractionResult(
        yaml_path="$import",
        kind=_IMPORT_KEY,
        reference=str(prefix).strip(),
        range=rng,
        value=str(prefix).strip(),
        value_range=rng,
    )


def extract_yaml_dsl_import_path_reference_by_cursor(
    yaml_text: str,
    position: EditorPosition,
) -> YamlCursorExtractionResult:
    """基于 `yaml_text + position` 抽取 YAML DSL 顶层 `imports.*` 的 path 值.

    约束:
    - 仅做静态解析,无副作用
    - 失败时降级为“空结果 + warnings”,不得 crash
    - v1 仅覆盖单行 scalar string (`imports.<alias>: <path>`)
    """

    base = _extract_yaml_dsl_reference_by_cursor(yaml_text, position, allowed_kinds=("imports_path",))
    if base.range is None:
        fallback = _fallback_extract_imports_path_value_by_cursor(yaml_text, position)
        if fallback is not None:
            return fallback
        return base
    return YamlCursorExtractionResult(
        yaml_path=base.yaml_path,
        kind="imports_path",
        reference=base.reference,
        range=base.range,
        value=str(base.reference or ""),
        value_range=base.range,
        warnings=base.warnings,
    )


def _fallback_extract_imports_path_value_by_cursor(  # noqa: PLR0911
    yaml_text: str,
    position: EditorPosition,
) -> Optional[YamlCursorExtractionResult]:
    """Fallback for `imports.*: <empty>` where YAML parser marks null values on the next line.

    We do a conservative, line-based detection:
    - cursor must be on a `key:` line under a `imports:` parent line
    - produce a zero-length range at cursor for completion (Ctrl+Space)
    """

    lines = str(yaml_text or "").splitlines()
    line_idx0 = int(position.line) - 1
    if not (0 <= line_idx0 < len(lines)):
        return None
    line_text = str(lines[line_idx0])
    if not line_text.strip() or line_text.lstrip().startswith("#"):
        return None

    m = _IMPORTS_KEY_VALUE_LINE_RE.match(line_text)
    if not m:
        return None
    indent_text, key, _value_tail = m.group(1), m.group(2), m.group(3)
    if not key or not _SIMPLE_KEY_RE.match(str(key)):
        return None

    indent = len(indent_text or "")
    if not _is_under_imports_block(lines, line_idx0, indent):
        return None

    cursor_col0 = int(position.column) - 1
    # `m.start(3)` points to the value tail after `:` + optional whitespace.
    # For empty values, users may place cursor right after `:` (before trailing whitespace),
    # so we accept cursor positions in the `:`-whitespace region as an empty prefix.
    value_start0 = int(m.start(3))

    colon_idx0 = line_text.find(":", int(m.end(2)))
    if colon_idx0 == -1:
        return None
    after_colon0 = int(colon_idx0) + 1
    if cursor_col0 < after_colon0:
        return None

    prefix = ""
    if cursor_col0 >= value_start0:
        prefix = str(line_text[int(value_start0) : int(cursor_col0)] or "")

    rng = EditorRange(start=position, end=position)
    if prefix.strip():
        rng = EditorRange(
            start=EditorPosition(line=int(position.line), column=int(value_start0) + 1),
            end=EditorPosition(line=int(position.line), column=int(cursor_col0) + 1),
        )

    return YamlCursorExtractionResult(
        yaml_path="imports.{}".format(str(key)),
        kind="imports_path",
        reference=str(prefix).strip(),
        range=rng,
        value=str(prefix).strip(),
        value_range=rng,
    )


def _is_under_imports_block(lines: List[str], line_idx0: int, indent: int) -> bool:
    """Returns True if the line at `line_idx0` is in a mapping directly under a parent `imports:` key."""
    idx = int(line_idx0) - 1
    while idx >= 0:
        raw = str(lines[idx])
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            idx -= 1
            continue
        parent_indent = len(raw) - len(raw.lstrip(" "))
        if int(parent_indent) >= int(indent):
            idx -= 1
            continue
        return bool(stripped.startswith("imports:"))
    return False


def extract_yaml_dsl_output_field_reference_by_cursor(
    yaml_text: str,
    position: EditorPosition,
) -> YamlCursorExtractionResult:
    """基于 `yaml_text + position` 抽取 YAML DSL `outputs[*].fields` 内的字段引用.

    约束:
    - 仅做静态解析,无副作用
    - 失败时降级为“空结果 + warnings”,不得 crash
    - v1 仅覆盖单行 scalar string (不覆盖 `*alias` token)
    """

    base = _extract_yaml_dsl_reference_by_cursor(yaml_text, position, allowed_kinds=("output_field_id",))
    if base.range is None:
        return base
    return YamlCursorExtractionResult(
        yaml_path=base.yaml_path,
        kind="output_field_id",
        reference=base.reference,
        range=base.range,
        value=str(base.reference or ""),
        value_range=base.range,
        warnings=base.warnings,
    )


def extract_yaml_dsl_aggregate_field_reference_by_cursor(
    yaml_text: str,
    position: EditorPosition,
) -> YamlCursorExtractionResult:
    """基于 `yaml_text + position` 抽取 YAML DSL `outputs[*].aggregate` 内的字段引用.

    覆盖范围(至少):
    - `outputs[*].aggregate.group_by[*]` / `group_by[*][*]`
    - `outputs[*].aggregate.fields.*.*.field`
    - `outputs[*].aggregate.fields.*.*.fields[*]`
    - `outputs[*].aggregate.fields.*.(row_number|rank|dense_rank).by|partition_by[*]|order_by[*]`
    - `outputs[*].aggregate.fields.*.score_by_rank.rank_field`

    约束:
    - 仅做静态解析,无副作用
    - 失败时降级为“空结果 + warnings”,不得 crash
    - 空 scalar / 空 list item 场景必须可用于 completion (Ctrl+Space)
    """

    base = _extract_yaml_dsl_reference_by_cursor(yaml_text, position, allowed_kinds=("aggregate_field_ref",))
    if base.range is None:
        return base
    return YamlCursorExtractionResult(
        yaml_path=base.yaml_path,
        kind="aggregate_field_ref",
        reference=base.reference,
        range=base.range,
        value=str(base.reference or ""),
        value_range=base.range,
        warnings=base.warnings,
    )


def extract_yaml_dsl_yaml_alias_reference_by_cursor(
    yaml_text: str,
    position: EditorPosition,
) -> YamlCursorExtractionResult:
    """基于 `yaml_text + position` 抽取 YAML alias token `*name`(仅用于 editor 导航/解释).

    说明:
    - YAML parser 会把 `*alias` 解析为引用节点,通常无法保留 alias token 的源码 range。
    - editor 侧仅依赖文本扫描定位 token range,并在 core 中做 anchor 定位与解释.
    """
    warnings: List[str] = []
    lines = str(yaml_text or "").splitlines()
    line_idx0 = int(position.line) - 1
    if not (0 <= line_idx0 < len(lines)):
        return YamlCursorExtractionResult(warnings=tuple(warnings))
    line_text = str(lines[line_idx0])
    cursor_col0 = int(position.column) - 1
    if not (0 <= cursor_col0 <= len(line_text)):
        return YamlCursorExtractionResult(warnings=tuple(warnings))

    # Match `*alias_name` on the current line and choose the match under cursor.
    matches = list(re.finditer(r"\*[A-Za-z_][A-Za-z0-9_]*", line_text))
    for m in matches:
        start0, end0 = m.start(), m.end()
        if not (int(start0) <= cursor_col0 <= int(end0)):
            continue
        token = m.group(0)
        alias_name = token[1:]
        rng = EditorRange(
            start=EditorPosition(line=int(position.line), column=int(start0) + 1),
            end=EditorPosition(line=int(position.line), column=int(end0) + 1),
        )
        return YamlCursorExtractionResult(
            yaml_path="",
            kind="yaml_alias",
            reference=str(alias_name),
            range=rng,
            value=str(token),
            value_range=rng,
            warnings=tuple(warnings),
        )

    return YamlCursorExtractionResult(warnings=tuple(warnings))


def extract_yaml_dsl_expression_token_by_cursor(
    yaml_text: str,
    position: EditorPosition,
) -> YamlCursorExtractionResult:
    """抽取 compute/where 等表达式 scalar 内的 identifier token.

    约束:
    - 仅做静态解析,无副作用
    - 失败时降级为“空结果 + warnings”,不得 crash
    - v1 仅覆盖单行 scalar,且仅返回 token 的精确 range
    """

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
        result = _extract_expression_token_from_node(root, lines=lines, path=[], position=position)
    except Exception as exc:  # noqa: BLE001
        warnings.append("cursor extraction failed: {}: {}".format(type(exc).__name__, exc))
        return YamlCursorExtractionResult(warnings=tuple(warnings))

    if result is None:
        return YamlCursorExtractionResult(warnings=tuple(warnings))
    return YamlCursorExtractionResult(
        yaml_path=result.yaml_path,
        kind=result.kind,
        reference=result.reference,
        range=result.range,
        value=result.value,
        value_range=result.value_range,
        warnings=tuple(warnings) + tuple(result.warnings),
    )


def _extract_expression_token_from_node(
    node: object,
    *,
    lines: List[str],
    path: List[str],
    position: EditorPosition,
) -> Optional[YamlCursorExtractionResult]:
    node_id = str(getattr(node, "id", ""))

    if node_id == "scalar":
        yaml_path = ".".join(path)
        return _extract_from_expression_scalar_value(
            node,
            lines=lines,
            yaml_path=yaml_path,
            path=path,
            position=position,
        )

    if node_id == "mapping":
        for key_node, value_node in cast_value(node):
            key = str(getattr(key_node, "value", ""))
            if not key:
                continue
            key_path = [*path, key]
            nested = _extract_expression_token_from_node(
                value_node,
                lines=lines,
                path=key_path,
                position=position,
            )
            if nested is not None:
                return nested
        return None

    if node_id == "sequence":
        for idx, item_node in enumerate(cast_value(node)):
            idx_path = [*path, str(idx)]
            nested = _extract_expression_token_from_node(
                item_node,
                lines=lines,
                path=idx_path,
                position=position,
            )
            if nested is not None:
                return nested
        return None

    return None


def _expression_kind_for_path(path: List[str]) -> str:
    if len(path) >= _EXPR_FIELDS_COMPUTE_PATH_MIN_LEN and str(path[0]) == "fields" and str(path[-1]) == "compute":
        return "expression_fields_compute"

    if (
        len(path) >= _EXPR_OUTPUTS_WHERE_PATH_MIN_LEN
        and str(path[0]) == "outputs"
        and _is_int_str(str(path[1]))
        and str(path[-1]) == "where"
    ):
        return "expression_outputs_where"

    if (
        len(path) >= _EXPR_OUTPUTS_AGGREGATE_COMPUTE_PATH_MIN_LEN
        and str(path[0]) == "outputs"
        and _is_int_str(str(path[1]))
        and str(path[2]) == "aggregate"
        and str(path[3]) == "fields"
        and str(path[-1]) == "compute"
    ):
        return "expression_outputs_aggregate_compute"

    return ""


def _extract_from_expression_scalar_value(
    node: object,
    *,
    lines: List[str],
    yaml_path: str,
    path: List[str],
    position: EditorPosition,
) -> Optional[YamlCursorExtractionResult]:
    kind = _expression_kind_for_path(path)
    if not kind:
        return None

    bounds = _scalar_content_bounds(node, lines)
    if bounds is None:
        return None

    line, content_start0, content_end0 = bounds
    if not _position_in_slice(position, line=line, start_col0=content_start0, end_col0=content_end0):
        return None

    line_text = str(lines[int(line) - 1])
    source_text = line_text[int(content_start0) : int(content_end0)]
    cursor_col0 = int(position.column) - 1
    cursor_offset = int(cursor_col0) - int(content_start0)
    if not (0 <= cursor_offset <= len(source_text)):
        return None

    for m in _EXPR_IDENTIFIER_RE.finditer(source_text):
        start0 = int(m.start())
        end0 = int(m.end())
        if not (start0 <= cursor_offset <= end0):
            continue
        token = m.group(0)
        rng = EditorRange(
            start=EditorPosition(line=int(line), column=int(content_start0) + int(start0) + 1),
            end=EditorPosition(line=int(line), column=int(content_start0) + int(end0) + 1),
        )
        return YamlCursorExtractionResult(
            yaml_path=yaml_path,
            kind=kind,
            reference=str(token),
            range=rng,
            value=str(token),
            value_range=rng,
        )

    # Cursor is inside an expression scalar, but not on an identifier token.
    # Still return a zero-length range so editor completion (Ctrl+Space) can work.
    cursor_col1 = int(cursor_col0) + 1
    empty_rng = EditorRange(
        start=EditorPosition(line=int(line), column=int(cursor_col1)),
        end=EditorPosition(line=int(line), column=int(cursor_col1)),
    )
    return YamlCursorExtractionResult(
        yaml_path=yaml_path,
        kind=kind,
        reference="",
        range=empty_rng,
        value="",
        value_range=empty_rng,
    )


def extract_yaml_dsl_entity_reference_by_cursor(
    yaml_text: str,
    position: EditorPosition,
) -> YamlCursorExtractionResult:
    """基于 `yaml_text + position` 抽取 YAML DSL 内的实体 ID 引用.

    约束:
    - 仅做静态解析,无副作用
    - 失败时降级为“空结果 + warnings”,不得 crash
    - 支持复合引用 `source_id.field_id` 的子 token range
    """

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
        result = _extract_entity_from_node(root, lines=lines, path=[], position=position, warnings=warnings)
    except Exception as exc:  # noqa: BLE001
        warnings.append("cursor extraction failed: {}: {}".format(type(exc).__name__, exc))
        return YamlCursorExtractionResult(warnings=tuple(warnings))

    if result is None:
        return YamlCursorExtractionResult(warnings=tuple(warnings))
    return YamlCursorExtractionResult(
        yaml_path=result.yaml_path,
        kind=result.kind,
        reference=result.reference,
        range=result.range,
        value=result.value,
        value_range=result.value_range,
        warnings=tuple(warnings) + tuple(result.warnings),
    )


def _extract_entity_from_node(
    node: object,
    *,
    lines: List[str],
    path: List[str],
    position: EditorPosition,
    warnings: List[str],
) -> Optional[YamlCursorExtractionResult]:
    node_id = str(getattr(node, "id", ""))

    if node_id == "scalar":
        yaml_path = ".".join(path)
        return _extract_from_entity_scalar_value(
            node,
            lines=lines,
            yaml_path=yaml_path,
            path=path,
            position=position,
        )

    if node_id == "mapping":
        for key_node, value_node in cast_value(node):
            key = str(getattr(key_node, "value", ""))
            if not key:
                continue
            key_path = [*path, key]
            nested = _extract_entity_from_node(
                value_node,
                lines=lines,
                path=key_path,
                position=position,
                warnings=warnings,
            )
            if nested is not None:
                return nested
        return None

    if node_id == "sequence":
        for idx, item_node in enumerate(cast_value(node)):
            idx_path = [*path, str(idx)]
            nested = _extract_entity_from_node(
                item_node,
                lines=lines,
                path=idx_path,
                position=position,
                warnings=warnings,
            )
            if nested is not None:
                return nested
        return None

    return None


def _extract_from_entity_scalar_value(
    node: object,
    *,
    lines: List[str],
    yaml_path: str,
    path: List[str],
    position: EditorPosition,
) -> Optional[YamlCursorExtractionResult]:
    base_kind = _entity_reference_kind(path)
    if not base_kind:
        return None

    reference_raw = str(getattr(node, "value", "") or "")
    bounds = _scalar_content_bounds(node, lines)
    if bounds is None:
        return None

    line, content_start0, content_end0 = bounds
    if content_start0 > content_end0 or not _position_in_slice(position, line=line, start_col0=content_start0, end_col0=content_end0):
        return None

    cursor_col0 = int(position.column) - 1
    cursor_result = _extract_entity_reference_and_ranges(
        base_kind,
        reference_raw,
        cursor_col0=cursor_col0,
        line=line,
        content_start_col0=content_start0,
        yaml_path=yaml_path,
    )
    if cursor_result is None or cursor_result.range is None or cursor_result.value_range is None:
        return None
    if _position_in_range(position, cursor_result.range):
        return cursor_result
    return None


def _extract_entity_reference_and_ranges(
    base_kind: str,
    raw_value: str,
    *,
    cursor_col0: int,
    line: int,
    content_start_col0: int,
    yaml_path: str,
) -> Optional[YamlCursorExtractionResult]:
    trimmed, start_offset, end_offset = _trim_value(raw_value)
    if base_kind != "relation_step" and not trimmed:
        return None

    value_range = _range_for_offsets(line, content_start_col0, start_offset, end_offset)

    if base_kind == "relation_step":
        dot_idx = trimmed.find(".")

        cursor_offset_in_content = int(cursor_col0) - int(content_start_col0)
        cursor_offset_in_content = max(0, min(int(cursor_offset_in_content), len(str(raw_value))))
        cursor_offset_in_trimmed = max(0, min(int(cursor_offset_in_content) - int(start_offset), len(trimmed)))

        if dot_idx == -1:
            kind = "relation_step_source_id"
            token = trimmed
            token_start_offset = start_offset
            token_end_offset = end_offset
        elif cursor_offset_in_trimmed <= int(dot_idx):
            kind = "relation_step_source_id"
            token = trimmed[:dot_idx]
            token_start_offset = start_offset
            token_end_offset = start_offset + dot_idx
        else:
            kind = "relation_step_field_id"
            token = trimmed[dot_idx + 1 :]
            token_start_offset = start_offset + dot_idx + 1
            token_end_offset = end_offset

        token_range = _range_for_offsets(line, content_start_col0, token_start_offset, token_end_offset)
        return YamlCursorExtractionResult(
            yaml_path=yaml_path,
            kind=kind,
            reference=token,
            range=token_range,
            value=trimmed,
            value_range=value_range,
        )

    if base_kind == "source_id":
        kind = "source_id"
    elif base_kind == "relation_id":
        kind = "relation_id"
    elif base_kind == "output_name":
        kind = "output_name"
    elif base_kind == "workflow_run_id":
        kind = "workflow_run_id"
    else:
        kind = str(base_kind)

    return YamlCursorExtractionResult(
        yaml_path=yaml_path,
        kind=kind,
        reference=trimmed,
        range=value_range,
        value=trimmed,
        value_range=value_range,
    )


def _is_int_str(text: str) -> bool:
    raw = str(text or "")
    return bool(raw and raw.isdigit())


def _is_relation_step_reference_parent_path(parent_path: List[str]) -> bool:
    if not parent_path:
        return False
    if str(parent_path[0]) == "relations":
        return len(parent_path) >= _RELATION_STEP_PARENT_PATH_MIN_LEN
    return bool(
        len(parent_path) >= _RELATION_STEP_INLINE_PARENT_PATH_MIN_LEN
        and str(parent_path[-1]) == "relation"
        and str(parent_path[-3]) == "fields"
    )


def _relation_step_reference_kind(path: List[str]) -> str:
    # scalar: ... steps.<idx>.from/to
    if (
        path
        and str(path[-1]) in ("from", "to")
        and len(path) >= _RELATION_STEP_SCALAR_PATH_MIN_LEN
        and str(path[-3]) == "steps"
        and _is_int_str(str(path[-2]))
    ):
        parent = path[:-3]
        return "relation_step" if _is_relation_step_reference_parent_path(parent) else ""

    # list item: ... steps.<idx>.from/to.<idx>
    if (
        _is_int_str(str(path[-1]))
        and len(path) >= _RELATION_STEP_LIST_PATH_MIN_LEN
        and str(path[-2]) in ("from", "to")
        and str(path[-4]) == "steps"
        and _is_int_str(str(path[-3]))
    ):
        parent = path[:-4]
        return "relation_step" if _is_relation_step_reference_parent_path(parent) else ""

    return ""


def _entity_reference_kind(path: List[str]) -> str:
    kind = ""
    if not path:
        return kind

    leaf = str(path[-1])

    # derived fields / source fields
    if leaf == "source" and len(path) >= _FIELDS_REF_PATH_MIN_LEN and str(path[-3]) == "fields":
        kind = "source_id"
    elif leaf == "relation" and len(path) >= _FIELDS_REF_PATH_MIN_LEN and str(path[-3]) == "fields":
        kind = "relation_id"
    else:
        relation_step = _relation_step_reference_kind(path)
        if relation_step:
            kind = relation_step
        elif str(path[0]) == "outputs" and leaf == "from":
            kind = "output_name"
        else:
            kind = _workflow_run_reference_kind(path) or ""

    return kind


def _workflow_run_reference_kind(path: List[str]) -> str:
    if len(path) < _WORKFLOW_PATH_PREFIX_MIN_LEN:
        return ""
    if str(path[0]) != "workflow" or str(path[1]) != "runs":
        return ""

    if len(path) >= _WORKFLOW_RUN_REF_PATH_MIN_LEN and str(path[-2]) == "depends_on" and _is_int_str(str(path[-1])):
        return "workflow_run_id"
    if len(path) >= _WORKFLOW_RUN_REF_PATH_MIN_LEN and str(path[-1]) == "run" and str(path[-2]) == "main_rows_from":
        return "workflow_run_id"
    return ""


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


def _extract_from_scalar_value(  # noqa: PLR0911
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
    if bounds is None:
        return None

    line, content_start0, content_end0 = bounds

    if not _position_in_slice(position, line=line, start_col0=content_start0, end_col0=content_end0):
        # Empty scalars often appear as a single slot (start == end) while editors
        # allow cursor positions further to the right (trailing whitespace).
        # Allow cursor in trailing whitespace for empty scalars (until a comment / non-space).
        if int(content_start0) != int(content_end0) or int(position.line) != int(line):
            return None
        cursor_col0 = int(position.column) - 1
        if cursor_col0 < int(content_end0):
            return None
        line_text = str(lines[int(line) - 1])
        cursor_col0 = max(0, min(int(cursor_col0), len(line_text)))
        tail = line_text[int(content_end0) : int(cursor_col0)]
        if tail.strip():
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
        # For empty scalars, use the cursor position as a zero-length replacement range so
        # completion can still work when cursor is placed at end-of-line.
        if not str(cursor_result.reference or "").strip():
            cursor_rng = EditorRange(start=position, end=position)
            return YamlCursorExtractionResult(
                yaml_path=yaml_path,
                reference="",
                range=cursor_rng,
            )
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
    if int(start_col0) <= cursor_col0 <= int(end_col0):
        return True
    # Empty scalars often yield `start_col0 == end_col0` (single cursor slot),
    # but editors commonly place the cursor at end-of-line (`end_col0 + 1`).
    return int(start_col0) == int(end_col0) and cursor_col0 == int(end_col0) + 1


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
        return YamlCursorExtractionResult(
            yaml_path=yaml_path,
            reference="",
            range=_range_for_offsets(line, content_start_col0, start_offset, end_offset),
        )
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

    kind = ""
    if len(path) >= _IMPORTS_PATH_MIN_LEN and str(path[0]) == "imports":
        kind = "imports_path"
    else:
        leaf = str(path[-1])
        if (
            len(path) >= _OUTPUTS_FIELDS_PATH_MIN_LEN
            and str(path[0]) == "outputs"
            and _is_int_str(str(path[1]))
            and str(path[2]) == "fields"
            and _is_int_str(str(path[-1]))
        ):
            kind = "output_field_id"
        elif _is_output_aggregate_field_ref_path(path):
            kind = "aggregate_field_ref"
        elif leaf in ("loader", "call_by"):
            kind = leaf
        elif leaf == _IMPORT_KEY or (len(path) >= _IMPORT_LIST_PATH_MIN_LEN and str(path[-2]) == _IMPORT_KEY):
            kind = _IMPORT_KEY
        elif len(path) >= _RETRY_SHOULD_RETRY_PATH_MIN_LEN and str(path[-2]) == "retry" and leaf == "should_retry":
            kind = "retry.should_retry"

    return kind


def _is_output_aggregate_field_ref_path(path: List[str]) -> bool:
    """Returns True if `path` points to a scalar/list-item field reference under `outputs[*].aggregate`."""

    if len(path) < _OUTPUTS_AGGREGATE_REF_PATH_MIN_LEN:
        return False
    if str(path[0]) != "outputs" or not _is_int_str(str(path[1])):
        return False
    if str(path[2]) != "aggregate":
        return False

    return bool(
        _is_output_aggregate_group_by_ref_path(path)
        or _is_output_aggregate_metric_field_ref_path(path)
        or _is_output_aggregate_metric_fields_item_ref_path(path)
        or _is_output_aggregate_rank_ref_path(path)
        or _is_output_aggregate_score_by_rank_ref_path(path)
    )


def _is_output_aggregate_group_by_ref_path(path: List[str]) -> bool:
    if str(path[3]) != "group_by":
        return False
    # group_by scalar (permissive) or list items (including composite key `group_by[*][*]`)
    return str(path[-1]) == "group_by" or _is_int_str(str(path[-1]))


def _is_output_aggregate_fields_ref_prefix(path: List[str]) -> bool:
    return str(path[3]) == "fields"


def _is_output_aggregate_metric_field_ref_path(path: List[str]) -> bool:
    if not _is_output_aggregate_fields_ref_prefix(path):
        return False
    # outputs.<i>.aggregate.fields.<out_field_id>.<metric_kind>.field
    return str(path[-1]) == "field" and len(path) >= _OUTPUTS_AGGREGATE_FIELDS_FIELD_PATH_MIN_LEN


def _is_output_aggregate_metric_fields_item_ref_path(path: List[str]) -> bool:
    if not _is_output_aggregate_fields_ref_prefix(path):
        return False
    # outputs.<i>.aggregate.fields.<out_field_id>.<metric_kind>.fields[*]
    return _is_int_str(str(path[-1])) and len(path) >= _OUTPUTS_AGGREGATE_FIELDS_FIELDS_ITEM_PATH_MIN_LEN and str(path[-2]) == "fields"


def _is_output_aggregate_rank_ref_path(path: List[str]) -> bool:
    if not _is_output_aggregate_fields_ref_prefix(path):
        return False

    # outputs.<i>.aggregate.fields.<out_field_id>.<rank_kind>.by
    if str(path[-1]) == "by" and len(path) >= _OUTPUTS_AGGREGATE_FIELDS_RANK_BY_PATH_MIN_LEN:
        return str(path[-2]) in _AGGREGATE_RANK_KINDS

    # outputs.<i>.aggregate.fields.<out_field_id>.<rank_kind>.(partition_by|order_by)[*]
    if _is_int_str(str(path[-1])) and len(path) >= _OUTPUTS_AGGREGATE_FIELDS_RANK_LIST_ITEM_PATH_MIN_LEN:
        return str(path[-3]) in _AGGREGATE_RANK_KINDS and str(path[-2]) in ("partition_by", "order_by")

    return False


def _is_output_aggregate_score_by_rank_ref_path(path: List[str]) -> bool:
    if not _is_output_aggregate_fields_ref_prefix(path):
        return False
    return (
        len(path) >= _OUTPUTS_AGGREGATE_FIELDS_SCORE_BY_RANK_PATH_MIN_LEN
        and str(path[-1]) == "rank_field"
        and str(path[-2]) == "score_by_rank"
    )


def _is_supported_reference_path(path: List[str], *, allowed_kinds: Tuple[str, ...]) -> bool:
    kind = _reference_kind(path)
    return bool(kind and kind in allowed_kinds)
