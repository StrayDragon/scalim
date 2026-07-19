## Context

二开将长期依赖 Event/Hook 注册面。当前实现与规范把事件身份稀释为 `str`，并把 payload 类藏在 `_events`，与类型安全扩展目标相反。

本 design 固定 **Event/Hook 身份域** 的分层，显式覆盖旧「进程内也偏 builtin str」偏好。

## Goals / Non-Goals

**Goals**
- 进程内：`EventType` 为唯一事件身份 SSOT。
- 注册严进：仅 `EventType`；裸 `str` fail-fast。
- Typed payload 从 `scalim.events` 公开导出，成为 handler 类型契约。
- 边界（JSONL/viz/capture 文件）：可编码 `.value`；读回进程 MUST 变为 `EventType`。
- 更新 specs + `AGENTS.md`，避免回归。

**Non-Goals**
- 不改 Options/policy（`FailurePolicy` 等）的严进迁移（另轨）。
- 不实现进程外 event-bridge（见 `notplan/c999-hook-event-bridge`）。
- 不改变既有 catalog 字符串 **取值**（成员 `.value` 保持稳定，避免无意义 churn）；变的是类型身份与作者面。

## Decisions

### D1 — 进程内身份 = `EventType`

- `Event.event_type: EventType`
- `Observer.event_types` / `Hook.event_types: Optional[Set[EventType]]`
- `wants` / `emit` / dispatch map / manager 索引键：统一 `EventType`（或等价地以 Enum 成员为键；禁止以「作者面 str」为 API）
- `validate_event_types`：只接受 `EventType`（或 `None`）；拒绝 builtin `str` 与未知成员

### D2 — 公开 payload Tier-1

- 稳定 payload 数据类从 `scalim.events`（或明确的公开子模块再 re-export）导出
- 更新 public-api pragma / `just gen-docs`
- `scalim.events._events` 降为实现细节；用户材料 MUST NOT 再示范私有导入

### D3 — 边界编码 ≠ 进程内身份

- `to_dict` / Viz JSONL / capture 落盘 MAY 写 `event_type: str`（`.value`）
- 任何把边界数据载入进程内 `Event` 的路径 MUST 解析为 `EventType`（未知值 fail-fast，除非显式 unknown 逃生且文档化）
- **不要求** pickle/state 为了“纯 builtin”而把进程内 `Event.event_type` 降级成 str；若 state 需跨版本，编码层单独处理，读回仍为 Enum

### D4 — 与 r73 / AGENTS Policy 的关系

- `runtime-policy-normalization` r73 继续约束 **policy-like** 跨 YAML/state 的闭集
- **EventType / 事件订阅 / Event envelope 身份** 划出例外：进程内 MUST 持有 Enum；作者面 MUST 为 Enum
- `AGENTS.md` 增补该例外，避免代理按旧 wire-str 规则把 Event 身份再稀释回 `str`

### D5 — 未知事件

- 推荐：扩展 catalog + 新 `EventType` 成员
- `supports_unknown_event_types`：保留为框架/实验逃生口；MUST NOT 成为公开二开文档的默认路径

### D6 — 热路径

- 允许用 `EventType` 做 dict 键（`StrEnum`/`str` 子类仍可与历史字符串键互通时需在迁移中收敛到 Enum 键）
- handler 缓存语义（r417 / r691）保持：按 event identity 缓存 callable；身份类型从 str 换成 `EventType` 不削弱缓存要求

## Risks / Trade-offs

- **BREAKING**：裸字符串订阅、比较 `event.event_type == "pipeline.start"`、私有 `_events` 导入均需迁移。
  - 缓解：迁移说明 + 公开 re-export + 清晰 TypeError/ValueError 文案列出允许的 `EventType` 成员。
- capture/viz 消费者若假设 `Event.event_type` 永远是 builtin `str`：需同步适配（读 `.value` 或接受 Enum）。
- 与旧 r56 场景「不得导入 payload」冲突：本 change **有意修改**该合约。

## Migration Plan

1. 规范与 `AGENTS.md` 先落地（本 propose）。
2. Apply：公开导出 payload → 升 `Event.event_type` → 注册校验严进 → hub/managers/hooks/ob 对齐 → 测例与文档 → `just qa`。
3. 外部仓：`EventType` 订阅保持；`_events` → `scalim.events`；删除裸 str 订阅。

## Open Questions

（无阻塞；unknown 逃生口保留但不推广。）
