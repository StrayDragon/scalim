# tasks: c0-event-type-enum-identity

## Propose（已完成）

- [x] 0.1 写好 `proposal.md` / `design.md`（含 Event 域 Enum 身份新约束与 AGENTS 例外）
- [x] 0.2 delta：`hooks-observability-structure`（modify r56/r268 + add r930/r931/r932）
- [x] 0.3 delta：`hooks-events`（add r933/r934）
- [x] 0.4 `llman sdd validate c0-event-type-enum-identity --no-interactive`
- [x] 0.5 `llman sdd show c0-event-type-enum-identity --json --deltas-only` 可见 7 条 delta

## Apply

- [x] 1.1 更新根 `AGENTS.md` Policy 段：Event/Hook 身份与 `Event` envelope 以 `EventType` 为进程内 SSOT；不适用「wire/out 必须 builtin str」的进程内约束；边界 `.value` 仅限落盘/JSONL/viz 且读回须归一
- [x] 1.2 公开导出 typed payload（`scalim.events` + `__all__` / public-api pragma）；禁止用户材料示范 `_events`；改 SSOT 后 `just gen-docs`
- [x] 2.1 `Event.event_type` 改为 `EventType`；emit 路径写入 Enum
- [x] 2.2 `Observer.event_types` / `Hook.event_types` → `Optional[Set[EventType]]`；`validate_event_types` 拒绝裸 `str`
- [x] 2.3 manager / `wants` / dispatch 键与 envelope 对齐为 `EventType`
- [x] 2.4 `to_dict`/viz/capture 边界 MAY 出 str；读回 MUST → `EventType`
- [x] 3.1 单测：裸 str 注册失败；Enum 注册成功；分发正确；公开 payload import
- [x] 3.2 文档/升级说明；`supports_unknown_event_types` 非推荐二开路径
- [x] 3.3 `just qa` 全绿；`llman sdd validate c0-event-type-enum-identity --strict --no-interactive`；`llman sdd validate --all --strict --no-interactive`
