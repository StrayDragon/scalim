from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from scalim_cli import yaml_dsl as yaml_dsl_cli

from scalim import _project_constants

if TYPE_CHECKING:
    from collections.abc import Sequence

DEMAND_SCHEMA_REL = Path("src") / "scalim" / "dsl" / "yaml_dsl" / "schema" / "demand.gen.json"
WORKFLOW_SCHEMA_REL = Path("src") / "scalim" / "dsl" / "yaml_dsl" / "schema" / "workflow.gen.json"
CLI_SOURCE_REL = Path("packages") / "scalim-cli" / "src" / "scalim_cli" / "yaml_dsl.py"
# NOTE:
# - CLI lives in independent dist `scalim-cli` (Python >= 3.10).
# - For one-off external usage, prefer `uvx scalim-cli ...` to match uvx semantics.

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


def _render_spec_requirement_map(title: str, spec_summaries: Sequence[dict[str, Any]]) -> list[str]:
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
            lines.append(f"  - {requirement}")
    return lines


def _assert_default_schema_path_is_repo_relative(repo_root: Path) -> None:
    default_schema_path = yaml_dsl_cli._default_schema_path().resolve()  # noqa: SLF001
    try:
        default_schema_repo_rel = _path_to_posix(default_schema_path.relative_to(repo_root))
    except ValueError as exc:
        msg = f"CLI 默认 `schema` 路径不在仓库内: {default_schema_path}"
        raise YamlDslCliReferenceError(msg) from exc

    expected = _path_to_posix(DEMAND_SCHEMA_REL)
    if default_schema_repo_rel != expected:
        msg = f"CLI 默认 `schema` 路径与规范 `schema` 文件不一致: {default_schema_repo_rel}"
        raise YamlDslCliReferenceError(msg)


