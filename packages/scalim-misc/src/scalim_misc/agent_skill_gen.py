"""
技能生成器说明:
- 使用 `YAML` 注释分区来固定示例类型:
  `# region SCALIM-SKILL:<tag>[:<id>]` ... `# endregion`(标签 `tag` 取值:`minimal`、`advanced`、`relations`、`compute`、`relations-compute`、`example-full`).
- 在 `notebooks/marimo/examples/` 下扫描分区;分区中的 `YAML` 片段必须是合法的 `YAML DSL`.
- 元数据:在 `src/scalim/dsl/by_yaml/schema_dsl/constants.py` 中使用 `_schema_meta(md=..., examples=[...])`,以生成 `markdownDescription`/`examples`,用于 `YAML` `LSP` 悬停提示.
"""

import ast
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from textwrap import dedent, indent
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from scalim.dsl.by_yaml.schema_dsl import constants as yaml_types
from scalim.dsl.by_yaml.schema_dsl.builder import build_demand_schema

SKILL_NAME = "scalim-yaml-dsl"
SKILL_TITLE = "Scalim YAML DSL"
SKILL_DESCRIPTION = (
    "Scalim YAML DSL 使用与排错指南,涵盖 sources/fields/relations/output 等配置. "
    "触发词: scalim dsl, scalim yaml dsl, scalim config, 使用 scalim 框架 yaml dsl 编写需求"
)
FORBIDDEN_NAME_WORDS = {"anthropic", "claude"}
XML_TAG_RE = re.compile(r"<[^>]+>")
ABS_PATH_RE = re.compile(r"(?P<prefix>^|[\s:])(?P<quote>['\"])?(?P<path>(?:/|[A-Za-z]:[\\/])[^'\"\s#]+)(?P=quote)?")
REGION_START_RE = re.compile(
    r"^\s*#\s*region\s+SCALIM-SKILL:(?P<tag>[a-z0-9_-]+)(?::(?P<id>[a-z0-9_.-]+))?\s*$",
    re.IGNORECASE,
)
REGION_END_RE = re.compile(r"^\s*#\s*endregion\s*$", re.IGNORECASE)
ADVANCED_TAGS = {"advanced", "relations", "compute", "relations-compute", "relations_compute"}
YAML_REGION_TAGS = {"minimal", "advanced", "relations", "compute", "relations-compute"}
NOTEBOOKS_EXAMPLES_REL = Path("notebooks") / "marimo" / "examples"

REQUIRED_DSL_KEYS = tuple(yaml_types.DEMAND_SCHEMA_REQUIRED)


class GenerationError(RuntimeError):
    pass


def is_forbidden_output(path: Path) -> bool:
    home = Path.home()
    forbidden_roots = [
        home / ".codex" / "skills",
        home / ".claude" / "skills",
        Path("/etc") / "codex" / "skills",
    ]
    for root in forbidden_roots:
        try:
            path.relative_to(root)
        except ValueError:
            continue
        return True
    return False


