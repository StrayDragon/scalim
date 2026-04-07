# ruff: noqa: T201
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from scalim.dsl.yaml_dsl.schema_dsl import constants as yaml_schema_constants
from scalim.dsl.yaml_dsl.schema_dsl.doc_texts import SOURCE_FIELD_EXTRACT_MD
from scalim_misc.cli_docs import build_yaml_dsl_command_docs
from scalim_misc.markdown_inject import InjectBlockSpec, replace_markdown_injected_block
from scalim_misc.yaml_dsl_cli_reference_md import (
    DOCS_CLI_MIN_COMMANDS_BEGIN,
    DOCS_CLI_MIN_COMMANDS_END,
    WORKFLOW_CLI_MIN_COMMANDS_BEGIN,
    WORKFLOW_CLI_MIN_COMMANDS_END,
    render_yaml_dsl_cli_min_commands_markdown,
    render_yaml_dsl_cli_reference_markdown,
    render_yaml_dsl_workflow_cli_min_commands_markdown,
)


USER_GUIDE_SOURCE_FIELD_EXTRACT_BEGIN = "<!-- BEGIN AUTOGEN:yaml-dsl-source-field-extract -->"
USER_GUIDE_SOURCE_FIELD_EXTRACT_END = "<!-- END AUTOGEN:yaml-dsl-source-field-extract -->"

UPGRADES_INDEX_BEGIN = "<!-- BEGIN AUTOGEN:yaml-dsl-upgrades-index -->"
UPGRADES_INDEX_END = "<!-- END AUTOGEN:yaml-dsl-upgrades-index -->"
UPGRADES_SSOT_DIR_REL = Path("artifacts") / "skills" / "scalim-yaml-dsl" / "references" / "upgrades"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def _write_text_if_changed(path: Path, content: str) -> bool:
    if content and not content.endswith("\n"):
        content += "\n"
    if path.exists() and path.is_symlink():
        raise RuntimeError("拒绝覆盖软链文件: {}".format(path))
    existing = _read_text(path) if path.exists() else ""
    if existing == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _diff_text(got: str, expected: str, a_name: str, b_name: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            got.splitlines(),
            expected.splitlines(),
            fromfile=a_name,
            tofile=b_name,
            lineterm="",
        )
    )


def _check_exact_text(path: Path, expected: str) -> Tuple[bool, str]:
    got = _read_text(path) if path.exists() else ""
    if got == expected:
        return True, ""
    return False, _diff_text(got, expected, str(path), str(path) + " (expected)")


def _detect_docs_dir(repo_root: Path) -> Path:
    """读取 `docs/zensical.toml` 的 `docs_dir`,失败时回退到 `docs/doc`."""
    zensical_toml = repo_root / "docs" / "zensical.toml"
    default = repo_root / "docs" / "doc"
    if not zensical_toml.exists():
        return default

    text = _read_text(zensical_toml)
    m = re.search(r'^\s*docs_dir\s*=\s*"(.+?)"\s*$', text, flags=re.MULTILINE)
    if not m:
        return default
    raw = m.group(1).strip()
    if not raw:
        return default
    return (zensical_toml.parent / raw).resolve()


def _autogen_md_header(*, sources: Sequence[str]) -> str:
    lines = [
        "<!--",
        "本文件由 `just gen-docs` (scripts/gen-docs.py) 自动生成,请勿手动修改.",
    ]
    if sources:
        lines.append("Sources:")
        for src in sources:
            lines.append("- {}".format(src))
    lines.extend(["-->", ""])
    return "\n".join(lines)


def _collapse_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    return json.loads(text or "{}")


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _schema_ref_name(schema: Dict[str, Any]) -> str:
    ref = str(schema.get("$ref") or "").strip()
    if not ref:
        return ""
    if ref.startswith("#/definitions/"):
        return ref.rsplit("/", 1)[-1]
    return ref


