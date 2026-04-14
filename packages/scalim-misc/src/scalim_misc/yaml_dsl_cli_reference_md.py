from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from scalim_cli import yaml_dsl as yaml_dsl_cli

from scalim import _project_constants

DEMAND_SCHEMA_REL = Path("src") / "scalim" / "dsl" / "yaml_dsl" / "schema" / "demand.gen.json"
WORKFLOW_SCHEMA_REL = Path("src") / "scalim" / "dsl" / "yaml_dsl" / "schema" / "workflow.gen.json"
CLI_SOURCE_REL = Path("packages") / "scalim-cli" / "src" / "scalim_cli" / "yaml_dsl.py"
CLI_DIST_NAME = "{}-cli".format(_project_constants.DIST_NAME)

DOCS_CLI_MIN_COMMANDS_BEGIN = "<!-- BEGIN AUTOGEN:yaml-dsl-cli-min-commands -->"
DOCS_CLI_MIN_COMMANDS_END = "<!-- END AUTOGEN:yaml-dsl-cli-min-commands -->"

WORKFLOW_CLI_MIN_COMMANDS_BEGIN = "<!-- BEGIN AUTOGEN:yaml-dsl-workflow-cli-min-commands -->"
WORKFLOW_CLI_MIN_COMMANDS_END = "<!-- END AUTOGEN:yaml-dsl-workflow-cli-min-commands -->"

SKILL_CLI_MIN_COMMANDS_BEGIN = "<!-- BEGIN AUTOGEN:yaml-dsl-skill-cli-min-commands -->"
SKILL_CLI_MIN_COMMANDS_END = "<!-- END AUTOGEN:yaml-dsl-skill-cli-min-commands -->"


class YamlDslCliReferenceError(RuntimeError):
    pass


def _path_to_posix(path: Any) -> str:
    return str(path).replace("\\", "/")


def _render_spec_requirement_map(title: str, spec_summaries: Sequence[Dict[str, Any]]) -> List[str]:
    if not spec_summaries:
        return []
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


def _assert_default_schema_path_is_repo_relative(repo_root: Path) -> None:
    default_schema_path = yaml_dsl_cli._default_schema_path().resolve()  # noqa: SLF001
    try:
        default_schema_repo_rel = _path_to_posix(default_schema_path.relative_to(repo_root))
    except ValueError as exc:
        msg = "CLI 默认 `schema` 路径不在仓库内: {}".format(default_schema_path)
        raise YamlDslCliReferenceError(msg) from exc

    expected = _path_to_posix(DEMAND_SCHEMA_REL)
    if default_schema_repo_rel != expected:
        msg = "CLI 默认 `schema` 路径与规范 `schema` 文件不一致: {}".format(default_schema_repo_rel)
        raise YamlDslCliReferenceError(msg)