def build_skill(repo_root: Path, output_root: Path) -> Dict[str, Any]:
    skill_dir = output_root / SKILL_NAME
    references_dir = skill_dir / "references"
    manifest_path = build_manifest_path(output_root)
    legacy_manifest_path = skill_dir / "build-manifest.json"
    if is_forbidden_output(skill_dir):
        raise GenerationError("拒绝写入到用户技能目录下.")

    schema = build_demand_schema()

    notebook_root = repo_root / NOTEBOOKS_EXAMPLES_REL
    notebook_examples, notebook_sources = extract_yaml_examples_from_marked_files(notebook_root)
    example_full_sections, example_full_sources = extract_skill_sections_from_paths(
        [
            repo_root / NOTEBOOKS_EXAMPLES_REL / "demo_big_data_report" / "README.md",
            repo_root / NOTEBOOKS_EXAMPLES_REL / "demo_big_data_report" / "_loaders.py",
            repo_root / NOTEBOOKS_EXAMPLES_REL / "demo_big_data_report" / "demo_a0_tutor.py",
            repo_root / NOTEBOOKS_EXAMPLES_REL / "demo_big_data_report" / "by_yaml_dsl" / "ecommerce_report.yaml",
        ]
    )
    test_examples = extract_yaml_examples_from_tests(
        [
            repo_root / "tests" / "test_yaml_dsl.py",
            repo_root / "tests" / "test_yaml_converter_transforms.py",
        ]
    )
    minimal_example, advanced_example = select_examples(notebook_examples, test_examples)
    minimal_example, advanced_example = require_examples(
        minimal_example,
        advanced_example,
        notebook_examples,
        test_examples,
    )
    example_full_yaml = require_section(example_full_sections, "example-full", "yaml")

    normalized_minimal, minimal_paths = normalize_paths_in_text(minimal_example, repo_root)
    normalized_advanced, advanced_paths = normalize_paths_in_text(advanced_example, repo_root)
    normalized_full_yaml, full_paths = normalize_paths_in_text(example_full_yaml, repo_root)

    example_full_readme = render_example_full_readme(
        example_full_sections,
        "references/example-full/ecommerce_report.yaml",
        repo_root,
    )
    normalized_example_full_readme, example_full_paths = normalize_paths_in_text(example_full_readme, repo_root)

    dsl_reference_md, coverage_index = render_dsl_reference(schema)

    skill_md = render_skill_md(
        top_level_fields=coverage_index["top_level_fields"],
        minimal_example=normalized_minimal,
        advanced_example=normalized_advanced,
        example_full_readme_path="references/example-full/README.md",
        example_full_yaml_path="references/example-full/ecommerce_report.yaml",
    )

    files: List[Tuple[Path, str]] = [
        (skill_dir / "SKILL.md", skill_md),
        (references_dir / "dsl-reference.md", dsl_reference_md),
        (references_dir / "example-full" / "README.md", normalized_example_full_readme),
        (references_dir / "example-full" / "ecommerce_report.yaml", normalized_full_yaml),
    ]

    for path, content in files:
        write_text(path, content)

    script_outputs: List[Path] = []
    script_inputs: List[Path] = []

    scripts_dir = skill_dir / "scripts"
    if scripts_dir.exists():
        for child in scripts_dir.iterdir():
            if child.is_file():
                child.unlink()
        if not any(scripts_dir.iterdir()):
            scripts_dir.rmdir()

    legacy_examples_dir = references_dir / "examples"
    if legacy_examples_dir.exists():
        for child in sorted(legacy_examples_dir.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        if legacy_examples_dir.exists() and not any(legacy_examples_dir.iterdir()):
            legacy_examples_dir.rmdir()

    legacy_usage_guide = references_dir / "usage-guide.md"
    if legacy_usage_guide.is_file():
        legacy_usage_guide.unlink()

    schema_path = references_dir / "demand.schema.json"
    if schema_path.is_file():
        schema_path.unlink()

    legacy_examples_path = references_dir / "examples.md"
    if legacy_examples_path.is_file():
        legacy_examples_path.unlink()

    if legacy_manifest_path.is_file():
        legacy_manifest_path.unlink()

    manifest = build_manifest(
        repo_root=repo_root,
        skill_dir=skill_dir,
        inputs=[
            repo_root / "src" / "scalim" / "dsl" / "by_yaml" / "schema_dsl" / "constants.py",
        ]
        + notebook_sources
        + example_full_sources
        + script_inputs,
        outputs=[path for path, _ in files] + script_outputs,
        coverage_index=coverage_index,
        path_normalization=dedupe_mappings(minimal_paths + advanced_paths + full_paths + example_full_paths),
    )

    write_text(manifest_path, dump_json(manifest) + "\n")
    return manifest


def validate_skill(repo_root: Path, output_root: Path) -> bool:
    skill_dir = output_root / SKILL_NAME
    manifest_path = build_manifest_path(output_root)
    if not skill_dir.exists():
        print("未找到技能输出目录: {}".format(skill_dir))
        return False
    if not manifest_path.exists():
        print("未找到构建清单: {}".format(manifest_path))
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        build_skill(repo_root, tmp_root)
        tmp_skill_dir = tmp_root / SKILL_NAME
        tmp_manifest_path = build_manifest_path(tmp_root)

        expected_files = list_files(tmp_skill_dir)
        actual_files = list_files(skill_dir)

        if expected_files != actual_files:
            print("输出文件集合不一致.")
            print("期望: {}".format(expected_files))
            print("实际: {}".format(actual_files))
            return False

        for rel_path in expected_files:
            expected_path = tmp_skill_dir / rel_path
            actual_path = skill_dir / rel_path
            if read_bytes(expected_path) != read_bytes(actual_path):
                print("检测到内容漂移: {}".format(rel_path))
                return False
        if read_bytes(tmp_manifest_path) != read_bytes(manifest_path):
            print("检测到内容漂移: {}".format(manifest_path.name))
            return False

    return True


def list_files(root: Path) -> List[str]:
    files = []
    for path in root.rglob("*"):
        if path.is_file():
            files.append(str(path.relative_to(root)))
    return sorted(files)


def render_skill_md(
    top_level_fields: Sequence[str],
    minimal_example: str,
    advanced_example: str,
    example_full_readme_path: str,
    example_full_yaml_path: str,
) -> str:
    frontmatter = "---\nname: {name}\ndescription: {desc}\n---\n\n".format(
        name=SKILL_NAME,
        desc=json.dumps(SKILL_DESCRIPTION, ensure_ascii=False),
    )

    lines = [
        "# {title}".format(title=SKILL_TITLE),
        "",
        "## 使用说明",
        "- 使用 `references/dsl-reference.md` 获取字段/枚举完整说明.",
        "- 使用 `references/example-full/README.md` 了解 loader、约束与完整示例.",
        "- 示例仅存放在 `references/example-full/`",
        "- 校验 YAML(完整): `uv run scalim-cli yaml-dsl validate <file.yaml>`.",
        "- 校验 YAML(schema-only): `uv run scalim-cli yaml-dsl schema validate <file.yaml>`.",
        "- Schema 查询: `scalim-cli yaml-dsl schema show` / `scalim-cli yaml-dsl schema path`.",
        "- 安装(推荐): `uv tool install /path/to/scalim[cli]`.",
        "- 安装(备选): `pip install --user /path/to/scalim[cli]`.",
        "",
        "## 适用场景",
        "- 编写或修改 Scalim YAML DSL 配置.",
        "- 基于 schema/validator 做配置校验.",
        "- 排查 loader、relations 或字段映射错误.",
        "",
        "## 能力范围",
        "- 提供完整 schema 与字段/枚举说明.",
        "- 提供完整可运行示例与真实 loader.",
        "- 提供校验命令指引(完整 + schema-only).",
        "",
        "## 限制",
        "- 不直接执行 Scalim 任务,仅提供指引与参考.",
        "- 示例集保持最小化(仅一个完整示例).",
    ]

    lines.extend(
        [
            "",
            "## 参考文档",
            "- `references/dsl-reference.md` - 字段/枚举完整说明.",
            "- `{}` - 完整示例说明(含 loader 与约束).".format(example_full_readme_path),
            "- `{}` - 完整 YAML 配置示例.".format(example_full_yaml_path),
            "",
            "顶层字段:",
        ]
    )

    for field_name in top_level_fields:
        lines.append("- `{}`".format(field_name))

    validate_frontmatter(SKILL_NAME, SKILL_DESCRIPTION)
    return frontmatter + "\n".join(lines)


def render_dsl_reference(schema: Dict[str, Any]) -> Tuple[str, Dict[str, List[str]]]:
    properties = schema.get("properties", {})
    definitions = schema.get("definitions", {})

    top_level_fields = list(yaml_types.DEMAND_SCHEMA_PROPERTIES_ORDER)
    for key in properties.keys():
        if key not in top_level_fields:
            top_level_fields.append(key)

    definition_names = sorted(definitions.keys())
    coverage_index = {
        "top_level_fields": top_level_fields,
        "definitions": definition_names,
    }

    lines = [
        "# Scalim YAML DSL Reference",
        "",
        "## Coverage Index",
        "Top-level fields:",
    ]
    for name in top_level_fields:
        lines.append("- {}".format(name))

    lines.append("")
    lines.append("Definitions:")
    for name in definition_names:
        lines.append("- {}".format(name))

    lines.extend(["", "## Top-Level Fields"])
    for name in top_level_fields:
        field_schema = properties.get(name, {})
        lines.append(format_schema_entry(name, field_schema))

    lines.extend(["", "## Definitions"])
    for def_name in definition_names:
        lines.append("### {}".format(def_name))
        def_schema = definitions.get(def_name, {})
        def_props = def_schema.get("properties", {})
        if not def_props:
            lines.append("- (no properties)")
            lines.append("")
            continue
        lines.append("Properties:")
        for prop_name in sorted(def_props.keys()):
            lines.append(format_schema_entry(prop_name, def_props[prop_name]))
        lines.append("")

    return "\n".join(lines), coverage_index


def render_example_full_readme(
    sections: Sequence[Dict[str, Optional[str]]],
    yaml_path: str,
    repo_root: Path,
) -> str:
    required_ids = ("loader", "constraints")
    section_map: Dict[str, List[Dict[str, Optional[str]]]] = {}
    for item in sections:
        if item.get("tag") != "example-full":
            continue
        section_id = item.get("id")
        if not section_id:
            continue
        section_map.setdefault(section_id, []).append(
            {
                "text": dedent_block(item["text"] or ""),
                "source": item.get("source"),
            }
        )

    for section_id in required_ids:
        if not section_map.get(section_id):
            raise GenerationError("缺少 `example-full` 分区: '{}'".format(section_id))

    def format_source_comment(source: Optional[str], comment_prefix: str) -> Optional[str]:
        if not source:
            return None
        source_path = Path(source)
        source_text = str(source_path)
        repo_root_str = str(repo_root)
        if source_path.is_absolute() and is_within_repo(source_text, repo_root_str):
            source_text = strip_repo_prefix(source_text, repo_root_str)
        return "{} source: {}".format(comment_prefix, source_text.replace("\\", "/"))

    def join_sections(items: List[Dict[str, Optional[str]]], comment_prefix: str) -> str:
        parts: List[str] = []
        for item in items:
            text = (item.get("text") or "").strip()
            if not text:
                continue
            source_line = format_source_comment(item.get("source"), comment_prefix)
            if source_line:
                parts.append(source_line)
            parts.append(text)
        return "\n\n".join(parts).strip()

    lines = [
        "# 完整 YAML DSL 示例",
        "",
        "当你需要完整 YAML 配置与真实 loader 时使用本示例.",
        "",
        "## 文件",
        "- YAML: `{}`".format(yaml_path),
        "",
        "## Loader 实现 (demo_big_data_report)",
        "```python",
        join_sections(section_map["loader"], "#"),
        "```",
        "",
        "## 框架约束 (校验 + allowlist)",
        "```python",
        join_sections(section_map["constraints"], "#"),
        "```",
    ]

    optional_sections = [
        ("run-yaml", "使用 `run()` 运行", "python"),
    ]
    for section_id, title, language in optional_sections:
        content_items = section_map.get(section_id)
        if not content_items:
            continue
        lines.extend(
            [
                "",
                "## {}".format(title),
                "```{}".format(language),
                join_sections(content_items, "#"),
                "```",
            ]
        )

    return "\n".join(lines) + "\n"


def format_schema_entry(name: str, schema: Dict[str, Any]) -> str:
    description = schema.get("markdownDescription") or schema.get("description", "")
    entry = "- `{}`".format(name)
    if description:
        entry += ": {}".format(description)
    enum_values = schema.get("enum")
    default_value = schema.get("default")
    examples = schema.get("examples")
    if enum_values:
        entry += " (enum: {})".format(", ".join(str(item) for item in enum_values))
    if default_value is not None:
        entry += " (default: {})".format(default_value)
    if examples:
        entry += " (examples: {})".format(format_schema_examples(examples))
    return entry


def format_schema_examples(examples: Any) -> str:
    if not isinstance(examples, list):
        examples = [examples]
    formatted = []
    for item in examples:
        if isinstance(item, str):
            formatted.append("`{}`".format(item))
        else:
            formatted.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
    return ", ".join(formatted)


def dedent_block(text: str) -> str:
    return dedent(text).strip("\n")


def extract_yaml_examples_from_marked_files(
    root: Path,
    exclude_dirs: Optional[Sequence[Path]] = None,
) -> Tuple[List[Dict[str, Optional[str]]], List[Path]]:
    if not root.exists():
        raise GenerationError("未找到示例根目录: {}".format(root))
    examples: List[Dict[str, Optional[str]]] = []
    sources: List[Path] = []
    for path in iter_text_files(root, exclude_dirs=exclude_dirs):
        extracted = extract_skill_regions_from_text(path, read_text(path))
        if extracted:
            yaml_only = [item for item in extracted if item.get("tag") in YAML_REGION_TAGS]
            if not yaml_only:
                continue
            sources.append(path)
            examples.extend(yaml_only)
    return examples, sources


def extract_skill_sections_from_paths(paths: Sequence[Path]) -> Tuple[List[Dict[str, Optional[str]]], List[Path]]:
    sections: List[Dict[str, Optional[str]]] = []
    sources: List[Path] = []
    for path in paths:
        if not path.exists():
            raise GenerationError("未找到技能源文件: {}".format(path))
        extracted = extract_skill_regions_from_text(path, read_text(path))
        if extracted:
            sources.append(path)
            sections.extend(extracted)
    return sections, sources


def require_section(sections: Sequence[Dict[str, Optional[str]]], tag: str, section_id: str) -> str:
    matches = [item["text"] for item in sections if item.get("tag") == tag and item.get("id") == section_id and item.get("text")]
    if not matches:
        raise GenerationError("缺少 SCALIM-SKILL 区块: {}:{}".format(tag, section_id))
    if len(matches) > 1:
        raise GenerationError("发现多个 SCALIM-SKILL 区块: {}:{}".format(tag, section_id))
    return matches[0] or ""


def iter_text_files(root: Path, exclude_dirs: Optional[Sequence[Path]] = None) -> Iterable[Path]:
    allowed = {".md", ".markdown", ".yaml", ".yml", ".py"}
    excluded = [item.resolve() for item in (exclude_dirs or [])]
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if excluded and is_within_any(path, excluded):
            continue
        if path.suffix.lower() not in allowed:
            continue
        yield path


def is_within_any(path: Path, roots: Sequence[Path]) -> bool:
    for root in roots:
        try:
            path.resolve().relative_to(root)
        except ValueError:
            continue
        return True
    return False


def extract_skill_regions_from_text(path: Path, text: str) -> List[Dict[str, Optional[str]]]:
    examples: List[Dict[str, Optional[str]]] = []
    collecting = False
    tag: Optional[str] = None
    section_id: Optional[str] = None
    buffer: List[str] = []
    start_line = 0

    for line_no, line in enumerate(text.splitlines(), 1):
        start_match = REGION_START_RE.match(line)
        end_match = REGION_END_RE.match(line)
        if start_match:
            if collecting:
                raise GenerationError("{} 中第 {} 行出现嵌套的 SCALIM-SKILL 区块".format(path, line_no))
            raw_tag = normalize_skill_tag(start_match.group("tag"))
            if raw_tag not in allowed_skill_tags():
                raise GenerationError("{} 中第 {} 行的 SCALIM-SKILL 标签 '{}' 未知".format(path, line_no, raw_tag))
            collecting = True
            tag = raw_tag
            section_id = normalize_skill_id(start_match.group("id"))
            buffer = []
            start_line = line_no
            continue
        if end_match:
            if not collecting:
                raise GenerationError("{} 中第 {} 行出现未匹配的 SCALIM-SKILL `endregion`".format(path, line_no))
            content = "\n".join(buffer).strip()
            if not content:
                raise GenerationError("{} 中的 SCALIM-SKILL 区块为空(开始于第 {} 行)".format(path, start_line))
            if tag in YAML_REGION_TAGS and not is_dsl_yaml(content):
                raise GenerationError("{} 中的 SCALIM-SKILL 区块不是 YAML DSL(开始于第 {} 行)".format(path, start_line))
            examples.append(build_example(content, tag, section_id=section_id, source=path))
            collecting = False
            tag = None
            section_id = None
            buffer = []
            start_line = 0
            continue
        if collecting:
            buffer.append(line)

    if collecting:
        raise GenerationError("{} 中的 SCALIM-SKILL 区块未闭合(开始于第 {} 行)".format(path, start_line))
    return examples


def normalize_skill_tag(tag: str) -> str:
    tag = tag.strip().lower().replace("_", "-")
    if tag == "relation":
        return "relations"
    return tag


def normalize_skill_id(section_id: Optional[str]) -> Optional[str]:
    if not section_id:
        return None
    return section_id.strip().lower().replace("_", "-")


def allowed_skill_tags() -> Tuple[str, ...]:
    return ("minimal", "advanced", "relations", "compute", "relations-compute", "example-full")


def build_example(
    text: str,
    tag: Optional[str],
    section_id: Optional[str] = None,
    source: Optional[Path] = None,
) -> Dict[str, Optional[str]]:
    payload: Dict[str, Optional[str]] = {"text": text, "tag": tag, "id": section_id}
    if source is not None:
        payload["source"] = str(source)
    return payload


def is_dsl_yaml(text: str) -> bool:
    lowered = text.lower()
    return all(item in lowered for item in REQUIRED_DSL_KEYS)


def select_examples(
    notebook_examples: List[Dict[str, Optional[str]]],
    test_examples: List[Dict[str, Optional[str]]],
) -> Tuple[Optional[Dict[str, Optional[str]]], Optional[Dict[str, Optional[str]]]]:
    notebook_examples = dedupe_examples(notebook_examples)
    test_examples = dedupe_examples(test_examples)

    minimal = None
    advanced = None

    if notebook_examples:
        minimal = choose_tagged_example(notebook_examples, {"minimal"})
        advanced = choose_tagged_example(notebook_examples, ADVANCED_TAGS)
        return minimal, advanced

    minimal = choose_minimal_example(test_examples)
    advanced = choose_relations_compute_example(test_examples)

    if minimal and advanced and normalize_yaml(minimal["text"]) == normalize_yaml(advanced["text"]):
        exclude = {normalize_yaml(minimal["text"])}
        advanced_alt = choose_relations_compute_example(test_examples, exclude)
        if advanced_alt:
            advanced = advanced_alt
        else:
            minimal_alt = choose_minimal_example(test_examples, exclude)
            if minimal_alt:
                minimal = minimal_alt

    return minimal, advanced


def choose_minimal_example(
    examples: List[Dict[str, Optional[str]]],
    exclude: Optional[Iterable[str]] = None,
) -> Optional[Dict[str, Optional[str]]]:
    if not examples:
        return None
    exclude_set = set(exclude or [])
    candidates = [example for example in examples if normalize_yaml(example["text"]) not in exclude_set]
    if not candidates:
        return None
    return min(candidates, key=lambda item: count_non_empty_lines(item["text"]))


def choose_relations_compute_example(
    examples: List[Dict[str, Optional[str]]],
    exclude: Optional[Iterable[str]] = None,
) -> Optional[Dict[str, Optional[str]]]:
    exclude_set = set(exclude or [])
    matches = []
    for example in examples:
        text = example["text"]
        if normalize_yaml(text) in exclude_set:
            continue
        lowered = text.lower()
        if "relations:" in lowered or "compute:" in lowered:
            matches.append(example)
    if matches:
        return min(matches, key=lambda item: count_non_empty_lines(item["text"]))
    return None


def choose_tagged_example(
    examples: List[Dict[str, Optional[str]]],
    tags: Iterable[str],
) -> Optional[Dict[str, Optional[str]]]:
    tag_set = set(tags)
    matches = [example for example in examples if example.get("tag") in tag_set]
    if matches:
        return min(matches, key=lambda item: count_non_empty_lines(item["text"]))
    return None


def require_examples(
    minimal_example: Optional[Dict[str, Optional[str]]],
    advanced_example: Optional[Dict[str, Optional[str]]],
    notebook_examples: List[Dict[str, Optional[str]]],
    test_examples: List[Dict[str, Optional[str]]],
) -> Tuple[str, str]:
    missing = []
    if not minimal_example:
        missing.append("minimal 示例")
    if not advanced_example:
        missing.append("relations/compute 示例")
    if missing:
        if notebook_examples:
            raise GenerationError(
                "`notebooks/marimo/examples` 中缺少 {}(当前找到 {}). "
                "请添加 `# region SCALIM-SKILL:minimal` 与 `# region SCALIM-SKILL:advanced` 区块.".format(
                    ", ".join(missing),
                    len(notebook_examples),
                )
            )
        raise GenerationError(
            "缺少 {}. 请在 `notebooks/marimo/examples/` 下添加 `# region SCALIM-SKILL:minimal` 与 `# region SCALIM-SKILL:advanced` 区块.".format(
                ", ".join(missing)
            )
        )

    minimal_text = minimal_example["text"]
    advanced_text = advanced_example["text"]
    if normalize_yaml(minimal_text) == normalize_yaml(advanced_text):
        raise GenerationError(
            "仅发现 1 个唯一的 YAML DSL 示例(`notebooks`: {}, `tests`: {}). "
            "请再添加一个示例,确保 `minimal` 与 `relations/compute` 示例不同.".format(
                len(notebook_examples),
                len(test_examples),
            )
        )

    return minimal_text, advanced_text


def count_non_empty_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.strip())