def render_yaml_dsl_cli_reference_markdown(
    repo_root: Path,
    command_docs: Sequence[dict[str, Any]],
    *,
    generated_by: str,
    spec_summaries: Sequence[dict[str, Any]] = (),
    canonical_example_path: str | None = None,
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
        f"此文档由 `{generated_by}` 自动生成.",
        "",
        "## Canonical Sources",
        f"- CLI implementation: `{_path_to_posix(CLI_SOURCE_REL)}`",
        "- Project identity constants: `src/scalim/_project_constants.py`",
        f"- Demand schema file: `{repo_schema_path}`",
        f"- Workflow schema file: `{workflow_repo_schema_path}`",
    ]
    if canonical_example_path:
        lines.append(f"- Canonical example: `{_path_to_posix(canonical_example_path)}`")

    lines.extend(
        [
            "",
            "## Command Variants",
            "### Repo",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl validate <file.yaml>`",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl validate --workflow <workflow.yaml> <demand.yaml>`",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl validate --type workflow <workflow.yaml>`",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl schema validate <file.yaml>`",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl schema validate --workflow <workflow.yaml> <demand.yaml>`",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl schema validate --schema {workflow_repo_schema_path} <workflow.yaml>`",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl schema show`",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl schema path`",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`",
            f"- `uv run {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`",
            "",
            "### External",
            f"- `uvx {_project_constants.CLI_NAME} yaml-dsl validate <file.yaml>`",
            f"- `uvx {_project_constants.CLI_NAME} yaml-dsl validate --workflow <workflow.yaml> <demand.yaml>`",
            f"- `uvx {_project_constants.CLI_NAME} yaml-dsl validate --type workflow <workflow.yaml>`",
            f"- `uvx {_project_constants.CLI_NAME} yaml-dsl schema validate <file.yaml>`",
            f"- `uvx {_project_constants.CLI_NAME} yaml-dsl schema validate --workflow <workflow.yaml> <demand.yaml>`",
            f"- `uvx {_project_constants.CLI_NAME} yaml-dsl schema show`",
            f"- `uvx {_project_constants.CLI_NAME} yaml-dsl schema path`",
            f"- `uvx {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`",
            f"- `uvx {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`",
            "",
            "## Validate Layering",
            "- `yaml-dsl validate --type demand`: 使用 internal validator,更适合语义校验、旧写法迁移收敛与输出路径定位.",
            (
                "- `yaml-dsl validate --workflow <workflow.yaml>`: 仅对 demand 生效;注入 workflow.resources.{books,files} "
                "作为 outputs 绑定校验上下文."
            ),
            (
                "- `yaml-dsl validate --type workflow`: 静态/编译期 workflow 校验,递归校验 workflow 引用的 demands,"
                "并检查 outputs/books 绑定一致性."
            ),
            "- `yaml-dsl validate` 默认 `--type auto`: 根据 YAML 顶层结构推断 demand/workflow;CI/脚本建议显式传 `--type workflow`.",
            "- `yaml-dsl schema validate`: 使用 JSON Schema,更适合 schema-only 校验、编辑器/LSP 对齐与 unknown-field strict 收敛.",
            (
                "- `yaml-dsl schema validate --workflow <workflow.yaml>`: 仅对 demand 生效;注入 workflow.resources.{books,files} "
                "作为 outputs 绑定校验上下文."
            ),
            "",
            "## LSP / Schema Header",
            f"- Repo schema path: `{repo_schema_path}`",
            f"- Workflow schema path: `{workflow_repo_schema_path}`",
            "- Canonical example: 故意不写 schema 头(`# $schema: ...`),避免把本机路径固化进共享 YAML.",
            (
                "- 批量写入/更新头部(默认同时写 Red Hat + JetBrains modeline; 可用 `--comment-style` 控制): "
                f"`uv run {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`"
            ),
            (
                f"- Workflow modeline: `uv run {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type workflow --comment-style all "  # noqa: E501
                f"<paths...>`"
            ),
            f"- Repo query: `uv run {_project_constants.CLI_NAME} yaml-dsl schema path`",
            f"- External query: `uvx {_project_constants.CLI_NAME} yaml-dsl schema path`",
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

    lines.extend(_render_spec_requirement_map("## llmanspec Requirement Map", spec_summaries))

    lines.extend(["", "## Command Details"])
    for command_doc in command_docs:
        command_name = " ".join(command_doc["tokens"])
        lines.extend(
            [
                f"### `{command_name}`",
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
        f"uv run {_project_constants.CLI_NAME} yaml-dsl validate --type workflow path/to/workflow.yaml",
        "```",
        "",
        "2) schema-only 校验(结构/unknown-fields;依赖 `workflow.gen.json`):",
        "",
        "```bash",
        f"uv run {_project_constants.CLI_NAME} yaml-dsl schema validate --schema {workflow_schema_path} path/to/workflow.yaml",
        "```",
        "",
        "本地编辑时,推荐直接批量写入 schema modeline(同 demand YAML 的做法一致,只是在 `--type` 上改为 `workflow`):",
        "",
        (
            "- 批量写入/更新 `$schema` 头部(默认同时写 Red Hat + JetBrains 两种 modeline; 用 `--comment-style` 控制): "
            f"`uv run {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`"
        ),
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
        f"- demand YAML 仓库内语义校验(内置 validator): `uv run {_project_constants.CLI_NAME} yaml-dsl validate {placeholder_prefix}/demand.yaml`",  # noqa: E501
        (
            "- demand YAML 在 workflow 上下文中校验(outputs 允许引用 workflow.resources.*): "
            f"`uv run {_project_constants.CLI_NAME} yaml-dsl validate --workflow {placeholder_prefix}/workflow.yaml {placeholder_prefix}/demand.yaml`"  # noqa: E501
        ),
        (
            "- workflow YAML 仓库内 full validate(静态/编译期;递归校验引用的 demands;不执行 workflow): "
            f"`uv run {_project_constants.CLI_NAME} yaml-dsl validate --type workflow {placeholder_prefix}/workflow.yaml`"
        ),
        "  - 若 workflow demand 路径使用 alias 语法,可用 `--path-alias <alias>=<path>` 注入解析",
        f"- demand YAML 仓库内 schema-only(更快): `uv run {_project_constants.CLI_NAME} yaml-dsl schema validate {placeholder_prefix}/demand.yaml`",  # noqa: E501
        (
            "- demand YAML 在 workflow 上下文中 schema-only(outputs 允许引用 workflow.resources.*): "
            f"`uv run {_project_constants.CLI_NAME} yaml-dsl schema validate --workflow {placeholder_prefix}/workflow.yaml {placeholder_prefix}/demand.yaml`"  # noqa: E501
        ),
        (
            "- workflow YAML schema-only(需显式 workflow schema): "
            f"`uv run {_project_constants.CLI_NAME} yaml-dsl schema validate --schema {workflow_schema_path} {placeholder_prefix}/workflow.yaml`"  # noqa: E501
        ),
        f"- 仓库外语义校验: `uvx {_project_constants.CLI_NAME} yaml-dsl validate {placeholder_prefix}/config.yaml`",
        f"- 仓库外 schema-only: `uvx {_project_constants.CLI_NAME} yaml-dsl schema validate {placeholder_prefix}/config.yaml`",
        f"- 查询 schema 路径(仓库内): `uv run {_project_constants.CLI_NAME} yaml-dsl schema path`",
        f"- 查询 schema 路径(仓库外): `uvx {_project_constants.CLI_NAME} yaml-dsl schema path`",
        "",
        (
            "skill 中的 canonical example 故意不带头部(也就是 schema modeline)。本地编辑时,"
            "我们一般用下面这套“团队通用”的做法(直接批量写入头部,"
            "不依赖内置 schema server):"
        ),
        "",
        (
            "- 批量插入/更新头部(默认同时写 Red Hat + JetBrains 两种 modeline; 用 `--comment-style` 控制): "
            f"`uv run {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`"
        ),
        "",
        "```yaml",
        "# yaml-language-server: $schema=.../demand.gen.json",
        "# $schema: .../demand.gen.json",
        "```",
        "",
        "workflow YAML 同理,只是 `--type` 与 schema 文件名不同:",
        "",
        f"- `uv run {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`",
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
        f"- demand YAML 仓库内完整校验: `uv run {_project_constants.CLI_NAME} yaml-dsl validate <demand.yaml>`",
        f"- demand YAML workflow 上下文校验: `uv run {_project_constants.CLI_NAME} yaml-dsl validate --workflow <workflow.yaml> <demand.yaml>`",  # noqa: E501
        f"- demand YAML 仓库内 schema 校验: `uv run {_project_constants.CLI_NAME} yaml-dsl schema validate <demand.yaml>`",
        (
            f"- demand YAML workflow 上下文 schema 校验: `uv run {_project_constants.CLI_NAME} yaml-dsl schema validate --workflow <workflow.yaml> <demand.yaml>`"  # noqa: E501
        ),
        (
            "- workflow YAML 仓库内完整校验(静态/编译期;递归校验引用的 demands;不执行 workflow): "
            f"`uv run {_project_constants.CLI_NAME} yaml-dsl validate --type workflow <workflow.yaml>`"
        ),
        (
            "- workflow YAML 仓库内 schema 校验(结构/unknown-fields; 必须显式 schema 路径): "
            f"`uv run {_project_constants.CLI_NAME} yaml-dsl schema validate --schema {workflow_schema_path} <workflow.yaml>`"
        ),
        f"- 仓库外完整校验: `uvx {_project_constants.CLI_NAME} yaml-dsl validate <file.yaml>`",
        f"- 仓库外 schema 校验: `uvx {_project_constants.CLI_NAME} yaml-dsl schema validate <file.yaml>`",
        f"- 仓库内查询 schema 绝对路径: `uv run {_project_constants.CLI_NAME} yaml-dsl schema path`",
        f"- 仓库外查询 schema 绝对路径: `uvx {_project_constants.CLI_NAME} yaml-dsl schema path`",
        "",
        (
            "完整 canonical example 故意不带头部(也就是 schema modeline)。本地编辑时,我们一般用下面这套“团队通用”的做法(直接批量写入头部,"
            "不依赖内置 schema server):"
        ),
        "",
        (
            "- 批量插入/更新头部(默认同时写 Red Hat + JetBrains 两种 modeline; 用 `--comment-style` 控制): "
            f"`uv run {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`"
        ),
        f"- workflow YAML 同理: `uv run {_project_constants.CLI_NAME} yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`",  # noqa: E501
        "",
        "运行入口已迁出 CLI,统一使用 Python API(需 allowlist):",
        "",
        "```python",
        "from scalim.dsl.yaml_dsl import (",
        "    DemandRunOptions,",
        "    DemandRunSecurityOptions,",
        "    WorkflowRunOptions,",
        "    run,",
        "    run_workflow,",
        ")",
        "",
        "demand = DemandRunOptions(",
        "    security=DemandRunSecurityOptions(",
        '        allowed_modules=frozenset(["myapp.loaders"]),',
        "    ),",
        ")",
        "",
        "run(",
        '    "path/to/demand.yaml",',
        "    options=demand,",
        ")",
        "",
        "run_workflow(",
        '    "path/to/workflow.yaml",',
        "    options=WorkflowRunOptions(demand=demand),",
        ")",
        "```",
        "",
        "```yaml",
        "# yaml-language-server: $schema=.../demand.gen.json",
        "# $schema: .../demand.gen.json",
        "```",
    ]
    return "\n".join(lines).rstrip() + "\n"
