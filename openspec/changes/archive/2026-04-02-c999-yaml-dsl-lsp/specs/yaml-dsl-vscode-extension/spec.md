## ADDED Requirements

### Requirement: VSCode extension MUST cooperate with redhat.vscode-yaml for schema binding
系统 MUST 定义 VSCode 扩展 v1 行为,以与 `redhat.vscode-yaml` 协同提供结构(schema) + 语义(LSP)体验:

- 扩展 MUST 不替换 `redhat.vscode-yaml`,而是通过工作区 `yaml.schemas` 绑定 Scalim demand/workflow schema
- schema 绑定 MUST 使用 `scalim` 包内置的 `demand.gen.json`/`workflow.gen.json`(或等价可发布资源)
- 当 project discovery 能识别 YAML 类型时,扩展 SHOULD 仅对匹配的文件绑定对应 schema

#### Scenario: schema mapping is configured for demand YAML
- **WHEN** 用户在 VSCode 打开一个被识别为 demand 的 YAML
- **THEN** 扩展 MUST 确保该文件使用 demand schema

### Requirement: VSCode extension MUST manage LSP server lifecycle with an isolated venv
系统 MUST 要求 VSCode 扩展负责启动/管理 YAML DSL LSP server:

- 扩展 MUST 在 `globalStorageUri` 下维护隔离的 Python venv
- 扩展 MUST 以 pinned 版本安装 LSP server 包,并支持升级/回滚
- server 启动失败时,扩展 MUST 以可诊断提示告知用户,且不得阻塞编辑器的基础 YAML 体验

#### Scenario: extension provisions and starts the server
- **WHEN** 用户首次在工作区启用该扩展
- **THEN** 扩展 MUST 创建 venv 并启动 LSP server
- **AND** 若 provisioning 失败,MUST 提示用户失败原因与修复方式

### Requirement: Extension MUST sync project discovery config to both schema mapping and LSP
扩展 MUST 读取并应用项目发现/配置结果:

- 扩展 MUST 读取 nearest `scalim.yaml`(或等价配置)并将其作为 LSP server 的 discovery 输入
- 扩展 SHOULD 将 discovery 结果反映到 schema mapping(例如 demand/workflow 的文件识别规则)
- 扩展 MUST 提供诊断信息用于排障(例如当前使用的 config 路径与 python_roots)

#### Scenario: config changes update schema and LSP behavior
- **GIVEN** 用户修改了 `scalim.yaml` 中与 discovery 相关的配置
- **WHEN** 扩展检测到配置变化
- **THEN** schema mapping 与 LSP 行为 MUST 按新配置更新
