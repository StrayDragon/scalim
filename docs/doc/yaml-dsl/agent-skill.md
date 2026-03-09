# 集成AI环境 (Agent Skill)

??? note "适用读者"
    - 使用方开发者/数据同学:希望让智能助手更稳定地写/改 Scalim YAML
    - 项目贡献者:需要生成/校验 skill 产物并避免漂移

??? note "维护提示"
    - 生成与产物结构:[`scripts/gen-agent-skill.py`](#code=scripts/gen-agent-skill.py)、[`packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`](#code=packages/scalim-misc/src/scalim_misc/agent_skill_gen.py)
    - 默认产物目录:[`artifacts/skills/scalim-yaml-dsl/`](#code=artifacts/skills/scalim-yaml-dsl/)
    - 若改动 schema/示例来源/输出目录结构,需要同步更新本页

仓库内置一份 **Scalim YAML DSL 的集成AI环境(Agent Skill)**,目的是把“任务分流 + 校验入口 + 全量 generated catalog + 渐进迁移 playbook”整理成可直接喂给 Agent 的材料,降低写错 YAML、误用旧写法与错误下沉 Python 逻辑的概率.

## 1. 产物在哪里(直接用)

- 技能入口:[`artifacts/skills/scalim-yaml-dsl/SKILL.md`](#code=artifacts/skills/scalim-yaml-dsl/SKILL.md)
- 手工 task references:
  - [`artifacts/skills/scalim-yaml-dsl/references/task-authoring.md`](#code=artifacts/skills/scalim-yaml-dsl/references/task-authoring.md)
  - [`artifacts/skills/scalim-yaml-dsl/references/task-upgrade-legacy.md`](#code=artifacts/skills/scalim-yaml-dsl/references/task-upgrade-legacy.md)
  - [`artifacts/skills/scalim-yaml-dsl/references/task-validate-debug.md`](#code=artifacts/skills/scalim-yaml-dsl/references/task-validate-debug.md)
  - [`artifacts/skills/scalim-yaml-dsl/references/task-report-migration-playbook.md`](#code=artifacts/skills/scalim-yaml-dsl/references/task-report-migration-playbook.md)
- 受控生成 references:
  - [`artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md`](#code=artifacts/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md)
  - [`artifacts/skills/scalim-yaml-dsl/references/generated/cli-lsp-reference.gen.md`](#code=artifacts/skills/scalim-yaml-dsl/references/generated/cli-lsp-reference.gen.md)
  - [`artifacts/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml`](#code=artifacts/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml)

使用时通常需要把整个目录 `artifacts/skills/scalim-yaml-dsl/` 交给你的 Agent 系统. `SKILL.md` 只负责任务路由,细节说明在 `references/` 中按需读取.
其中 generated references 由 `scripts/gen-agent-skill.py` 基于 schema、CLI 与相关 `openspec/specs/` 自动摘录生成,manual references 则保留人工维护的任务预设与迁移 heuristics.

## 2. 怎么让智能助手用它写/改 YAML

一种通用的用法(不绑定具体工具):

1. 把 `SKILL.md` 作为“任务路由与最小命令入口”
2. 让助手按任务类型读取对应 reference,不要默认把所有 generated catalog 一次性塞进上下文
3. 让助手先对齐 schema 约束,再用 `validate` 收敛语义问题
4. 让助手输出 YAML 或迁移方案时同时附上“已验证什么 / 未验证什么”

生成或修改 YAML 后,建议跑一次校验:

- 仓库内语义校验(内置 validator): `uv run scalim-cli yaml-dsl validate path/to/config.yaml`
- 仓库内 schema-only(更快): `uv run scalim-cli yaml-dsl schema validate path/to/config.yaml`
- 仓库外语义校验: `uvx --from "scalim[cli]" scalim-cli yaml-dsl validate path/to/config.yaml`
- 仓库外 schema-only: `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema validate path/to/config.yaml`
- 查询 schema 路径(仓库内): `uv run scalim-cli yaml-dsl schema path`
- 查询 schema 路径(仓库外): `uvx --from "scalim[cli]" scalim-cli yaml-dsl schema path`

skill 中的 canonical example 故意不带 YAML LSP 头。需要编辑器补全时,再把 `schema path` 查询结果按本机环境写成:

```yaml
# yaml-language-server: $schema=/absolute/path/to/demand.gen.json
```

不要把 `.venv/...` 或 `site-packages/...` 这类机器相关路径固化进共享示例文件.

## 3. 安装到常见 skills 目录(可选)

生成器默认只写入仓库内的 `artifacts/skills/`,并拒绝直接写入用户 skills 目录(避免误覆盖).

如果你的工具约定从用户 skills 目录读取,你可以手动复制/软链到类似位置:

- `~/.codex/skills/scalim-yaml-dsl/`
- `~/.claude/skills/scalim-yaml-dsl/`

关键是保持目录结构不变(`SKILL.md` + `agents/openai.yaml` + `references/`).

## 4. 贡献者:如何更新/校验技能包

当你修改了 YAML DSL schema、CLI 命令语义、相关 OpenSpec spec 或 canonical example 来源,建议同步更新 generated 产物:

- 生成:`just gen-agent-skill`
- 漂移校验:`just validate-agent-skill`

generated 产物清单与输入/输出校验和在:

- [`artifacts/skills/scalim-yaml-dsl.build-manifest.json`](#code=artifacts/skills/scalim-yaml-dsl.build-manifest.json)
