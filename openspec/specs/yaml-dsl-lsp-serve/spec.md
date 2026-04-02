# yaml-dsl-lsp-serve Specification

## Purpose
提供一个跨编辑器可复用的 YAML DSL LSP server 启动入口（默认 stdio），并约束其日志/降级行为，
以保证编辑器集成稳定且可排障。

## Requirements
### Requirement: CLI MUST provide a stable `scalim-yaml-dsl-lsp serve` entrypoint (stdio by default)
系统 MUST 提供一个稳定的 server 启动入口，供任意 LSP client 通过一个命令拉起：

- MUST 提供命令：`scalim-yaml-dsl-lsp serve`
- MUST 默认以 stdio 模式运行（stdout/stderr 分离；stdout 仅用于 JSON-RPC）
- MAY 提供 `--tcp` 模式（仅用于 debug；不作为 v1 必选）
- MUST 支持配置日志输出到 stderr 或文件（不得写入 stdout）

#### Scenario: server is started via stdio without log pollution
- **GIVEN** 用户在终端执行 `scalim-yaml-dsl-lsp serve`
- **WHEN** LSP client 与 server 通过 stdio 交互
- **THEN** stdout MUST 仅包含 JSON-RPC payload
- **AND** 任何日志 MUST 输出到 stderr 或日志文件

### Requirement: serve initialization failure MUST be diagnosable and MUST NOT emit partial JSON-RPC
当 server 依赖缺失或初始化失败时，系统 MUST：

- MUST 以非 0 exit code 退出
- MUST 在 stderr 输出可诊断的错误信息
- MUST NOT 在 stdout 输出半截 JSON-RPC（不得污染 LSP client 通道）

#### Scenario: missing server dependency yields clean failure
- **GIVEN** 环境未安装 `scalim-yaml-dsl-lsp[server]`（缺少 `pygls`）
- **WHEN** 用户执行 `scalim-yaml-dsl-lsp serve`
- **THEN** 进程 MUST 立即失败并返回非 0
- **AND** stderr MUST 包含“需要安装 server extra”的提示
- **AND** stdout MUST 为空

### Requirement: CLI MUST provide a `dump-discovery` troubleshooting entrypoint
系统 MUST 提供一个排障入口用于导出 project discovery 摘要（便于用户自助诊断或粘贴到 issue）：

- MUST 提供命令：`scalim-yaml-dsl-lsp dump-discovery <yaml_path> --json`
- MUST 输出 JSON payload（至少包含 `project_root/scalim_yaml_path/python_roots/allowed_yaml_roots`）
- MUST 为静态无副作用（仅文件系统读取与解析；不得执行用户代码）

#### Scenario: dump-discovery returns a JSON summary for an arbitrary YAML file
- **GIVEN** 用户有一个 YAML 文件 `demo.yaml`
- **WHEN** 执行 `scalim-yaml-dsl-lsp dump-discovery demo.yaml --json`
- **THEN** stdout MUST 输出一个 JSON 对象
- **AND** JSON MUST 包含 `project_root/scalim_yaml_path/python_roots/allowed_yaml_roots` 字段

### Requirement: Serve contract MUST include a troubleshooting entrypoint
系统 MUST 提供可排障入口，用于让用户确认当前 workspace 的 project discovery 摘要：

- project_root
- scalim_yaml_path（可为空）
- python_roots
- allowed_yaml_roots

该信息 MUST 可通过日志或可查询命令获得（实现形式由 design 决定）。

#### Scenario: user can obtain discovery summary for an issue report
- **WHEN** 用户按文档执行排障步骤
- **THEN** 用户 MUST 能获得 discovery 摘要并可粘贴到 issue
