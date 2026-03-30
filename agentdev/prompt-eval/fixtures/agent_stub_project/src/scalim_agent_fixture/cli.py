from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Callable, List, Optional


def _schema_path() -> Path:
    # Fixture convention: run from the workspace root.
    return Path.cwd().resolve() / "schema" / "demand.gen.json"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _top_level_block_lines(text: str, *, key: str) -> Optional[List[str]]:
    # Very small YAML-ish block extractor (indentation based; good enough for fixtures).
    lines = text.splitlines()
    start: Optional[int] = None
    for idx, line in enumerate(lines):
        if line.startswith("{}:".format(key)) and (line.strip() == "{}:".format(key)):
            start = idx + 1
            break
    if start is None:
        return None

    block: List[str] = []
    for line in lines[start:]:
        if not line.strip():
            block.append(line)
            continue
        if not line.startswith(" ") and not line.startswith("\t"):
            break
        block.append(line)
    return block


def _main_source_block(text: str) -> Optional[List[str]]:
    return _top_level_block_lines(text, key="main_source")


def _fields_block(text: str) -> Optional[List[str]]:
    return _top_level_block_lines(text, key="fields")


def _validate_no_derived_in_main_source(text: str) -> Optional[str]:
    block = _main_source_block(text)
    if not block:
        return None
    for line in block:
        if re.search(r"\b(compute|call_by)\s*:", line):
            return "Derived logic (compute/call_by) must not appear inside `main_source` block."
    return None


def _validate_has_derived_in_top_fields(text: str) -> Optional[str]:
    block = _fields_block(text)
    if not block:
        return "Missing top-level `fields:` block."
    for line in block:
        if re.search(r"\b(compute|call_by)\s*:", line):
            return None
    return "Expected at least one derived field (compute/call_by) under top-level `fields:`."


def _extract_schema_header(text: str) -> Optional[str]:
    for line in text.splitlines()[:20]:
        if "$schema=" not in line:
            continue
        m = re.search(r"\$schema=([^\s]+)", line)
        if m:
            return m.group(1).strip()
    return None


def _cmd_yaml_dsl_schema_path(_args: argparse.Namespace) -> int:
    sys.stdout.write(str(_schema_path()) + "\n")
    return 0


def _cmd_yaml_dsl_schema_validate(args: argparse.Namespace) -> int:
    yaml_path = Path(args.yaml_file).resolve()
    if not yaml_path.exists():
        sys.stderr.write("YAML file not found: {}\n".format(yaml_path))
        return 1
    text = _read_text(yaml_path)
    header = _extract_schema_header(text)
    expected = str(_schema_path())
    if header != expected:
        sys.stderr.write("Schema header mismatch.\n")
        sys.stderr.write("  expected: {}\n".format(expected))
        sys.stderr.write("  observed: {}\n".format(header or "(missing)"))
        return 1
    sys.stdout.write("OK\n")
    return 0


def _cmd_yaml_dsl_validate(args: argparse.Namespace) -> int:
    yaml_path = Path(args.yaml_file).resolve()
    if not yaml_path.exists():
        sys.stderr.write("YAML file not found: {}\n".format(yaml_path))
        return 1
    text = _read_text(yaml_path)

    msg = _validate_no_derived_in_main_source(text)
    if msg:
        sys.stderr.write(msg + "\n")
        return 1

    msg = _validate_has_derived_in_top_fields(text)
    if msg:
        sys.stderr.write(msg + "\n")
        return 1

    sys.stdout.write("OK\n")
    return 0


def _cmd_missing(_args: argparse.Namespace) -> int:
    sys.stderr.write("Unknown command.\n")
    return 2


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog=Path(sys.argv[0]).name)
    subparsers = parser.add_subparsers(dest="command")

    yaml_dsl = subparsers.add_parser("yaml-dsl", help="fixture-only YAML DSL utilities")
    yaml_dsl_sub = yaml_dsl.add_subparsers(dest="yaml_dsl_command")

    validate = yaml_dsl_sub.add_parser("validate", help="fixture validate")
    validate.add_argument("yaml_file")
    validate.set_defaults(func=_cmd_yaml_dsl_validate)

    schema = yaml_dsl_sub.add_parser("schema", help="fixture schema helpers")
    schema_sub = schema.add_subparsers(dest="yaml_dsl_schema_command")

    schema_path = schema_sub.add_parser("path", help="print schema path")
    schema_path.set_defaults(func=_cmd_yaml_dsl_schema_path)

    schema_validate = schema_sub.add_parser("validate", help="fixture schema validate")
    schema_validate.add_argument("yaml_file")
    schema_validate.set_defaults(func=_cmd_yaml_dsl_schema_validate)

    args = parser.parse_args(list(argv) if argv is not None else None)
    func: Callable[[argparse.Namespace], int] = getattr(args, "func", _cmd_missing)
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
