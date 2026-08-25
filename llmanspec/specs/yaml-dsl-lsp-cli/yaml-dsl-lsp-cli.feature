# language: zh-CN
# capability: yaml-dsl-lsp-cli
# purpose: 提供一个跨编辑器可复用的 YAML DSL LSP server 启动入口（默认 stdio），并约束其日志/降级行为， 以保证编辑器集成稳定且可排障。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-lsp-cli

  @req:r116 @human
  场景: CLI MUST provide a stable `scalim-yaml-dsl-lsp serve` entrypoint (stdio by defau
    - 系统 MUST 提供一个稳定的 server 启动入口，供任意 LSP client 通过一个命令拉起： - MUST 提供命令：`scalim-yaml-dsl-lsp serve` - MUST 默认以 stdio 模式运行（stdout/stderr 分离；stdout 仅用于 JSON-RPC） - MAY 提供 `--tcp` 模式（仅用于 debug；不作为 v1 必选） - MUST 支持配置日志输出到 stderr 或文件（不得写入 stdout）

  @req:r358 @human
  场景: serve initialization failure MUST be diagnosable and MUST NOT emit partial JSON-
    - 当 server 依赖缺失或初始化失败时，系统 MUST： - MUST 以非 0 exit code 退出 - MUST 在 stderr 输出可诊断的错误信息 - MUST NOT 在 stdout 输出半截 JSON-RPC（不得污染 LSP client 通道） - stderr 的错误信息 MUST 包含可执行的修复提示示例，且至少覆盖两条路径： - **installed 修复**：重新安装 `scalim-yaml-dsl-lsp` 以补齐依赖（例如 `uv tool install scalim-yaml-dsl-lsp`） - **ephemeral 修复**：使用 `uvx` 一键启动（例如 `uvx scalim-yaml-dsl-lsp serve --log-level INFO`）

  @req:r479 @human
  场景: CLI MUST provide a `dump-discovery` troubleshooting entrypoint
    - 系统 MUST 提供一个排障入口用于导出 project discovery 摘要（便于用户自助诊断或粘贴到 issue）： - MUST 提供命令：`scalim-yaml-dsl-lsp dump-discovery <yaml_path> --json` - MUST 输出 JSON payload（至少包含 `project_root/scalim_yaml_path/python_roots/allowed_yaml_roots`） - MUST 为静态无副作用（仅文件系统读取与解析；不得执行用户代码）

  @req:r561 @human
  场景: Serve contract MUST include a troubleshooting entrypoint
    - 系统 MUST 提供可排障入口，用于让用户确认当前 workspace 的 project discovery 摘要： - project_root - scalim_yaml_path（可为空） - python_roots - allowed_yaml_roots 该信息 MUST 可通过日志或可查询命令获得（实现形式由 design 决定）。
  @req:r116 @human
  场景: server-is-started-via-stdio-without-log-pollution
    - 必须成立：假如 用户在终端执行 `scalim-yaml-dsl-lsp serve`；当 LSP client 与 server 通过 stdio 交互；那么 stdout MUST 仅包含 JSON-RPC payload
    假如 用户在终端执行 `scalim-yaml-dsl-lsp serve`
    当 LSP client 与 server 通过 stdio 交互
    那么 stdout MUST 仅包含 JSON-RPC payload
  @req:r358 @human
  场景: missing-server-dependency-yields-clean-failure
    - 必须成立：假如 环境已安装 `scalim-yaml-dsl-lsp`，但运行时依赖缺失（例如安装时使用了 `--no-deps` 导致缺少 `pygls`）；当 用户执行 `scalim-yaml-dsl-lsp serve`；那么 进程 MUST 立即失败并返回非 0
    假如 环境已安装 `scalim-yaml-dsl-lsp`，但运行时依赖缺失（例如安装时使用了 `--no-deps` 导致缺少 `pygls`）
    当 用户执行 `scalim-yaml-dsl-lsp serve`
    那么 进程 MUST 立即失败并返回非 0
  @req:r479 @human
  场景: dump-discovery-returns-a-json-summary-for-an-arbitrary-yaml-
    - 必须成立：假如 用户有一个 YAML 文件 `demo.yaml`；当 执行 `scalim-yaml-dsl-lsp dump-discovery demo.yaml --json`；那么 stdout MUST 输出一个 JSON 对象
    假如 用户有一个 YAML 文件 `demo.yaml`
    当 执行 `scalim-yaml-dsl-lsp dump-discovery demo.yaml --json`
    那么 stdout MUST 输出一个 JSON 对象
  @req:r561 @human
  场景: user-can-obtain-discovery-summary-for-an-issue-report
    - 必须成立：当 用户按文档执行排障步骤；那么 用户 MUST 能获得 discovery 摘要并可粘贴到 issue
    当 用户按文档执行排障步骤
    那么 用户 MUST 能获得 discovery 摘要并可粘贴到 issue
