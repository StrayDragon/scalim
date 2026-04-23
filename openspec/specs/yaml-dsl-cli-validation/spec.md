# yaml-dsl-cli-validation Specification

## Purpose
定义 CLI 校验工具的行为契约，包括校验分层、诊断输出格式与错误定位，确保 CLI 结果可用于 IDE 跳转、CI 报告与脚本化消费。

## Related Concepts
- YAML DSL 校验模块
- CLI LSP 集成
- Config validator 服务层
- Unknown fields 检测
- Validation issues 类型
- 校验测试覆盖
## Requirements
### Requirement: CLI 与 runtime core 职责分离
系统 MUST 允许 CLI 实现独立于 runtime core 发行，但 MUST 保持对外行为契约一致：
- 校验逻辑 MUST 委托 runtime core 的可复用服务层，不得在 CLI 中复制语义实现
- runtime core MUST 可在不安装 CLI 的环境中被 import 使用
- CLI 的退出码、JSON payload 结构、诊断输出格式 MUST 保持规范一致

#### Scenario: runtime 可独立使用
- **GIVEN** 环境未安装 CLI 发行物
- **WHEN** 调用方导入并使用 runtime 入口
- **THEN** 导入与运行 MUST 成功

#### Scenario: CLI 复用统一校验逻辑
- **WHEN** YAML 在 runtime compile 中失败
- **THEN** CLI validate MUST 以相同结构失败

### Requirement: 校验契约 SSOT
系统 MUST 将 YAML DSL 的输入契约规则集中为单一实现：
- workflow compile、runtime compile、CLI validate MUST 复用同一套校验规则
- 对同一非法输入，不同入口 MUST 给出一致的接受/拒绝结果
- 错误信息 MUST 包含一致的关键字段（逻辑 path、失败原因、修复建议）

#### Scenario: 非法输入在各入口一致失败
- **GIVEN** 用户提供非法配置（如非法 sheet_name/输出名）
- **WHEN** 通过不同入口校验
- **THEN** 各入口 MUST 均 fail-fast 且给出一致诊断

### Requirement: CLI validate 职责边界
系统 SHALL 明确区分 validate 与 schema validate：
- `validate` 使用内部语义校验器，输出可行动诊断
- `validate` MUST NOT 执行 JSONSchema 校验，MUST NOT 输出 schema 依赖相关 warning
- `schema validate` 作为 schema-only 校验入口，依赖 `jsonschema` 并在缺失时 fail-fast
- 系统 MUST 对同一未知字段避免重复诊断（unknown-fields 与 additionalProperties 重叠时去重）

#### Scenario: validate 不依赖 jsonschema
- **GIVEN** 运行环境未安装 jsonschema
- **WHEN** 用户运行 validate 命令
- **THEN** 命令应正常执行且不输出 schema 依赖 warning

#### Scenario: schema validate 收集完整错误
- **GIVEN** YAML 配置触发多条 schema 错误
- **WHEN** 用户运行 schema validate
- **THEN** 输出 MUST 包含全部错误且排序稳定

#### Scenario: 未知字段诊断不重复
- **WHEN** 配置包含未知字段
- **THEN** 错误列表 MUST 包含 unknown-fields 诊断
- **AND** MUST NOT 包含同一路径的 additionalProperties 错误

### Requirement: 校验覆盖 fail-late 情况
系统 MUST 确保 validate 与 schema validate 对已知 fail-late 形态给出一致失败结果：
- 非法 mapping key（空 key/不匹配 identifier pattern）
- 空 loader/key 字段
- retry enabled 但缺失 should_retry
- 非法 streaming/fields 配置

#### Scenario: fail-late 情况早期捕获
- **GIVEN** YAML 包含上述任一错误形态
- **WHEN** 用户执行 validate
- **THEN** 命令 MUST 失败且错误指向对应路径

### Requirement: JSON 输出格式
系统 SHALL 在 `--json` 模式下输出结构化 JSON，包含 `ok`、`errors`、`yaml_path` 字段。

#### Scenario: JSON 输出结构
- **WHEN** 使用 `--json` 校验配置
- **THEN** 输出可解析的 JSON 且包含必需字段

