import difflib
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import (
    DoubleQuotedScalarString,
    FoldedScalarString,
    LiteralScalarString,
    PlainScalarString,
    PreservedScalarString,
    SingleQuotedScalarString,
)

from scalim.vendor.yamlx.ruamel.yaml import YAML

_EXCLUDED_DIR_NAMES: Tuple[str, ...] = (".tmp", "dist")

_TARGET_KEYS: Tuple[str, ...] = ("loader", "call_by", "compute")
_TARGET_RETRY_KEY = "retry"
_TARGET_RETRY_SHOULD_RETRY_KEY = "should_retry"

_CALL_BY_LONG_LINE_THRESHOLD = 120
_LC_DATA_VALUE_POS_LEN = 4


@dataclass(frozen=True)
class TextPosition:
    line: int
    character: int

    def as_dict(self) -> Dict[str, Any]:
        return {"line": self.line, "character": self.character}


@dataclass(frozen=True)
class TextRange:
    start: TextPosition
    end: TextPosition

    def as_dict(self) -> Dict[str, Any]:
        return {"start": self.start.as_dict(), "end": self.end.as_dict()}


@dataclass(frozen=True)
class LintIssue:
    code: str
    severity: str
    message: str
    path: str
    range: TextRange

    def as_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
            "range": self.range.as_dict(),
        }


def discover_yaml_files(paths: Sequence[Path]) -> Tuple[List[Path], List[str]]:
    errors: List[str] = []
    output: List[Path] = []

    for raw in paths:
        path = Path(raw)
        if not path.exists():
            errors.append("Path does not exist: {}".format(path))
            continue
        if path.is_file():
            if path.suffix.lower() not in (".yaml", ".yml"):
                errors.append("Not a YAML file: {}".format(path))
                continue
            output.append(path)
            continue

        if not path.is_dir():
            errors.append("Not a file or directory: {}".format(path))
            continue

        output.extend(_iter_yaml_files_recursively(path))

    unique = sorted({item.resolve() for item in output}, key=str)
    return unique, errors


def _iter_yaml_files_recursively(root: Path) -> Iterator[Path]:
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in (".yaml", ".yml"):
            continue
        if _has_excluded_parent(candidate):
            continue
        yield candidate


def _has_excluded_parent(path: Path) -> bool:
    return any(part in _EXCLUDED_DIR_NAMES for part in path.parts)


def format_yaml_dsl_file(path: Path) -> Tuple[bool, Optional[str], Optional[str]]:
    try:
        old_text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return False, None, "Failed to read: {}: {}".format(type(exc).__name__, exc)

    new_text, changed, error = format_yaml_dsl_text(old_text)
    if error is not None:
        return False, None, error
    if not changed:
        return False, old_text, None

    try:
        _ = path.write_text(new_text, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return False, None, "Failed to write: {}: {}".format(type(exc).__name__, exc)
    return True, new_text, None


def format_yaml_dsl_text(text: str) -> Tuple[str, bool, Optional[str]]:
    yaml_rt = _make_yaml_rt(text)

    try:
        data = yaml_rt.load(text)
    except Exception as exc:  # noqa: BLE001
        return text, False, "YAML parse failed: {}: {}".format(type(exc).__name__, exc)

    if data is None:
        return text, False, None

    changed = _apply_formatting_inplace(data)
    if not changed:
        return text, False, None

    buf = StringIO()
    try:
        yaml_rt.dump(data, buf)
    except Exception as exc:  # noqa: BLE001
        return text, False, "YAML dump failed: {}: {}".format(type(exc).__name__, exc)

    new_text = buf.getvalue()
    return new_text, new_text != text, None


def diff_text(*, old_text: str, new_text: str, path: Path) -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=str(path),
        tofile=str(path),
    )
    return "".join(diff)


