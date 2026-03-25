# yaml-dsl-editor-config Specification

**状态: ⏳ 规划中**

## ADDED Requirements

### Requirement: 系统支持读取 `scalim.config.yaml`

系统 MUST 支持在 workspace 根目录读取并解析 `scalim.config.yaml`，作为编辑器/LSP 的配置 SSOT。

#### Scenario: 配置文件存在时读取
- **WHEN** workspace 根目录存在 `scalim.config.yaml`
- **THEN** 系统读取并解析该文件用于后续文件识别与语义能力分流

#### Scenario: 配置文件不存在时使用默认
- **WHEN** workspace 根目录不存在 `scalim.config.yaml`
- **THEN** 系统使用默认配置：
  - demand globs: `**/*.scalim.demand.yaml`
  - workflow globs: `**/*.scalim.workflow.yaml`
  - python roots: 若存在 `src/` 则为 `["src"]`，否则为 `["."]`

### Requirement: `yaml_dsl.files` 定义 DSL 文件识别规则

系统 MUST 支持通过 `yaml_dsl.files` 配置列表识别哪些 YAML 文件属于 Scalim DSL，并区分其类型边界。

#### Scenario: 支持 demand 与 workflow 两种类型
- **WHEN** `yaml_dsl.files[*].type` 为 `demand` 或 `workflow`
- **THEN** 系统按对应 `globs` 将文件分类到 demand 或 workflow 能力边界

#### Scenario: 禁止未知类型
- **WHEN** `yaml_dsl.files[*].type` 不是 `demand`/`workflow`
- **THEN** 系统 MUST 报告配置错误并拒绝加载该配置文件

### Requirement: `yaml_dsl.python.roots` 定义 Python roots

系统 MUST 支持通过 `yaml_dsl.python.roots` 指定用于静态引用解析的 Python roots。

#### Scenario: roots 为字符串列表
- **WHEN** `yaml_dsl.python.roots` 提供为字符串列表
- **THEN** 系统将其作为模块落盘解析的搜索 roots（不执行 import）

### Requirement: `yaml_dsl.lsp.diagnostics` 定义诊断触发策略

系统 MUST 支持通过 `yaml_dsl.lsp.diagnostics` 配置诊断触发策略。

#### Scenario: 支持 on_save 与 on_change debounce
- **WHEN** 配置包含 `on_save` 与 `on_change_debounce_ms`
- **THEN** 系统按配置触发 Diagnostics（保存触发 + 变更去抖触发）

