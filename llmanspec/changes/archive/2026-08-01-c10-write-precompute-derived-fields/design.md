# Design: write-precompute（写出前延迟物化）

## Goals

- 零 DSL、**无** runtime 物化总开关、**无** YAML `virtual`/`lazy`：仅用现有字段依赖/消费者关系自动识别 late；不安全则保持早算。
- 将「仅用于最终写出」的派生字段推迟到 row 写出前计算，减少 `BatchContext` 写回与驻留。
- 第一期包含无 `$ctx` 的 `call_by`（用户确认范围）；含 `$ctx` 排除。
- 峰值 RSS 相对基线 ≤ +10%（预期常更好）。
- 默认 `seq` 不回退。

## Non-goals

- multi-output / `call_groups` 语法。
- 替换 `openpyxl`。
- 跨行 memo（见 memo 后置案）。
- 第一期 **行 + 列** 均支持链式晚算（late 子图拓扑）；「无子图外消费者」才可 late。
- Apply 前以 `mvp/repro_complex_baseline.py` 固定黄金值与峰值契约（见 design Q3）。

> Column sink：不再视为「永远另案」。行 sink late-at-write_row 为切片 A；**列 sink late-at-write_column** 为同 change 切片 B（调研结论见下文「按列 stream write」）。切片 B 可在 A 之后落地，但设计上必须兼容「写完一列就忘掉」。

## Late 字段判定（SSOT 思路）

字段 `f` 可进入 `late_fields` 当且仅当：

1. `f` ∈ `plan.target_fields`；
2. 不存在任何后续算子/字段以 `f` 为依赖（其它 derived deps、LoadRef `from_field`、key_fields 等——**只认 Plan/IR 显式边**）；
3. `f` 为派生字段，且：
   - `compute_expr`，或
   - `call_by` 且 **不** 需要 ctx（无 `ctx` / `ctx_attr` 参数）；
4. `f` 的依赖在写出点已可获得（main/ref 已加载，或同属 late 子图且可拓扑排序）。

不确定则 **不 late**（保守回退现路径）。

## 执行形态

```text
现路径:  ... → Compute(含全部派生) → Write(从 context 取)
新路径:  ... → Compute(仅 non-late) → Write(前: 算 late 子图 → 写行；late 不落 context)
```

- Row-local deps cache：dict/数组，仅当前行生命周期。
- Late 子图内按拓扑序计算；中间 late 结果可留在 row-local，不写 context。

## 语义边界

| 项目 | 契约 |
|------|------|
| 写出值 | 与优化前一致 |
| quiet / fast_fail | 沿用现有 compute guardrails；fast_fail 在写出前触发时，已写出前缀语义须与「若该计算仍在旧 compute 阶段失败」对齐或在 spec 显式写清差异 |
| `call_by` 副作用 | **次数不变**；**时机**可从 compute 段后移到 write-precompute |
| `$ctx` call_by | 禁止 late |
| 事件 | 仍发 `FIELD_COMPUTE`；`meta.scalim_compute_phase` ∈ `{operator, write_precompute}` |

## 与 c20（row-wise fusion）的边界

- c10：改变 **哪些字段在哪一阶段算**（late vs early）。
- c20：在同一阶段内改变 **循环嵌套 / 调用归并**（field-major → row-wise / 同 deps 复用）。
- **组织决议（2026-08-01）**：保持 **两个 SDD change**；实现共享「依赖 → 算法 → 结果值」物化原语（`call_by`/`compute_expr` 同逻辑）。late 路径行内 deps 复用算 **c10**；c20 只作用于仍在 compute 段的非 late 字段——避免两套融合引擎。
- 可组合：non-late 段可被 c20 融合；late 段可在写出前做行内复用（c10 已含 row-local cache，避免与 c20 双重发明——late 路径的行内复用算 c10 职责）。

## 评估标准（合入门槛）

| 维度 | 门槛 |
|------|------|
| 正确性 | 固定 Demand + rows，写出行值深度相等；被下游消费的字段永不 late（单测） |
| 性能 | 约定 MVP（建议：≥2k 行 × ≥20 个仅输出派生，含无 ctx call_by）：端到端实际耗时下降 **≥15%** 或给出证据说明未达标原因并降级为 opt-in |
| 内存 | 峰值 RSS 变化 ≤ +10%；优先证明下降 |
| 兼容 | 无新 YAML；`seq` bench 关键 group 不回退（`just bench-compare-fail` 阈值与仓库惯例一致，默认 mean:10%） |
| py3.6 | `.tmp/venvs/py36-scalim` + `PYTHONPATH=src` 跑 smoke repro |

## 测试 seam（已确认）

- `ScalimEngine.run` + `PlanBuilder` + row sink（`InMemoryRowDataSink` / 对齐 `write_row_aligned`）。
- Observer 未注册时无额外事件税（wants-gated）。
- 不引入脱离现有 pytest 的平行 harness；本仓库暂无 `bdd:`，场景以 pytest + 日后 Specs landing 的 `spec.toon` 为准。

## 实现触点（预估）

- `planning/plan.py` 或 runtime：计算 `late_fields` / 消费者集。
- `execution/pipeline/base/_row_emission.py`：写出前计算。
- `execution/executor/operators/compute`：跳过 late 字段。
- tests：`tests/execution/` 新用例 + `.tmp/repro/write-precompute/`。

## 与「按列 stream write」——补充调研（2026-08-01）

用户直觉：融合可能把多列结果先堆在临时过程里；更想要的是一种 **延迟物化策略**——虚拟/计算字段尽量拖到 **最后一次写入** 才算。

这与 c10 同向，且要和「列模式省上下文」对齐，而不是打架。

