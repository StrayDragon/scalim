---
name: lsp-pygls-expert
description: "pygls 2.x 的 LSP Language Server 开发与排障：LanguageServer/FeatureManager、handlers(async/sync/thread)、Workspace/TextDocument/PositionCodec、Protocol/JSON-RPC 扩展、converter hooks、以及 stdio/tcp/ws IO。"
---

# lsp-pygls-expert

## 事实来源优先级（避免版本不一致）

1. **官方 docs 优先**：以用户项目锁定的 `pygls` 版本为准。
2. **用户环境源码验证**：文档有歧义/与现象冲突时，以用户环境 `pygls` 源码为准（site-packages / 项目 vendor）。
3. **本 skill：仅 docs 快照索引**：`references/pygls-2.1.1/docs/source/**` 是 *pygls 2.1.1* docs 快照，用于定位主题与关键词；最终结论仍以“用户实际版本 + 源码行为”为准。

## 默认约定（只用新写法）

- 用户给旧写法/旧代码时，默认直接升级到 **pygls 2.x**（不做兼容层），并以用户源码核对（见 `references/50-migrations-v1-to-v2.md`）。
- 输出尽量：最小可运行片段 + 关键符号定位（文件路径 + `rg` 模板）。

## 快速入口

- 导航与 `rg`：`references/00-navigation.md`
- docs 快照索引：`references/_docs_index.md`
- 主题索引：`references/10-server-core.md`、`references/15-workspace-positions.md`、`references/20-builtins-and-lifecycle.md`、`references/30-handler-types-threading.md`、`references/40-protocol-extension.md`
- v1→v2：`references/50-migrations-v1-to-v2.md`
