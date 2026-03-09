# yaml-dsl-agent-guidance Specification

**状态: ✅ 已实现**

## Purpose
定义 `scalim-yaml-dsl` 手工维护 skill 的任务驱动组织方式,确保 agent 能基于最小入口、明确命令和按需 references 一次完成 YAML 编写、升级、校验、订正与渐进迁移方案设计.

## Context
实现位于 `artifacts/skills/scalim-yaml-dsl/`.
该能力与自动生成的参考产物配合工作: `SKILL.md` 负责任务路由和最小操作入口,手工 references 负责场景预设与迁移 heuristics,受控参考产物负责完整语法/API catalog.

## Related Code (as implemented)
- `artifacts/skills/scalim-yaml-dsl/SKILL.md`
- `artifacts/skills/scalim-yaml-dsl/agents/openai.yaml`
- `artifacts/skills/scalim-yaml-dsl/references/task-authoring.md`
- `artifacts/skills/scalim-yaml-dsl/references/task-upgrade-legacy.md`
- `artifacts/skills/scalim-yaml-dsl/references/task-validate-debug.md`
- `artifacts/skills/scalim-yaml-dsl/references/task-report-migration-playbook.md`
- `tests/test_agent_skill_generator.py`
- `docs/doc/yaml-dsl/agent-skill.md`

## Requirements

### Requirement: Task-Driven Manual Skill Entry
系统 MUST 提供手工维护的 YAML DSL skill 本体,用于把 agent 引导到正确的任务路径,而不是把 skill 退化为单个 schema 摘要页.

手工维护的 `SKILL.md` MUST 明确覆盖至少以下任务类型:
- 新建或修改 YAML DSL 配置
- 将旧写法直接升级到当前结构
- 对现有 YAML 做 schema/full validate 与订正
- 为某类 legacy 批量报表脚本设计渐进迁移方案

`SKILL.md` MUST 指示 agent 先识别任务类型,再按需读取最少的 references,而不是默认加载全部参考资料.
`SKILL.md` MUST 保持 routing-first: 只保留任务分流、最小命令入口与对一层直达 references 的链接; 详细场景预设、迁移 heuristics 与完整语法目录 MUST 放在被直接链接的 references 中.

#### Scenario: 新建 YAML 任务走 authoring 路径
- **WHEN** 用户请求编写或重构 YAML DSL 配置
- **THEN** skill 必须引导 agent 先读取 authoring 相关 references
- **THEN** 不得要求 agent 先通读全部 generated references

#### Scenario: 旧写法升级任务直接按新结构处理
- **WHEN** 用户请求把旧 YAML DSL 写法升级为当前写法
- **THEN** skill 必须引导 agent 直接迁移到当前结构
- **THEN** 不得默认保留 legacy 写法作为兼容层

#### Scenario: 详细预设通过一层直达 references 提供
- **WHEN** 用户请求报表迁移 playbook、validate/debug 细则或完整语法目录
- **THEN** `SKILL.md` 必须直接链接到对应 reference
- **THEN** 不得要求 agent 先经过二级索引页再找到真正内容

### Requirement: CLI and LSP Guidance Is Explicit
手工维护的 skill MUST 直接提供可复制的 CLI/LSP 指引,覆盖仓库内与脱离仓库两种使用方式.

指引 MUST 明确包含:
- `uv run PROJECT_CLI_NAME yaml-dsl validate <file.yaml>`
- `uv run PROJECT_CLI_NAME yaml-dsl schema validate <file.yaml>`
- `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME yaml-dsl validate <file.yaml>`
- `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME yaml-dsl schema validate <file.yaml>`
- `uv run PROJECT_CLI_NAME yaml-dsl schema path`
- `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME yaml-dsl schema path`
- `# yaml-language-server: $schema=...` 的 header 参考

skill MUST 明确指出 schema path 可通过 `PROJECT_CLI_NAME yaml-dsl schema path` 查询,并提供 header 模板.
skill MUST 明确指出 canonical example 不应固化本机 `.venv/...`、`site-packages/...` 或仓库私有相对路径头部.

#### Scenario: 仓库内用户获取校验指引
- **WHEN** 用户在仓库内工作并请求校验 YAML
- **THEN** skill 必须提供 `uv run PROJECT_CLI_NAME ...` 形式的命令

#### Scenario: 脱离仓库用户获取 CLI 指引
- **WHEN** 用户不在仓库内但需要运行 CLI 校验
- **THEN** skill 必须提供 `uvx --from "PROJECT_DIST_NAME[cli]" PROJECT_CLI_NAME ...` 形式的命令

#### Scenario: 用户需要配置 YAML LSP
- **WHEN** 用户请求编辑器补全或 schema 头部示例
- **THEN** skill 必须提供 `$schema` header 示例与 schema path 获取方式

### Requirement: Skill Provides Sanitized Migration Playbook
手工维护的 skill MUST 包含脱敏后的“legacy 批量报表脚本渐进迁移到 YAML DSL” playbook,用于指导 agent 在不暴露业务私有路径、系统名或实现细节的前提下完成调研与方案设计.

