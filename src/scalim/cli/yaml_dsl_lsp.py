# pragma: allow-non-core-file boundary: cli surface may migrate out; not part of core coverage gate
import re
from io import StringIO
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from ..vendor.dataclassesx import dataclass
from ..vendor.yamlx.ruamel.yaml import YAML

DEFAULT_SCHEMA_TYPE = "demand"
DEFAULT_MAX_SCAN_LINES = 10

_SCHEMA_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")

_INTELLIJ_SCHEMA_PATTERN = re.compile(r"^\s*#\s*\$schema\s*:\s*(?P<ref>.*)\s*$")
_YAML_LANGUAGE_SERVER_SCHEMA_PATTERN = re.compile(r"^\s*#\s*yaml-language-server\s*:\s*\$schema\s*=\s*(?P<ref>.*)\s*$")

COMMENT_STYLE_ALL = "all"
COMMENT_STYLE_JETBRAINS = "jetbrains"
COMMENT_STYLE_REDHAT = "redhat"

COMMENT_STYLE_CHOICES = (
    COMMENT_STYLE_ALL,
    COMMENT_STYLE_JETBRAINS,
    COMMENT_STYLE_REDHAT,
)
DEFAULT_COMMENT_STYLE = COMMENT_STYLE_ALL


def schema_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "dsl" / "yaml_dsl" / "schema"


DEFAULT_SCHEMA_PATH = str(schema_dir())


def resolve_schema_ref(schema_type: str, schema_path: str) -> str:
    schema_type = (schema_type or "").strip() or DEFAULT_SCHEMA_TYPE
    if not _SCHEMA_TYPE_PATTERN.match(schema_type):
        msg = "Invalid schema type: {}".format(schema_type)
        raise ValueError(msg)

    schema_path = (schema_path or "").strip() or DEFAULT_SCHEMA_PATH
    schema_filename = "{}.gen.json".format(schema_type)

    if schema_path.endswith(".json"):
        return schema_path

    if schema_path.startswith(("http://", "https://")):
        base_url = schema_path.rstrip("/")
        return "{}/{}".format(base_url, schema_filename)

    base_dir = Path(schema_path)
    return str(base_dir / schema_filename)


def make_intellij_schema_modeline(schema_ref: str) -> str:
    return "# $schema: {}".format(schema_ref)


def make_yaml_language_server_schema_modeline(schema_ref: str) -> str:
    return "# yaml-language-server: $schema={}".format(schema_ref)


def make_schema_modelines(schema_ref: str, *, comment_style: str) -> List[str]:
    comment_style = (comment_style or "").strip() or DEFAULT_COMMENT_STYLE

    if comment_style == COMMENT_STYLE_ALL:
        return [
            make_yaml_language_server_schema_modeline(schema_ref),
            make_intellij_schema_modeline(schema_ref),
        ]
    if comment_style == COMMENT_STYLE_JETBRAINS:
        return [make_intellij_schema_modeline(schema_ref)]
    if comment_style == COMMENT_STYLE_REDHAT:
        return [make_yaml_language_server_schema_modeline(schema_ref)]

    msg = "Invalid comment style: {} (expected one of: {})".format(comment_style, ", ".join(COMMENT_STYLE_CHOICES))
    raise ValueError(msg)


def _is_schema_modeline(line: str) -> bool:
    return bool(_INTELLIJ_SCHEMA_PATTERN.match(line) or _YAML_LANGUAGE_SERVER_SCHEMA_PATTERN.match(line))


def _roundtrip_noop_text(text: str) -> str:
    """使用仓库内置的 `ruamel.yaml` `rt` `round-trip`,对文本执行 `load`→`dump` 的 `no-op` 字节级幂等门禁。"""
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

    data = yaml_rt.load(text)
    buf = StringIO()
    yaml_rt.dump(data, buf)
    return buf.getvalue()


def _strip_schema_modelines(lines: Sequence[str], *, max_scan_lines: int) -> List[str]:
    scan_limit = min(len(lines), int(max_scan_lines))
    indices = [idx for idx in range(scan_limit) if _is_schema_modeline(lines[idx])]
    if not indices:
        return list(lines)

    start = min(indices)
    end = max(indices)
    if end + 1 < len(lines) and not str(lines[end + 1]).strip():
        end += 1
    return [*lines[:start], *lines[end + 1 :]]


