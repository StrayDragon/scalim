# Design: row-wise fusion（含安全外壳下的 call_by）

## 为何重新纳入 call_by

| 顾虑（旧） | 处置（新） |
|------------|------------|
| 副作用顺序 | **常态假设**：`call_by` 用于计算字段，一般无打印/写全局/外设副作用；**不排除**例外。同组内改为「一行内按字段稳定序依次调用」；**每字段每行仍调用一次**（次数不变）。若脚本依赖 field-major 全局副作用顺序：在 `fast_fail` 或订阅字段事件时 **禁用融合**；极端需求另走显式 opt-in（见下「缓存/纯函数声明」讨论，不在本 change 发明第二套 `call_by` 语法） |
| `$ctx` | 直接排除，不进 group |
| 事件顺序 | 仅当 **未** wants `FIELD_COMPUTE`/`OPERATOR_SPAN` 时融合 |
| 与 MVP | 宽表薄 call_by 是已测 N×M 热点 → **必须覆盖** 才有 ROI |
| 旧 notplan | `llmanspec/notplan/c0-compute-rowwise-fusion` 已 SUPERSEDED；「仅 compute_expr」不再作 SSOT |

**本 change 不减少 call_by 调用次数**（那是 multi-output 显式语法）。本 change 减少的是：`get_field_value` 重复、字段循环的框架分支/异常边界摊销。

### 与「用户自选 cached_call_by」的关系（决策记录，本 change 不做）

另增 `cached_call_by` 字段（旧 `call_by` 不动）能让用户自判「可缓存」，但维护成本高：两套 authoring、两套校验/文档/LSP、迁移叙事分裂。仓库已有 **实验性** 按字段 memo（`execution-call-by-memoization` + `SCALIM_EXP_CALL_BY_MEMOIZE_*`）。若产品化，优先 **在现有 `call_by` 上加克制开关**（如 `memoize: true` / `pure: true`），而不是并行关键字；且 memo 解决的是「贵计算 + 依赖值重复」，c20 解决的是「薄计算 × 多字段」框架税——二者互补，不要互相替代。

## N×M 框架税举例（教学 + MVP）

完整白话例子与可跑脚本见：`mvp/README.md`、`mvp/repro_nxm_framework_tax.py`。

极简版：2 行 × 3 个同依赖薄 `call_by` 时，field-major 约 **12** 次依赖读取；row-wise 同 deps 约 **4** 次；计算器调用两边都是 **6**。乘数换成数千行 × 数十字段即 MVP 所测。

## Goals / Non-goals

**Goals**

- 零 DSL；`compute_expr` + 无 ctx `call_by`。
- 外壳内默认开；外壳外 ≡ 今日 field-major。
- 值等价；每 `(field, row)` calculator 调用次数等价。
- RSS ≤ +10%；`seq` 不回退。

**Non-goals**

- 隐式 multi-output（一次调用多字段）。
- 列式 batch call_by。
- LoadRef / adaptive（c30）。
- 含 `$ctx` 的融合。

## Fusion group 规则（第一期）

1. 同一 compute segment（pre-ref 或 post-ref）。
2. 组内无边（字段互不依赖）。
3. deps **完全相同**（强约束，易维护）；后续任务可放宽「高重叠 + index map」。
4. 成员为 `compute_expr` 或无 ctx `call_by`。
5. 通过安全外壳检查。

## 执行形态

```text
旧: for field in group: for row: load deps(field); calc; store
新: for row: load deps(union=identical); for field in group: calc; store
```

可选 tile（例如 64/256 行）仅用于降低缓存局部性调优；缓冲大小须证明 ≤10% 峰值。

## 安全外壳

| 条件 | 行为 |
|------|------|
| `compute_mode == fast_fail` | 不融合 |
| wants FIELD_COMPUTE 或 OPERATOR_SPAN | 不融合 |
| 任一候选含 ctx（`call_ctx_key`） | 该字段不进组 |
| `IColumnSink` | 不融合（Q2-B） |
| 行 streaming / 非流式行 | **可融合**（Q2-B）；须测与 row emission 一致 |
| `is_constant_compute` | 不进组（批次级一次算，与 row-wise 冲突） |
| EXP call_by memo 对该字段生效 | 整组不融合（Q2b） |

## 与 c10 的组合

- c10 决定字段在 early compute 还是 write-precompute。
- c20 只作用于 **仍在 compute 算子段** 的字段集合。
- write-precompute 路径上的行内 deps 复用归 c10，避免两套融合引擎。
- **组织决议**：两个 SDD change 并列；共享「依赖 → 算法 → 值」物化原语（不按 call_by/expr 拆引擎）。

## 评估标准

| 维度 | 门槛 |
|------|------|
| 正确性 | 值相等；每字段 `calc_calls` 计数相等（instrumented calculator） |
| 性能 | 宽表 call_by MVP（对齐 `.tmp/repro/perf-baseline` wide_derived 量级）：耗时 **≥15%** 改善或 opt-in 降级并写明 |
| 内存 | 峰值 ≤ +10% |
| 回退 | 打开 noop Observer 订阅 FIELD_COMPUTE → 路径回退且仍正确 |
| py3.6 | smoke repro |
| bench | `just bench-compare` seq 不回退 |

