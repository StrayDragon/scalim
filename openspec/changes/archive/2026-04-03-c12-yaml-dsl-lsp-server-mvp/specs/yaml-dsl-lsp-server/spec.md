## ADDED Requirements

### Requirement: Server MUST publish diagnostics on didOpen/didChange using shared core
系统 MUST 在收到 `textDocument/didOpen` 与 `textDocument/didChange` 后发布 diagnostics：

- MUST 复用 shared core diagnostics API（不得 shell-out CLI）
- MUST 将 shared core 的 1-based range 正确转换为 LSP 0-based range
- MUST 在解析失败时降级为“空 diagnostics + 可诊断日志”（不得崩溃/卡死）

#### Scenario: didChange triggers diagnostics publish
- **GIVEN** 某 YAML 文本发生变更
- **WHEN** server 收到 didChange
- **THEN** server MUST 发布 diagnostics
- **AND** diagnostics 的 range MUST 能用于编辑器 underline（0-based）

### Requirement: Server MUST support call_by head parsing for definition/hover/completion
当 `call_by` 字段形如 `ref(args...)` 时，server MUST 至少支持解析并处理头部 `ref`：

- definition/hover/completion MUST 基于 `ref` 执行
- range MUST 精确覆盖 `ref`（不得包含参数段）

#### Scenario: call_by head resolves without considering args
- **GIVEN** 某 YAML 包含 `call_by: \"pkg.mod:fn(a=1)\"`
- **WHEN** 用户在 `pkg.mod:fn` 上触发 definition
- **THEN** server MUST 解析并尝试定位 `pkg.mod:fn` 的定义

### Requirement: Definition/hover/completion MUST only trigger when cursor is inside the reference range
系统 MUST 仅当光标位于被识别的 Python 引用范围内时，才返回 definition/hover/completion 结果；否则 MUST 返回空结果。

#### Scenario: cursor outside reference yields empty result
- **GIVEN** 某 YAML 行包含 `loader: \"pkg.mod:func\"`
- **WHEN** 光标位于该行的非引用区域并触发 definition
- **THEN** server MUST 返回空 locations