def _schema_kind(schema: Dict[str, Any]) -> str:
    ref_name = _schema_ref_name(schema)
    if ref_name:
        return "ref={}".format(ref_name)

    for key in ("allOf", "oneOf", "anyOf"):
        items = schema.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            item_ref = _schema_ref_name(item)
            if item_ref:
                return "ref={}".format(item_ref)

    type_value = schema.get("type")
    if isinstance(type_value, list):
        type_value = "|".join(str(item) for item in type_value)
    type_text = _collapse_text(type_value)

    if type_text == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            item_kind = _schema_kind(items)
            if item_kind:
                return "array[{}]".format(item_kind)
        return "array"

    if type_text:
        return type_text

    if "enum" in schema:
        return "enum"
    if "properties" in schema or "additionalProperties" in schema:
        return "object"
    return ""


def _render_yaml_schema_reference(repo_root: Path) -> str:
    schema_rel = Path("src") / "scalim" / "dsl" / "yaml_dsl" / "schema" / "demand.gen.json"
    schema_path = repo_root / schema_rel
    schema = _load_json(schema_path)
    workflow_schema_rel = Path("src") / "scalim" / "dsl" / "yaml_dsl" / "schema" / "workflow.gen.json"
    workflow_schema_path = repo_root / workflow_schema_rel
    workflow_schema = _load_json(workflow_schema_path)

    properties = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    ordered: List[str] = []
    for field_name in yaml_schema_constants.DEMAND_SCHEMA_PROPERTIES_ORDER:
        if field_name in properties:
            ordered.append(field_name)
    for field_name in sorted(properties.keys()):
        if field_name not in ordered:
            ordered.append(field_name)

    lines = [
        _autogen_md_header(
            sources=[
                "`{}`".format(str(schema_rel).replace("\\", "/")),
                "`{}`".format(str(workflow_schema_rel).replace("\\", "/")),
                "Schema generator: `just gen-yaml-dsl-schema`",
            ]
        ).rstrip("\n"),
        "# YAML Schema 参考(生成)",
        "",
        "此页用于快速对齐 YAML DSL 的字段集合与 `required` 边界.",
        "",
        "## Top-Level Fields",
    ]
    for field_name in ordered:
        field_schema = properties.get(field_name) or {}
        desc = _collapse_text(field_schema.get("markdownDescription") or field_schema.get("description") or "")
        kind = _schema_kind(field_schema)

        suffix_parts = []
        if kind:
            if kind.startswith("ref="):
                suffix_parts.append(kind)
            else:
                suffix_parts.append("type={}".format(kind))
        if desc:
            suffix_parts.append(desc)
        suffix = ": " + "; ".join(suffix_parts) if suffix_parts else ""
        req = " (required)" if field_name in required else ""
        lines.append("- `{}`{}{}".format(field_name, req, suffix))

    definitions = schema.get("definitions") or {}
    if definitions:
        lines.extend(["", "## Definitions"])
        for name in sorted(definitions.keys()):
            def_schema = definitions.get(name) or {}
            def_desc = _collapse_text(def_schema.get("markdownDescription") or def_schema.get("description") or "")
            def_props = def_schema.get("properties") or {}
            def_required = set(def_schema.get("required") or [])

            lines.extend(["", "### `{}`".format(name)])
            if def_desc:
                lines.extend(["", def_desc])

            if def_required:
                lines.append("")
                lines.append("- Required: {}".format(", ".join("`{}`".format(item) for item in sorted(def_required))))

            for prop_name in sorted(def_props.keys()):
                prop_schema = def_props.get(prop_name) or {}
                prop_desc = _collapse_text(prop_schema.get("description") or prop_schema.get("markdownDescription") or "")
                prop_kind = _schema_kind(prop_schema)

                suffix_parts = []
                if prop_kind:
                    if prop_kind.startswith("ref="):
                        suffix_parts.append(prop_kind)
                    else:
                        suffix_parts.append("type={}".format(prop_kind))
                if "default" in prop_schema:
                    suffix_parts.append("default={}".format(_format_scalar(prop_schema.get("default"))))
                enum_values = prop_schema.get("enum")
                if isinstance(enum_values, list) and enum_values:
                    suffix_parts.append("enum={}".format("|".join(_format_scalar(item) for item in enum_values)))
                if prop_desc:
                    suffix_parts.append(prop_desc)

                suffix = ": " + "; ".join(suffix_parts) if suffix_parts else ""
                req = " (required)" if prop_name in def_required else ""
                lines.append("- `{}`{}{}".format(prop_name, req, suffix))

    workflow_properties = workflow_schema.get("properties") or {}
    workflow_required = set(workflow_schema.get("required") or [])
    workflow_ordered: List[str] = sorted(workflow_properties.keys())

    lines.extend(["", "## Workflow Schema", "", "### Top-Level Fields"])
    for field_name in workflow_ordered:
        field_schema = workflow_properties.get(field_name) or {}
        desc = _collapse_text(field_schema.get("markdownDescription") or field_schema.get("description") or "")
        kind = _schema_kind(field_schema)

        suffix_parts = []
        if kind:
            if kind.startswith("ref="):
                suffix_parts.append(kind)
            else:
                suffix_parts.append("type={}".format(kind))
        if desc:
            suffix_parts.append(desc)
        suffix = ": " + "; ".join(suffix_parts) if suffix_parts else ""
        req = " (required)" if field_name in workflow_required else ""
        lines.append("- `{}`{}{}".format(field_name, req, suffix))

    workflow_definitions = workflow_schema.get("definitions") or {}
    if workflow_definitions:
        lines.extend(["", "### Definitions"])
        for name in sorted(workflow_definitions.keys()):
            def_schema = workflow_definitions.get(name) or {}
            def_desc = _collapse_text(def_schema.get("markdownDescription") or def_schema.get("description") or "")
            def_props = def_schema.get("properties") or {}
            def_required = set(def_schema.get("required") or [])

            lines.extend(["", "#### `{}`".format(name)])
            if def_desc:
                lines.extend(["", def_desc])

            if def_required:
                lines.append("")
                lines.append("- Required: {}".format(", ".join("`{}`".format(item) for item in sorted(def_required))))

            for prop_name in sorted(def_props.keys()):
                prop_schema = def_props.get(prop_name) or {}
                prop_desc = _collapse_text(prop_schema.get("description") or prop_schema.get("markdownDescription") or "")
                prop_kind = _schema_kind(prop_schema)

                suffix_parts = []
                if prop_kind:
                    if prop_kind.startswith("ref="):
                        suffix_parts.append(prop_kind)
                    else:
                        suffix_parts.append("type={}".format(prop_kind))
                if "default" in prop_schema:
                    suffix_parts.append("default={}".format(_format_scalar(prop_schema.get("default"))))
                enum_values = prop_schema.get("enum")
                if isinstance(enum_values, list) and enum_values:
                    suffix_parts.append("enum={}".format("|".join(_format_scalar(item) for item in enum_values)))
                if prop_desc:
                    suffix_parts.append(prop_desc)

                suffix = ": " + "; ".join(suffix_parts) if suffix_parts else ""
                req = " (required)" if prop_name in def_required else ""
                lines.append("- `{}`{}{}".format(prop_name, req, suffix))

    lines.extend(["", "## Notes", "- 完整字段语义以 `scalim-cli yaml-dsl validate` 的运行时行为为准."])
    return "\n".join(lines).rstrip() + "\n"


