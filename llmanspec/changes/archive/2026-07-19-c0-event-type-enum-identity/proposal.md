---
depends_on: []
---

## Why

二开（自定义 Observer / Hook 注册）需要**可发现、可穷举、可类型检查**的事件身份，而不是可任意拼写的 `str`。

现状把 `Event.event_type`、`Observer.event_types` / `Hook.event_types` 标成 `str` / `Set[str]`，并把 typed payload 数据类标成“内部细节”（`hooks-observability-structure` r56）。这与未来扩展面冲突：作者面被迫使用泛化 `str`，IDE/类型检查无法约束闭集，私有 `_events` 导入成为事实依赖。

本变更**有意偏离**旧全局偏好「闭集跨边界落 builtin `str`、进程内也偏 `str`」（见 `c0-policy-enum-first` / AGENTS Policy / `runtime-policy-normalization` r73）在 **Event/Hook 身份域**上的适用性：该域以 **`EventType` 为进程内唯一真相**，优先长期可维护性与类型安全，不把 wire-str 当作作者面或进程内身份。

## What Changes

- **BREAKING**：进程内事件身份统一为 `EventType`（`Event.event_type`、订阅集、`wants`/`emit`/dispatch 键）。
- **BREAKING**：`Observer.event_types` / `Hook.event_types` 严进为 `Optional[Set[EventType]]`；注册时对裸 `str` fail-fast。
- **BREAKING / 契约翻转**：typed payload 数据类升为 `scalim.events` 公开 Tier-1 契约；禁止再要求用户依赖 `scalim.events._events`。
- 修订 `hooks-observability-structure` r56 / r268，使合约与上述作者面一致。
- 修订根 `AGENTS.md`：明确 Event/Hook 身份域**不适用**「wire/out 必须 builtin str」的进程内约束；边界编码 `.value` 仅用于落盘/JSONL/viz，读回 MUST 归一为 `EventType`。
- 扩展走 catalog 登记；`supports_unknown_event_types` 仅逃生口，非推荐二开路径。

## Capabilities

### New Capabilities

（无；身份合约落在既有 hooks/events 能力上）

### Modified Capabilities

- `hooks-observability-structure`：公开契约从「str + 内部 payload」改为「`EventType` + 公开 typed payload」。
- `hooks-events`：补充 envelope / 注册 / catalog 扩展的 Enum 身份要求。

## Impact

- 代码：`src/scalim/events/**`、`src/scalim/ob/**`、`src/scalim/hooks/**`、相关 tests/docs/skills/public-api 目录。
- 外部使用方（如 et_project Observer）：已用 `EventType` 成员者多为净收益；裸字符串订阅与 `_events` 私有导入必须迁移。
- Docs/SSOT：`AGENTS.md`、events 用户文档、public-api 生成入口（只改 SSOT 后 `just gen-docs`）。
- **非本变更**：Options 侧 `FailurePolicy` / `parallel_mode` 等政策 Enum 严进（另开 change）。
