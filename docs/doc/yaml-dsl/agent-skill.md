# 集成AI环境 (Agent Skill)

??? note "适用读者"
    - 使用方开发者/数据同学:希望让智能助手更稳定地写/改 Scalim YAML
    - 项目贡献者:需要生成/校验 skill 产物并避免漂移

??? note "维护提示"
    - 生成与产物结构:[`scripts/gen-agent-skill.py`](#code=scripts/gen-agent-skill.py)、[`packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`](#code=packages/scalim-misc/src/scalim_misc/agent_skill_gen.py)
    - 默认产物目录:[`agentdev/skills/scalim-yaml-dsl/`](#code=agentdev/skills/scalim-yaml-dsl/)
    - 若改动 schema/示例来源/输出目录结构,需要同步更新本页
    - Python 侧稳定导入入口与治理边界见:[公共 API 导入指南](../getting-started/public-api.gen.md)

仓库里维护了一套 **Scalim YAML DSL 的 Agent Skill**: 把任务分流、最小命令入口、校验入口、生成的 catalog、迁移 playbook 放在同一个目录里,方便直接交给智能助手用,少踩坑。

## 1. 产物在哪里(直接用)

- 技能入口:[`agentdev/skills/scalim-yaml-dsl/SKILL.md`](#code=agentdev/skills/scalim-yaml-dsl/SKILL.md)
- 手工 task references:
  - [`agentdev/skills/scalim-yaml-dsl/references/task-authoring.md`](#code=agentdev/skills/scalim-yaml-dsl/references/task-authoring.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/task-workflow-authoring.md`](#code=agentdev/skills/scalim-yaml-dsl/references/task-workflow-authoring.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/task-upgrade-legacy.md`](#code=agentdev/skills/scalim-yaml-dsl/references/task-upgrade-legacy.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/task-validate-debug.md`](#code=agentdev/skills/scalim-yaml-dsl/references/task-validate-debug.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/task-runtime-troubleshooting.md`](#code=agentdev/skills/scalim-yaml-dsl/references/task-runtime-troubleshooting.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/task-workflow-validate-debug.md`](#code=agentdev/skills/scalim-yaml-dsl/references/task-workflow-validate-debug.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/task-workflow-versioned-outputs.md`](#code=agentdev/skills/scalim-yaml-dsl/references/task-workflow-versioned-outputs.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/task-report-migration-playbook.md`](#code=agentdev/skills/scalim-yaml-dsl/references/task-report-migration-playbook.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/task-downstream-adaptation.md`](#code=agentdev/skills/scalim-yaml-dsl/references/task-downstream-adaptation.md)
- 受控生成 references:
  - [`agentdev/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md`](#code=agentdev/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/generated/cli-lsp-reference.gen.md`](#code=agentdev/skills/scalim-yaml-dsl/references/generated/cli-lsp-reference.gen.md)
  - [`agentdev/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml`](#code=agentdev/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml)
  - [`agentdev/skills/scalim-yaml-dsl/references/generated/yaml-dsl-upgrades.gen.md`](#code=agentdev/skills/scalim-yaml-dsl/references/generated/yaml-dsl-upgrades.gen.md) (breaking/migration 快速索引)
  - `agentdev/skills/scalim-yaml-dsl/references/upgrades/*.md` (升级指南 SSOT; docs-site 对应页面由此生成)

一般把整个目录 `agentdev/skills/scalim-yaml-dsl/` 交给你的 Agent 就行: `SKILL.md` 负责分流,细节再按需从 `references/` 读取。
`references/generated/` 由 `scripts/gen-agent-skill.py` 根据 schema、CLI 与相关 `openspec/specs/` 自动摘录生成; `references/` 里的 task 文档则保留人工维护的任务预设与迁移经验.

## 2. 怎么让智能助手用它写/改 YAML

常见用法(不绑定具体工具):

1. 把 `SKILL.md` 作为“任务路由与最小命令入口”
2. 让助手按任务类型读取对应 reference,不要默认把所有 generated catalog 一次性塞进上下文
3. 让助手先对齐 schema 约束,再用 `validate` 收敛语义问题
4. 让助手输出 YAML 或迁移方案时同时附上“已验证什么 / 未验证什么”

写完/改完 YAML 后,建议跑一遍校验:

<!-- BEGIN AUTOGEN:yaml-dsl-cli-min-commands -->
- demand YAML 仓库内语义校验(内置 validator): `uv run scalim-cli yaml-dsl validate path/to/demand.yaml`
- demand YAML 在 workflow 上下文中校验(outputs 允许引用 workflow.resources.*): `uv run scalim-cli yaml-dsl validate --workflow path/to/workflow.yaml path/to/demand.yaml`
- workflow YAML 仓库内 full validate(静态/编译期;递归校验引用的 demands;不执行 workflow): `uv run scalim-cli yaml-dsl validate --type workflow path/to/workflow.yaml`
  - 若 workflow demand 路径使用 alias 语法,可用 `--path-alias <alias>=<path>` 注入解析
- demand YAML 仓库内 schema-only(更快): `uv run scalim-cli yaml-dsl schema validate path/to/demand.yaml`
- demand YAML 在 workflow 上下文中 schema-only(outputs 允许引用 workflow.resources.*): `uv run scalim-cli yaml-dsl schema validate --workflow path/to/workflow.yaml path/to/demand.yaml`
- workflow YAML schema-only(需显式 workflow schema): `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json path/to/workflow.yaml`
- 仓库外语义校验: `uvx scalim-cli yaml-dsl validate path/to/config.yaml`
- 仓库外 schema-only: `uvx scalim-cli yaml-dsl schema validate path/to/config.yaml`
- 查询 schema 路径(仓库内): `uv run scalim-cli yaml-dsl schema path`
- 查询 schema 路径(仓库外): `uvx scalim-cli yaml-dsl schema path`

skill 中的 canonical example 故意不带头部(也就是 schema modeline)。本地编辑时,我们一般用下面这套“团队通用”的做法(直接批量写入头部,不依赖内置 schema server):

- 批量插入/更新头部(默认同时写 Red Hat + JetBrains 两种 modeline; 用 `--comment-style` 控制): `uv run scalim-cli yaml-dsl upsert-lsp-comment --type demand --comment-style all <paths...>`

```yaml
# yaml-language-server: $schema=.../demand.gen.json
# $schema: .../demand.gen.json
```

workflow YAML 同理,只是 `--type` 与 schema 文件名不同:

- `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`

```yaml
# yaml-language-server: $schema=.../workflow.gen.json
# $schema: .../workflow.gen.json
```
<!-- END AUTOGEN:yaml-dsl-cli-min-commands -->

不要把 `.venv/...` 或 `site-packages/...` 这类机器相关路径固化进共享示例文件.

## 3. 安装到常见 skills 目录(可选)

生成器默认只写入仓库内的 `agentdev/skills/`,并拒绝直接写入用户 skills 目录(避免误覆盖).

如果你的工具约定从用户 skills 目录读取,你可以手动复制/软链到类似位置:

- `~/.codex/skills/scalim-yaml-dsl/`
- `~/.claude/skills/scalim-yaml-dsl/`

关键是保持目录结构不变(`SKILL.md` + `agents/openai.yaml` + `references/`).

## 4. 贡献者:如何更新/校验技能包

当你修改了 YAML DSL schema、CLI 命令语义、相关 OpenSpec spec 或 canonical example 来源,建议同步更新 generated 产物:

- 生成:`just gen-agent-skill`
- 漂移校验:`just validate-agent-skill`

漂移校验会在临时目录重建受控输出并逐字节对拍,覆盖范围仅包含:

- `agentdev/skills/scalim-yaml-dsl/references/*.gen.*`
- `agentdev/skills/scalim-yaml-dsl/references/generated/`

## 5. 贡献者:如何评估 skill 效果(prompt-eval)

本仓库提供 `prompt-eval` 用于对 skill 做回归评估:

- 确定性 core(不耗 token): `just prompt-eval`
- promptfoo(T0; prompt 级别): `just prompt-eval-llm`
- coding agent(T1; 更昂贵,更贴近真实用户): `just prompt-eval-agent`

文档见:

- [Prompt 评测(workflow)](../dev/prompt-eval.md)
- [Prompt 评测: Coding agent (T1)](../dev/prompt-eval-agent.md)
