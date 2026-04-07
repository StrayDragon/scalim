"""
`scalim-yaml-dsl` skill 生成器.

本模块只负责生成 `artifacts/skills/scalim-yaml-dsl/references/*.gen.*`、
`artifacts/skills/scalim-yaml-dsl/references/generated/`.

生成内容分层如下:
- 语法目录: `src/scalim/dsl/yaml_dsl/schema/demand.gen.json` 与 `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json` 为语法真相
- CLI/LSP 参考: `src/scalim/cli/yaml_dsl.py` 为唯一命令真相
- 规范摘要: `openspec/specs/` 中相关 spec 作为维护来源,自动摘录 requirement 索引
- canonical example: `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`

手工维护的 `SKILL.md` 与非 generated references 一般不由这里写入或重排.
例外: 若存在手工 reference `references/task-upgrade-legacy.md`,生成器会在约定的 marker 区块内
注入“升级批次索引”,用于把 `artifacts/skills/scalim-yaml-dsl/references/upgrades/` 的升级文档同步到 skill 参考中.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from scalim.vendor.yamlx import yaml

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
from scalim.dsl.yaml_dsl._internal.config_parsing.imports import (
    ScalimYamlImportExpansionError,
    contains_import_syntax,
    expand_imports_inplace,
)
from scalim.dsl.yaml_dsl._internal.config_parsing.validator import ConfigValidator
from scalim.dsl.yaml_dsl.runtime.builtin_callables import list_public_builtin_callable_ids
from scalim.dsl.yaml_dsl.schema_dsl import constants as yaml_schema_constants

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

SPEC_SUMMARY_REPLACEMENTS = (
    (
        "workflow schema MUST reject legacy workflow IO fields (`writes`, `workbooks`, `csvs`, `sheetbooks`)",
        "workflow schema MUST reject legacy workflow IO fields",
    ),
    (
        "workflow YAML MUST use `workflow.resources.books` and MUST reject `writes` authoring surface",
        "workflow YAML MUST use `workflow.resources.books` and MUST reject the legacy workflow write authoring surface",
    ),
)

GENERATED_ROOT_REL = Path("references") / "generated"
REFERENCES_ROOT_REL = Path("references")
SYNTAX_CATALOG_REL = REFERENCES_ROOT_REL / "syntax-catalog.gen.md"
CLI_LSP_REFERENCE_REL = GENERATED_ROOT_REL / "cli-lsp-reference.gen.md"
CANONICAL_EXAMPLE_OUTPUT_REL = GENERATED_ROOT_REL / "example-full" / "ecommerce_report.gen.yaml"
UPGRADES_NOTES_REL = GENERATED_ROOT_REL / "yaml-dsl-upgrades.gen.md"

SCHEMA_REL = Path("src") / "scalim" / "dsl" / "yaml_dsl" / "schema" / "demand.gen.json"
WORKFLOW_SCHEMA_REL = Path("src") / "scalim" / "dsl" / "yaml_dsl" / "schema" / "workflow.gen.json"
CLI_SOURCE_REL = Path("src") / "scalim" / "cli" / "yaml_dsl.py"
CANONICAL_EXAMPLE_SOURCE_REL = (
    Path("notebooks") / "marimo" / "demo_big_data_report" / "chapters_of_yaml_dsl" / "declared_yaml_dsl" / "ecommerce_report.yaml"
)

UPGRADES_SSOT_ROOT_REL = Path("artifacts") / "skills" / "scalim-yaml-dsl" / "references" / "upgrades"
UPGRADE_LEGACY_REFERENCE_REL = REFERENCES_ROOT_REL / "task-upgrade-legacy.md"
UPGRADES_INDEX_BEGIN_MARKER = "<!-- BEGIN AUTOGEN:yaml-dsl-upgrades -->"
UPGRADES_INDEX_END_MARKER = "<!-- END AUTOGEN:yaml-dsl-upgrades -->"

SYNTAX_SPEC_RELS = (
    Path("openspec") / "specs" / "yaml-dsl-schema" / "spec.md",
    Path("openspec") / "specs" / "demand-dsl" / "spec.md",
    Path("openspec") / "specs" / "yaml-dsl-workflow" / "spec.md",
    Path("openspec") / "specs" / "yaml-dsl-books-resources" / "spec.md",
    Path("openspec") / "specs" / "yaml-dsl-output-overrides" / "spec.md",
    Path("openspec") / "specs" / "source-relations" / "spec.md",
    Path("openspec") / "specs" / "field-compute" / "spec.md",
    Path("openspec") / "specs" / "source-cache" / "spec.md",
    Path("openspec") / "specs" / "workflow-cache-pool" / "spec.md",
    Path("openspec") / "specs" / "workflow-observability-bridge" / "spec.md",
    Path("openspec") / "specs" / "runtime-pruning" / "spec.md",
    Path("openspec") / "specs" / "loader-retry-policy" / "spec.md",
    Path("openspec") / "specs" / "runtime-guardrails" / "spec.md",
    Path("openspec") / "specs" / "performance-observability" / "spec.md",
    Path("openspec") / "specs" / "output-mode-api" / "spec.md",
)

CLI_SPEC_RELS = (Path("openspec") / "specs" / "yaml-dsl-cli-validation" / "spec.md",)


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


def build_skill(repo_root: Path, output_root: Path) -> List[str]:
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
        SYNTAX_CATALOG_REL: render_syntax_catalog(repo_root, schema, workflow_schema, syntax_specs),
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

    return list_managed_output_files(skill_dir)


def validate_skill(repo_root: Path, output_root: Path) -> bool:
    skill_dir = output_root / SKILL_NAME
    generated_root = skill_dir / GENERATED_ROOT_REL

    if not generated_root.exists():
        print("未找到 `references/generated/` 目录: {}".format(generated_root))
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        build_skill(repo_root, tmp_root)
        tmp_skill_dir = tmp_root / SKILL_NAME

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


def _compact_ws(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _encode_toon(repo_root: Path, value: Any) -> str:
    tool = repo_root / "scripts" / "tool-toon.py"
    if not tool.exists():
        raise GenerationError("缺少 TOON 工具脚本: {}".format(tool))

    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
    cmd = [
        "uv",
        "--preview-features",
        "extra-build-dependencies",
        "run",
        str(tool),
        "encode",
        "--delimiter",
        "tab",
        "--indent",
        "2",
    ]
    proc = subprocess.run(
        cmd,
        input=payload,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or proc.stdout or "").strip()
        raise GenerationError("TOON 编码失败: {}\n{}".format(" ".join(cmd), stderr))
    return proc.stdout


def _wrap_toon_markdown(*, title: str, intro_lines: Sequence[str], toon_text: str) -> str:
    lines = [title, ""]
    lines.extend([line.rstrip() for line in intro_lines if str(line).strip()])
    lines.extend(["", "```toon", toon_text.rstrip(), "```", ""])
    return "\n".join(lines).rstrip() + "\n"


def _collect_schema_constraints(schema_value: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("pattern", "minimum", "maximum", "minItems", "maxItems", "minProperties", "maxProperties"):
        if key in schema_value:
            parts.append("{}={}".format(key, schema_value[key]))

    additional_props = schema_value.get("additionalProperties")
    if additional_props is not None:
        parts.append("additionalProperties={}".format(_compact_ws(describe_inline_schema(additional_props)).replace("`", "")))

    if "items" in schema_value:
        parts.append("items={}".format(_compact_ws(describe_inline_schema(schema_value["items"])).replace("`", "")))

    for variant_key in ("oneOf", "anyOf", "allOf"):
        variants = schema_value.get(variant_key)
        if variants:
            parts.append("{}={}".format(variant_key, len(variants)))

    return "; ".join(parts)


def render_syntax_catalog(
    repo_root: Path,
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

    def _compact_inline(schema_value: Any) -> str:
        return _compact_ws(describe_inline_schema(schema_value)).replace("`", "")

    def _compact_type(schema_value: Dict[str, Any]) -> str:
        return _compact_ws(summarize_schema_type(schema_value)).replace("`", "")

    def _compact_desc(schema_value: Dict[str, Any]) -> Optional[str]:
        desc = schema_value.get("markdownDescription") or schema_value.get("description")
        if not desc:
            return None
        return _compact_ws(desc)

    def _value_or_json(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    def _enum_string(schema_value: Dict[str, Any]) -> Optional[str]:
        enum_values = schema_value.get("enum")
        if not enum_values:
            return None
        return "|".join(str(item) for item in enum_values)

    def _examples_string(schema_value: Dict[str, Any]) -> Optional[str]:
        examples = schema_value.get("examples")
        if not examples:
            return None
        return json.dumps(examples, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    demand_required = set(schema.get("required", []) or [])
    demand_top_fields = [{"name": name, "required": bool(name in demand_required)} for name in top_level_fields]

    builtin_ids = list_public_builtin_callable_ids()
    builtin_ids_rendered = ["^{}".format(item) for item in builtin_ids] if builtin_ids else []

    spec_rows = []
    for summary in spec_summaries:
        spec_rows.append(
            {
                "slug": summary["slug"],
                "path": summary["path"],
                "purpose": _compact_ws(summary.get("purpose", "")),
                "requirements": "\n".join(_compact_ws(item) for item in summary.get("requirements", []) if str(item).strip()),
            }
        )

    entry_rows: List[Dict[str, Any]] = []
    prop_rows: List[Dict[str, Any]] = []

    def _add_entry(*, scope: str, key: str, schema_path: str, schema_value: Dict[str, Any], required: bool) -> None:
        entry_id = len(entry_rows) + 1
        entry_rows.append(
            {
                "id": entry_id,
                "scope": scope,
                "key": key,
                "schema_path": schema_path,
                "required": bool(required),
                "ref": schema_value.get("$ref"),
                "type": _compact_type(schema_value) or None,
                "desc": _compact_desc(schema_value),
                "enum": _enum_string(schema_value),
                "default": _value_or_json(schema_value.get("default")),
                "const": _value_or_json(schema_value.get("const")),
                "examples": _examples_string(schema_value),
                "constraints": _compact_ws(_collect_schema_constraints(schema_value)) or None,
            }
        )

        child_props = schema_value.get("properties")
        if not isinstance(child_props, dict) or not child_props:
            return
        child_required = set(schema_value.get("required", []) or [])
        for child_name in sort_schema_properties(child_props):
            child_schema = child_props[child_name]
            prop_rows.append(
                {
                    "entry_id": entry_id,
                    "name": child_name,
                    "required": bool(child_name in child_required),
                    "summary": _compact_inline(child_schema),
                }
            )

    for field_name in top_level_fields:
        field_schema = properties.get(field_name, {})
        if not isinstance(field_schema, dict):
            field_schema = {}
        _add_entry(
            scope="demand.field",
            key=field_name,
            schema_path="properties.{}".format(field_name),
            schema_value=field_schema,
            required=field_name in demand_required,
        )

    for definition_name in definition_names:
        definition_schema = definitions.get(definition_name, {})
        if not isinstance(definition_schema, dict):
            definition_schema = {}
        _add_entry(
            scope="demand.definition",
            key=definition_name,
            schema_path="definitions.{}".format(definition_name),
            schema_value=definition_schema,
            required=False,
        )

    workflow_required = set(workflow_schema.get("required", []) or [])
    workflow_entry = workflow_schema.get("properties", {}).get("workflow", {})
    workflow_props = workflow_entry.get("properties", {}) if isinstance(workflow_entry, dict) else {}
    runs_schema = workflow_props.get("runs", {}) if isinstance(workflow_props, dict) else {}
    run_item_schema = runs_schema.get("items", {}) if isinstance(runs_schema, dict) else {}
    options_schema = workflow_props.get("options", {}) if isinstance(workflow_props, dict) else {}
    resources_schema = workflow_props.get("resources", {}) if isinstance(workflow_props, dict) else {}
    resource_props = resources_schema.get("properties", {}) if isinstance(resources_schema, dict) else {}
    books_schema = resource_props.get("books", {}) if isinstance(resource_props, dict) else {}

    if isinstance(workflow_entry, dict):
        _add_entry(
            scope="workflow",
            key="workflow",
            schema_path="properties.workflow",
            schema_value=workflow_entry,
            required="workflow" in workflow_required,
        )
    if isinstance(run_item_schema, dict) and run_item_schema:
        _add_entry(
            scope="workflow",
            key="workflow.runs[*]",
            schema_path="properties.workflow.properties.runs.items",
            schema_value=run_item_schema,
            required=False,
        )
    if isinstance(options_schema, dict) and options_schema:
        _add_entry(
            scope="workflow",
            key="workflow.options",
            schema_path="properties.workflow.properties.options",
            schema_value=options_schema,
            required=False,
        )
    if isinstance(resources_schema, dict) and resources_schema:
        _add_entry(
            scope="workflow",
            key="workflow.resources",
            schema_path="properties.workflow.properties.resources",
            schema_value=resources_schema,
            required=False,
        )
    if isinstance(books_schema, dict) and books_schema:
        _add_entry(
            scope="workflow",
            key="workflow.resources.books",
            schema_path="properties.workflow.properties.resources.properties.books",
            schema_value=books_schema,
            required=False,
        )

    toon_data = {
        "generated_by": "scripts/gen-agent-skill.py",
        "sources": {
            "demand_schema": path_to_posix(SCHEMA_REL),
            "workflow_schema": path_to_posix(WORKFLOW_SCHEMA_REL),
            "canonical_example": path_to_posix(CANONICAL_EXAMPLE_OUTPUT_REL),
            "validator": "src/scalim/dsl/yaml_dsl/_internal/config_parsing/validator.py",
        },
        "builtin_callables": builtin_ids_rendered,
        "demand_top_fields": demand_top_fields,
        "demand_definitions": definition_names,
        "openspec_requirement_map": spec_rows,
        "entries": entry_rows,
        "properties": prop_rows,
        "workflow_key_paths": [
            "workflow.runs",
            "workflow.runs[*].id",
            "workflow.runs[*].demand",
            "workflow.runs[*].depends_on",
            "workflow.runs[*].init_vars",
            "workflow.options",
            "workflow.options.ctx",
            "workflow.options.cache_pool",
            "workflow.resources",
            "workflow.resources.books",
        ],
        "workflow_validation": [
            "Repo schema-only: uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>",
            "LSP header: # yaml-language-server: $schema=.../workflow.gen.json OR # $schema: .../workflow.gen.json (use yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>)",
        ],
    }

    intro = [
        "此文档由 `scripts/gen-agent-skill.py` 自动生成.",
        "为节省 token,主体数据以 TOON 格式给出;使用时建议直接复制下方 code block.",
    ]
    toon_text = _encode_toon(repo_root, toon_data)
    return _wrap_toon_markdown(title="# Scalim YAML DSL Syntax Catalog", intro_lines=intro, toon_text=toon_text)


def render_workflow_syntax_catalog(workflow_schema: Dict[str, Any]) -> List[str]:
    top_required = set(workflow_schema.get("required", []) or [])
    workflow_entry = workflow_schema.get("properties", {}).get("workflow", {})
    workflow_required = "workflow" in top_required

    workflow_props = workflow_entry.get("properties", {}) if isinstance(workflow_entry, dict) else {}
    runs_schema = workflow_props.get("runs", {}) if isinstance(workflow_props, dict) else {}
    run_item_schema = runs_schema.get("items", {}) if isinstance(runs_schema, dict) else {}
    run_props = run_item_schema.get("properties", {}) if isinstance(run_item_schema, dict) else {}
    options_schema = workflow_props.get("options", {}) if isinstance(workflow_props, dict) else {}
    resources_schema = workflow_props.get("resources", {}) if isinstance(workflow_props, dict) else {}
    resource_props = resources_schema.get("properties", {}) if isinstance(resources_schema, dict) else {}
    books_schema = resource_props.get("books", {}) if isinstance(resource_props, dict) else {}

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
        "- `workflow.options` (optional; max_concurrency/failure_policy/cache_pool/ctx)",
        "- `workflow.options.ctx` (optional; ctx guardrails)",
        "- `workflow.options.cache_pool` (optional; workflow-scope cache pool)",
        "- `workflow.resources` (optional)",
        "- `workflow.resources.books` (optional; shared Excel book outputs)",
        "",
        "### Validation",
        "- Repo schema-only: `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>`",
        "- LSP header: `# yaml-language-server: $schema=.../workflow.gen.json` 或 `# $schema: .../workflow.gen.json` (推荐用 `yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`)",
        "",
    ]

    if isinstance(workflow_entry, dict):
        lines.extend(render_schema_entry("`workflow`", workflow_entry, required=workflow_required, level=3))
    if isinstance(run_item_schema, dict) and run_item_schema:
        lines.extend(render_schema_entry("`workflow.runs[*]`", run_item_schema, required=False, level=3))
    if isinstance(options_schema, dict) and options_schema:
        lines.extend(render_schema_entry("`workflow.options`", options_schema, required=False, level=3))
    if isinstance(resources_schema, dict) and resources_schema:
        lines.extend(render_schema_entry("`workflow.resources`", resources_schema, required=False, level=3))
    if isinstance(books_schema, dict) and books_schema:
        lines.extend(render_schema_entry("`workflow.resources.books`", books_schema, required=False, level=3))

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

    def _split_upgrade_id(stem: str) -> Tuple[str, str]:
        m = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", stem)
        if not m:
            return "", stem
        return m.group(1), m.group(2)

    def _clean_lines(lines: Sequence[str]) -> Optional[str]:
        cleaned: List[str] = []
        for raw in lines:
            s = str(raw or "").strip()
            s = re.sub(r"^[-*]\s+", "", s)
            s = re.sub(r"^\d+[\.)]\s+", "", s)
            s = _compact_ws(s)
            if not s:
                continue
            cleaned.append(s)
        return "\n".join(cleaned).strip() if cleaned else None

    upgrades = []
    for path in sorted(upgrades_root.glob("*.md"), key=lambda item: item.name):
        if path.name == "index.md":
            continue
        content = read_text(path)
        title = extract_markdown_h1(content) or path.name
        doc_rel = path_to_posix(REFERENCES_ROOT_REL / "upgrades" / path.name)
        date, slug = _split_upgrade_id(path.stem)
        openspec_archive = extract_backtick_path(content, prefix="openspec/changes/archive/") or extract_backtick_path(
            content, prefix="openspec/changes/"
        )
        spec_path = extract_backtick_path(content, prefix="openspec/specs/")

        summary_lines = extract_markdown_section_lines(content, heading_prefix="## 变更摘要", max_lines=16)
        migration_lines = extract_markdown_section_lines(content, heading_prefix="## Migration Checklist", max_lines=24)
        if not migration_lines:
            migration_lines = extract_markdown_section_lines(content, heading_prefix="## 升级建议", max_lines=24)

        upgrades.append(
            {
                "date": date or None,
                "slug": slug,
                "title": title,
                "ssot": doc_rel,
                "openspec": openspec_archive,
                "spec": spec_path,
                "summary": _clean_lines(summary_lines or []),
                "migration": _clean_lines(migration_lines or []),
            }
        )

    toon_data = {
        "generated_by": "scripts/gen-agent-skill.py",
        "source_root": path_to_posix(REFERENCES_ROOT_REL / "upgrades"),
        "upgrades": upgrades,
    }
    intro = [
        "此文档由 `scripts/gen-agent-skill.py` 自动生成,来源: `references/upgrades/`。",
        "为节省 token,主体数据以 TOON 格式给出;使用时建议直接复制下方 code block.",
    ]
    toon_text = _encode_toon(repo_root, toon_data)
    return _wrap_toon_markdown(title="# YAML DSL Upgrades (Generated)", intro_lines=intro, toon_text=toon_text)


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
        purpose = sanitize_spec_summary_text(extract_markdown_section(text, "## Purpose"))
        requirements = []
        for line in text.splitlines():
            if line.startswith("### Requirement:"):
                requirements.append(sanitize_spec_summary_text(line.split(":", 1)[1].strip()))
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


def sanitize_spec_summary_text(text: str) -> str:
    sanitized = text
    for old, new in SPEC_SUMMARY_REPLACEMENTS:
        sanitized = sanitized.replace(old, new)
    return sanitized


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


def path_to_posix(path: Any) -> str:
    return str(path).replace("\\", "/")
