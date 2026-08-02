---
depends_on: []
---

## Why

当 `lookup_chunk_size` 把一次 `LoadRef(keys)` 拆成多片时，当前实现是 **串行** 调 loader。在 I/O / RTT 主导（数据库、远程接口）时，片数会把固定等待线性放大。

批次内多路独立 LoadRef 已可由 `parallel_mode=adaptive` 重叠等待；但 **同一 source 的多 chunk** 仍串行，成为下一块短板。合成 MVP 已证明 adaptive 在多独立 ref + 延迟下可达约 **1.6×～2.0×**；chunk 并行是同一故事在「单 ref 超大键集」上的延续。

约束：

- **默认行为不变**（未 opt-in = 今日串行分片）。
- **不新增 YAML 字段**：复用已有 `lookup_chunk_size`；并行开关走 Python runtime policy（YAML=authoring / Python=policy）。
- 不引入第三种并行心智；用户仍理解 `seq` / `adaptive`，外加「允许分片并行」的运行选项。
- 峰值 RSS ≤ +10%；并发度有上限，避免默认打爆外部系统。
- 零字段 DSL 迁移。

## What Changes

- 为 `lookup_chunk_size` 分片路径增加 **opt-in 并行**：同批、同一步的多个 chunk loader 调用可线程并发，合并结果与串行分片语义等价。
- 显式并发上限与取消/超时与现有 adaptive 护栏对齐或复用（见 design）。
- 可观测：每 chunk 仍发 `loader_call`（含 key 计数），可对比串行/并行。
- Specs：**新建** `execution-refloader-chunk-parallelism` 为并行分片合约 SSOT；`parallel-execution` / `ir-source-relations` / `execution-adaptive-guardrails` / `demand-dsl` 仅交叉引用（见 design「Specs SSOT」）。
- 证据：多 chunk + 模拟 RTT 的 A/B；`seq` 无 opt-in 时零回退；py3.6。

**不改**

- YAML schema 新键。
- 默认 `seq`/`adaptive` 下「未开启 chunk 并行」的行为。
- 派生字段融合（c10/c20）。

## Capabilities

### New Capabilities

- `execution-refloader-chunk-parallelism`：opt-in 分片并行语义、合并等价、限流、观测、默认关。

### Modified Capabilities

- `parallel-execution`：交叉引用——说明与 `adaptive`（跨 LoadRef）和 chunk 并行（同 ref 分片）的层次关系；**不**把 chunk 并行塞进 r311 边界定义。
- `execution-adaptive-guardrails`：交叉引用——全局帽复用 resolved workers W / 父任务超时；**不**在此 spec 展开 chunk 算法。
- `ir-source-relations`：交叉引用——串行 `lookup_chunk_size` 合并（r694）仍为分片合并语义 SSOT；并行 MUST ≡ 该语义。
- `demand-dsl`：不变（`lookup_chunk_size` 仍只表示分片大小 / authoring）。

## Impact

- **兼容**：默认路径比特级保持串行分片；opt-in 后值等价、调用次数 = chunk 数（与串行相同），仅时间重叠。
- **性能**：多 chunk + RTT 场景目标相对串行分片加速建议 **≥1.5×**（证据驱动可调）。
- **内存**：≤ +10% 峰值；主要风险在外部 QPS 而非 RSS。
- **维护**：并行仅落在 `load_ref/loader.py` 分片合并路径；策略开关一处；池形态见 design Q2-B′。
- **风险**：opt-in 后放大 DB 并发——文档与 **全局帽=W** 强制。

## Open Questions（已全部收口）

| ID | 决议 | 详见 |
|----|------|------|
| Q1 | 仅 `adaptive` + opt-in；`seq` 永不 chunk 并行 | `design.md` |
| Q2 | 独立 chunk 池 + 全局帽=W（B′） | `design.md` |
| Q3 | opt-in：`DemandRunRuntimeOptions` / `PipelineOverrides`；无新 YAML | `design.md` |
| Q4 | 超时/取消跟父 LoadRef；无独立 chunk timeout | `design.md` |
| Q5 | `loader_call` 完成序 + `chunk_offset`；不缓冲排序 | `design.md` |

**非本 change**：YAML 中非编排类字段迁 Python —— 见 draft **`c40-yaml-runtime-policy-boundary`**（调研任务，后续 agent 承接）。

## Ethics

- `ethics.risk_level`: medium（外部系统压力）
- `ethics.prohibited_actions`: 默认开启 chunk 并行；无上限扇出；为加速静默改变合并语义
- `ethics.required_evidence`: 串行 vs 并行结果等价 + 耗时证据 + 限流测试
- `ethics.refusal_contract`: 无法证明合并等价时不得合入
- `ethics.escalation_policy`: 若需 YAML 暴露开关，须另议（与 runtime-policy-boundary 原则冲突时升级确认）