def _extract_markdown_h1(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def _extract_markdown_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    collecting = False
    buffer = []
    for line in lines:
        if line.startswith(heading):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if not collecting:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        buffer.append(stripped)
    return " ".join(buffer)


def _render_openspec_index(repo_root: Path) -> str:
    specs_root = repo_root / "openspec" / "specs"
    spec_paths = sorted(p for p in specs_root.glob("*/spec.md") if p.is_file())
    entries = []
    for path in spec_paths:
        rel = path.relative_to(repo_root).as_posix()
        slug = path.parent.name
        text = _read_text(path)
        title = _extract_markdown_h1(text) or slug
        purpose = _collapse_text(_extract_markdown_section(text, "## Purpose")) or ""
        status_line = ""
        for line in text.splitlines()[:10]:
            if line.strip().startswith("**状态:"):
                status_line = _collapse_text(line.strip())
                break
        entries.append((slug, title, status_line, purpose, rel))

    lines = [
        _autogen_md_header(sources=["`openspec/specs/*/spec.md`"]).rstrip("\n"),
        "# OpenSpec 索引(生成)",
        "",
        "说明:",
        "- 本页仅做“索引与链接”,不把 `openspec/specs/**` 作为站点页面.",
        "- 规范本体以仓库文件为准,请通过代码链接打开.",
        "",
        "## Specs",
    ]
    for slug, title, status_line, purpose, rel in sorted(entries, key=lambda item: item[0]):
        summary_parts = []
        if status_line:
            summary_parts.append(status_line)
        if purpose:
            summary_parts.append(purpose)
        summary = " ".join(summary_parts).strip()
        lines.extend(
            [
                "",
                "### `{}`".format(slug),
                "- Title: {}".format(title),
                "- Source: [spec.md](#code={})".format(rel),
            ]
        )
        if summary:
            lines.append("- Summary: {}".format(summary))
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_yaml_dsl_upgrades_index(repo_root: Path) -> str:
    ssot_dir = (repo_root / UPGRADES_SSOT_DIR_REL).resolve()
    if not ssot_dir.exists():
        return "- (未发现升级文档)\n"

    docs: List[str] = []
    for path in sorted(ssot_dir.glob("*.md"), key=lambda item: item.name):
        title = _extract_markdown_h1(_read_text(path)) or path.name
        if path.name == "index.md":
            continue
        rel = (UPGRADES_SSOT_DIR_REL / path.name).as_posix()
        docs.append("- [{}](#code={})".format(title, rel))

    if not docs:
        docs.append("- (未发现升级文档)")

    return "\n".join(docs).rstrip() + "\n"


def _cleanup_yaml_dsl_upgrades_dir(docs_dir: Path) -> List[Path]:
    """清空 `upgrades` 生成目录(保留 `index.md`),避免遗留文件导致不一致."""
    upgrades_dir = (docs_dir / "yaml-dsl" / "upgrades").resolve()
    if not upgrades_dir.exists():
        return []

    removed: List[Path] = []
    for path in sorted(upgrades_dir.glob("*.md"), key=lambda item: item.name):
        if path.name == "index.md":
            continue
        path.unlink()
        removed.append(path)
    return removed


def _expected_generated_markdown(repo_root: Path, docs_dir: Path) -> Dict[Path, str]:
    cli_reference = docs_dir / "yaml-dsl" / "cli-reference.gen.md"
    command_docs = build_yaml_dsl_command_docs()
    cli_reference_content = _autogen_md_header(
        sources=[
            "`src/scalim/cli/yaml_dsl.py`",
            "`packages/scalim-misc/src/scalim_misc/cli_docs.py`",
            "`packages/scalim-misc/src/scalim_misc/yaml_dsl_cli_reference_md.py`",
        ]
    ) + render_yaml_dsl_cli_reference_markdown(
        repo_root,
        command_docs,
        generated_by="just gen-docs",
        canonical_example_path="artifacts/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml",
    )

    expected: Dict[Path, str] = {
        docs_dir / "yaml-dsl" / "schema-reference.gen.md": _render_yaml_schema_reference(repo_root),
        cli_reference: cli_reference_content,
        docs_dir / "specs" / "openspec-index.gen.md": _render_openspec_index(repo_root),
    }
    return expected


def _check_generated_markdown(expected: Dict[Path, str], docs_dir: Path) -> List[Tuple[Path, str]]:
    failed: List[Tuple[Path, str]] = []

    existing_gen_md = sorted(p for p in docs_dir.rglob("*.gen.md") if p.is_file())
    expected_paths = sorted(expected.keys())
    unexpected = sorted(set(existing_gen_md) - set(expected_paths))
    if unexpected:
        failed.append(
            (
                docs_dir,
                "unexpected generated markdown files under docs dir:\n"
                + "\n".join("- {}".format(p) for p in unexpected)
                + "\nFix: remove them or add them to `scripts/gen-docs.py`.",
            )
        )

    for path, expected_text in expected.items():
        ok, diff = _check_exact_text(path, expected_text)
        if not ok:
            failed.append((path, diff or "(diff unavailable)"))
    return failed


def _sync_generated_markdown(expected: Dict[Path, str]) -> List[Path]:
    changed: List[Path] = []
    for path, content in expected.items():
        if _write_text_if_changed(path, content):
            changed.append(path)
    return changed


def _expected_injected_docs(repo_root: Path, docs_dir: Path) -> Dict[Path, str]:
    user_guide = docs_dir / "yaml-dsl" / "user-guide.md"
    original = _read_text(user_guide)
    updated = replace_markdown_injected_block(
        original,
        spec=InjectBlockSpec(
            begin_marker=USER_GUIDE_SOURCE_FIELD_EXTRACT_BEGIN,
            end_marker=USER_GUIDE_SOURCE_FIELD_EXTRACT_END,
            label=str(user_guide),
        ),
        content=SOURCE_FIELD_EXTRACT_MD,
    )
    expected: Dict[Path, str] = {user_guide: updated}

    upgrades_index = docs_dir / "yaml-dsl" / "upgrades" / "index.md"
    original = _read_text(upgrades_index)
    updated = replace_markdown_injected_block(
        original,
        spec=InjectBlockSpec(
            begin_marker=UPGRADES_INDEX_BEGIN,
            end_marker=UPGRADES_INDEX_END,
            label=str(upgrades_index),
        ),
        content=_render_yaml_dsl_upgrades_index(repo_root),
    )
    expected[upgrades_index] = updated

    workflow_doc = docs_dir / "yaml-dsl" / "workflow.md"
    original = _read_text(workflow_doc)
    updated = replace_markdown_injected_block(
        original,
        spec=InjectBlockSpec(
            begin_marker=WORKFLOW_CLI_MIN_COMMANDS_BEGIN,
            end_marker=WORKFLOW_CLI_MIN_COMMANDS_END,
            label=str(workflow_doc),
        ),
        content=render_yaml_dsl_workflow_cli_min_commands_markdown(),
    )
    expected[workflow_doc] = updated

    agent_skill_doc = docs_dir / "yaml-dsl" / "agent-skill.md"
    original = _read_text(agent_skill_doc)
    updated = replace_markdown_injected_block(
        original,
        spec=InjectBlockSpec(
            begin_marker=DOCS_CLI_MIN_COMMANDS_BEGIN,
            end_marker=DOCS_CLI_MIN_COMMANDS_END,
            label=str(agent_skill_doc),
        ),
        content=render_yaml_dsl_cli_min_commands_markdown(),
    )
    expected[agent_skill_doc] = updated

    return expected


def _check_injected_docs(expected: Dict[Path, str]) -> List[Tuple[Path, str]]:
    failed: List[Tuple[Path, str]] = []
    for path, expected_text in expected.items():
        ok, diff = _check_exact_text(path, expected_text)
        if not ok:
            failed.append((path, diff or "(diff unavailable)"))
    return failed


def _sync_injected_docs(expected: Dict[Path, str]) -> List[Path]:
    changed: List[Path] = []
    for path, content in expected.items():
        if _write_text_if_changed(path, content):
            changed.append(path)
    return changed


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="生成 docs-site 的受控 `*.gen.*` 与 injected blocks,并提供 drift check.")
    p.add_argument("--check", action="store_true", help="仅检查漂移,不写入文件.")
    args = p.parse_args(list(argv or sys.argv[1:]))

    repo_root = _repo_root()
    docs_dir = _detect_docs_dir(repo_root)

    expected_gen_md = _expected_generated_markdown(repo_root, docs_dir)
    expected_injected = _expected_injected_docs(repo_root, docs_dir)

    if args.check:
        failed: List[Tuple[Path, str]] = []
        failed.extend(_check_generated_markdown(expected_gen_md, docs_dir))
        failed.extend(_check_injected_docs(expected_injected))

        if failed:
            sys.stderr.write("检测到文档生成物漂移:\n")
            for path, diff in failed:
                sys.stderr.write("\n--- {}\n{}\n".format(str(path), diff))
            sys.stderr.write("\n修复: 运行 `just gen-docs`\n")
            return 1

        sys.stdout.write("OK: 文档生成物一致\n")
        return 0

    changed: List[Path] = []
    changed.extend(_cleanup_yaml_dsl_upgrades_dir(docs_dir))
    changed.extend(_sync_generated_markdown(expected_gen_md))
    changed.extend(_sync_injected_docs(expected_injected))

    unique_changed: List[Path] = []
    seen: set[Path] = set()
    for path in changed:
        if path in seen:
            continue
        seen.add(path)
        unique_changed.append(path)
    changed = unique_changed

    if changed:
        sys.stdout.write("已更新:\n")
        for path in changed:
            sys.stdout.write("  - {}\n".format(str(path)))
    else:
        sys.stdout.write("无变更.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
