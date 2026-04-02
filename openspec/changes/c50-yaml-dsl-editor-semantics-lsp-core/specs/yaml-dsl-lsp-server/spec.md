# yaml-dsl-lsp-server Specification (Delta)

## ADDED Requirements

### Requirement: LSP server MUST delegate editor semantics to shared core library
系统 MUST 在 LSP server 内统一复用抽离后的 editor semantics core（`scalim-yaml-dsl-lsp`），作为 diagnostics/definition/completion 的语义 SSOT，避免在 server 层复制实现细节。

#### Scenario: server uses shared core for diagnostics
- **WHEN** LSP server 收到 diagnostics 请求
- **THEN** server MUST 调用 shared core 的 diagnostics API 产生结果
- **AND** MUST NOT 在 server 层重复实现 validator/schema 规则

