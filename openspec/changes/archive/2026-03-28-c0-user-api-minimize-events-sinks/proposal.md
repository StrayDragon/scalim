## Why

当前仓库中 `scalim.events` / `scalim.sinks` 的导出面偏大（截至 2026-03-28：`events.__all__=74`、`sinks.__all__=33`），其中相当一部分符号的存在主要是为了让仓内 tests/packages/notebooks 书写方便；但它们会被外部调用方自然视为“官方公共 API”，从而放大后续重构与治理成本。

本变更以**用户视角**重新定义这两类模块的公共导出：只保留真实用户需要的稳定入口与契约，内部测试/实现需要的符号改为直接从内部模块导入（允许破坏性迁移，不提供兼容层），避免“内部便利导出”反向固化为公共契约。

## What Changes

- **BREAKING**：收敛 `scalim.events` 的公共导出面：
  - 仅保留用户侧需要的稳定入口（事件 envelope、事件类型常量、目录查询等）。
  - 不再从 `scalim.events` 包根 re-export 全量 typed payload 数据类（如 `BatchStartEvent` 等）；typed payload 作为内部实现细节存在，用户侧以 `Event.event_type` + `Event.payload` 的稳定字段/键为准。
- **BREAKING**：收敛 `scalim.sinks` 的公共导出面：
  - 保留用户侧需要的 sink 契约与常用 sinks；移除仅用于内部实现/测试便捷的 helper 与中间态工具（不再通过包根聚合导出）。
  - 仓内 tests/packages/notebooks 对被移除符号的引用统一迁移到内部模块路径或新的稳定分组入口（若需要）。
- 将 “public API 入口清单 + `__all__` 白名单门禁 + 用户可见材料导入约束” 扩展到 events/sinks：
  - `__all__` 变更必须可回归（显式白名单、fail-fast）。
  - 用户可见材料（docs/notebooks/skills）不得推广 events/sinks 的内部实现模块路径。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `public-api-surface-governance`: 将稳定公开入口的“显式编目 + 用户可见材料导入约束 + 回归门禁”扩展到 `scalim.events` / `scalim.sinks`，以用户视角收敛导出面。
- `hooks-observability-structure`: 调整“事件契约集中”的要求：typed payload 数据类不再作为公共导入契约；公共契约收敛为 `Event` envelope + `event_type` + 可审计的目录/关键字段。

## Impact

- 代码：`src/scalim/events/__init__.py`、`src/scalim/sinks/__init__.py` 及其被仓内大量引用的导出符号会发生破坏性调整；会同步迁移仓内所有引用点。
- 测试/示例：tests/packages/notebooks 会出现广泛 import 迁移（预期内）；以 `just qa` 与 examples gate 为最终验收。
- 文档治理：若涉及 docs-site，只修改 `docs/doc/**` 的手工页面；不手改任何 `.gen.*` 文件与 `BEGIN/END AUTOGEN` 注入区块内部；生成/漂移以 `just gen-docs` 与 `just qa` 为准。

