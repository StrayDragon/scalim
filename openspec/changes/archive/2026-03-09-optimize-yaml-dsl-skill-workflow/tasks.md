## 1. Generator Boundary Refactor

- [x] 1.1 重构 `scripts/gen-agent-skill.py` 与 `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`,将受控输出收敛到 `references/generated/` 与 manifest
- [x] 1.2 移除生成器对 `SKILL.md`、manual references 与旧自动生成 guidance 文件的创建/覆盖逻辑
- [x] 1.3 调整 generated references 的输出布局,固定生成 `references/generated/syntax-catalog.md`、`references/generated/cli-lsp-reference.md` 与单个 canonical example `references/generated/example-full/ecommerce_report.yaml`

## 2. Manual Skill Rewrite

- [x] 2.1 手工重写 `artifacts/skills/scalim-yaml-dsl/SKILL.md`,改为 task-driven 入口并补充 `uv run` / `uvx --from "PROJECT_DIST_NAME[cli]"` / `schema validate` / schema path / `$schema` header 指引
- [x] 2.2 新增或重写 manual references,覆盖 authoring、v3 升级、validate/debug 与脱敏的 legacy 批量报表渐进迁移 playbook,并让 `SKILL.md` 以一层直达链接方式路由到这些 references
- [x] 2.3 让 manual skill 明确 YAML/Python 职责切分规则,包括大宽表、多 sheet、compare 路由、runtime state 与最薄 Python 适配层判断

## 3. Validation, Tests, and Docs

- [x] 3.1 更新生成器测试,验证 deterministic generated outputs、canonical example 的 schema/full validate、CLI/LSP reference 来源真实性以及“不覆盖 manual files”
- [x] 3.2 增加 manual skill contract tests,验证 `SKILL.md` 的关键命令、一层直达的必要 references 链接与 manual/generated 边界
- [x] 3.3 更新相关 docs / just 说明并运行 `openspec validate --all --strict --no-interactive` 完成变更校验
