import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from ..vendor.dataclassesx import dataclass

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
    return Path(__file__).resolve().parents[1] / "dsl" / "by_yaml" / "schema"


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


def upsert_schema_modelines_text(
    text: str,
    *,
    schema_modelines: Sequence[str],
    max_scan_lines: int = DEFAULT_MAX_SCAN_LINES,
) -> Tuple[str, bool]:
    newline = "\r\n" if "\r\n" in text else "\n"
    ends_with_newline = text.endswith("\n")

    lines = text.splitlines()
    scan_limit = min(len(lines), max_scan_lines)

    header_end = scan_limit
    for idx in range(scan_limit):
        stripped = lines[idx].strip()

        if not stripped:
            continue

        if stripped.startswith("#"):
            continue

        header_end = idx
        break

    header_lines = [line for line in lines[:header_end] if not _is_schema_modeline(line)]
    while header_lines and not header_lines[0].strip():
        _ = header_lines.pop(0)

    new_lines: List[str] = list(schema_modelines)
    new_lines.append("")
    new_lines.extend(header_lines)
    new_lines.extend(lines[header_end:])

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

    new_text, changed = upsert_schema_modelines_text(text, schema_modelines=schema_modelines, max_scan_lines=max_scan_lines)
    if not changed:
        return UpsertResult(path=path, changed=False)

    try:
        _ = path.write_text(new_text, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return UpsertResult(path=path, changed=False, error="Failed to write: {}".format(exc))

    return UpsertResult(path=path, changed=True)


__all__ = ()
