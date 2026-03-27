"""
`scalim-yaml-dsl` skill 生成器.

本模块只负责生成 `artifacts/skills/scalim-yaml-dsl/references/*.gen.*`、
`artifacts/skills/scalim-yaml-dsl/references/generated/` 与
`scalim-yaml-dsl.build-manifest.json`.

生成内容分层如下:
- 语法目录: `src/scalim/dsl/by_yaml/schema/demand.gen.json` 与 `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 为语法真相
- CLI/LSP 参考: `src/scalim/cli/yaml_dsl.py` 为唯一命令真相
- 规范摘要: `openspec/specs/` 中相关 spec 作为维护来源,自动摘录 requirement 索引
- canonical example: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`

手工维护的 `SKILL.md` 与非 generated references 一般不由这里写入或重排.
例外: 若存在手工 reference `references/task-upgrade-legacy.md`,生成器会在约定的 marker 区块内
注入“升级批次索引”,用于把 `artifacts/skills/scalim-yaml-dsl/references/upgrades/` 的升级文档同步到 skill 参考中.
"""

import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml

from scalim_misc.cli_docs import build_yaml_dsl_command_docs
from scalim_misc.markdown_inject import InjectBlockError, InjectBlockSpec, replace_markdown_injected_block
from scalim_misc.yaml_dsl_cli_reference_md import (
    SKILL_CLI_MIN_COMMANDS_BEGIN,
    SKILL_CLI_MIN_COMMANDS_END,
    render_yaml_dsl_cli_reference_markdown,
    render_yaml_dsl_skill_cli_min_commands_markdown,
)

from scalim import _project_constants
from scalim.cli import yaml_dsl as yaml_dsl_cli
from scalim.dsl.by_yaml.config_parsing.imports import (
    ScalimYamlImportExpansionError,
    contains_import_syntax,
    expand_imports_inplace,
)
from scalim.dsl.by_yaml.config_parsing.validator import ConfigValidator
from scalim.dsl.by_yaml.runtime.builtin_callables import list_public_builtin_callable_ids
from scalim.dsl.by_yaml.schema_dsl import constants as yaml_schema_constants

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

SKILL_NAME = "scalim-yaml-dsl"
SKILL_TITLE = "Scalim YAML DSL"
SKILL_DESCRIPTION = (
    "Scalim YAML DSL 编写、升级、校验、订正与渐进迁移指南. "
    "Use when Codex needs to author or refactor YAML DSL, upgrade legacy config to the current structure, "
    "run schema/full validation, debug CLI/LSP behavior, or plan gradual migration for report scripts."
)
FORBIDDEN_NAME_WORDS = {"anthropic", "claude"}
XML_TAG_RE = re.compile(r"<[^>]+>")

FORBIDDEN_SKILL_ROOTS = (
    Path.home() / ".codex" / "skills",
    Path.home() / ".claude" / "skills",
    Path("/etc") / "codex" / "skills",
)

GENERATED_ROOT_REL = Path("references") / "generated"
REFERENCES_ROOT_REL = Path("references")
SYNTAX_CATALOG_REL = REFERENCES_ROOT_REL / "syntax-catalog.gen.md"
CLI_LSP_REFERENCE_REL = GENERATED_ROOT_REL / "cli-lsp-reference.gen.md"
CANONICAL_EXAMPLE_OUTPUT_REL = GENERATED_ROOT_REL / "example-full" / "ecommerce_report.gen.yaml"
UPGRADES_NOTES_REL = GENERATED_ROOT_REL / "yaml-dsl-upgrades.gen.md"

SCHEMA_REL = Path("src") / "scalim" / "dsl" / "by_yaml" / "schema" / "demand.gen.json"
WORKFLOW_SCHEMA_REL = Path("src") / "scalim" / "dsl" / "by_yaml" / "schema" / "workflow.gen.json"
CLI_SOURCE_REL = Path("src") / "scalim" / "cli" / "yaml_dsl.py"
CANONICAL_EXAMPLE_SOURCE_REL = Path("notebooks") / "marimo" / "demo_big_data_report" / "by_yaml_dsl" / "ecommerce_report.yaml"

UPGRADES_SSOT_ROOT_REL = Path("artifacts") / "skills" / "scalim-yaml-dsl" / "references" / "upgrades"
UPGRADE_LEGACY_REFERENCE_REL = REFERENCES_ROOT_REL / "task-upgrade-legacy.md"
UPGRADES_INDEX_BEGIN_MARKER = "<!-- BEGIN AUTOGEN:yaml-dsl-upgrades -->"
UPGRADES_INDEX_END_MARKER = "<!-- END AUTOGEN:yaml-dsl-upgrades -->"