def render_yaml_dsl_cli_reference_markdown(
    repo_root: Path,
    command_docs: Sequence[Dict[str, Any]],
    *,
    generated_by: str,
    spec_summaries: Sequence[Dict[str, Any]] = (),
    canonical_example_path: Optional[str] = None,
) -> str:
    """Render a full Markdown CLI/LSP reference for YAML DSL.

    `command_docs` MUST come from the CLI parser recording (SSOT).
    """
    _assert_default_schema_path_is_repo_relative(repo_root)

    repo_schema_path = _path_to_posix(DEMAND_SCHEMA_REL)
    workflow_repo_schema_path = _path_to_posix(WORKFLOW_SCHEMA_REL)

    lines = [
        "# Scalim YAML DSL CLI and LSP Reference",
        "",
        "此文档由 `{}` 自动生成.".format(generated_by),
        "",
        "## Canonical Sources",
        "- CLI implementation: `{}`".format(_path_to_posix(CLI_SOURCE_REL)),
        "- Project identity constants: `src/scalim/_project_constants.py`",
        "- Demand schema file: `{}`".format(repo_schema_path),
        "- Workflow schema file: `{}`".format(workflow_repo_schema_path),
    ]
    if canonical_example_path:
        lines.append("- Canonical example: `{}`".format(_path_to_posix(canonical_example_path)))

    lines.extend(
        [
            "",
            "## Command Variants",
            "### Repo",
            "- `uv run {cli} yaml-dsl validate <file.yaml>`".format(cli=_project_constants.CLI_NAME),
            "- `uv run {cli} yaml-dsl validate --type workflow <workflow.yaml>`".format(cli=_project_constants.CLI_NAME),
            "- `uv run {cli} yaml-dsl schema validate <file.yaml>`".format(cli=_project_constants.CLI_NAME),
            "- `uv run {cli} yaml-dsl schema validate --schema {workflow_schema} <workflow.yaml>`".format(
                cli=_project_constants.CLI_NAME,
                workflow_schema=workflow_repo_schema_path,
            ),
            "- `uv run {cli} yaml-dsl schema show`".format(cli=_project_constants.CLI_NAME),
            "- `uv run {cli} yaml-dsl schema path`".format(cli=_project_constants.CLI_NAME),
            "- `uv run {cli} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`".format(
                cli=_project_constants.CLI_NAME
            ),
            "- `uv run {cli} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`".format(
                cli=_project_constants.CLI_NAME
            ),
            "",
            "### External",
            '- `uvx --from "{dist}" {cli} yaml-dsl validate <file.yaml>`'.format(
                dist=CLI_DIST_NAME,
                cli=_project_constants.CLI_NAME,
            ),
            '- `uvx --from "{dist}" {cli} yaml-dsl validate --type workflow <workflow.yaml>`'.format(
                dist=CLI_DIST_NAME,
                cli=_project_constants.CLI_NAME,
            ),
            '- `uvx --from "{dist}" {cli} yaml-dsl schema validate <file.yaml>`'.format(
                dist=CLI_DIST_NAME,
                cli=_project_constants.CLI_NAME,
            ),
            '- `uvx --from "{dist}" {cli} yaml-dsl schema show`'.format(
                dist=CLI_DIST_NAME,
                cli=_project_constants.CLI_NAME,
            ),
            '- `uvx --from "{dist}" {cli} yaml-dsl schema path`'.format(
                dist=CLI_DIST_NAME,
                cli=_project_constants.CLI_NAME,
            ),
            '- `uvx --from "{dist}" {cli} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`'.format(
                dist=CLI_DIST_NAME,
                cli=_project_constants.CLI_NAME,
            ),
            '- `uvx --from "{dist}" {cli} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`'.format(
                dist=CLI_DIST_NAME,
                cli=_project_constants.CLI_NAME,
            ),
            "",
            "## Validate Layering",
            "- `yaml-dsl validate --type demand`: 使用 internal validator,更适合语义校验、旧写法迁移收敛与输出路径定位.",
            (
                "- `yaml-dsl validate --type workflow`: 静态/编译期 workflow 校验,递归校验 workflow 引用的 demands,"
                "并检查 outputs/books 绑定一致性."
            ),
            "- `yaml-dsl validate` 默认 `--type auto`: 根据 YAML 顶层结构推断 demand/workflow;CI/脚本建议显式传 `--type workflow`.",
            "- `yaml-dsl schema validate`: 使用 JSON Schema,更适合 schema-only 校验、编辑器/LSP 对齐与 unknown-field strict 收敛.",
            "",
            "## LSP / Schema Header",
            "- Repo schema path: `{}`".format(repo_schema_path),
            "- Workflow schema path: `{}`".format(workflow_repo_schema_path),
            "- Canonical example: 故意不写 schema 头(`# $schema: ...`),避免把本机路径固化进共享 YAML.",
            (
                "- 批量写入/更新头部(默认同时写 Red Hat + JetBrains modeline; 可用 `--comment-style` 控制): "
                "`uv run {cli} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`"
            ).format(cli=_project_constants.CLI_NAME),
            ("- Workflow modeline: `uv run {cli} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`").format(
                cli=_project_constants.CLI_NAME
            ),
            "- Repo query: `uv run {cli} yaml-dsl schema path`".format(cli=_project_constants.CLI_NAME),
            '- External query: `uvx --from "{dist}" {cli} yaml-dsl schema path`'.format(
                dist=CLI_DIST_NAME,
                cli=_project_constants.CLI_NAME,
            ),
            (
                '- Python fallback: `python -c "import os, scalim; print(os.path.join(os.path.dirname(scalim.__file__), '
                "'dsl/yaml_dsl/schema/demand.gen.json'))\"`"
            ),
            "- 本地编辑时再把上面命令输出写入头部; 不要把 `.venv/...` 或其它机器相关路径提交到共享示例.",
            "```yaml",
            "# yaml-language-server: $schema=.../demand.gen.json",
            "# $schema: .../demand.gen.json",
            "# yaml-language-server: $schema=.../workflow.gen.json",
            "# $schema: .../workflow.gen.json",
            "```",
        ]
    )

    lines.extend(_render_spec_requirement_map("## OpenSpec Requirement Map", spec_summaries))

    lines.extend(["", "## Command Details"])
    for command_doc in command_docs:
        command_name = " ".join(command_doc["tokens"])
        lines.extend(
            [
                "### `{}`".format(command_name),
                "- Help: {}".format(command_doc["help"]),
                "- Usage: `{}`".format(command_doc["usage"]),
            ]
        )
        help_full = str(command_doc.get("help_full") or "").rstrip()
        if help_full:
            lines.extend(["- Full help:", "```text", help_full.rstrip(), "```"])
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_yaml_dsl_workflow_cli_min_commands_markdown() -> str:
    workflow_schema_path = _path_to_posix(WORKFLOW_SCHEMA_REL)
    lines = [
        "1) workflow-level full validate(静态/编译期;递归校验引用的 demands;不执行 workflow):",
        "",
        "```bash",
        "uv run {cli} yaml-dsl validate --type workflow path/to/workflow.yaml".format(cli=_project_constants.CLI_NAME),
        "```",
        "",
        "2) schema-only 校验(结构/unknown-fields;依赖 `workflow.gen.json`):",
        "",
        "```bash",
        "uv run {cli} yaml-dsl schema validate --schema {schema} path/to/workflow.yaml".format(
            cli=_project_constants.CLI_NAME,
            schema=workflow_schema_path,
        ),
        "```",
        "",
        "本地编辑时,推荐直接批量写入 schema modeline(同 demand YAML 的做法一致,只是在 `--type` 上改为 `workflow`):",
        "",
        (
            "- 批量写入/更新 `$schema` 头部(默认同时写 Red Hat + JetBrains 两种 modeline; 用 `--comment-style` 控制): "
            "`uv run {cli} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`"
        ).format(cli=_project_constants.CLI_NAME),
        "",
        "```yaml",
        "# yaml-language-server: $schema=.../workflow.gen.json",
        "# $schema: .../workflow.gen.json",
        "```",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_yaml_dsl_cli_min_commands_markdown(*, placeholder_prefix: str = "path/to") -> str:
    workflow_schema_path = _path_to_posix(WORKFLOW_SCHEMA_REL)
    lines = [
        "- demand YAML 仓库内语义校验(内置 validator): `uv run {cli} yaml-dsl validate {p}/demand.yaml`".format(
            cli=_project_constants.CLI_NAME, p=placeholder_prefix
        ),
        (
            "- workflow YAML 仓库内 full validate(静态/编译期;递归校验引用的 demands;不执行 workflow): "
            "`uv run {cli} yaml-dsl validate --type workflow {p}/workflow.yaml`"
        ).format(cli=_project_constants.CLI_NAME, p=placeholder_prefix),
        "  - 若 workflow demand 路径使用 alias 语法,可用 `--path-alias <alias>=<path>` 注入解析",
        "- demand YAML 仓库内 schema-only(更快): `uv run {cli} yaml-dsl schema validate {p}/demand.yaml`".format(
            cli=_project_constants.CLI_NAME, p=placeholder_prefix
        ),
        (
            "- workflow YAML schema-only(需显式 workflow schema): "
            "`uv run {cli} yaml-dsl schema validate --schema {workflow_schema} {p}/workflow.yaml`"
        ).format(cli=_project_constants.CLI_NAME, workflow_schema=workflow_schema_path, p=placeholder_prefix),
        '- 仓库外语义校验: `uvx --from "{dist}" {cli} yaml-dsl validate {p}/config.yaml`'.format(
            dist=CLI_DIST_NAME,
            cli=_project_constants.CLI_NAME,
            p=placeholder_prefix,
        ),
        '- 仓库外 schema-only: `uvx --from "{dist}" {cli} yaml-dsl schema validate {p}/config.yaml`'.format(
            dist=CLI_DIST_NAME,
            cli=_project_constants.CLI_NAME,
            p=placeholder_prefix,
        ),
        "- 查询 schema 路径(仓库内): `uv run {cli} yaml-dsl schema path`".format(cli=_project_constants.CLI_NAME),
        '- 查询 schema 路径(仓库外): `uvx --from "{dist}" {cli} yaml-dsl schema path`'.format(
            dist=CLI_DIST_NAME,
            cli=_project_constants.CLI_NAME,
        ),
        "",
        (
            "skill 中的 canonical example 故意不带头部(也就是 schema modeline)。本地编辑时,"
            "我们一般用下面这套“团队通用”的做法(直接批量写入头部,"
            "不依赖内置 schema server):"
        ),
        "",
        (
            "- 批量插入/更新头部(默认同时写 Red Hat + JetBrains 两种 modeline; 用 `--comment-style` 控制): "
            "`uv run {cli} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`"
        ).format(cli=_project_constants.CLI_NAME),
        "",
        "```yaml",
        "# yaml-language-server: $schema=.../demand.gen.json",
        "# $schema: .../demand.gen.json",
        "```",
        "",
        "workflow YAML 同理,只是 `--type` 与 schema 文件名不同:",
        "",
        "- `uv run {cli} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`".format(
            cli=_project_constants.CLI_NAME
        ),
        "",
        "```yaml",
        "# yaml-language-server: $schema=.../workflow.gen.json",
        "# $schema: .../workflow.gen.json",
        "```",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_yaml_dsl_skill_cli_min_commands_markdown() -> str:
    workflow_schema_path = _path_to_posix(WORKFLOW_SCHEMA_REL)
    lines = [
        "- demand YAML 仓库内完整校验: `uv run {cli} yaml-dsl validate <demand.yaml>`".format(cli=_project_constants.CLI_NAME),
        "- demand YAML 仓库内 schema 校验: `uv run {cli} yaml-dsl schema validate <demand.yaml>`".format(cli=_project_constants.CLI_NAME),
        (
            "- workflow YAML 仓库内完整校验(静态/编译期;递归校验引用的 demands;不执行 workflow): "
            "`uv run {cli} yaml-dsl validate --type workflow <workflow.yaml>`"
        ).format(cli=_project_constants.CLI_NAME),
        (
            "- workflow YAML 仓库内 schema 校验(结构/unknown-fields; 必须显式 schema 路径): "
            "`uv run {cli} yaml-dsl schema validate --schema {schema} <workflow.yaml>`"
        ).format(cli=_project_constants.CLI_NAME, schema=workflow_schema_path),
        '- 仓库外完整校验: `uvx --from "{dist}" {cli} yaml-dsl validate <file.yaml>`'.format(
            dist=CLI_DIST_NAME,
            cli=_project_constants.CLI_NAME,
        ),
        '- 仓库外 schema 校验: `uvx --from "{dist}" {cli} yaml-dsl schema validate <file.yaml>`'.format(
            dist=CLI_DIST_NAME,
            cli=_project_constants.CLI_NAME,
        ),
        "- 仓库内查询 schema 绝对路径: `uv run {cli} yaml-dsl schema path`".format(cli=_project_constants.CLI_NAME),
        '- 仓库外查询 schema 绝对路径: `uvx --from "{dist}" {cli} yaml-dsl schema path`'.format(
            dist=CLI_DIST_NAME,
            cli=_project_constants.CLI_NAME,
        ),
        "",
        (
            "完整 canonical example 故意不带头部(也就是 schema modeline)。本地编辑时,我们一般用下面这套“团队通用”的做法(直接批量写入头部,"
            "不依赖内置 schema server):"
        ),
        "",
        (
            "- 批量插入/更新头部(默认同时写 Red Hat + JetBrains 两种 modeline; 用 `--comment-style` 控制): "
            "`uv run {cli} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`"
        ).format(cli=_project_constants.CLI_NAME),
        "- workflow YAML 同理: `uv run {cli} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`".format(
            cli=_project_constants.CLI_NAME
        ),
        "",
        "运行入口已迁出 CLI,统一使用 Python API(需 allowlist):",
        "",
        "```python",
        "from scalim.dsl.yaml_dsl import RunOptions, run, run_workflow",
        "",
        "run(",
        '    "path/to/demand.yaml",',
        "    options=RunOptions(",
        '        allowed_modules=frozenset(["myapp.loaders"]),',
        "    ),",
        ")",
        "",
        "run_workflow(",
        '    "path/to/workflow.yaml",',
        "    options=RunOptions(",
        '        allowed_modules=frozenset(["myapp.loaders"]),',
        "    ),",
        ")",
        "```",
        "",
        "```yaml",
        "# yaml-language-server: $schema=.../demand.gen.json",
        "# $schema: .../demand.gen.json",
        "```",
    ]
    return "\n".join(lines).rstrip() + "\n"
