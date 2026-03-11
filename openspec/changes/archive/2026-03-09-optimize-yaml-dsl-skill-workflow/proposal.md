## Why

当前 YAML DSL skill 由生成器直接产出整包内容,但产物更接近 schema 导出而不是面向 agent 的任务型工作流. 这导致 skill 虽然能触发,却难以支持“一次引用后直接完成 YAML 重构、校验、订正或渐进迁移方案设计”这类高价值任务.

同时,业务侧已经出现一类稳定的迁移需求:把旧的批量报表脚本渐进迁移到 YAML DSL,但保留必要的 Python 边界用于 compare、运行时状态和多 sheet 组装. 这类经验需要被脱敏后沉淀进 skill,让 agent 能自动判断哪些逻辑应该下沉到 YAML,哪些应该暂留在 Python.

## What Changes

- 将 `scripts/gen-agent-skill.py` 与 skill 生成逻辑改为仅生成和校验受控的 generated references,不再直接生成或覆盖手工维护的 `SKILL.md`.
- 将 `artifacts/skills/scalim-yaml-dsl/` 调整为手工维护的 task-driven skill,核心目标是帮助 agent 一次完成 YAML DSL 编写、升级到最新写法、校验订正和渐进迁移方案设计.
- 为 skill 增加明确的 CLI/LSP 指引,包括:
  - 仓库内使用 `uv run PROJECT_CLI_NAME ...`
  - 脱离仓库使用 `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME ...`
  - schema path 查询与 `# yaml-language-server: $schema=...` 头部参考
- 将自动生成内容拆分为更适合渐进披露的 references,固定为语法目录、CLI/LSP 参考与单个受控 full example(`references/generated/example-full/ecommerce_report.yaml`),并要求生成后做真实校验与测试.
- 手工维护的 `SKILL.md` 只承担任务分流、最小命令入口与 references 导航职责; richer 场景预设与迁移 heuristics 放在一层直达的 `references/` 中,遵循 `skill-creator` 的渐进披露约束.
- 在手工维护的 skill 中加入脱敏后的“渐进迁移某类批量报表脚本到 YAML DSL”场景指引,明确:
  - 大宽表 + 分组拆多 sheet
  - compare 友好的渐进路由
  - 直接引用下游 BLL loader 与最薄 Python 适配层的判断标准
  - 当前 YAML DSL 能力边界下哪些逻辑应暂留 Python

## Capabilities

### New Capabilities
- `yaml-dsl-agent-guidance`: 手工维护的 YAML DSL skill 必须以任务驱动方式组织编写、校验、订正与渐进迁移指导,并包含脱敏的迁移场景决策规则、CLI/LSP 指引和引用顺序.

### Modified Capabilities
- `agent-skill-export`: 自动生成器的职责从“生成完整 skill 包”收缩为“生成并校验 generated references 与构建清单”,不得覆盖手工维护的 skill 本体.

## Impact

- 受影响代码:
  - `scripts/gen-agent-skill.py`
  - `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`
  - `artifacts/skills/scalim-yaml-dsl/`
  - `tests/test_agent_skill_generator.py`
- 受影响产物:
  - `artifacts/skills/scalim-yaml-dsl/SKILL.md`
  - `artifacts/skills/scalim-yaml-dsl/references/**`
- 受影响流程:
  - `just gen-agent-skill`
  - `just validate-agent-skill`
  - 文档中关于 YAML DSL skill 的维护与使用说明
