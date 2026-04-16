# ruff: noqa: T201
from __future__ import annotations

import ast
import argparse
import difflib
import json
import re
import sys
from dataclasses import dataclass
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
UPGRADES_SSOT_DIR_REL = Path("agentdev") / "skills" / "scalim-yaml-dsl" / "references" / "upgrades"


@dataclass(frozen=True)
class _PublicApiEntrypoint:
    order: int
    module: str
    description: str
    common_scenario: str


_PUBLIC_API_ENTRYPOINT_MARKER_RE = re.compile(
    r"^#\s*pragma:\s*scalim-public-api\s+tier(?P<tier>\d+):(?P<order>\d+):(?P<module>[A-Za-z0-9_\\.]+)\|(?P<desc>[^|]*)\|(?P<scenario>.*)$",
    flags=re.IGNORECASE,
)


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


def _is_relative_to(path: Path, maybe_parent: Path) -> bool:
    try:
        path.relative_to(maybe_parent)
    except ValueError:
        return False
    return True


def _iter_py_files(root: Path, *, exclude_dirs: Sequence[Path]) -> Iterable[Path]:
    for path in sorted(root.rglob("*.py")):
        if not path.is_file():
            continue
        if any(_is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        yield path


def _module_name_for_path(path: Path, *, src_root: Path) -> str:
    rel = path.relative_to(src_root)
    if rel.name == "__init__.py":
        rel = rel.parent
    else:
        rel = rel.with_suffix("")
    return ".".join(rel.parts)


def _extract_module_all(path: Path, *, repo_root: Path) -> Tuple[str, ...] | None:
    """返回模块中最后一次出现的 `__all__` 字面量赋值(如果存在)。"""
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(repo_root)).replace("\\", "/")
    tree = ast.parse(text, filename=rel)

    last_value: ast.AST | None = None
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
                last_value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                last_value = node.value

    if last_value is None:
        return None

    if not isinstance(last_value, (ast.List, ast.Tuple)):
        return None

    values: List[str] = []
    for elt in list(last_value.elts):
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            values.append(str(elt.value))
            continue
        return None
    return tuple(values)


def _scan_public_exports(repo_root: Path) -> Dict[str, Tuple[str, ...]]:
    src_root = repo_root / "src"
    scan_root = src_root / "scalim"
    exclude_dirs = (scan_root / "vendor",)

    all_by_module: Dict[str, Tuple[str, ...]] = {}
    for path in _iter_py_files(scan_root, exclude_dirs=exclude_dirs):
        mod = _module_name_for_path(path, src_root=src_root)
        exported = _extract_module_all(path, repo_root=repo_root)
        if exported is None:
            continue
        all_by_module[mod] = exported
    return all_by_module


def _discover_public_api_entrypoints(repo_root: Path, *, tier: int) -> Tuple[_PublicApiEntrypoint, ...]:
    scan_root = repo_root / "src" / "scalim"
    exclude_dirs = (scan_root / "vendor",)

    entrypoints: List[_PublicApiEntrypoint] = []
    errors: List[str] = []

    for path in sorted(scan_root.rglob("__init__.py"), key=lambda p: str(p)):
        if any(_is_relative_to(path, ex) for ex in exclude_dirs):
            continue
        rel = str(path.relative_to(repo_root)).replace("\\", "/")
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            m = _PUBLIC_API_ENTRYPOINT_MARKER_RE.match(line.strip())
            if not m:
                continue
            got_tier = int(m.group("tier"))
            if got_tier != int(tier):
                continue
            module = str(m.group("module") or "").strip()
            desc = str(m.group("desc") or "").strip()
            scenario = str(m.group("scenario") or "").strip()
            order = int(m.group("order"))
            if not module:
                errors.append("{}:{}: missing module".format(rel, lineno))
                continue
            if not desc:
                errors.append("{}:{}: missing description for {}".format(rel, lineno, module))
                continue
            if not scenario:
                errors.append("{}:{}: missing scenario for {}".format(rel, lineno, module))
                continue
            entrypoints.append(
                _PublicApiEntrypoint(
                    order=order,
                    module=module,
                    description=desc,
                    common_scenario=scenario,
                )
            )

    if errors:
        raise RuntimeError("检测到公共 `API` 入口标记不合法(最多展示 20 条):\n{}".format("\n".join("- {}".format(e) for e in errors[:20])))

    by_module: Dict[str, _PublicApiEntrypoint] = {}
    duplicates: List[str] = []
    for entry in entrypoints:
        if entry.module in by_module:
            duplicates.append(entry.module)
            continue
        by_module[entry.module] = entry

    if duplicates:
        raise RuntimeError("检测到重复的公共 `API` 入口标记: {}".format(", ".join(sorted(set(duplicates)))))

    discovered = sorted(by_module.values(), key=lambda e: (int(e.order), str(e.module)))
    if not discovered:
        raise RuntimeError(
            "未找到公共 `API` 入口标记(层级={})。请添加类似如下的标记:\n"
            "`# pragma: scalim-public-api tier1:10:scalim.dsl.yaml_dsl|...|...`".format(tier)
        )
    return tuple(discovered)


