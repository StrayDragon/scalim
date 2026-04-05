## MODIFIED Requirements

### Requirement: VSCode extension MUST cooperate with redhat.vscode-yaml for schema binding
系统 MUST 定义 VSCode 扩展 v1 行为,以与 `redhat.vscode-yaml` 协同提供结构(schema) + 语义(LSP)体验:

- 扩展 MUST 不替换 `redhat.vscode-yaml`,而是通过工作区 `yaml.schemas` 绑定 Scalim demand/workflow schema
- schema 绑定 MUST 使用 `scalim` 包内置的 `demand.gen.json`/`workflow.gen.json`(或等价可发布资源)
- 当 project discovery 能识别 YAML 类型时,扩展 SHOULD 仅对匹配的文件绑定对应 schema
- project discovery 的类型判定 SHOULD 以 schema(required) 为 SSOT,并与 LSP server 的判定保持一致（避免 schema 与语义边界漂移）

#### Scenario: schema mapping is configured for demand YAML
- **WHEN** 用户在 VSCode 打开一个被识别为 demand 的 YAML
- **THEN** 扩展 MUST 确保该文件使用 demand schema

