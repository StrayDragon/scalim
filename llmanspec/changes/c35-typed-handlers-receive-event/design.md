# Design: typed handlers receive Event envelope

## Decision

**Typed Observer / Hook 回调一律接收完整 `Event`。**  
Payload 仍是公开 dataclass，挂在 `event.payload`；横切上下文只走 `event.meta`。不引入双签名兼容层。

## Current vs Target

```text
Today:
  EventDispatchObserver.on_event → handler(event.payload)
  HookManager typed emit         → handler(payload)

Target:
  EventDispatchObserver.on_event → handler(event)   # Event
  HookManager typed emit         → handler(event)   # Event
  HookManager on_event path      → handler(event)   # unchanged
```

Handler 习惯写法：

```python
def on_field_compute(self, event: Event) -> None:
    payload = event.payload  # FieldComputeEvent
    phase = event.meta.get("scalim_compute_phase")
```

## Specs SSOT

| Spec | 动作 |
|------|------|
| `hooks-observability-structure` | 更新 r56（或新增 req）：typed handler MUST 接收 `Event`；MUST 仍能经 `.payload` 消费公开类型；补 scenario：`FIELD_COMPUTE` + `meta.scalim_compute_phase` |
| `governance-extension-points` | r417 补一句：缓存的 callable 入参为 `Event` envelope |

无新 capability 目录。

## Migration（仓内）

机械替换面（大范围，按「先改分发 → 再迁调用方」）：

1. `src/scalim/ob/observer.py`：`handler(event)`
2. `src/scalim/hooks/_base.py` + `manager_events.py`（及类型别名）：typed 签名 / 分发改 `Event`
3. presets：`logs` / `performance` / `viz_handlers` / 其它覆写 `on_*` 处
4. tests / fixtures / examples / notebooks public_api 章
5. `agentdev/skills/scalim-public-api`：upgrade 卡 + SKILL；可选短 upgrade `references/upgrades/YYYY-MM-DD-typed-handlers-event-envelope.md`

## Capture / adaptive

Capture 已存完整 `Event`；回放走同一分发。改入参后 replay 自然带 meta——须在测试中覆盖至少一条 capture→replay + meta。

## Non-goals

- 不把 `scalim_compute_phase` 迁入 `FieldComputeEvent`
- 不改 fusion 安全外壳（订阅 `FIELD_COMPUTE` 仍关 fusion）
- 不做 `TypeError` 回退到 payload 的双轨

## Docs / gen

- 手工：specs、skills、少量架构/releases 交叉句
- 无新 `*.gen.*` 依赖；若 public-api skill 生成物因示例漂移，走既有 `just gen-public-api-skill` / drift gate