def _render_public_api_import_guide(repo_root: Path) -> str:
    exports_by_module = _scan_public_exports(repo_root)
    tier1_entrypoints = _discover_public_api_entrypoints(repo_root, tier=1)

    missing_tier1 = sorted({e.module for e in tier1_entrypoints if e.module not in exports_by_module})
    if missing_tier1:
        raise RuntimeError("入口列表缺少 `__all__`(或无法解析为字面量): {}".format(", ".join(missing_tier1)))

    sources = [
        "`src/scalim/**` module-level `__all__` exports (AST-scanned; excludes `src/scalim/vendor/**`)",
        "`src/scalim/**/__init__.py` markers: `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`",
        "`scripts/check-api-surface-governance.py`",
        "`scripts/check-user-material-import-boundaries.py`",
        "`notebooks/marimo/example_public_api_suite/`",
        "`tests/public_api/`",
    ]

    lines: List[str] = [
        _autogen_md_header(sources=sources).rstrip("\n"),
        "# 公共 API 导入指南（生成）",
        "",
        '??? note "适用读者"',
        "    - 使用方:在 Python 里调用 Scalim,希望导入路径稳定、可回归",
        "    - 贡献者:需要扩展/治理 public API,避免“看起来能 import 但其实是内部实现细节”",
        "",
        "本仓库将“public API”定义为:用户在 Python 侧可稳定导入、并被回归门禁覆盖的一组 `scalim.*` 模块与符号。",
        "核心约束来自三处(约定优先):",
        "",
        "- `__all__` 治理规则(模块内符号级): [`scripts/check-api-surface-governance.py`](#code=scripts/check-api-surface-governance.py)",
        "- 用户材料导入边界(文档/示例/skills): [`scripts/check-user-material-import-boundaries.py`](#code=scripts/check-user-material-import-boundaries.py)",
        "- 示例覆盖(可交互/可对拍): `notebooks/marimo/example_public_api_suite/`(见 [主线教程](demo-big-data-report.md))",
        "",
        "## 1) 推荐导入（Tier 1:稳定入口）",
        "",
        "下表中的模块是我们在文档中明确推荐的稳定入口(约定):优先从这些 facade 模块导入,避免引用内部实现细节。",
        "",
        "| 模块 | `__all__` 导出数 | 说明 | 常见场景 |",
        "| --- | ---: | --- | --- |",
    ]

    for entry in tier1_entrypoints:
        exports = exports_by_module.get(entry.module, ())
        lines.append(
            "| `{}` | {} | {} | {} |".format(
                entry.module,
                len(exports),
                entry.description,
                entry.common_scenario,
            )
        )

    lines.extend(
        [
            "",
            "最常见的“只关心导入”的用法:",
            "",
            "```python",
            "from scalim.dsl.yaml_dsl import RunOverrides, compile, run, run_workflow",
            "```",
            "",
            "需要工具链能力(例如输出配置/基准路径推导)时:",
            "",
            "```python",
            "from scalim.dsl.yaml_dsl.tools import derive_base_module_path, load_output_config",
            "```",
            "",
            "需要 workflow 配置类型/校验能力时:",
            "",
            "```python",
            "from scalim.dsl.yaml_dsl.workflow import WorkflowConfig, load_workflow_config",
            "```",
            "",
            "需要 IR(中间表示)类型时,推荐“模块导入”减少符号级耦合:",
            "",
            "```python",
            "from scalim.spec import ir as ir",
            "```",
            "",
            "需要事件类型/目录查询入口时:",
            "",
            "```python",
            "from scalim.events import Event, EventType, get_event_catalog",
            "```",
            "",
            "需要常用 sinks 时:",
            "",
            "```python",
            "from scalim.sinks import CSVSink",
            "```",
            "",
            "需要内存 sinks(调试/测试/捕获) 时:",
            "",
            "```python",
            "from scalim.sinks.memory import InMemoryRowDataSink",
            "```",
            "",
            "需要 pandas sinks(可选依赖) 时:",
            "",
            "```python",
            "from scalim.sinks.pandas import PandasRowSink",
            "```",
            "",
            "### Tier 1: `__all__` 导出清单（自动生成）",
            "",
            "本节用于对齐“模块内符号级契约”(即 `from <module> import <name>` 的白名单集合)。",
            "",
        ]
    )

    for entry in tier1_entrypoints:
        exports = exports_by_module.get(entry.module, ())
        lines.append("#### `{}`".format(entry.module))
        lines.append("")
        lines.append("- Export count: `{}`".format(len(exports)))
        lines.append("")
        lines.append("```python")
        lines.append("from {} import (".format(entry.module))
        for name in exports:
            lines.append("    {},".format(name))
        lines.append(")")
        lines.append("```")
        lines.append("")

    lines.extend(
        [
            "## 2) 其它可用导入（Tier 2:可用但不在稳定白名单）",
            "",
            "这些模块当前也对外导出了 `__all__`,但**不在 Tier 1 curated 白名单**内:适合高级用户/贡献者使用,但不建议“把它当成稳定入口依赖”。",
            "如果你确实需要依赖它们,建议:",
            "",
            "- pin 版本 + 自己维护回归(尤其是导出面较大的模块)",
            "- 优先通过更上层的稳定入口间接使用(例如优先用 `scalim.dsl.yaml_dsl.*`)",
            "",
            "常见的 Tier 2 模块(非穷举):",
            "",
            "- `scalim.exceptions`:异常 taxonomy",
            "- `scalim.hooks`:hook 扩展点导出",
            "- `scalim.planning`:计划/编排相关导出",
            "- `scalim.execution`:执行相关导出",
            "- `scalim.ob`:observer 相关导出",
            "",
            "## 3) 治理与验收（对贡献者）",
            "",
            "### 3.1 `__all__` 的含义",
            "",
            "- 对外“公开导出”的 **符号级契约**: `from <module> import <name>` 的稳定集合",
            "- 要求 **显式** 定义,避免“无意暴露内部实现”",
            "",
            "### 3.2 治理脚本:禁止隐式暴露内部模块",
            "",
            "`scripts/check-api-surface-governance.py` 强制:",
            "",
            "- `__all__` 不得导出(非 dunder 的) `_name`",
            "- `_internal/` 与 `_*.py` 这类内部实现模块必须显式 `__all__ = []`(或 `()`)封堵导出面",
            "",
            "### 3.3 Tier 1 编目（SSOT）",
            "",
            "Tier 1 curated entrypoints 的 SSOT 不在本生成器里手写维护,而是通过源码注释标注自动发现:",
            "",
            "- 在相关包的 `__init__.py` 内添加一行标注:",
            "  - `# pragma: scalim-public-api tier1:<order>:<module>|<desc>|<scenario>`",
            "- 该行会被 `just gen-docs` 读取并生成本页的 Tier 1 表格与导出清单。",
            "",
            "### 3.4 如何自查",
            "",
            "```bash",
            "python3 scripts/check-api-surface-governance.py --check",
            "python3 scripts/check-user-material-import-boundaries.py --check",
            "pytest -q tests/public_api/test_example_public_api_suite.py --no-cov",
            "just qa",
            "```",
            "",
            "## 4) 结构评估与打分（阶段性）",
            "",
            "**综合评分: 9.1/10**",
            "",
            "理由(摘要):",
            "",
            "- 优点:Tier 1 入口清晰,有 `__all__` 白名单 + gate,回归成本低",
            "- 优点:YAML DSL 运行入口(`scalim.dsl.yaml_dsl`)与 workflow/IR 的稳定导入路径已明确拆出",
            "- 代价:仍有部分 Tier 2 模块导出面偏大/偏“平铺”,但它们不在 curated 白名单内；若需依赖建议自行 pin 版本并维护回归",
            "",
            "导出规模不在文档里维护数值快照:以 `__all__` 治理规则 + 示例覆盖为准。",
            "",
            "## 5) 代价与优化方向（Brainstorming）",
            "",
            "这里的“优化”指结构与治理成本,不是添加新功能。",
            "",
            "### 5.1 主要代价点",
            "",
            "- 部分 Tier 2 模块的导出面仍可能偏大且平铺:",
            "  - 使用方容易“随手 import 一个看起来能用的符号”并形成隐式依赖",
            "  - 贡献者很难判断“删/改一个符号是否 breaking”",
            "",
            "### 5.2 可选优化方向（不落地,仅用于评估）",
            "",
            "1) **文档侧收敛(最低成本)**:保留现状,但把“推荐导入组合”写清楚,并将 Tier 2 明确标为高级入口(本页已做)。",
            "2) **引入更细粒度稳定子模块(中成本,可能 breaking)**:为部分高 churn 的 Tier 2 领域引入稳定分组模块,并把推荐导入从“平铺符号”转向“分组模块”。",
            "3) **收窄导出面(高成本,明确 breaking)**:对代表性的大导出面模块做显式收敛,只保留“长期承诺”的符号;该方向建议用 OpenSpec 变更管理并配合版本策略,避免静默破坏下游。",
            "",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


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
            "`packages/scalim-cli/src/scalim_cli/yaml_dsl.py`",
            "`packages/scalim-misc/src/scalim_misc/cli_docs.py`",
            "`packages/scalim-misc/src/scalim_misc/yaml_dsl_cli_reference_md.py`",
        ]
    ) + render_yaml_dsl_cli_reference_markdown(
        repo_root,
        command_docs,
        generated_by="just gen-docs",
        canonical_example_path="agentdev/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml",
    )

    expected: Dict[Path, str] = {
        docs_dir / "yaml-dsl" / "schema-reference.gen.md": _render_yaml_schema_reference(repo_root),
        cli_reference: cli_reference_content,
        docs_dir / "getting-started" / "public-api.gen.md": _render_public_api_import_guide(repo_root),
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