def lint_yaml_dsl_text(text: str, *, source_path: str) -> Tuple[List[LintIssue], Optional[str]]:
    yaml_rt = _make_yaml_rt(text)
    try:
        data = yaml_rt.load(text)
    except Exception as exc:  # noqa: BLE001
        msg = "YAML parse failed: {}: {}".format(type(exc).__name__, exc)
        return [
            LintIssue(
                code="YDL000",
                severity="error",
                message=msg,
                path=source_path,
                range=_single_pos_range(line=1, character=1),
            )
        ], None

    if data is None:
        return [], None

    source_lines = text.splitlines()
    issues: List[LintIssue] = []
    for parent, key, value, key_kind in _iter_target_fields(data):
        issue_range = _issue_range_for_value(source_lines, parent, key)
        if issue_range is None:
            continue
        issues.extend(_lint_target_field_value(key_kind, value=value, issue_range=issue_range, source_path=source_path))

    return issues, None


def _make_yaml_rt(text: str) -> YAML:
    newline = "\r\n" if "\r\n" in text else "\n"

    yaml_rt = YAML(typ="rt")
    yaml_rt.line_break = newline  # pyright: ignore[reportAttributeAccessIssue]  # pragma: allow-dynattr third-party: ruamel YAML config
    yaml_rt.preserve_quotes = True
    yaml_rt.width = 4096
    yaml_rt.indent(mapping=2, sequence=4, offset=2)

    first_nonempty = ""
    for line in text.splitlines():
        if line.strip():
            first_nonempty = line
            break
    yaml_rt.explicit_start = first_nonempty.strip() == "---"

    return yaml_rt


def _apply_formatting_inplace(data: Any) -> bool:
    changed = False
    for parent, key, value, _key_kind in _iter_target_fields(data):
        if not isinstance(value, str):
            continue
        if _is_block_scalar_string(value):
            continue
        if not isinstance(value, (DoubleQuotedScalarString, SingleQuotedScalarString)):
            continue
        if not _is_safe_plain_scalar(str(value)):
            continue
        parent[key] = PlainScalarString(str(value))
        changed = True
    return changed


def _iter_target_fields(obj: Any) -> Iterator[Tuple[CommentedMap, str, Any, str]]:
    if isinstance(obj, CommentedMap):
        for key, value in obj.items():
            if isinstance(key, str) and key in _TARGET_KEYS:
                yield obj, key, value, key

            if (
                isinstance(key, str)
                and key == _TARGET_RETRY_KEY
                and isinstance(value, CommentedMap)
                and _TARGET_RETRY_SHOULD_RETRY_KEY in value
            ):
                yield value, _TARGET_RETRY_SHOULD_RETRY_KEY, value.get(_TARGET_RETRY_SHOULD_RETRY_KEY), "retry.should_retry"

            yield from _iter_target_fields(value)
        return

    for child in _iter_children(obj):
        yield from _iter_target_fields(child)


def _value_position(parent: CommentedMap, key: str) -> Optional[Tuple[int, int]]:
    loc = parent.lc.data.get(key)  # type: ignore[attr-defined]  # pragma: allow-dynattr third-party: ruamel lc
    if not loc or len(loc) < _LC_DATA_VALUE_POS_LEN:
        return None
    value_line0 = int(loc[2])
    value_col0 = int(loc[3])
    return value_line0, value_col0


def _extract_scalar_token(source_lines: Sequence[str], value_line0: int, value_col0: int) -> str:
    if value_line0 < 0 or value_line0 >= len(source_lines):
        return ""
    line = source_lines[value_line0]
    if value_col0 < 0 or value_col0 > len(line):
        return ""

    sub = line[value_col0:]
    if not sub:
        return ""

    if sub[0] in ("'", '"'):
        return _extract_quoted_scalar_token(sub)

    return _extract_plain_scalar_token(sub)