def dedupe_examples(examples: List[Dict[str, Optional[str]]]) -> List[Dict[str, Optional[str]]]:
    seen: Dict[str, Dict[str, Optional[str]]] = {}
    for example in examples:
        normalized = normalize_yaml(example["text"])
        existing = seen.get(normalized)
        if existing:
            if example.get("tag") and not existing.get("tag"):
                seen[normalized] = example
            continue
        seen[normalized] = example
    return list(seen.values())


def normalize_paths_in_text(text: str, repo_root: Path) -> Tuple[str, List[Dict[str, Any]]]:
    repo_root_str = str(repo_root)
    mappings: List[Dict[str, Any]] = []
    normalized_lines = []

    for line in text.splitlines():
        line_external = False
        line_mappings: List[Dict[str, Any]] = []

        def repl(match: re.Match) -> str:
            nonlocal line_external
            prefix = match.group("prefix") or ""
            quote = match.group("quote") or ""
            original = match.group("path")
            if original and set(original) == {"/"}:
                return match.group(0)
            normalized, external = normalize_absolute_path(original, repo_root_str)
            if normalized == original:
                return match.group(0)
            line_mappings.append({"original": original, "normalized": normalized, "external": external})
            if external:
                line_external = True
            return "{prefix}{quote}{value}{quote}".format(prefix=prefix, quote=quote, value=normalized)

        new_line = ABS_PATH_RE.sub(repl, line)
        if line_external and "#" not in new_line:
            new_line = new_line + "  # external"
        normalized_lines.append(new_line)
        mappings.extend(line_mappings)

    return "\n".join(normalized_lines), dedupe_mappings(mappings)


