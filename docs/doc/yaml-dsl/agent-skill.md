# 集成AI环境 (Agent Skill)

??? note "适用读者"
    - 使用方开发者/数据同学:希望让智能助手更稳定地写/改 Scalim YAML
    - 项目贡献者:需要生成/校验 skill 产物并避免漂移

??? note "维护提示"
    - 生成与产物结构:[`scripts/gen-agent-skill.py`](#code=scripts/gen-agent-skill.py)、[`packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`](#code=packages/scalim-misc/src/scalim_misc/agent_skill_gen.py)
    - 默认产物目录:[`artifacts/skills/scalim-yaml-dsl/`](#code=artifacts/skills/scalim-yaml-dsl/)
    - 若改动 schema/示例来源/输出目录结构,需要同步更新本页

仓库内置一份 **Scalim YAML DSL 的集成AI环境(Agent Skill)**,目的是把“字段/枚举规则 + 一份完整示例 + 校验入口”整理成可直接喂给 Agent 的材料,降低写错 YAML 的概率.

## 1. 产物在哪里(直接用)

- 技能说明:[`artifacts/skills/scalim-yaml-dsl/SKILL.md`](#code=artifacts/skills/scalim-yaml-dsl/SKILL.md)
- 字段/枚举参考(schema + OpenSpec 摘要生成):[`artifacts/skills/scalim-yaml-dsl/references/dsl-reference.md`](#code=artifacts/skills/scalim-yaml-dsl/references/dsl-reference.md)
- 完整示例(含 loader/约束说明 + YAML):[`artifacts/skills/scalim-yaml-dsl/references/example-full/`](#code=artifacts/skills/scalim-yaml-dsl/references/example-full/)

使用时通常需要把整个目录 `artifacts/skills/scalim-yaml-dsl/` 交给你的 Agent 系统(确保 `SKILL.md` 与 `references/` 都可读).

## 2. 怎么让智能助手用它写/改 YAML

一种通用的用法(不绑定具体工具):

1. 把 `SKILL.md` 作为“技能说明/约束”,把 `references/` 作为“可检索参考材料”
2. 让助手先对齐 schema 约束(必填字段、互斥关系、枚举值范围)
3. 让助手输出 YAML 时尽量只输出 YAML(便于你直接校验/运行)

生成或修改 YAML 后,建议跑一次校验:

- 语义校验(内置 validator):`scalim-cli yaml-dsl validate path/to/config.yaml`
- schema-only(更快):`scalim-cli yaml-dsl schema validate path/to/config.yaml`

## 3. 安装到常见 skills 目录(可选)

生成器默认只写入仓库内的 `artifacts/skills/`,并拒绝直接写入用户 skills 目录(避免误覆盖).

如果你的工具约定从用户 skills 目录读取,你可以手动复制/软链到类似位置:

- `~/.codex/skills/scalim-yaml-dsl/`
- `~/.claude/skills/scalim-yaml-dsl/`

关键是保持目录结构不变(`SKILL.md` + `references/`).

## 4. 贡献者:如何更新/校验技能包

当你修改了 YAML DSL schema 或示例来源,建议同步更新技能包产物:

- 生成:`just gen-agent-skill`
- 漂移校验:`just validate-agent-skill`

生成清单与输入/输出校验和在:

- [`artifacts/skills/scalim-yaml-dsl.build-manifest.json`](#code=artifacts/skills/scalim-yaml-dsl.build-manifest.json)
