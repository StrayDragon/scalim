# Tasks: c35-typed-handlers-receive-event

> 测试边界（已确认）：**A–D**（不含 capture→replay 独立 E）。无 `bdd:`。

## 已决议

| ID | 决议 |
|----|------|
| Q1 | Hook typed 与 Observer 同批改为收 `Event` |
| Q2 | 参数名仍为 `event`，类型改为 `Event` |
| Q3 | 不启用 `bdd:`；场景留 `spec.toon` |
| Seams | A Observer typed 分发；B Hook typed + on_event 并存；C presets；D FIELD_COMPUTE + `meta.scalim_compute_phase` |

## 0. Specs landing（`change start` 之后）

- [x] 0.1 更新 live `llmanspec/specs/hooks-observability-structure/spec.toon`：typed Observer/Hook handler MUST 接收 `Event`；经 `.payload` 消费公开类型；scenario：`FIELD_COMPUTE` + `meta.scalim_compute_phase` 在 typed 路径可见
- [x] 0.2 更新 `governance-extension-points` r417（或旁注）：缓存 callable 入参为 `Event` envelope
- [x] 0.3 `llman sdd validate c35-typed-handlers-receive-event --strict --no-interactive`；`readyToImplement=true`

## 1. 分发核心（Seam A + B）

- [ ] 1.1 `EventDispatchObserver.on_event`：`handler(event)`；测：typed `on_*` 收到 `Event`，`.payload`/`.meta` 可读；handler 缓存仍命中（r417）
- [ ] 1.2 `IExecutionHook` / `BaseHook` / `HookManager` typed 分发改 `Event`；测：typed 与 `on_event` 仍可并存（r729）
- [ ] 1.3 类型别名 / `HookTypedHandler` 等注解与 py3.6 边界对齐

## 2. 仓内迁移（Seam C）

- [ ] 2.1 presets：`logs` / `performance` / `viz_handlers` 及其它覆写 `on_*` 的实现改为经 `event.payload`
- [ ] 2.2 tests / fixtures / examples / public_api 章机械迁移；全量相关 pytest 绿
- [ ] 2.3（可选展示）viz / logs 可消费 `scalim_compute_phase`——不阻塞合入，有则勾

## 3. Phase 可读回归（Seam D）

- [ ] 3.1 单测：emit `FIELD_COMPUTE` 且 `meta.scalim_compute_phase` 有值时，typed `on_field_compute` 能读到同一 meta（Observer；Hook 至少一条）

## 4. 文档与下游适配

- [ ] 4.1 `agentdev/skills/scalim-public-api`：upgrade 卡（Before/After）+ SKILL / `task-event-type-adaptation` 交叉；注明 breaking
- [ ] 4.2 人类交叉：`docs/doc/viz/scalim-viz.md` / 0.10 highlights 中「typed 看不到 meta」表述改为「typed 收 Event」
- [ ] 4.3 若 public-api 生成物漂移：`just gen-public-api-skill`（禁止手改 `*.gen.*`）

## 5. 门禁

- [ ] 5.1 相关 pytest + `just llmanspec-check`（或等价 validate）绿
- [ ] 5.2 不引入 payload/Event 双签名兼容层