def normalize_absolute_path(path: str, repo_root_str: str) -> Tuple[str, bool]:
    if not is_absolute_path(path):
        return path, False
    if is_within_repo(path, repo_root_str):
        rel = strip_repo_prefix(path, repo_root_str)
        normalized = "$REPO_ROOT/" + rel.replace("\\", "/")
        return normalized, False
    basename = path_basename(path)
    normalized = "$LOCAL_PATH/" + basename
    return normalized, True


def is_absolute_path(path: str) -> bool:
    if path.startswith("/"):
        return True
    return bool(re.match(r"^[A-Za-z]:[\\/]", path))


def is_within_repo(path: str, repo_root_str: str) -> bool:
    if not path.startswith(repo_root_str):
        return False
    suffix = path[len(repo_root_str) :]
    return suffix == "" or suffix.startswith("/") or suffix.startswith("\\")


def strip_repo_prefix(path: str, repo_root_str: str) -> str:
    rel = path[len(repo_root_str) :]
    return rel.lstrip("/\\")


def path_basename(path: str) -> str:
    if "\\" in path or re.match(r"^[A-Za-z]:", path):
        import ntpath

        return ntpath.basename(path)
    return os.path.basename(path)


def dedupe_mappings(mappings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = {}
    for mapping in mappings:
        key = mapping["original"]
        if key not in seen:
            seen[key] = mapping
    return [seen[key] for key in sorted(seen.keys())]


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


def build_manifest(
    repo_root: Path,
    skill_dir: Path,
    inputs: Iterable[Path],
    outputs: Iterable[Path],
    coverage_index: Dict[str, List[str]],
    path_normalization: List[Dict[str, Any]],
) -> Dict[str, Any]:
    input_entries = []
    for path in sorted(set(inputs), key=lambda item: str(item)):
        if not path.exists():
            continue
        rel = str(path.relative_to(repo_root))
        input_entries.append({"path": rel, "sha256": sha256_file(path)})

    output_entries = []
    for path in sorted(set(outputs), key=lambda item: str(item)):
        if not path.exists():
            continue
        rel = str(path.relative_to(skill_dir))
        output_entries.append({"path": rel, "sha256": sha256_file(path)})

    manifest = {
        "skill_name": SKILL_NAME,
        "inputs": input_entries,
        "outputs": output_entries,
        "coverage_index": coverage_index,
        "path_normalization": path_normalization,
    }
    return manifest


def build_manifest_path(output_root: Path) -> Path:
    return output_root / "{}.build-manifest.json".format(SKILL_NAME)


def dump_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)


