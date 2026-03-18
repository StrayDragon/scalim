## MODIFIED Requirements

### Requirement: Task-Driven Manual Skill Entry
系统 MUST 提供手工维护的 YAML DSL skill 本体,用于把 agent 引导到正确的任务路径,而不是把 skill 退化为单个 schema 摘要页.

手工维护的 `SKILL.md` MUST 明确覆盖至少以下任务类型:
- 新建或修改 YAML DSL 配置(demand YAML)
- 编排多条 demand 的 workflow YAML 配置(workflow YAML)
- 将旧写法直接升级到当前结构
- 对现有 YAML 做 schema/full validate 与订正(demand YAML)
- 对 workflow YAML 做 schema validate 与排错(workflow YAML)
- 为某类 legacy 批量报表脚本设计渐进迁移方案

`SKILL.md` MUST 指示 agent 先识别任务类型,再按需读取最少的 references,而不是默认加载全部参考资料.
`SKILL.md` MUST 保持 routing-first: 只保留任务分流、最小命令入口与对一层直达 references 的链接; 详细场景预设、迁移 heuristics 与完整语法目录 MUST 放在被直接链接的 references 中.

#### Scenario: 新建 YAML 任务走 authoring 路径
- **WHEN** 用户请求编写或重构 YAML DSL 配置
- **THEN** skill 必须引导 agent 先读取 authoring 相关 references
- **THEN** 不得要求 agent 先通读全部 generated references

#### Scenario: workflow 编排任务走 workflow authoring 路径
- **WHEN** 用户请求编写或重构 workflow YAML 配置
- **THEN** skill 必须引导 agent 优先读取 workflow authoring 相关 references
- **THEN** 不得要求 agent 先通读全部 demand 语法目录或 generated references

#### Scenario: 旧写法升级任务直接按新结构处理
- **WHEN** 用户请求把旧 YAML DSL 写法升级为当前写法
- **THEN** skill 必须引导 agent 直接迁移到当前结构
- **THEN** 不得默认保留 legacy 写法作为兼容层

#### Scenario: 详细预设通过一层直达 references 提供
- **WHEN** 用户请求报表迁移 playbook、validate/debug 细则或完整语法目录
- **THEN** `SKILL.md` 必须直接链接到对应 reference
- **THEN** 不得要求 agent 先经过二级索引页再找到真正内容

## ADDED Requirements

### Requirement: Workflow CLI and LSP Guidance Is Explicit
系统 MUST 更新 `artifacts/skills/scalim-yaml-dsl/**`,使其在 workflow YAML 场景下也能提供明确、可复制的校验与 LSP 指引,并与当前实现边界保持一致:

- workflow YAML 仅支持 schema-only 校验（`yaml-dsl schema validate`）；不得引导用户对 workflow YAML 运行 `yaml-dsl validate` 作为“语义校验入口”.
- workflow YAML 的仓库内 schema-only 校验 MUST 提供显式 `--schema` 写法（schema 位置以仓库内 `workflow.gen.json` 为准）。
- workflow YAML 的本地编辑体验 MUST 提供 schema server + modeline 指引,并使用 `--type workflow`.

#### Scenario: workflow schema-only 校验指引
- **WHEN** 用户请求校验 workflow YAML
- **THEN** skill 必须提供 `uv run PROJECT_CLI_NAME yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>` 形式的命令
- **THEN** 不得建议直接使用 demand schema 或省略 `--schema`

#### Scenario: workflow LSP modeline 指引
- **WHEN** 用户请求让编辑器对 workflow YAML 提供补全/hover
- **THEN** skill 必须给出 schema server 与 upsert 命令,至少包含:
  - `uv run PROJECT_CLI_NAME yaml-dsl schema-serve`
  - `uv run PROJECT_CLI_NAME yaml-dsl upsert-lsp-comment --type workflow --schema-path http://localhost:62831 <paths...>`
- **THEN** 并给出 `$schema` header 示例（例如 `# $schema: http://localhost:62831/workflow.gen.json`）

