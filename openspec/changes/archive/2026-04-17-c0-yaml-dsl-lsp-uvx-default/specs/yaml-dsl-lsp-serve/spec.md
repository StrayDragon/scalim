# yaml-dsl-lsp-serve (delta) Specification

## MODIFIED Requirements

### Requirement: serve initialization failure MUST be diagnosable and MUST NOT emit partial JSON-RPC
当 server 依赖缺失或初始化失败时，系统 MUST：

- MUST 以非 0 exit code 退出
- MUST 在 stderr 输出可诊断的错误信息
- MUST NOT 在 stdout 输出半截 JSON-RPC（不得污染 LSP client 通道）
- stderr 的错误信息 MUST 包含可执行的修复提示示例，且至少覆盖两条路径：
  - **installed 修复**：重新安装 `scalim-yaml-dsl-lsp` 以补齐依赖（例如 `uv tool install scalim-yaml-dsl-lsp`）
  - **ephemeral 修复**：使用 `uvx` 一键启动（例如 `uvx scalim-yaml-dsl-lsp serve --log-level INFO`）

#### Scenario: missing server dependency yields clean failure
- **GIVEN** 环境已安装 `scalim-yaml-dsl-lsp`，但运行时依赖缺失（例如安装时使用了 `--no-deps` 导致缺少 `pygls`）
- **WHEN** 用户执行 `scalim-yaml-dsl-lsp serve`
- **THEN** 进程 MUST 立即失败并返回非 0
- **AND** stderr MUST 包含可操作的安装/修复提示（至少包含 `uv tool install scalim-yaml-dsl-lsp` 与 `uvx scalim-yaml-dsl-lsp serve --log-level INFO` 的等价提示）
- **AND** stdout MUST 为空

