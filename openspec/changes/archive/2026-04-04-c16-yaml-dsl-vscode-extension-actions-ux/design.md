## Context

在 VSCode extension MVP 能稳定拉起 server 后，体验的关键提升点是：

- 把 server 的 LSP code actions 映射成 VSCode 用户熟悉的 Quick Fix
- 提供“一键排障入口”：日志、版本、discovery 摘要、打开/创建 `scalim.yaml`
- 在 UI 上暴露 server 运行状态（降低支持成本）

这些能力大多属于 extension 的 glue/UX 层，不应在 server 侧实现。

本变更仅针对扩展工程 `extras/vscode-scalim/` 的 UX/glue 增量（扩展源代码长期固定在 `extras/`）。

## Goals / Non-Goals

**Goals:**

- 将 server 的 `textDocument/codeAction` / `workspace/executeCommand` 完整映射为 VSCode Quick Fix
- 增加常用命令：
  - 重启 server
  - 打开日志/输出
  - 显示 discovery 摘要
  - 打开/创建 `scalim.yaml`
- 增加最小状态栏信息（server 状态、版本、当前 workspace 的 project root）
- 扩展侧不得复制 YAML DSL 语义；诊断与修复建议必须来自 server/shared core

**Non-Goals:**

- 引入复杂 UI（WebView 配置面板等）
- 扩展 scope 外的编辑器支持（其它编辑器走 `yaml-dsl-lsp-editor-integration-guides`）

## Decisions

1) **Quick Fix 的来源与呈现**

- 以 language client 提供的 code action API 直接消费 server actions
- extension 仅做：
  - 文案/分组的 VSCode 友好化（不改变语义）
  - executeCommand 的桥接与错误提示

2) **统一的诊断输出通道**

- 使用 VSCode OutputChannel 作为日志主入口
- 提供命令直接打开该输出通道

3) **状态栏最小化**

- MVP 级别仅展示：
  - server running/stopped
  - 当前 server 版本（或 pinned 版本）
  - project root（若可得）

## Risks / Trade-offs

- [不同 VSCode 版本对 code actions 表现差异] → 覆盖最基础 API，避免依赖实验性特性
- [actions 文案漂移] → 以 server 的稳定 command id 为 SSOT；extension 仅做展示层映射

## Migration Plan

- 仅增强 VSCode extension，不改变 server 或 DSL 运行时语义。

## Open Questions

- 是否需要在 VSCode UI 中展示更详细的 discovery 表格（后置，可能需要 WebView）？
