## Context

当前 `scalim-yaml-dsl-lsp` core 已经能：

- 基于文件系统与 AST 静态解析 Python 引用（definition/hover/completion）
- 在不 shell-out CLI 的前提下输出结构化 diagnostics（含 range）

但 LSP server 要实现 `textDocument/definition` / `hover` / `completion` / `codeAction`，必须解决一个前置问题：

- LSP client 提供的是 `uri + Position(0-based)`
- core 的 Python 解析 API 接受的是“引用字符串”（例如 `pkg.mod:func`）

因此需要一个可复用的桥接层：从 YAML 文本与光标位置抽取出“命中的字段 + 参考字符串 + 可编辑范围”。

## Goals / Non-Goals

**Goals:**

- 提供稳定的 cursor-extraction API，作为 server 与后续 actions 的 SSOT：
  - `Position -> (yaml_path, raw_value, range, warnings)`
  - 覆盖 `loader` / `call_by` / `retry.should_retry` 的最小可用语义
- 抽取逻辑对语法错误、复杂 YAML 形态必须可降级（不崩溃，返回空结果 + warnings）
- 1-based/0-based 的边界清晰：core 保持 1-based，server 做转换

**Non-Goals:**

- 完整覆盖 YAML 全部语法（多行字符串、flow style、anchors/aliases、复杂 escape 等）——这些留给后续 P2
- 对 workflow YAML 引入运行时语义抽取
- 为每个 YAML 字段提供通用的“光标->字段”能力（v1 仅覆盖 Python 引用字段）

## Decisions

1) **shared core 提供最小“语义光标抽取”API**

把“什么算命中 / 命中后抽取什么”固定在 shared core，而不是分散在 server handlers 中，避免：

- definition/hover/completion/codeAction 对命中判定不一致
- 后续改动需要同步多处 handler

2) **v1 优先支持单行 scalar string**

为了尽快服务 `loader/call_by/retry.should_retry` 的跳转与 actions，v1 只需要覆盖最常见形态：

- `loader: pkg.mod:func`
- `call_by: "pkg.mod:func(arg=1)"`
- `retry: { should_retry: pkg.mod:pred }`

复杂 YAML 抽取（多行/flow/复杂引号）归入后续提案。

3) **对 `call_by` 做“头部解析”**

当 `call_by` 字段形如 `ref(args...)` 时，只提取 `ref`，并将 range 定位到 `ref` 这段（而不是整段字符串），以便：

- go-to-definition 直接跳到 `ref`
- completion 只在 `ref` 上触发
- codeAction 能对 `ref` 进行精确替换

4) **字段命中集合：v1 固定 allowlist（不做可配置）**

- v1 仅覆盖 `loader` / `call_by` / `retry.should_retry` 作为命中字段集合（SSOT 在 shared core 代码里）
- 后续若要扩展到其它 Python 引用字段（例如 `sinks.*.writer` 等），通过“新增显式规则 + 测试”迭代，不引入运行时配置（避免不同编辑器/插件间语义漂移）

5) **yaml_path 表示：统一使用 canonical dot path**

- cursor-extraction 输出的 `yaml_path` MUST 与 diagnostics 的 path 口径一致（canonical dot path）
- 这样 diagnostics/logs/actions 能共用同一套路径字符串，降低排障与实现复杂度

## Risks / Trade-offs

- [YAML 语法覆盖不全] → v1 聚焦单行 scalar；将复杂形态纳入后续提案并补测试矩阵
- [range 计算不一致导致 underline 偏移] → 用黄金用例覆盖：引号/不带引号、`:`/`.` 两种引用风格、`call_by(args)` 头部 range
- [性能：频繁解析 YAML] → v1 允许按请求解析；server 侧可缓存 parsed document（后续优化）

## Migration Plan

- 该变更只新增 shared core API，不改变现有 CLI/运行时语义，无迁移成本。
- 后续 LSP server MVP 必须改为调用该 API（而不是自建抽取逻辑）。

## Open Questions

（无；v1 已收敛为固定 allowlist + canonical dot path）