SYNTAX_SPEC_RELS = (
    Path("openspec") / "specs" / "yaml-dsl-schema" / "spec.md",
    Path("openspec") / "specs" / "demand-dsl" / "spec.md",
    Path("openspec") / "specs" / "yaml-dsl-workflow" / "spec.md",
    Path("openspec") / "specs" / "source-relations" / "spec.md",
    Path("openspec") / "specs" / "field-compute" / "spec.md",
    Path("openspec") / "specs" / "source-cache" / "spec.md",
    Path("openspec") / "specs" / "workflow-cache-pool" / "spec.md",
    Path("openspec") / "specs" / "workflow-shared-output-containers" / "spec.md",
    Path("openspec") / "specs" / "workflow-sheetbook-resources" / "spec.md",
    Path("openspec") / "specs" / "workflow-observability-bridge" / "spec.md",
    Path("openspec") / "specs" / "runtime-pruning" / "spec.md",
    Path("openspec") / "specs" / "loader-retry-policy" / "spec.md",
    Path("openspec") / "specs" / "runtime-guardrails" / "spec.md",
    Path("openspec") / "specs" / "performance-observability" / "spec.md",
    Path("openspec") / "specs" / "output-mode-api" / "spec.md",
)

CLI_SPEC_RELS = (
    Path("openspec") / "specs" / "yaml-dsl-cli-validation" / "spec.md",
    Path("openspec") / "specs" / "yaml-dsl-editor-core" / "spec.md",
)


class GenerationError(RuntimeError):
    pass


def is_forbidden_output(path: Path) -> bool:
    for root in FORBIDDEN_SKILL_ROOTS:
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            continue
        return True
    return False


def build_skill(repo_root: Path, output_root: Path) -> Dict[str, Any]:
    skill_dir = output_root / SKILL_NAME
    if is_forbidden_output(skill_dir):
        raise GenerationError("拒绝写入到用户技能目录下.")

    schema_path = repo_root / SCHEMA_REL
    workflow_schema_path = repo_root / WORKFLOW_SCHEMA_REL
    cli_path = repo_root / CLI_SOURCE_REL
    canonical_example_source = repo_root / CANONICAL_EXAMPLE_SOURCE_REL

    schema = load_json_file(schema_path, "schema")
    workflow_schema = load_json_file(workflow_schema_path, "workflow schema")
    syntax_specs = load_spec_summaries(repo_root, SYNTAX_SPEC_RELS)
    cli_specs = load_spec_summaries(repo_root, CLI_SPEC_RELS)
    command_docs = build_yaml_dsl_command_docs()
    canonical_example_text = build_canonical_example(repo_root)
    canonical_example_fragments = build_canonical_example_fragments(repo_root)
    validate_canonical_example(repo_root, canonical_example_text, fragments=canonical_example_fragments)

    upgrades_root = repo_root / UPGRADES_SSOT_ROOT_REL
    generated_files = {
        SYNTAX_CATALOG_REL: render_syntax_catalog(schema, workflow_schema, syntax_specs),
        CLI_LSP_REFERENCE_REL: render_yaml_dsl_cli_reference_markdown(
            repo_root,
            command_docs,
            generated_by="scripts/gen-agent-skill.py",
            spec_summaries=cli_specs,
            canonical_example_path=path_to_posix(CANONICAL_EXAMPLE_OUTPUT_REL),
        ),
        CANONICAL_EXAMPLE_OUTPUT_REL: canonical_example_text,
        UPGRADES_NOTES_REL: render_yaml_dsl_upgrades_notes(repo_root, upgrades_root),
    }
    for fragment_name, fragment_text in canonical_example_fragments.items():
        fragment_rel = GENERATED_ROOT_REL / "example-full" / fragment_name
        generated_files[fragment_rel] = fragment_text
    sync_generated_files(skill_dir, generated_files)
    sync_upgrade_legacy_reference(repo_root, skill_dir)
    sync_skill_cli_min_commands(skill_dir)

    outputs = [skill_dir / rel_path for rel_path in sorted(generated_files.keys(), key=lambda item: str(item))]
    fragment_inputs = [canonical_example_source.parent / name for name in sorted(canonical_example_fragments)]
    inputs = (
        [schema_path, workflow_schema_path, cli_path, canonical_example_source]
        + fragment_inputs
        + [repo_root / rel for rel in SYNTAX_SPEC_RELS + CLI_SPEC_RELS]
    )

    manifest = build_manifest(
        repo_root=repo_root,
        skill_dir=skill_dir,
        inputs=inputs,
        outputs=outputs,
        coverage_index=build_coverage_index(schema, workflow_schema, syntax_specs, cli_specs, command_docs),
    )
    write_text(build_manifest_path(output_root), dump_json(manifest))
    return manifest


def validate_skill(repo_root: Path, output_root: Path) -> bool:
    skill_dir = output_root / SKILL_NAME
    manifest_path = build_manifest_path(output_root)
    generated_root = skill_dir / GENERATED_ROOT_REL

    if not generated_root.exists():
        print("未找到 `references/generated/` 目录: {}".format(generated_root))
        return False
    if not manifest_path.exists():
        print("未找到构建清单: {}".format(manifest_path))
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        build_skill(repo_root, tmp_root)
        tmp_skill_dir = tmp_root / SKILL_NAME
        tmp_manifest_path = build_manifest_path(tmp_root)
        tmp_generated_root = tmp_skill_dir / GENERATED_ROOT_REL

        expected_files = list_managed_output_files(tmp_skill_dir)
        actual_files = list_managed_output_files(skill_dir)
        if expected_files != actual_files:
            print("受控参考文件集合不一致.")
            print("期望: {}".format(expected_files))
            print("实际: {}".format(actual_files))
            return False

        for rel_path in expected_files:
            expected_path = tmp_skill_dir / rel_path
            actual_path = skill_dir / rel_path
            if read_bytes(expected_path) != read_bytes(actual_path):
                print("检测到受控产物内容漂移: {}".format(rel_path))
                return False

        if read_bytes(tmp_manifest_path) != read_bytes(manifest_path):
            print("检测到内容漂移: {}".format(manifest_path.name))
            return False

    return True


