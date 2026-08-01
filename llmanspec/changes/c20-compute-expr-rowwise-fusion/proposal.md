---
depends_on: []
---

## Why

合成 MVP（宽表大量薄 `call_by`）显示：吞吐从「长表少字段」量级掉到约 **1/4～1/5**，主因是固定开销近似 **行数 × 字段数（N×M）**——反复取依赖 + Python 调度，而不是单次业务函数体。

早期草稿曾把融合范围写成「仅 `compute_expr`、不含 `call_by`」，理由是：

- `call_by` 可能有副作用，融合会改变**同字段簇内**的调用交错顺序；
- `$ctx` / 事件 `FIELD_COMPUTE` 顺序（field-major → row-wise）更敏感。

**但按 MVP，真正的 N×M 热点正是薄 `call_by`。** 若 c20 排除 `call_by`，则几乎打不中已测量瓶颈，维护上也会逼业务去「改成 compute_expr」——迁移成本高，与决议相反。

因此本 change **修订范围**：在**安全外壳**下对 **`compute_expr` 与无 `$ctx` 的 `call_by`** 做 row-wise / 同依赖复用融合；含 `$ctx` 或无法证明安全时 **回退**现路径。id 仍用 `c20-compute-expr-rowwise-fusion`（已确认），正文以本修订为准。

约束：

- 零新 DSL；不要求用户改成列式 batch API。
- 峰值 RSS ≤ +10%。
- 默认 `seq` 不回退；观测订阅 / fast_fail 时宁可禁用融合，也不静默改对外顺序。

## What Changes

- 内部优化：在 compute 段内，将满足约束的派生字段组成 fusion group，改为 **按行**：一次读取 union deps → 依次计算组内字段并写回。
- 候选字段：
  - `compute_expr`；
  - **无 `$ctx`/`ctx_attr` 的 `call_by`**（打中 MVP N×M）；
  - 组内字段**互不依赖**；第一期优先 **deps 完全相同**，再考虑高重叠放宽。
- **安全外壳（默认融合仅在外壳内）**（**已决议**，与 `design.md` 一致）：
  - `fast_fail` → 不融合；
  - instrumentation `wants(FIELD_COMPUTE)` 或 `OPERATOR_SPAN` → 不融合；
  - 含 `$ctx`（`call_ctx_key`）→ 不进入 group；`is_constant_compute` → 不进入 group；
  - **行** streaming / 非流式行：**可融合**；**`IColumnSink`：不融合**（Q2-B）；
  - 组内任一字段 EXP `call_by` memo 生效 → **整组不融合**（Q2b）；
  - 融合组：**同一** pre-ref 或 post-ref segment；deps **完全相同**（Q1）；组内无边。
- **不**做隐式「多个不同 call_by 函数合并成一次调用」（那是 multi-output / `call_groups`，另案、显式语法）。本 change 只减少 **重复取 deps + 调度框架税**；每个字段仍调用自己的 calculator **一次/行**（`calc_calls == N×M`，Q3），除非未来显式语法 change。
- Specs：`execution-compute-rowwise-fusion`（新建）并与 `execution-hotpath-fastpaths` 交叉引用。
- 证据：扩展 `.tmp/repro/` 宽表 `call_by` A/B；py3.6；bench 不回退。

**不改**

- YAML 字段写法；不引入 `call_groups`。
- `parallel_mode` / LoadRef 并行（属 c30）。
- 默认开启大 LRU memo。

## Capabilities

### New Capabilities

- `execution-compute-rowwise-fusion`：融合候选规则、安全外壳、与 field-major 值等价、禁用条件、内存有界。

### Modified Capabilities

- `execution-hotpath-fastpaths`：默认 fastpath 与「外壳外回退」一致。
- `ir-field-compute`：仅交叉引用「融合不改变单字段计算器签名」。
- `performance-observability`：若外壳外禁用，说明与事件顺序的关系。

## Impact

- **兼容**：无 DSL；值与 **每字段每行调用次数** 保持；事件顺序在外壳内因未订阅而不暴露；外壳外行为与今日一致。
- **性能**：宽表薄 call_by MVP 目标端到端耗时下降 **≥15%**（以 evidence 为准）；主要打 N×M 取依赖/调度税。
- **内存**：允许小 tile 缓冲，峰值 ≤+10%；禁止跨批按行缓存（对齐 hotpath r579）。
- **维护**：融合逻辑集中、可开关回退；与 c10 late 集合正交（先算谁由 c10 定，段内怎么循环由 c20 定）；**组织决议**：两 change + 共享物化原语，不合并目录。
- **风险**：常态下 `call_by` 视为计算字段（少副作用）；**不排除**依赖 field-major 副作用顺序的脚本——用外壳（观测 / fast_fail 回退）降低；不新增并行的 `cached_call_by` 关键字；与 EXP memo 互斥（Q2b），不叠加以免调用次数口径混乱。
- **notplan**：`llmanspec/notplan/c0-compute-rowwise-fusion` 已标 SUPERSEDED，改指向本 change。

## Open Questions（已全部收口）

| ID | 决议 | 详见 |
|----|------|------|
| Q1 | deps 完全相同 | `design.md` |
| Q2 | 行开 / 列不开 | `design.md` |
| Q2b | memo → 整组不融合 | `design.md` |
| Q3 | `calc_calls == N×M` | `design.md` |
| 组织 | 两 change + 共享原语 | `design.md` / c10 `design.md` |

## Ethics

- `ethics.risk_level`: medium
- `ethics.prohibited_actions`: 在未订阅场景外静默改变 FIELD_COMPUTE 全局顺序却宣称无契约变更；将不同 call_by 函数隐式合并为一次调用；引入行数线性跨批缓存
- `ethics.required_evidence`: 宽表 call_by MVP 对拍（值 + 每字段调用计数）+ RSS + py3.6
- `ethics.refusal_contract`: 达不到值/调用次数等价时不得默认开启
- `ethics.escalation_policy`: 若要「一次调用写多字段」（减少调用次数），必须新开显式语法 change