def _roundtrip_noop_gate_error(
    text: str,
    *,
    failure_prefix: str,
    mismatch_message: str,
) -> Optional[str]:
    try:
        dumped = _roundtrip_noop_text(text)
    except Exception as exc:  # noqa: BLE001
        return "{}: {}: {}".format(failure_prefix, type(exc).__name__, exc)
    if dumped != text:
        return mismatch_message
    return None


def _minimal_edit_gate_error(old_text: str, new_text: str, *, max_scan_lines: int) -> Optional[str]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    if _strip_schema_modelines(old_lines, max_scan_lines=max_scan_lines) != _strip_schema_modelines(
        new_lines, max_scan_lines=max_scan_lines
    ):
        return "Refusing to edit: upsert would modify YAML body beyond modeline header"
    return None


def upsert_schema_modelines_text(
    text: str,
    *,
    schema_modelines: Sequence[str],
    max_scan_lines: int = DEFAULT_MAX_SCAN_LINES,
) -> Tuple[str, bool]:
    newline = "\r\n" if "\r\n" in text else "\n"
    ends_with_newline = text.endswith("\n")

    lines = text.splitlines()
    scan_limit = min(len(lines), int(max_scan_lines))

    cleaned_lines: List[str] = []
    for idx, line in enumerate(lines):
        if idx < scan_limit and _is_schema_modeline(line):
            continue
        cleaned_lines.append(line)

    insert_at = 0
    cleaned_scan_limit = min(len(cleaned_lines), int(max_scan_lines))
    for idx in range(cleaned_scan_limit):
        if cleaned_lines[idx].strip() != "---":
            continue
        prefix = cleaned_lines[:idx]
        prefix_nonempty = [line for line in prefix if str(line).strip()]
        prefix_noncomment = [line for line in prefix_nonempty if not str(line).lstrip().startswith("#")]
        if not prefix_noncomment:
            insert_at = idx + 1
        break

    new_lines: List[str] = list(cleaned_lines)
    new_lines[insert_at:insert_at] = list(schema_modelines)

    sep_idx = insert_at + len(schema_modelines)
    if sep_idx < len(new_lines) and str(new_lines[sep_idx]).strip():
        new_lines.insert(sep_idx, "")

    new_text = newline.join(new_lines)
    if ends_with_newline and not new_text.endswith(newline):
        new_text += newline

    return new_text, new_text != text


@dataclass
class UpsertResult:
    path: Path
    changed: bool
    error: Optional[str] = None


def upsert_schema_modelines_file(
    path: Path,
    *,
    schema_modelines: Sequence[str],
    max_scan_lines: int = DEFAULT_MAX_SCAN_LINES,
) -> UpsertResult:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return UpsertResult(path=path, changed=False, error="Failed to read: {}".format(exc))

    error = _roundtrip_noop_gate_error(
        text,
        failure_prefix="Round-trip no-op failed",
        mismatch_message="Refusing to edit: YAML round-trip no-op is not byte-idempotent for this file",
    )
    if error is not None:
        return UpsertResult(path=path, changed=False, error=error)

    new_text, changed = upsert_schema_modelines_text(text, schema_modelines=schema_modelines, max_scan_lines=max_scan_lines)
    if changed:
        error = _minimal_edit_gate_error(text, new_text, max_scan_lines=max_scan_lines)
        if error is not None:
            return UpsertResult(path=path, changed=False, error=error)

        error = _roundtrip_noop_gate_error(
            new_text,
            failure_prefix="Round-trip no-op failed after upsert",
            mismatch_message="Refusing to edit: post-upsert YAML round-trip no-op is not byte-idempotent",
        )
        if error is not None:
            return UpsertResult(path=path, changed=False, error=error)

        try:
            _ = path.write_text(new_text, encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            return UpsertResult(path=path, changed=False, error="Failed to write: {}".format(exc))

    return UpsertResult(path=path, changed=changed)


__all__ = ()
