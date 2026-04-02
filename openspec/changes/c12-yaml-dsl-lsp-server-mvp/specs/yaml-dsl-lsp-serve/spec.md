## ADDED Requirements

### Requirement: YAML DSL LSP server MUST be startable via a stable stdio entrypoint
系统 MUST 提供一个稳定的启动入口，用于通过 stdio 拉起 YAML DSL LSP server：

- 默认 MUST 使用 stdio（stdin/stdout）
- MUST 支持输出可诊断日志（至少到 stderr 或可配置文件）
- MUST 在初始化失败时以可诊断方式退出（不得输出半截 JSON-RPC）

#### Scenario: client can start server via stdio
- **WHEN** 任意 LSP client 以 stdio 启动 server
- **THEN** server MUST 正常完成 initialize/initialized 交互并开始处理文本事件

### Requirement: Server MUST treat TCP transport as optional and debugging-only
系统 MUST 保持 stdio 为 v1 编辑器集成默认路径；系统 MAY 额外提供 TCP 模式，但仅用于本地 debug：

- TCP MUST NOT 作为 v1 编辑器集成默认路径

#### Scenario: tcp is optional and does not replace stdio
- **WHEN** 用户以 tcp 模式启动 server
- **THEN** server MUST 行为与 stdio 模式一致（除传输层外）

### Requirement: Distribution MUST expose a CLI entrypoint with `serve` and `dump-discovery`
系统 MUST 提供一个稳定的 CLI 入口 `scalim-yaml-dsl-lsp`，并支持子命令：

- `scalim-yaml-dsl-lsp serve`：启动 LSP server（默认 stdio）
- `scalim-yaml-dsl-lsp dump-discovery <yaml_path> --json`：输出 discovery 摘要（JSON 可序列化）

discovery 摘要 MUST 至少包含：

- project_root
- scalim_yaml_path（可为空）
- python_roots
- allowed_yaml_roots

#### Scenario: dump-discovery prints a JSON discovery payload
- **GIVEN** 用户提供一个存在的 YAML 文件路径
- **WHEN** 用户运行 `scalim-yaml-dsl-lsp dump-discovery <yaml_path> --json`
- **THEN** 命令 MUST 输出包含 `project_root/scalim_yaml_path/python_roots/allowed_yaml_roots` 的 JSON payload
