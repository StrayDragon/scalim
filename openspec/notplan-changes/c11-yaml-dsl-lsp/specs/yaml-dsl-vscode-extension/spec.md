# yaml-dsl-vscode-extension Specification

**状态: ⏳ 规划中**

## ADDED Requirements

### Requirement: 扩展与 `redhat.vscode-yaml` 协同而非替换

VSCode 扩展 MUST 将 `redhat.vscode-yaml` 作为依赖扩展并与其协同工作。

#### Scenario: 声明扩展依赖
- **WHEN** 扩展发布并安装到 VSCode
- **THEN** 扩展 manifest MUST 声明依赖 `redhat.vscode-yaml`

### Requirement: 扩展负责 schema 绑定（零配置默认可用）

扩展 MUST 在无需用户手写 settings 的情况下，为 Scalim DSL YAML 文件绑定对应 schema。

#### Scenario: 默认 glob 的 schema 绑定
- **WHEN** workspace 中存在 `**/*.scalim.demand.yaml` 或 `**/*.scalim.workflow.yaml`
- **THEN** 扩展通过 `yamlValidation` 将其绑定到内置的 demand/workflow schema

### Requirement: 扩展支持从 `scalim.config.yaml` 同步 schema 映射

当用户自定义 globs 时，扩展 MUST 提供命令将映射同步到工作区 `yaml.schemas`。

#### Scenario: 同步命令写入 yaml.schemas
- **WHEN** 用户执行 `Sync YAML Schemas From scalim.config.yaml`
- **THEN** 扩展读取 `scalim.config.yaml` 并将映射写入工作区 settings 的 `yaml.schemas`

### Requirement: 扩展负责 Python LSP server 的环境管理与启动

扩展 MUST 在 `globalStorageUri` 下维护 venv，并以 pinned 版本安装/升级 LSP server 与其依赖。

#### Scenario: 首次激活创建 venv 并安装依赖
- **WHEN** 扩展首次激活且 venv 不存在
- **THEN** 扩展创建 venv 并安装 pinned 的 LSP server 包与 `scalim` 依赖

#### Scenario: 启动 server 并连接 language client
- **WHEN** 扩展完成 venv 准备
- **THEN** 扩展以 stdio 方式启动 Python LSP server 并建立 LSP 连接

