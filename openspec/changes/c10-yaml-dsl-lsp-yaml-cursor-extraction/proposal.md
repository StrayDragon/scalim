## Why

`scalim-yaml-dsl-lsp` 的 shared core 已具备 diagnostics 与 Python 引用静态解析（definition/hover/completion）的能力，但 LSP server 侧要把这些能力“接到编辑器光标上”，仍缺少一个稳定的基础：**把 LSP Position 映射为 YAML DSL 内的“字段路径 + 字符串值 + 精确 range”**。

如果每个 handler（definition/hover/completion/codeAction）各自去做 YAML 光标抽取，会导致实现重复、边界不一致、以及后续维护成本陡增；因此需要先把“光标抽取”固化为 shared core 的 SSOT。

## What Changes

- 在 `scalim-yaml-dsl-lsp` shared core 中新增一个“YAML 光标抽取”能力（纯解析、无副作用）：
  - 输入：`yaml_text` + editor/LSP `position`
  - 输出：命中的 YAML 字段路径（canonical dot path）、原始字符串值、以及可用于 underline 的 `range`（core 仍以 1-based 表示）
  - v1 仅覆盖最常见的 **单行 scalar string**（含引号/不带引号）
- 为 Python 引用字段提供最小语义层：
  - 覆盖 `loader` / `call_by` / `retry.should_retry`
  - 对 `call_by: "ref(args...)"` 提供“头部解析”，产出 `ref`（参数段忽略）
- 新增单元测试与最小回归用例，确保 range/抽取行为稳定，可被后续 server 与 code actions 复用。

## Capabilities

### New Capabilities

（无；本提案只补齐 shared core 的缺口，不新增独立 capability）

### Modified Capabilities

- `yaml-dsl-editor-semantics-core`: 增加“基于 position 的 YAML 光标抽取”要求，使 server/IDE 能以 shared core 为 SSOT 实现 definition/hover/completion/code actions。

## Impact

- 受影响代码/资产：
  - `packages/scalim-yaml-dsl-lsp/`：新增/扩展 shared core 的 cursor-extraction API（Python 3.10+）
  - `tests/`：新增针对 YAML 光标抽取的单元测试（不依赖真实 LSP server）
- 约束：
  - 必须保持“静态、无副作用”（不得执行用户代码；不得改写进程级全局状态）
  - 失败时必须降级为“空结果 + 可诊断 warnings”（不得 crash）