### Requirement: 源码位置定位
系统 SHALL 在诊断输出中提供可跳转位置，格式至少包含 `path:line`。
- 当无法解析具体位置时，MUST 退化为文件级位置
- `ValidationIssue.path` MUST 使用 canonical 点号口径，支持 bracket 索引归一化

#### Scenario: 错误包含源码位置
- **WHEN** 校验失败
- **THEN** 输出应包含 `path:line[:column]` 位置

#### Scenario: bracket path 归一化
- **GIVEN** validator 产出 `outputs[0].path`
- **WHEN** CLI 输出诊断
- **THEN** MUST 能定位到对应源码位置
- **AND** 展示的逻辑路径 MUST 为 canonical 点号口径

### Requirement: Linter 风格输出
系统 SHALL 将非 JSON 输出统一为 linter/编译器风格，以单条诊断块展示级别、消息与位置，verbose 模式下附带源码片段。

#### Scenario: 使用 linter 风格输出
- **WHEN** 用户以默认方式运行校验
- **THEN** 每条诊断按 `ERROR ... --> path:line` 形式输出

### Requirement: Schema 发现与查看
系统 SHALL 提供 schema show 与 schema path 命令，用于查看当前 JSON Schema 及其路径。

#### Scenario: schema 查看
- **WHEN** 用户执行 schema show
- **THEN** 输出可解析的 JSON Schema

#### Scenario: schema 路径查看
- **WHEN** 用户执行 schema path
- **THEN** 输出 schema 的绝对路径

### Requirement: LSP comment 管理
系统 SHALL 提供 upsert-lsp-comment 命令，用于在 YAML 文件中插入或更新 schema modeline：
- 支持 Red Hat YAML Language Server 与 IntelliJ 两种格式
- 支持 `--comment-style` 控制写入风格
- 命令 MUST 幂等，未变更时不改写文件

#### Scenario: 插入两种 header
- **GIVEN** YAML 文件头部不包含 schema modeline
- **WHEN** 用户使用 `--comment-style all`
- **THEN** 文件头依次插入两种 modeline

#### Scenario: 仅保留特定 header
- **GIVEN** 文件包含两种 modeline
- **WHEN** 用户指定单一 comment-style
- **THEN** 仅保留对应格式的 modeline

### Requirement: Lint 命令
系统 MUST 提供 lint 命令，用于 YAML DSL authoring 风格与易踩坑点静态检查：
- 支持文件与目录输入，递归发现 YAML 文件
- 输出可跳转位置与稳定规则 code
- 支持 `--json` 与 `--fix`（仅执行确定性安全修复）
- v1 规则覆盖：quoted reference 可去引号、plain scalar 类型歧义、长 call_by 建议

#### Scenario: --fix 移除不必要引号
- **GIVEN** YAML 包含 `compute: "order_id"`
- **WHEN** 用户执行 lint --fix
- **THEN** 修复为 `compute: order_id` 且仍可解析为 string

#### Scenario: --json 输出结构化
- **WHEN** 用户执行 lint --json
- **THEN** 输出 JSON 包含 issue 的 code 与 range

### Requirement: Format 命令
系统 MUST 提供 format 命令，用于 YAML DSL 幂等格式化：
- 支持文件与目录输入
- format MUST 幂等（重复运行产生 0 diff）
- 聚焦特定字段的 string value 风格归一
- 仅当 plain scalar 仍会被解析为同一 string 时才去引号
- 支持 `--check` 与 `--diff`

#### Scenario: format 幂等且安全
- **GIVEN** YAML 包含 `loader: "pkg.mod:load_orders"`
- **WHEN** 用户执行 format
- **THEN** 输出 `loader: pkg.mod:load_orders`
- **AND** 再次运行 MUST 产生 0 diff

#### Scenario: format 保留必要引号
- **GIVEN** YAML 包含 `should_retry: "false"`
- **WHEN** 用户执行 format
- **THEN** 保留引号以确保值仍为 string

### Requirement: demand `schema validate` MUST support `--workflow` context for outputs→resources binding checks

系统 MUST 允许用户在对 **demand YAML** 执行 `yaml-dsl schema validate` 时提供 workflow 上下文参数：