### 三种时刻（用表说话）

同一批 2 行，输出 d0/d1/d2（仅写出、互不依赖）：

| 策略 | 过程里堆什么 | 和「写完一列就忘掉」 |
|------|--------------|----------------------|
| **早算**（今天常见） | 先把 d0/d1/d2 都算进上下文，再写 | 列模式写后可删，但算的阶段仍可能短暂三列都在 |
| **c20 按行融合** | 一行算完三列再换行 → 组结束时三列常同时在 | 与「一列一释放」**抢峰值**（组越大越明显） |
| **c10 晚算 / 写入时才算** | 上下文主要留原料（v0/v1…）；写 d0 前才算 d0 这一列，写出后可不落库 | 与列 stream **同向** |

列模式下的「最后一次写入」可以具体成：

```text
（本批）原料列已在上下文
→ 轮到写目标列 d0：临时算出本批所有行的 d0 → write_column(d0) → 不把 d0 留在 context
→ 再写 d1：同样「算完就写、不驻留」
```

这不是「整张表算完再写」，而是 **按列、在即将 `write_column` 的那一刻才物化该列**。

### 为何第一期设计曾写「Column sink 另案」

当时担心把 **行式** late（写出前按行算一整行）误接到列 sink 上，变成别扭的 N 次列扫描。  
更贴列契约的形态其实是：**late 的粒度是「列」而不是「行」**——与现有 `_write_column_if_target` 钩子天然接近（算子后写列 → 改为「写列前现场算 late 列」）。

### 策略面（硬约束：零开关、零新 DSL）

| 做法 | 决议 |
|------|------|
| **自动判定 late_fields**（仅用 Plan/IR **已有**字段依赖/消费者边） | **唯一主路径**；旧脚本不改 |
| 运行期总开关（`eager`/`late`） | **不做** |
| YAML / 字段上标 `virtual`/`lazy` 等新语法 | **不做** |

框架已有机制保证字段联系与依赖（规划期依赖闭包、`reverse_deps`、算子序等）。late 候选 =「在 `target_fields` 且无下游消费者」的派生字段；判不准或不安全则 **保持今日早算**（静默回退，不引入用户可见开关）。

### 仍须补的调研项（apply 前）

1. **列路径 MVP**：`IColumnSink` + 大量仅输出派生；对比 eager vs late-at-write_column 的耗时与 context 驻留字段数 / RSS。  
2. **依赖仍被其它列需要时**：late 列若被另一 late 列依赖，写顺序必须按拓扑；或禁止「late 依赖 late」第一期只允许 deps∈已物化非 late。  
3. **与 c20**：行 sink 上 late 子图可做行内 deps 复用（c10）；列 sink 上 late 按列算时，同 deps 的多列仍会重复读原料——那是 c20 列路径要不要开的问题（可默认不开）。  
4. **副作用时机**：call_by late 时调用挪到写列前（次数不变）——合约已写；列路径同样适用。

### 结论（调研中期判断）

- 「计算字段拖到最后写入才算」**值得做**，且已是本 change 核心，不是新方向。  
- 对 **列 stream**：应把 **late-at-write_column** 从「另案」提升为 **同 change 的明确第二切片**（可仍排在行 sink 切片之后，但不要当成无关 future）。  
- 对 **行 stream**：late-at-write_row（现 design 主形态）继续。  
- 与 c20：一个管 **何时算**，一个管 **怎么扫**；列模式下优先 c10 晚算，融合让路。

## Open questions → 收口进度

### Q1. Streaming + fast_fail「已写前缀」— **已决议（用户 2026-08-01）**

**决议：`fast_fail` = 计算失败则报错，并对 sink 做 discard 回滚；失败不可恢复，不得把半成品当成最终输出。**

因此「晚算 vs 早算失败前已写出哪些行」**不必位级一致**——失败路径以 **discard** 为准，用户看不到可用的半截结果。

- `quiet`：值语义仍须与今日一致（该格按既有规则写 None 等），跑完可正常 close。
- `fast_fail`：抛错 + `discard()`；单测锁定「失败且无最终产出」，**不**锁失败前缀行集合。
- 与现有 `ISink.discard` 失败清理合约对齐。

### Q2. capability 放哪 — **已决议（用户 2026-08-01）**

**决议：并入既有 `execution-hotpath-fastpaths`（更新该域），不新建平行 capability。**

依据：晚算是 **默认行为变更**；若另开专册会形成双 SSOT，易与热路径总则冲突/漂移。Specs landing 时在 `execution-hotpath-fastpaths` 增补/改写 MUST（late 判定、discard、事件 phase、内存有界），并审视是否与既有「行为保持」条款需要同步改写表述（「值语义保持；物化时机可延后」）。

### Q3. late→late 链式 — **已决议：C（行+列均含链式）**

**决议：本期行路径 + 列路径均支持链式晚算（late 子图拓扑）。**

- 「无下游消费者」= **无 late 子图以外的消费者**（LoadRef / 非 late 派生等仍阻断）；子图内部 late→late 允许。
- **Apply 前门禁**：必须先有 **复杂 MVP + 固定基准**（见 `mvp/repro_complex_baseline.py` 与 `evidence/baseline-complex.json`），覆盖：平坦晚算、链式晚算、行/列两种写出、期望值对拍、峰值草稿纸指标；实现后 engine A/B 不得劣于该基准契约（值相等；峰值不差于仿真上界的约定比例；`fast_fail`+discard）。
- 列路径链式须显式处理「中间 late 列暂留至依赖方写完再删」，并在 MVP/单测中固定行为，避免回归「一列一释放」语义时无证据。
