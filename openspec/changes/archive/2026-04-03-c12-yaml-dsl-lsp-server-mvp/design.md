## Context

`scalim-yaml-dsl-lsp` 已提供 editor/tooling 语义 shared core（project discovery、diagnostics、Python 引用解析），但缺少一个“可被任何编辑器通过 stdio 拉起”的 LSP server 形态。

在没有 server 的情况下：

- VSCode/Neovim/Zed/JetBrains 无法直接消费 shared core
- diagnostics/definition/hover/completion 无法在真实工程（imports/多目录）中端到端验证
- 后续 code actions 与 VSCode extension provisioning 无从落地

## Goals / Non-Goals

**Goals:**

- 提供一个可启动的 YAML DSL LSP server v1：
  - 默认 stdio（编辑器集成主路径）
  - 可选 tcp（仅用于 debug）
- v1 必须支持：
  - diagnostics（didOpen/didChange 驱动 publish）
  - go-to-definition（优先 `loader`/`call_by`/`retry.should_retry`）
  - hover（docstring）
  - completion（最小补全）
- server 必须复用 shared core 作为语义 SSOT：
  - 不得 shell-out CLI
  - 静态解析：不得执行用户代码、不得改写进程级全局状态（`sys.path` 等）
- 任意失败必须可降级：不崩溃、不退出、不返回半截 JSON-RPC；返回空结果 + warnings/logs

**Non-Goals:**

- code actions（单独变更：`yaml-dsl-lsp-server-code-actions`）
- 复杂 YAML 光标抽取（多行字符串/flow style/anchors 等，后置）
- 性能极致优化（v1 允许基础缓存；细粒度增量优化后置）

## Decisions

1) **pygls 2.x 作为 LSP 实现**

- 使用 `pygls` 实现 stdio LSP server
- server 依赖归属在 `scalim-yaml-dsl-lsp[server]`（extra），避免污染 `scalim` 运行时边界
- 实现时以 `pygls 2.1.x` 的官方 docs + 源码行为为准；仓库内可参考 `.codex/skills/lsp-pygls-expert/references/`（含 v1→v2 迁移与写法索引）

2) **光标语义抽取由 shared core 提供**

definition/hover/completion 需要 `Position -> reference` 的桥接能力。本变更依赖 `yaml-dsl-lsp-yaml-cursor-extraction`（shared core SSOT），以保证：

- handler 行为一致
- code actions 未来可复用同一抽取逻辑

3) **range 口径：core 1-based，server 负责转 0-based**

shared core 的 `EditorRange` 使用 1-based。server 将其转换为 LSP `Range`（0-based，end 为半开区间）：

- diagnostics range underline
- definition location range（若可提供）

4) **文档/缓存策略（v1）**

- 在 `didOpen/didChange` 缓存最新文本（按 URI）
- 每次请求可直接使用缓存文本（避免重复读盘）
- 复杂缓存（解析树复用/增量解析）后置

5) **serve 入口命名：`scalim-yaml-dsl-lsp serve`**

- v1 以单一 console entry + 子命令组织（便于扩展 `dump-discovery`/`version`/`doctor`）

6) **提供 discovery dump（排障入口）**

- 提供 CLI 子命令：`scalim-yaml-dsl-lsp dump-discovery <yaml_path> --json`
- server 侧在 debug 日志中输出 discovery 摘要（不回显 YAML 正文）

## Risks / Trade-offs

- [pygls handler 并发/线程模型踩坑] → v1 以最小同步/串行策略实现；必要时把重计算放到线程池（后置优化）
- [光标抽取覆盖不足导致“跳转不工作”] → v1 明确只覆盖单行 scalar；将复杂形态记录为后置并补充 fixtures 逐步扩展
- [range 偏移导致 underline 错位] → 用集成测试覆盖 1-based/0-based 转换与 head-range（`call_by(args)`）场景

## Migration Plan

- 新增 server 能力不改变现有运行时语义。
- VSCode extension 与多编辑器接入将以该 server 作为统一入口。

## Open Questions
（无；已收敛为 `scalim-yaml-dsl-lsp serve` + `dump-discovery`）
