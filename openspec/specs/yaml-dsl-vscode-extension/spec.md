# yaml-dsl-vscode-extension Specification

## Purpose
为 VSCode 用户提供 YAML DSL 的默认入口：在扩展侧负责 LSP server provisioning / lifecycle / 诊断输出，
并与 `redhat.vscode-yaml` 协作完成 schema 绑定，从而实现“开箱即用 + 可排障”的编辑体验。

本仓库的扩展源代码固定在 `extras/vscode-scalim/`（不迁移到 `packages/`/`frontend/`；发布/签名策略不影响源码目录位置）。
## Requirements
### Requirement: VSCode extension MUST cooperate with redhat.vscode-yaml for schema binding
系统 MUST 定义 VSCode 扩展 v1 行为,以与 `redhat.vscode-yaml` 协同提供结构(schema) + 语义(LSP)体验:

- 扩展 MUST 不替换 `redhat.vscode-yaml`,而是通过工作区 `yaml.schemas` 绑定 Scalim demand/workflow schema
- schema 绑定 MUST 使用 `scalim` 包内置的 `demand.gen.json`/`workflow.gen.json`(或等价可发布资源)
- 当 project discovery 能识别 YAML 类型时,扩展 SHOULD 仅对匹配的文件绑定对应 schema
- project discovery 的类型判定 SHOULD 以 schema(required) 为 SSOT,并与 LSP server 的判定保持一致（避免 schema 与语义边界漂移）

#### Scenario: schema mapping is configured for demand YAML
- **WHEN** 用户在 VSCode 打开一个被识别为 demand 的 YAML
- **THEN** 扩展 MUST 确保该文件使用 demand schema

### Requirement: VSCode extension MUST manage LSP server lifecycle with an isolated venv

系统 MUST 要求 VSCode 扩展负责启动/管理 YAML DSL LSP server，并在 `globalStorageUri` 下维护隔离的 Python venv：

- 扩展 MUST 以 pinned 版本安装 LSP server 发行物（MVP 默认建议：`scalim-yaml-dsl-lsp==0.7.5`；且 MUST 提供配置以覆盖 pinned 版本）
- extension provisioning MUST 依赖 Python >=3.10；若无法找到/版本不足，extension MUST 给出可诊断提示（不得静默失败）
- extension MUST 以 stdio 方式启动 `scalim-yaml-dsl-lsp serve`（遵循 `yaml-dsl-lsp-serve` contract）
- server 启动失败或 provisioning 失败时，extension MUST 提供可诊断提示（不得静默失败或阻塞基础 YAML 体验）
- 扩展 SHOULD 提供升级/回滚路径（MVP 可先实现“重装 pinned 版本”）

#### Scenario: first activation provisions and starts the server
- **WHEN** 用户首次在工作区启用该扩展
- **THEN** extension MUST 创建 venv 并安装 pinned 版本的 server 发行物
- **AND** extension MUST 成功启动 server 并提供可诊断日志

### Requirement: Extension MUST sync project discovery config to both schema mapping and LSP
扩展 MUST 读取并应用项目发现/配置结果:

- 扩展 MUST 读取 nearest `scalim.yaml`(或等价配置)并将其作为 LSP server 的 discovery 输入
- 扩展 SHOULD 将 discovery 结果反映到 schema mapping(例如 demand/workflow 的文件识别规则)
- 扩展 MUST 提供诊断信息用于排障(例如当前使用的 config 路径与 python_roots)

#### Scenario: config changes update schema and LSP behavior
- **GIVEN** 用户修改了 `scalim.yaml` 中与 discovery 相关的配置
- **WHEN** 扩展检测到配置变化
- **THEN** schema mapping 与 LSP 行为 MUST 按新配置更新

### Requirement: VSCode extension MUST surface LSP code actions as Quick Fix and provide one-click troubleshooting commands

系统 MUST 要求 VSCode extension 将 YAML DSL LSP server 的标准 LSP code actions 映射为 VSCode Quick Fix，并提供一键排障入口：

- Quick Fix MUST 直接来源于 server 的 `codeAction/executeCommand`（extension 不得复制语义规则）
- extension MUST 提供命令：重启 server、打开日志、显示当前 discovery 摘要、打开/创建 `scalim.yaml`
- extension SHOULD 提供状态栏信息（server 运行状态与版本）

#### Scenario: a Quick Fix can create scalim.yaml from the editor UI
- **GIVEN** 当前 YAML 无法发现 `scalim.yaml` 且 server 提供对应 Quick Fix
- **WHEN** 用户在 VSCode 中选择 Quick Fix
- **THEN** extension MUST 执行对应 command 并应用 `WorkspaceEdit`
- **AND** 用户 MUST 能在日志中看到可诊断信息（包含 discovery 摘要）

### Requirement: extension MUST provide a doctor command with actionable fixes

VSCode extension MUST 提供 `Scalim: Doctor` 预检命令，用于覆盖最常见的安装/配置失败路径，并对失败项提供可操作的修复引导（按钮/命令）。

#### Scenario: missing scalim.yaml is detected and guided
- **GIVEN** workspace 中缺失 `scalim.yaml`
- **WHEN** 用户运行 `Scalim: Doctor`
- **THEN** doctor MUST 报告失败项 “No scalim.yaml”
- **AND** MUST 提供“创建 scalim.yaml（从模板）/打开创建位置”的引导入口

### Requirement: diagnostic bundle MUST NOT include YAML contents

extension 的 “Copy Diagnostic Bundle” 功能 MUST 生成可粘贴到 issue 的诊断报告,且该报告 MUST NOT 包含用户 YAML 正文（隐私边界）。

#### Scenario: diagnostic bundle redacts YAML contents
- **GIVEN** workspace 中存在任意 YAML DSL 文件（含可能敏感内容）
- **WHEN** 用户执行 `Scalim: Copy Diagnostic Bundle`
- **THEN** 生成的文本 MUST 不包含 YAML 正文片段
- **AND** 仍 MUST 包含可用于排障的环境与 discovery 摘要（版本、Python 路径、scalim.yaml 路径、roots 摘要等）