def _extract_quoted_scalar_token(sub: str) -> str:
    quote = sub[0]
    i = 1
    while i < len(sub):
        ch = sub[i]
        if quote == "'" and ch == "'" and i + 1 < len(sub) and sub[i + 1] == "'":
            i += 2
            continue

        if quote == '"' and ch == '"' and i > 0 and sub[i - 1] == "\\":
            i += 1
            continue

        if ch == quote:
            i += 1
            break
        i += 1
    return sub[:i]


def _extract_plain_scalar_token(sub: str) -> str:
    i = 0
    while i < len(sub):
        ch = sub[i]
        if ch in (" ", "\t", "\r", "\n", "#"):
            break
        i += 1
    return sub[:i]


def _is_block_scalar_string(value: Any) -> bool:
    return isinstance(value, (LiteralScalarString, FoldedScalarString, PreservedScalarString))


def _is_safe_plain_scalar(value: str) -> bool:
    if not value:
        return False
    if "\n" in value or "\r" in value:
        return False
    try:
        yaml_safe = YAML(typ="safe")
        yaml_safe.version = (1, 2)
        data = yaml_safe.load("x: {}\n".format(value))
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(data, dict):
        return False
    parsed = data.get("x")
    return isinstance(parsed, str) and parsed == value


def _is_long_single_line_call_by(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if "\n" in value or "\r" in value:
        return False
    if _is_block_scalar_string(value):
        return False
    return len(value) > _CALL_BY_LONG_LINE_THRESHOLD


def _single_pos_range(*, line: int, character: int) -> TextRange:
    pos = TextPosition(line=int(line), character=int(character))
    return TextRange(start=pos, end=pos)


def _issue_range_for_value(source_lines: Sequence[str], parent: CommentedMap, key: str) -> Optional[TextRange]:
    loc = _value_position(parent, key)
    if loc is None:
        return None
    value_line0, value_col0 = loc

    token = _extract_scalar_token(source_lines, value_line0, value_col0)
    token_len = len(token)

    start = TextPosition(line=value_line0 + 1, character=value_col0 + 1)
    end = TextPosition(line=value_line0 + 1, character=value_col0 + 1 + token_len)
    return TextRange(start=start, end=end)


def _lint_target_field_value(
    key_kind: str,
    *,
    value: Any,
    issue_range: TextRange,
    source_path: str,
) -> List[LintIssue]:
    issues: List[LintIssue] = []

    if key_kind == "call_by" and _is_long_single_line_call_by(value):
        issues.append(
            LintIssue(
                code="YDL004",
                severity="info",
                message="call_by is long; consider YAML block scalar (|) for readability",
                path=source_path,
                range=issue_range,
            )
        )

    if key_kind in ("loader", "call_by", "compute", "retry.should_retry") and (isinstance(value, (bool, int, float)) or value is None):
        issues.append(
            LintIssue(
                code="YDL002",
                severity="error",
                message="value is not a string (YAML parsed as {}); quote it if you intended a string".format(type(value).__name__),
                path=source_path,
                range=issue_range,
            )
        )
        return issues

    if not isinstance(value, str):
        return issues

    if _is_block_scalar_string(value):
        return issues

    if isinstance(value, (DoubleQuotedScalarString, SingleQuotedScalarString)) and _is_safe_plain_scalar(str(value)):
        issues.append(
            LintIssue(
                code="YDL001",
                severity="warning",
                message="quoted reference can be plain scalar (remove quotes)",
                path=source_path,
                range=issue_range,
            )
        )

    return issues


def _iter_children(obj: Any) -> Iterator[Any]:
    if isinstance(obj, (CommentedSeq, list)):
        for item in obj:
            yield item
        return

    if isinstance(obj, dict):
        for value in obj.values():
            yield value
        return


__all__ = (
    "LintIssue",
    "TextPosition",
    "TextRange",
    "diff_text",
    "discover_yaml_files",
    "format_yaml_dsl_file",
    "format_yaml_dsl_text",
    "lint_yaml_dsl_text",
)