该 playbook MUST 指导 agent:
- 分析原始入口脚本及其直接依赖
- 识别主数据链路、宽表结构、聚合逻辑、分 sheet 导出逻辑
- 判断是否属于“大宽表 + 分组拆多 sheet”场景
- 判断当前 YAML DSL 不支持或不擅长的能力,例如多 sheet 输出、跨行聚合、多轮 runtime state 依赖
- 判断哪些 loader 可直接引用下游 BLL/服务方法,哪些必须保留最薄 Python 适配层
- 使用脱敏后的占位路径、占位 marker 与占位模块名描述迁移路由,而不是复用真实业务字面量

#### Scenario: 多 sheet 宽表场景被识别
- **WHEN** 目标脚本本质上是同一份宽表按规则拆分成多个 sheet
- **THEN** playbook 必须引导 agent 优先把宽表构建放到 YAML DSL
- **THEN** 并把多 sheet 组装保留在最薄 Python 边界

#### Scenario: 运行时状态超出 DSL 当前能力
- **WHEN** 目标逻辑依赖多轮 runtime state、compare 路由或其它当前 DSL 不擅长的能力
- **THEN** playbook 必须引导 agent 保留这些逻辑在 Python
- **THEN** 并说明保留原因与未来继续下沉的方向

#### Scenario: 可直接引用下游 loader
- **WHEN** 原场景使用的下游 BLL/服务方法符合 YAML DSL loader contract
- **THEN** playbook 必须引导 agent 优先直接引用这些方法
- **THEN** 只有在 contract 或能力边界不满足时才引入最小 Python 适配

#### Scenario: 迁移示例使用脱敏占位
- **WHEN** playbook 需要展示入口路由、marker 或模块路径示例
- **THEN** 文案必须使用脱敏占位写法
- **THEN** 不得直接出现真实项目名、绝对路径、私有模块名或私有 marker

### Requirement: Skill Encodes Gradual Migration Heuristics
skill MUST 为这类报表迁移任务提供清晰的职责切分准则,让 agent 自动判断哪些逻辑下沉到 YAML、哪些逻辑暂留 Python.

默认准则 MUST 包含:
- 主数据源定义、字段映射、sources/relations/output 编排优先进入 YAML
- 宽表生成完成后的多 sheet 分发、runtime context/state map、compare 路由可暂留 Python
- 对外入口签名与输出接口稳定性优先于“一次性全量重写”
- 在未明确要求兼容时,旧 DSL 写法直接升级到新写法

#### Scenario: 需要 compare-friendly 渐进路由
- **WHEN** 迁移任务要求保留 legacy/new 双路由用于 compare 或回滚观察
- **THEN** skill 必须引导 agent 仅保留最小 legacy 路由边界
- **THEN** 新实现内部结构仍按新写法一次到位收敛

#### Scenario: 目标是后续模板化复用
- **WHEN** 用户强调后续还会迁移同类脚本
- **THEN** skill 必须引导 agent 优先选择单 YAML + 单入口的精简结构
- **THEN** 不得默认拆出大量 `_loaders.py`、`_helpers.py`、`_adapters.py`

### Requirement: Full Syntax and API Catalog Remains Discoverable
skill MUST 提供对完整 YAML DSL 语法与相关 CLI API 的可发现入口,但这些全量信息 MUST 放在按需读取的 references 中.

至少 MUST 可发现:
- 顶层字段与 definitions
- enum/default/examples 或等价约束信息
- 互斥关系、必填关系与旧写法升级约束
- `yaml-dsl` 相关 CLI 命令与关键参数

#### Scenario: 用户请求完整语法目录
- **WHEN** 用户请求查看 YAML DSL 全量语法或 API
- **THEN** skill 必须把 agent 引导到 generated catalog
- **THEN** catalog 中必须覆盖完整字段与 CLI 入口

### Requirement: Skill-Creator Progressive Disclosure Is Enforced
skill MUST 遵循 `skill-creator` 风格的渐进披露约束: `SKILL.md` 保持精简,详细任务预设、排错说明与完整 catalog 通过 first-level references 按需加载.

至少 MUST 满足:
- `SKILL.md` 不内联完整 schema dump 或完整 playbook 正文
- task-specific manual references 与 generated references 都由 `SKILL.md` 直接链接
- 不依赖多层索引文档才能触达关键 guidance

#### Scenario: SKILL.md 不退化为 schema dump
- **WHEN** 维护者更新手工 skill
- **THEN** `SKILL.md` 必须仍以任务路由和命令入口为主
- **THEN** 完整语法/API 与大段场景预设应保留在 references 中

### Requirement: Validation-First Delivery Guidance
skill MUST 指导 agent 在交付 YAML 或迁移方案时优先完成可执行的校验与边界说明.

至少 MUST 包含:
- schema validate
- full validate
- 缺失依赖或环境前提时的显式说明
- 对“已验证什么、未验证什么”的交付要求

#### Scenario: 环境不完整时仍需说明验证边界
- **WHEN** 当前环境无法跑通真实数据库或下游系统
- **THEN** skill 必须要求 agent 明确说明缺少什么依赖
- **THEN** 并说明已完成哪些静态校验与 YAML 校验
