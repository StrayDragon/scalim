## MODIFIED Requirements

### Requirement: VSCode extension MUST manage LSP server lifecycle with an isolated venv

系统 MUST 要求 VSCode 扩展负责启动/管理 YAML DSL LSP server，并在 `globalStorageUri` 下维护隔离的 Python venv：

- 扩展 MUST 以 pinned 版本安装 LSP server 发行物（MVP 默认建议：`scalim-yaml-dsl-lsp[server]`）
- extension MUST 以 stdio 方式启动 server（遵循 `yaml-dsl-lsp-serve` contract）
- server 启动失败或 provisioning 失败时，extension MUST 提供可诊断提示（不得静默失败或阻塞基础 YAML 体验）
- 扩展 SHOULD 提供升级/回滚路径（MVP 可先实现“重装 pinned 版本”）

#### Scenario: first activation provisions and starts the server
- **WHEN** 用户首次在工作区启用该扩展
- **THEN** extension MUST 创建 venv 并安装 pinned 版本的 server 发行物
- **AND** extension MUST 成功启动 server 并提供可诊断日志