def build_canonical_example(repo_root: Path) -> str:
    source_path = repo_root / CANONICAL_EXAMPLE_SOURCE_REL
    if not source_path.exists():
        raise GenerationError("未找到唯一完整示例来源: {}".format(source_path))

    lines = []
    for raw_line in read_text(source_path).splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("# region SCALIM-SKILL:") or stripped == "# endregion":
            continue
        if stripped.startswith("# yaml-language-server: $schema="):
            continue
        if stripped.startswith("# $schema:"):
            continue
        lines.append(raw_line)

    return "\n".join(lines).strip() + "\n"


def build_canonical_example_fragments(repo_root: Path) -> Dict[str, str]:
    source_path = repo_root / CANONICAL_EXAMPLE_SOURCE_REL
    if not source_path.exists():
        raise GenerationError("未找到唯一完整示例来源: {}".format(source_path))

    try:
        payload = yaml.safe_load(read_text(source_path))
    except Exception as exc:  # noqa: BLE001
        msg = "唯一完整示例 YAML 解析失败: {}: {}".format(type(exc).__name__, exc)
        raise GenerationError(msg)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        return {}

    imports_raw = payload.get("imports")
    if imports_raw is None:
        return {}
    if not isinstance(imports_raw, dict):
        raise GenerationError("唯一完整示例 `imports` 必须为映射: {}".format(source_path))

    fragments: Dict[str, str] = {}
    base_dir = source_path.parent
    for alias, path_raw in sorted(imports_raw.items(), key=lambda item: str(item[0])):
        if not isinstance(alias, str) or not alias.strip():
            raise GenerationError("唯一完整示例 `imports` 的 `alias` 必须为非空字符串: {}".format(source_path))
        if not isinstance(path_raw, str) or not path_raw.strip():
            raise GenerationError("唯一完整示例 `imports.{}` 的路径必须为非空字符串".format(alias))
        fragment_name = str(path_raw).strip()
        if fragment_name.startswith("./"):
            fragment_name = fragment_name[2:]
        if not fragment_name:
            raise GenerationError("唯一完整示例 `imports.{}` 的路径不能为空".format(alias))

        fragment_path = (base_dir / fragment_name).resolve()
        if not fragment_path.exists():
            raise GenerationError("未找到唯一完整示例 `imports` 片段文件: {}".format(fragment_path))

        text = read_text(fragment_path).strip() + "\n"
        fragments[fragment_name] = text
    return fragments


def validate_canonical_example(repo_root: Path, yaml_text: str, *, fragments: Dict[str, str]) -> None:
    schema_path = repo_root / SCHEMA_REL
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        yaml_path = tmp_root / "ecommerce_report.yaml"
        write_text(yaml_path, yaml_text)
        for fragment_name, fragment_text in fragments.items():
            write_text(tmp_root / fragment_name, fragment_text)

        try:
            payload = yaml.safe_load(yaml_text)
        except Exception as exc:  # noqa: BLE001
            msg = "唯一完整示例 YAML 解析失败: {}: {}".format(type(exc).__name__, exc)
            raise GenerationError(msg)
        if payload is None:
            raise GenerationError("唯一完整示例 YAML 为空")
        if not isinstance(payload, dict):
            raise GenerationError("唯一完整示例 `YAML` 根节点必须为映射")

        payload_dict = dict(payload)
        try:
            if contains_import_syntax(payload_dict):
                _ = expand_imports_inplace(payload_dict, yaml_path=yaml_path)
        except ScalimYamlImportExpansionError as exc:
            raise GenerationError("唯一完整示例 `imports` 展开失败: {}".format(exc))

        validator = ConfigValidator(schema_path=str(schema_path))
        report = validator.validate_report(
            payload_dict,
            strict_unknown_fields=True,
            enable_jsonschema_validation=False,
        )
        issues = report.errors() + report.warnings()
        if issues:
            message = issues[0].message if issues else "未知校验错误"
            raise GenerationError("唯一完整示例未通过内部校验: {}".format(message))

        if jsonschema is None:  # pragma: no cover
            raise GenerationError("缺少 `jsonschema` 依赖,无法执行唯一完整示例的 `schema validate` 校验.")

        schema = load_json_file(schema_path, "schema")
        schema_validator = jsonschema.Draft7Validator(schema)
        errors = sorted(schema_validator.iter_errors(payload_dict), key=lambda item: str(list(getattr(item, "absolute_path", []))))
        if errors:
            error = errors[0]
            path = ".".join(str(part) for part in getattr(error, "absolute_path", [])) or "(root)"
            raise GenerationError("唯一完整示例未通过 `schema` 校验: {}: {}".format(path, error.message))


