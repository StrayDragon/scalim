---
depends_on:
  - c50-source-id-graph-refs
checkpointed: false
---

# Workflow 同名 `source_id` 的 per-run `LookupChunking`

草案（仅记想法）。c50 已把图边收成 id、策略只住每张 `DemandIr.sources`。本条不改行为；等需要「同一次 workflow 里两个 demand 同名源、不同分片」时再 `llman-sdd-propose`。

## Why

`DemandRunRuntimeOptions.lookup_chunking` 按 **`source_id` 字符串** 打进每张 demand 的目录。workflow 共用一份 `demand.runtime`；`WorkflowNodePatch` 目前能改节点 `batch_size` / `parallel_mode` / `components` 等，**没有** `lookup_chunking`（也没有 `source_cache` / `rows_reuse`）。

因此：workflow 里两个 run 都声明 `sources.customers` 时，全局 `lookup_chunking={"customers": LookupChunking.sized(N)}` 会给**两边各一份相同的 N**（各打各的目录，对象不串，但策略值相同）。这是按 id 一并处理，不是 catalog 泄漏。

真实报表入口通常就是这种形状：workflow 级一份 `lookup_chunking` 字典，节点级用 `patches_by_run_id` 调 `batch_size`。主表分批已经能限制本波次送给从表的 keys 数量；从表再用 `LookupChunking` 当关联侧二次切批。多数场景这样够用。

以后若两个同名源下游配额不同（一个 `max_batch=200`、一个不分片），才需要节点级 overlay。现在先接受「同名 id 共用一份 chunking」，把缺口记在这里。

## 当前语义（接受，本草案不改）

- 主表 `batch_size` 切 **主源行** → 每一波 `LoadRef` 的 lookup keys 来自**这一批主行**（从表输入量随主批变小）。
- `LookupChunking.sized(N)` 再切 **这一波 keys**（类似从表关联自己的 `batch_size`）。
- 未配置 / `{}` / `off()` ≡ 这一波 keys 一次 loader 调用。
- c50：每 demand 一份 catalog，同名 id **不泄漏**对象/cache；只是 overlay **值**按 id 对齐。

## What Changes

- 评估 `WorkflowNodePatch` 增加 `lookup_chunking`（及是否顺带 `source_cache` / `rows_reuse`），三态与现有 patch 一致：`UNSET` 继承 workflow 全局，显式 mapping 覆盖该节点。
- 覆盖优先级仍走 c40：节点 Python > workflow Python > YAML > builtin；只 `replace` 该节点 `DemandIr.sources`，不改图边。
- 黑盒：同 workflow 两个 demand 均有 `sources.customers`，patch 后 loader `chunk_offset` 不同；ch166 隔离断言保持。
- 新旋钮落 Python（New knob gate）；禁止 YAML 新字段。
- 非目标：per-field chunking；把 `LookupChunking` 级联成主表 `batch_size`。

## Capabilities / Impact

- 用户：今天继续用「全局 `lookup_chunking` + 节点 `batch_size`」；需要不同 chunking 时拆两次 `run()` 或等本 change 落地。
- 文档/skills：落实时改 workflow patch 表与 upgrade；SSOT 为 `WorkflowNodePatch` + r1004 优先级句，生成物走 `just gen-docs` / `just gen-agent-skill`。
- 风险：低。未实现前无行为变化。
