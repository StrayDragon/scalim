---
depends_on: []
branch: sdd/c35-typed-handlers-receive-event
base_sha: bc256677abfeaac7c8f5639b071987d266068584
checkpointed: false
---

## Why

0.10 write-precompute 把阶段信息放在 `Event.meta["scalim_compute_phase"]`，但 `EventDispatchObserver` typed 分发只把 `event.payload` 交给 `on_field_compute` 等处理器；Hook typed 路径同样只分发 payload。下游若只覆写 typed handler，**看不到 meta**，与「统一 `Event` envelope」叙事冲突，也迫使用户为读 meta 绕去 `on_event`。

目标：typed 与 `on_event` 共用同一 envelope——**不怕 breaking**（新主线版本），一次收口。

## What Changes

- `EventDispatchObserver.on_event` 分发：`handler(event)`（完整 `Event`），不再 `handler(event.payload)`。
- Hook typed 分发对齐：`IExecutionHook` / `BaseHook` / `HookManager` typed 回调入参改为 `Event`；`on_event(Event)` 语义不变（仍可与 typed 并存，见既有 r729）。
- 仓内 presets、tests、examples、public-api skill / upgrade 文档同步迁移：`event.payload` 取 typed payload，`event.meta` 读横切字段（含 `scalim_compute_phase`、workflow attribution）。
- Specs：更新 `hooks-observability-structure`（及必要交叉于 `governance-extension-points`）——typed handler MUST 接收 `Event` envelope；仍 MUST 能经 `Event.payload` 消费公开 payload 类型（强化而非否定 r56）。

**不改**

- `Event` / `EventType` / payload dataclass 字段形状（本 change 不把 phase 塞进 `FieldComputeEvent`）。
- `wants` 短路、capture/replay、handler 缓存策略（r417 / r691 仍成立；仅入参对象变）。
- YAML authoring；fusion / chunk 并行运行语义。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `hooks-observability-structure`：typed Observer/Hook 分发入参 = `Event`；文档化 `payload`/`meta` 读取约定；补充 scenario（field_compute + meta phase）。
- `governance-extension-points`：r417 缓存语义不变；注明分发对象为 envelope。

## Impact

- **兼容**：对覆写 `on_*` 且把参数当 payload dataclass 使用的下游为 **breaking**；迁移为一行：`payload = event.payload`（或改注解为 `Event` 后读字段）。
- **收益**：typed 路径可读 `meta`（phase、workflow 归因、worker 等）；viz/logs/performance 可展示 phase 而无第二通道。
- **维护**：Observer 与 Hook 两处分发对齐，避免长期双语义。
- **文档 SSOT**：行为合约以 live specs 为准；人类/agent 适配见 `agentdev/skills/scalim-public-api/references/`（upgrade 任务卡 + SKILL 交叉）；禁止手改 `*.gen.*`。

## Open Questions

| ID | 议题 | 建议默认 |
|----|------|----------|
| Q1 | Hook typed 是否与 Observer 同批改？ | **是**（否则 meta 仍双轨） |
| Q2 | 参数名是否仍叫 `event`？ | **是**（现已叫 event，仅类型从 payload → `Event`） |
| Q3 | 是否启用 `bdd:` runner？ | 默认否（与仓库现状一致；场景留 `spec.toon`）— 见本轮确认 |

## Ethics

- `ethics.risk_level`: medium（公共 Observer/Hook 签名 breaking）
- `ethics.prohibited_actions`: 只改 Observer 不改 Hook 却宣称 envelope 统一；静默兼容双签名（try payload/Event）长期并存；在默认分支提交 live specs
- `ethics.required_evidence`: 仓内 presets/tests 全绿；至少一条「typed handler 可读 `Event.meta`」回归；public-api 适配文档已更新
- `ethics.refusal_contract`: 无法证明 Hook/Observer 分发一致时不得合入
- `ethics.escalation_policy`: 若发现大量外部二开无法接受一次性 breaking，再议兼容 shim（默认不做）