def render_syntax_catalog(
    schema: Dict[str, Any],
    workflow_schema: Dict[str, Any],
    spec_summaries: Sequence[Dict[str, Any]],
) -> str:
    properties = schema.get("properties", {})
    definitions = schema.get("definitions", {})
    top_level_fields = list(yaml_schema_constants.DEMAND_SCHEMA_PROPERTIES_ORDER)
    for key in sorted(properties.keys()):
        if key not in top_level_fields:
            top_level_fields.append(key)

    definition_names = sorted(definitions.keys())

    lines = [
        "# Scalim YAML DSL Syntax Catalog",
        "",
        "此文档由 `scripts/gen-agent-skill.py` 自动生成.",
        "",
        "## Canonical Sources",
        "- Demand schema: `{}`".format(path_to_posix(SCHEMA_REL)),
        "- Workflow schema: `{}`".format(path_to_posix(WORKFLOW_SCHEMA_REL)),
        "- Canonical example: `{}`".format(path_to_posix(CANONICAL_EXAMPLE_OUTPUT_REL)),
        "- Runtime semantic validator: `src/scalim/dsl/by_yaml/config_parsing/validator.py`",
        "",
        "## Builtin Callable IDs (Public)",
    ]
    public_builtin_ids = list_public_builtin_callable_ids()
    if public_builtin_ids:
        for builtin_id in public_builtin_ids:
            lines.append("- `^{}`".format(builtin_id))
    else:
        lines.append("- (none)")

    lines.extend(
        [
            "",
            "> 注: `^<id>` 由运行入口参数 `builtin_callables` 提供词表;此处仅列出默认公开子集(保守暴露).",
            "",
            "## Top-Level Fields",
        ]
    )
    for field_name in top_level_fields:
        is_required = field_name in schema.get("required", [])
        lines.append("- `{}`{}".format(field_name, " (required)" if is_required else ""))

    lines.extend(["", "## Definitions"])
    for definition_name in definition_names:
        lines.append("- `{}`".format(definition_name))

    lines.extend(render_spec_requirement_map("## OpenSpec Requirement Map", spec_summaries))

    lines.extend(["", "## Top-Level Field Details"])
    for field_name in top_level_fields:
        field_schema = properties.get(field_name, {})
        lines.extend(
            render_schema_entry("`{}`".format(field_name), field_schema, required=field_name in schema.get("required", []), level=3)
        )

    lines.extend(["", "## Definition Details"])
    for definition_name in definition_names:
        definition_schema = definitions.get(definition_name, {})
        entry_lines = render_schema_entry("`{}`".format(definition_name), definition_schema, required=False, level=3)
        entry_lines.insert(1, "- Definition path: `definitions.{}`".format(definition_name))
        lines.extend(entry_lines)

    lines.extend(render_workflow_syntax_catalog(workflow_schema))

    return "\n".join(lines).rstrip() + "\n"


def render_workflow_syntax_catalog(workflow_schema: Dict[str, Any]) -> List[str]:
    top_required = set(workflow_schema.get("required", []) or [])
    workflow_entry = workflow_schema.get("properties", {}).get("workflow", {})
    workflow_required = "workflow" in top_required

    workflow_props = workflow_entry.get("properties", {}) if isinstance(workflow_entry, dict) else {}
    runs_schema = workflow_props.get("runs", {}) if isinstance(workflow_props, dict) else {}
    run_item_schema = runs_schema.get("items", {}) if isinstance(runs_schema, dict) else {}
    run_props = run_item_schema.get("properties", {}) if isinstance(run_item_schema, dict) else {}
    writes_schema = run_props.get("writes", {}) if isinstance(run_props, dict) else {}
    options_schema = workflow_props.get("options", {}) if isinstance(workflow_props, dict) else {}
    resources_schema = workflow_props.get("resources", {}) if isinstance(workflow_props, dict) else {}

    lines = [
        "",
        "## Workflow YAML (Generated)",
        "",
        "### Key Paths",
        "- `workflow.runs` (required)",
        "- `workflow.runs[*].id` (required)",
        "- `workflow.runs[*].demand` (required)",
        "- `workflow.runs[*].depends_on` (optional)",
        "- `workflow.runs[*].init_vars` (optional; supports `$ctx` directives)",
        "- `workflow.runs[*].writes` (optional; list of intents)",
        "- `workflow.options` (optional; max_concurrency/failure_policy/cache_pool/ctx)",
        "- `workflow.options.ctx` (optional; ctx guardrails)",
        "- `workflow.options.cache_pool` (optional; workflow-scope cache pool)",
        "- `workflow.resources` (optional; workbooks/csvs/sheetbooks)",
        "- `workflow.resources.workbooks` (optional; shared workbook outputs)",
        "- `workflow.resources.csvs` (optional; shared csv outputs)",
        "- `workflow.resources.sheetbooks` (optional; in-memory sheetbook outputs)",
        "",
        "### Validation",
        "- Repo schema-only: `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>`",
        "- LSP header: `# yaml-language-server: $schema=.../workflow.gen.json` 或 `# $schema: .../workflow.gen.json` (推荐用 `yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`)",
        "",
    ]

    if isinstance(workflow_entry, dict):
        lines.extend(render_schema_entry("`workflow`", workflow_entry, required=workflow_required, level=3))
    if isinstance(run_item_schema, dict) and run_item_schema:
        lines.extend(render_schema_entry("`workflow.runs[*]`", run_item_schema, required=False, level=3))
    if isinstance(writes_schema, dict) and writes_schema:
        lines.extend(render_schema_entry("`workflow.runs[*].writes`", writes_schema, required=False, level=3))
    if isinstance(options_schema, dict) and options_schema:
        lines.extend(render_schema_entry("`workflow.options`", options_schema, required=False, level=3))
    if isinstance(resources_schema, dict) and resources_schema:
        lines.extend(render_schema_entry("`workflow.resources`", resources_schema, required=False, level=3))

    return lines