- `yaml-dsl schema validate --workflow <workflow.yaml> <demand.yaml>`

当提供 `--workflow` 时，系统 MUST：

- 读取并解析 `<workflow.yaml>`，并提取可见资源 id 集合：
  - visible books = demand `resources.books` ∪ workflow `workflow.resources.books`
  - visible files = demand `resources.files` ∪ workflow `workflow.resources.files`
- 在 schema-only 校验的 outputs 绑定检查阶段，对每个 output 的 destination 执行资源存在性校验：
  - 若 output 绑定到 `to.book=<book_id>`：`<book_id>` MUST 存在于 visible books
  - 若 output 绑定到 `to.file=<file_id>`：`<file_id>` MUST 存在于 visible files
- 当 `<workflow.yaml>` 无法读取/解析时，schema validate MUST fail-fast（不得静默忽略 workflow 上下文）。

#### Scenario: schema validate accepts a workflow-declared book id
- **GIVEN** workflow YAML 声明 `workflow.resources.books.report`
- **AND** demand YAML 声明 `outputs[0].to.book: report`
- **AND** demand YAML 未声明 `resources.books.report`
- **WHEN** 调用方执行 `yaml-dsl schema validate --workflow workflow.yaml demand.yaml`
- **THEN** 校验 MUST 通过（退出码为 0）

#### Scenario: schema validate accepts a workflow-declared file id
- **GIVEN** workflow YAML 声明 `workflow.resources.files.detail_csv`
- **AND** demand YAML 声明 `outputs[0].to.file: detail_csv`
- **AND** demand YAML 未声明 `resources.files.detail_csv`
- **WHEN** 调用方执行 `yaml-dsl schema validate --workflow workflow.yaml demand.yaml`
- **THEN** 校验 MUST 通过（退出码为 0）

#### Scenario: schema validate fails fast when workflow context cannot be loaded
- **GIVEN** 用户提供不存在的 `--workflow missing.yaml`
- **WHEN** 调用方执行 `yaml-dsl schema validate --workflow missing.yaml demand.yaml`
- **THEN** 命令 MUST fail-fast（非零退出码）

#### Scenario: schema validate still rejects unknown ids even with workflow context
- **GIVEN** workflow YAML 未声明 `workflow.resources.books.report`
- **AND** demand YAML 未声明 `resources.books.report`
- **AND** demand YAML 声明 `outputs[0].to.book: report`
- **WHEN** 调用方执行 `yaml-dsl schema validate --workflow workflow.yaml demand.yaml`
- **THEN** 命令 MUST fail-fast（非零退出码）
- **AND** 错误 MUST 指向 `outputs[0].to.book`

### Requirement: demand `validate` MUST support the same `--workflow` context behavior as `schema validate`

系统 MUST 允许用户在对 **demand YAML** 执行 `yaml-dsl validate` 时提供 workflow 上下文参数：

- `yaml-dsl validate --workflow <workflow.yaml> <demand.yaml>`

并且该上下文的资源可见性语义 MUST 与 `schema validate` 一致（同一份输入在同一 workflow 上下文下，两者对 outputs→resources 绑定的接受/拒绝结果 MUST 一致）。

#### Scenario: validate accepts a workflow-declared resource id
- **GIVEN** workflow YAML 声明 `workflow.resources.books.report`
- **AND** demand YAML 声明 `outputs[0].to.book: report`
- **AND** demand YAML 未声明 `resources.books.report`
- **WHEN** 调用方执行 `yaml-dsl validate --workflow workflow.yaml demand.yaml`
- **THEN** 校验 MUST 通过（退出码为 0）

#### Scenario: validate accepts a workflow-declared file id
- **GIVEN** workflow YAML 声明 `workflow.resources.files.detail_csv`
- **AND** demand YAML 声明 `outputs[0].to.file: detail_csv`
- **AND** demand YAML 未声明 `resources.files.detail_csv`
- **WHEN** 调用方执行 `yaml-dsl validate --workflow workflow.yaml demand.yaml`
- **THEN** 校验 MUST 通过（退出码为 0）

## Notes
- CLI 实现可迁移到独立发行物，但必须保持行为契约
- lint 与 format 命令仅处理可安全自动修复的场景