def dump_schema_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if content and not content.endswith("\n"):
        content = content + "\n"
    path.write_text(content, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_yaml(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def extract_yaml_examples_from_tests(paths: Sequence[Path]) -> List[Dict[str, Optional[str]]]:
    examples: List[Dict[str, Optional[str]]] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                func_name = func.id
            elif isinstance(func, ast.Attribute):
                func_name = func.attr
            else:
                func_name = ""
            if func_name != "make_yaml_config":
                continue
            payload = build_yaml_from_call(node)
            if payload:
                examples.append(build_example(payload, None))
    return examples


def build_yaml_from_call(node: ast.Call) -> Optional[str]:
    kwargs: Dict[str, Optional[str]] = {}
    for kw in node.keywords:
        if not kw.arg:
            continue
        value = constant_string(kw.value)
        if value is None:
            continue
        kwargs[kw.arg] = value
    name = kwargs.get("name")
    sources = kwargs.get("sources")
    fields = kwargs.get("fields")
    if not name or not sources:
        return None
    return build_yaml_config(
        name=name,
        sources=sources,
        fields=fields,
        description=kwargs.get("description"),
        main_source=kwargs.get("main_source"),
        relations=kwargs.get("relations"),
    )


def constant_string(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    return None


def build_yaml_config(
    *,
    name: str,
    sources: str,
    fields: Optional[str] = None,
    description: Optional[str] = None,
    main_source: Optional[str] = None,
    relations: Optional[str] = None,
) -> str:
    header_lines = ["name: {}".format(name)]
    if description:
        header_lines.append("description: {}".format(description))

    parts = ["\n".join(header_lines)]
    if main_source:
        parts.append("main_source:\n" + indent(dedent(main_source).strip(), "  "))
    parts.append("sources:\n" + indent(dedent(sources).strip(), "  "))
    if fields:
        parts.append("fields:\n" + indent(dedent(fields).strip(), "  "))
    if relations:
        parts.append("relations:\n" + indent(dedent(relations).strip(), "  "))

    return "\n\n".join(parts) + "\n"