## 测试 seam（已确认）

- `ScalimEngine.run` + `PlanBuilder` + `InMemoryRowDataSink`
- 可选：注册/不注册 FIELD_COMPUTE observer 对照
- `.tmp/repro/rowwise-fusion/` 证据包

## Open questions → 推荐收口

### Q1. deps「完全相同」是否覆盖不足？ — **已决议：A**

**第一期坚持 deps 完全相同；不够再开 follow-up 放宽重叠。**

- 维护成本低；与 MVP「同 deps 薄 call_by」对齐。
- 高重叠但非全等：第二刀再做 index map，避免第一期把融合引擎做复杂。

### Q2. Streaming 何时启用融合？ — **已决议：B**

**行 streaming 开融合；`IColumnSink` 默认不融合。**

- 纯行依赖、宽薄同 deps：行路径明显受益（少重复读 deps）。
- 列路径让给 c10 晚算 / 「一列一写」。
- 跨域：融合组不会跨 LoadRef 段；同 deps ⇒ 同段。

### Q2b. memo 开启时与融合如何共存？ — **已决议：整组不融合**

**组内任一字段命中 EXP call_by memo → 整组不融合**（退回 field-major）。

- 与「无 memo 时 calc_calls == N×M」口径不打架。
- memo 与 fusion 互补场景留给产品化 memo 另案，不在 c20 硬揉。

### Q3. 与「调用次数不变」的验收 — **已决议：A**

**无 memo 的融合路径：instrumented calculator 计数必须 `== N×M`。** 若未来要减次数，另开 multi-output change，禁止塞进 c20。memo 开时走 Q2b 不融合，故仍满足 N×M。

### 已决议回顾

- 含无 `$ctx` 的 call_by；安全外壳；无 `cached_call_by`；memo 另案。
- **Q1**：融合组 deps **完全相同**（第一期不放宽重叠）。
- **组织**：与 c10 两 change + 共享物化原语。
- **Q2**：行 streaming 开融合；列 sink 默认不融合（B）。
- **Q2b**：组内任一字段 EXP memo 生效 → 整组不融合。
- **Q3**：融合路径 `calc_calls == N×M`（硬门禁）；减次数另案。

## 深挖补遗：`$ctx` / memo / 多 LoadRef（2026-08-01）

| 主题 | 风险 | 结论 |
|------|------|------|
| **`$ctx`** | 声明式：低；隐式全局副作用：中（任何优化都盖不住） | 用 `call_ctx_key` 排除已够；另禁 `is_constant_compute`；隐式副作用靠 fast_fail / 订阅事件回退 |
| **call_by memo** | 值：低；调用次数口径：中 | 按字段 LRU，融合若保持每字段行序则不新增错命中；但 memo **本身**就减调用次数 → 与 Q3 冲突 → 见 Q2b |
| **多 LoadRef** | 低 | Plan 固定 `Load→pre-compute→连续全部 LoadRef→post-compute`，不会「LoadRef 夹多段 compute」；按 pre/post 切段已够 |

证据要点：`call_by_requires_ctx` / `executor.py` 的 `use_ctx`；`call_by_memoization.py`；`build_plan_operators` + `iter_operator_segments`。

## 跨域调研（call_by / compute 会不会跨多个「域」）

仓库里没有统一的 Domain 类型。和融合相关的边界是：

| 边界 | 是什么 | 对融合 |
|------|--------|--------|
| **pre-ref / post-ref** | LoadRef **前/后** 两段 compute（`build_plan_operators`） | 组必须同段；**同 deps 的字段必然同段**（闭包判定） |
| **LoadRef** | 中间插入的取数；adaptive 只并行这段 | 融合不碰 LoadRef；不会把 pre 与 post 揉一组 |
| **Stage.level** | 依赖 DAG 层级（viz/深度） | 与 pre/post **正交**；同级无边才可进一组 |
| **`$ctx` / field_id** | 每字段独立 call context | 已排除出融合组 |
| **RuntimeBindings** | 按 field 注册计算器 | **不是**执行域 |

**单个** `call_by`/`compute_expr`：只在 **一个** compute 段里跑一遍算法，不会「一次调用跨 pre+post」。  
**依赖**可以跨段：post-ref 字段可读 LoadRef 结果、可读 pre-ref derived——这是正常流水线，不是把两个字段融成一组。

硬禁止的是另一类「跨域」：relation join key / ref `default.call_by` 依赖尚未 LoadRef 就绪的字段（规划 fail-fast）。

**对 B 的含义**：行路径开融合时，仍按「同一 pre-ref 段」或「同一 post-ref 段」各自组内融合；**不会**因为「跨了 LoadRef 的依赖链」就把前后两段字段融在一起。纯行、同 deps、无 ctx 的那批最受益；依赖 ref 列的那批在 post-ref 段里同样可融（彼此同 deps 时）。