def sync_skill_cli_min_commands(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return

    original = read_text(skill_md)
    if SKILL_CLI_MIN_COMMANDS_BEGIN not in original and SKILL_CLI_MIN_COMMANDS_END not in original:
        return
    try:
        injected = replace_markdown_injected_block(
            original,
            spec=InjectBlockSpec(
                begin_marker=SKILL_CLI_MIN_COMMANDS_BEGIN,
                end_marker=SKILL_CLI_MIN_COMMANDS_END,
                label=str(skill_md),
            ),
            content=render_yaml_dsl_skill_cli_min_commands_markdown(),
        )
    except InjectBlockError as exc:
        raise GenerationError(str(exc)) from exc

    if injected != original:
        write_text(skill_md, injected)


def sync_upgrade_legacy_reference(repo_root: Path, skill_dir: Path) -> None:
    """将升级批次索引注入到手工 reference 中(若存在)."""
    upgrades_root = repo_root / UPGRADES_SSOT_ROOT_REL
    if not upgrades_root.exists():
        return

    upgrade_reference_path = skill_dir / UPGRADE_LEGACY_REFERENCE_REL
    if not upgrade_reference_path.exists():
        return

    original = read_text(upgrade_reference_path)
    try:
        injected = replace_markdown_injected_block(
            original,
            spec=InjectBlockSpec(
                begin_marker=UPGRADES_INDEX_BEGIN_MARKER,
                end_marker=UPGRADES_INDEX_END_MARKER,
                label=str(upgrade_reference_path),
            ),
            content=render_yaml_dsl_upgrades_index(repo_root, upgrades_root),
        )
    except InjectBlockError as exc:
        raise GenerationError(str(exc)) from exc
    if injected != original:
        write_text(upgrade_reference_path, injected)


def render_yaml_dsl_upgrades_index(repo_root: Path, upgrades_root: Path) -> str:
    docs = []
    for path in sorted(upgrades_root.glob("*.md"), key=lambda item: item.name):
        if path.name == "index.md":
            continue
        title = extract_markdown_h1(read_text(path)) or path.name
        doc_rel = path_to_posix(REFERENCES_ROOT_REL / "upgrades" / path.name)
        content = read_text(path)
        openspec_archive = extract_backtick_path(content, prefix="openspec/changes/archive/") or extract_backtick_path(
            content, prefix="openspec/changes/"
        )
        spec_path = extract_backtick_path(content, prefix="openspec/specs/")
        docs.append(
            {
                "title": title,
                "doc_rel": doc_rel,
                "openspec_archive": openspec_archive,
                "spec_path": spec_path,
            }
        )

    if not docs:
        return "- (未发现升级文档)\n"

    lines = []
    for item in docs:
        lines.append("- {}".format(item["title"]))
        lines.append("  - SSOT: `{}`".format(item["doc_rel"]))
        if item["openspec_archive"]:
            lines.append("  - OpenSpec: `{}`".format(item["openspec_archive"]))
        if item["spec_path"]:
            lines.append("  - Spec: `{}`".format(item["spec_path"]))
    return "\n".join(lines).rstrip() + "\n"


def render_yaml_dsl_upgrades_notes(repo_root: Path, upgrades_root: Path) -> str:
    """从 upgrades 文档提取“变更摘要/迁移清单”片段,供 skill 使用(避免重复维护规则)."""
    if not upgrades_root.exists():
        return "# YAML DSL Upgrades (Generated)\n\n未找到 upgrades 文档目录: `{}`\n".format(
            path_to_posix(upgrades_root.relative_to(repo_root))
        )

    docs = []
    for path in sorted(upgrades_root.glob("*.md"), key=lambda item: item.name):
        if path.name == "index.md":
            continue
        content = read_text(path)
        title = extract_markdown_h1(content) or path.name
        doc_rel = path_to_posix(REFERENCES_ROOT_REL / "upgrades" / path.name)
        openspec_archive = extract_backtick_path(content, prefix="openspec/changes/archive/") or extract_backtick_path(
            content, prefix="openspec/changes/"
        )
        spec_path = extract_backtick_path(content, prefix="openspec/specs/")

        summary_lines = extract_markdown_section_lines(content, heading_prefix="## 变更摘要", max_lines=16)
        migration_lines = extract_markdown_section_lines(content, heading_prefix="## Migration Checklist", max_lines=24)
        if not migration_lines:
            migration_lines = extract_markdown_section_lines(content, heading_prefix="## 升级建议", max_lines=24)

        docs.append(
            {
                "title": title,
                "doc_rel": doc_rel,
                "openspec_archive": openspec_archive,
                "spec_path": spec_path,
                "summary_lines": summary_lines,
                "migration_lines": migration_lines,
            }
        )

    lines = [
        "# YAML DSL Upgrades (Generated)",
        "",
        "此文档由 `scripts/gen-agent-skill.py` 自动生成,来源: `references/upgrades/`。",
        "用于在使用 skill 时快速定位 breaking/migration,避免在多处重复维护易变规则。",
        "",
    ]

    if not docs:
        lines.append("- (未发现升级文档)")
        return "\n".join(lines).rstrip() + "\n"

    for item in docs:
        lines.extend(
            [
                "## {}".format(item["title"]),
                "- SSOT: `{}`".format(item["doc_rel"]),
            ]
        )
        if item["openspec_archive"]:
            lines.append("- OpenSpec: `{}`".format(item["openspec_archive"]))
        if item["spec_path"]:
            lines.append("- Spec: `{}`".format(item["spec_path"]))

        summary = item["summary_lines"] or []
        if summary:
            lines.append("- Summary:")
            lines.extend(["  {}".format(l.strip()) for l in summary])

        migration = item["migration_lines"] or []
        if migration:
            lines.append("- Migration:")
            lines.extend(["  {}".format(l.strip()) for l in migration])

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def extract_markdown_section_lines(text: str, *, heading_prefix: str, max_lines: int) -> List[str]:
    collecting = False
    in_code_block = False
    buffer: List[str] = []
    for line in text.splitlines():
        if line.startswith(heading_prefix):
            collecting = True
            continue
        if collecting and line.startswith("## "):
            break
        if not collecting:
            continue

        stripped = line.rstrip()
        if stripped.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not stripped.strip():
            continue

        buffer.append(stripped)
        if len(buffer) >= max_lines:
            break
    return buffer


def extract_markdown_h1(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return ""


def extract_backtick_path(text: str, *, prefix: str) -> Optional[str]:
    for match in re.finditer(r"`([^`]+)`", text):
        value = match.group(1)
        if value.startswith(prefix):
            return value
    return None


def render_spec_requirement_map(title: str, spec_summaries: Sequence[Dict[str, Any]]) -> List[str]:
    lines = ["", title]
    for summary in spec_summaries:
        lines.extend(
            [
                "### `{}`".format(summary["slug"]),
                "- Source: `{}`".format(summary["path"]),
                "- Purpose: {}".format(summary["purpose"]),
                "- Requirements:",
            ]
        )
        for requirement in summary["requirements"]:
            lines.append("  - {}".format(requirement))
    return lines


def render_schema_entry(title: str, schema: Dict[str, Any], required: bool, level: int) -> List[str]:
    lines = ["{} {}".format("#" * level, title)]
    if required:
        lines.append("- Required: `true`")

    ref = schema.get("$ref")
    if ref:
        lines.append("- `$ref`: `{}`".format(ref))

    type_summary = summarize_schema_type(schema)
    if type_summary:
        lines.append("- Type: {}".format(type_summary))

    description = schema.get("markdownDescription") or schema.get("description")
    if description:
        lines.append("- Description:")
        for item in str(description).strip().splitlines():
            lines.append("  {}".format(item.rstrip()))

    enum_values = schema.get("enum")
    if enum_values:
        lines.append("- Enum: {}".format(", ".join("`{}`".format(item) for item in enum_values)))

    default_value = schema.get("default")
    if default_value is not None:
        lines.append("- Default: `{}`".format(default_value))

    const_value = schema.get("const")
    if const_value is not None:
        lines.append("- Const: `{}`".format(const_value))

    examples = schema.get("examples")
    if examples:
        lines.append("- Examples: {}".format(format_examples(examples)))

    for key in ("pattern", "minimum", "maximum", "minItems", "maxItems", "minProperties", "maxProperties"):
        if key in schema:
            lines.append("- `{}`: `{}`".format(key, schema[key]))

    additional_props = schema.get("additionalProperties")
    if additional_props is not None:
        lines.append("- `additionalProperties`: {}".format(describe_inline_schema(additional_props)))

    if "items" in schema:
        lines.append("- `items`: {}".format(describe_inline_schema(schema["items"])))

    for variant_key in ("oneOf", "anyOf", "allOf"):
        variants = schema.get(variant_key)
        if variants:
            lines.append("- `{}`:".format(variant_key))
            for idx, option in enumerate(variants, 1):
                lines.append("  - {}. {}".format(idx, describe_inline_schema(option)))

    properties = schema.get("properties")
    if properties:
        required_children = set(schema.get("required", []))
        lines.append("- Properties:")
        for child_name in sort_schema_properties(properties):
            child_schema = properties[child_name]
            child_summary = describe_inline_schema(child_schema)
            suffix = " (required)" if child_name in required_children else ""
            lines.append("  - `{}`{}: {}".format(child_name, suffix, child_summary))
    lines.append("")
    return lines


def summarize_schema_type(schema: Dict[str, Any]) -> str:
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        return " | ".join("`{}`".format(item) for item in schema_type)
    if isinstance(schema_type, str):
        return "`{}`".format(schema_type)
    for variant_key in ("oneOf", "anyOf"):
        variants = schema.get(variant_key)
        if not variants:
            continue
        variant_types = []
        for option in variants:
            option_type = option.get("type")
            if isinstance(option_type, str):
                variant_types.append("`{}`".format(option_type))
            elif "$ref" in option:
                variant_types.append("ref `{}`".format(option["$ref"]))
        if variant_types:
            return " | ".join(variant_types)
    return ""


def describe_inline_schema(schema: Any) -> str:
    if isinstance(schema, bool):
        return "`{}`".format(str(schema).lower())
    if not isinstance(schema, dict):
        return "`{}`".format(schema)

    if "$ref" in schema:
        return "ref `{}`".format(schema["$ref"])

    parts = []
    schema_type = summarize_schema_type(schema)
    if schema_type:
        parts.append(schema_type)
    enum_values = schema.get("enum")
    if enum_values:
        parts.append("enum {}".format(", ".join("`{}`".format(item) for item in enum_values)))
    const_value = schema.get("const")
    if const_value is not None:
        parts.append("const `{}`".format(const_value))
    if "properties" in schema:
        parts.append("properties {}".format(", ".join("`{}`".format(key) for key in sort_schema_properties(schema["properties"]))))
    if "items" in schema:
        parts.append("items {}".format(describe_inline_schema(schema["items"])))
    if "oneOf" in schema:
        parts.append("oneOf({})".format(len(schema["oneOf"])))
    if "anyOf" in schema:
        parts.append("anyOf({})".format(len(schema["anyOf"])))
    if "allOf" in schema:
        parts.append("allOf({})".format(len(schema["allOf"])))
    description = schema.get("description")
    if description and not parts:
        parts.append(str(description))
    return ", ".join(parts) if parts else "`object`"


def sort_schema_properties(properties: Dict[str, Any]) -> List[str]:
    ordered = []
    for field_name in yaml_schema_constants.DEMAND_SCHEMA_PROPERTIES_ORDER:
        if field_name in properties:
            ordered.append(field_name)
    for key in sorted(properties.keys()):
        if key not in ordered:
            ordered.append(key)
    return ordered


def format_examples(examples: Any) -> str:
    if not isinstance(examples, list):
        examples = [examples]
    values = []
    for item in examples:
        if isinstance(item, str):
            values.append("`{}`".format(item))
        else:
            values.append("`{}`".format(json.dumps(item, ensure_ascii=False, sort_keys=True)))
    return ", ".join(values)


def load_spec_summaries(repo_root: Path, spec_paths: Sequence[Path]) -> List[Dict[str, Any]]:
    summaries = []
    for rel_path in spec_paths:
        abs_path = repo_root / rel_path
        if not abs_path.exists():
            raise GenerationError("未找到 OpenSpec 文件: {}".format(abs_path))
        text = read_text(abs_path)
        purpose = extract_markdown_section(text, "## Purpose")
        requirements = []
        for line in text.splitlines():
            if line.startswith("### Requirement:"):
                requirements.append(line.split(":", 1)[1].strip())
        if not requirements:
            raise GenerationError("OpenSpec 文件未包含需求条目: {}".format(abs_path))
        summaries.append(
            {
                "slug": rel_path.parent.name,
                "path": path_to_posix(rel_path),
                "purpose": purpose,
                "requirements": requirements,
            }
        )
    return summaries


def extract_markdown_section(text: str, heading: str) -> str:
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


def build_coverage_index(
    schema: Dict[str, Any],
    workflow_schema: Dict[str, Any],
    syntax_specs: Sequence[Dict[str, Any]],
    cli_specs: Sequence[Dict[str, Any]],
    command_docs: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    properties = schema.get("properties", {})
    top_level_fields = list(yaml_schema_constants.DEMAND_SCHEMA_PROPERTIES_ORDER)
    for key in sorted(properties.keys()):
        if key not in top_level_fields:
            top_level_fields.append(key)

    return {
        "top_level_fields": top_level_fields,
        "definitions": sorted(schema.get("definitions", {}).keys()),
        "workflow_fields": build_workflow_field_paths(workflow_schema),
        "syntax_specs": [{"slug": item["slug"], "path": item["path"], "requirements": item["requirements"]} for item in syntax_specs],
        "cli_specs": [{"slug": item["slug"], "path": item["path"], "requirements": item["requirements"]} for item in cli_specs],
        "commands": [" ".join(item["tokens"]) for item in command_docs],
    }


def build_workflow_field_paths(workflow_schema: Dict[str, Any]) -> List[str]:
    """Extract a stable list of key workflow field paths for coverage tracking."""
    workflow_entry = workflow_schema.get("properties", {}).get("workflow", {})
    if not isinstance(workflow_entry, dict):
        return []
    workflow_props = workflow_entry.get("properties", {})
    if not isinstance(workflow_props, dict):
        return []

    paths = ["workflow"]
    for key in ("runs", "options", "resources"):
        if key in workflow_props:
            paths.append("workflow.{}".format(key))

    runs = workflow_props.get("runs", {})
    if isinstance(runs, dict):
        item = runs.get("items", {})
        if isinstance(item, dict):
            item_props = item.get("properties", {})
            if isinstance(item_props, dict):
                for key in ("id", "demand", "depends_on", "init_vars", "writes"):
                    if key in item_props:
                        paths.append("workflow.runs[*].{}".format(key))

    options = workflow_props.get("options", {})
    if isinstance(options, dict):
        option_props = options.get("properties", {})
        if isinstance(option_props, dict):
            for key in ("max_concurrency", "failure_policy", "cache_pool", "ctx"):
                if key in option_props:
                    paths.append("workflow.options.{}".format(key))

    resources = workflow_props.get("resources", {})
    if isinstance(resources, dict):
        res_props = resources.get("properties", {})
        if isinstance(res_props, dict):
            for key in ("workbooks", "csvs", "sheetbooks"):
                if key in res_props:
                    paths.append("workflow.resources.{}".format(key))

    return paths


def sync_generated_files(skill_dir: Path, generated_files: Dict[Path, str]) -> None:
    generated_root = skill_dir / GENERATED_ROOT_REL
    references_root = skill_dir / REFERENCES_ROOT_REL
    expected_paths = {skill_dir / rel_path for rel_path in generated_files}

    if generated_root.exists():
        for path in sorted(generated_root.rglob("*"), key=lambda item: str(item), reverse=True):
            if path.is_file() and path not in expected_paths:
                path.unlink()
            elif path.is_dir() and not any(path.iterdir()):
                path.rmdir()

    if references_root.exists():
        for path in sorted(references_root.glob("*.gen.md"), key=lambda item: str(item), reverse=True):
            if path.is_file() and path not in expected_paths:
                path.unlink()

    for rel_path, content in generated_files.items():
        write_text(skill_dir / rel_path, content)


def build_manifest(
    repo_root: Path,
    skill_dir: Path,
    inputs: Iterable[Path],
    outputs: Iterable[Path],
    coverage_index: Dict[str, Any],
) -> Dict[str, Any]:
    input_entries = []
    for path in sorted(set(inputs), key=lambda item: str(item)):
        if not path.exists():
            continue
        input_entries.append({"path": path_to_posix(path.relative_to(repo_root)), "sha256": sha256_file(path)})

    output_entries = []
    for path in sorted(set(outputs), key=lambda item: str(item)):
        if not path.exists():
            continue
        output_entries.append({"path": path_to_posix(path.relative_to(skill_dir)), "sha256": sha256_file(path)})

    return {
        "skill_name": SKILL_NAME,
        "inputs": input_entries,
        "outputs": output_entries,
        "coverage_index": coverage_index,
    }


def build_manifest_path(output_root: Path) -> Path:
    return output_root / "{}.build-manifest.json".format(SKILL_NAME)


def list_files(root: Path, base: Optional[Path] = None) -> List[str]:
    if base is None:
        base = root
    items = []
    for path in root.rglob("*"):
        if path.is_file():
            items.append(path_to_posix(path.relative_to(base)))
    return sorted(items)


def list_managed_output_files(skill_dir: Path) -> List[str]:
    items = []
    generated_root = skill_dir / GENERATED_ROOT_REL
    references_root = skill_dir / REFERENCES_ROOT_REL

    if generated_root.exists():
        items.extend(list_files(generated_root, base=skill_dir))
    if references_root.exists():
        for path in references_root.glob("*.gen.md"):
            if path.is_file():
                items.append(path_to_posix(path.relative_to(skill_dir)))
    return sorted(set(items))


def load_json_file(path: Path, label: str) -> Dict[str, Any]:
    if not path.exists():
        raise GenerationError("未找到 {} 文件: {}".format(label, path))
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise GenerationError("{} JSON 无法解析: {}".format(label, path)) from exc


def dump_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def validate_frontmatter(name: str, description: str) -> None:
    if not name or len(name) > 64:
        raise GenerationError("技能名称长度不合法.")
    if name.lower() != name:
        raise GenerationError("技能名称必须为小写.")
    if not re.match(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", name):
        raise GenerationError("技能名称只能包含小写字母、数字与连字符(-).")
    if "--" in name:
        raise GenerationError("技能名称不能包含连续连字符(--).")
    if any(word in name for word in FORBIDDEN_NAME_WORDS):
        raise GenerationError("技能名称包含保留词.")
    if XML_TAG_RE.search(name):
        raise GenerationError("技能名称不能包含 XML 标签.")
    if not description or len(description) > 1024:
        raise GenerationError("技能描述长度不合法.")
    if XML_TAG_RE.search(description):
        raise GenerationError("技能描述不能包含 XML 标签.")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if content and not content.endswith("\n"):
        content += "\n"
    path.write_text(content, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_to_posix(path: Any) -> str:
    return str(path).replace("\\", "/")
