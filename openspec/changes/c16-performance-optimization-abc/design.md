## Context

Scalim 的核心执行链路为 `DemandIr` → `ExecutionPlan` → `Pipeline`/`BatchExecutor` → `Sink`。目前框架已具备 FR021/FR022/FR023（规划剪枝、运行时瘦身、流式写出）等能力，但在“关联 + 大批次 + 低观测”场景仍存在可避免的 CPU/内存开销：

- **热路径 wants-gated 不彻底**：即使未订阅某些诊断/观测事件，执行侧仍可能做逐行/逐键的额外计算与对象构造，仅在最终 `emit` 处短路。
- **BatchContext 存储开销偏高**：当前以“字段 → {row_id → value}”的 dict-of-dict 形态存储（批次内 `row_id` 实际为连续整数），在字段多/批次大时哈希表开销与对象数量会放大 RSS。
- **sink 写出需要中间 dict**：当前 `IColumnSink.write_column(field_key, Dict[row_id, value])`/`IRowSink.write_row(Dict[field_key, value])` 形态使 pipeline 在写出前必须构造 dict（对大批次/宽表会形成可见分配峰值）。

约束：
- `src/scalim/` 运行时必须兼容 Python 3.6。
- wants-gated 语义以 `openspec/specs/hooks-observability-structure/spec.md` 为 SSOT，要求在 `wants(event_type)=false` 时不引入热路径额外开销。
- 文档治理：`.gen.` 文件与 `BEGIN/END AUTOGEN` 块不得手改；如涉及站点内容，需通过 SSOT + `just gen-docs` 更新。
- OpenSpec 工件在共享/发布前必须通过 `just openspec-check`。

## Goals / Non-Goals

**Goals:**
- 以 A→B→C 渐进方式降低 RSS 峰值并提升吞吐，且每步都有 **c0 级护栏** 防回归。
- 强化 wants-gated：当无订阅者时避免逐行/逐键的无意义开销（不仅是“不构造 Event”）。
- 为批次内连续 `row_id` 引入 Dense 存储路径，降低 BatchContext 的对象与哈希开销。
- 为 sinks 增加可选 fastpath 写入能力，减少写出阶段的中间 dict 构造。
- 所有改动可通过现有基准与新增单测验证；默认 CI 不强依赖耗时/不稳定的性能门禁。

**Non-Goals:**
- 不改变 YAML DSL / IR / planning 的语义与公共行为（除非明确标注为 BREAKING 并同步 specs）。
- 不引入新的强运行时依赖（例如 numpy/pyarrow）来换取性能。
- 不在本变更中重写 execution 规划/调度（例如重新设计 adaptive scheduler）。

## Decisions

### Decision A: 把“热路径 wants-gated”从 emit 层推进到调用点

**选择：**
- 在执行热路径（典型：LoadRef 诊断、某些事件 payload 预处理）增加一次性门控：`if not wants(EVENT_X): skip expensive loop`。

**备选：**
- 仅在 `InstrumentationHub.emit_*` 内短路（现状）：仍会保留调用点的循环/对象构造成本。
- 把诊断全部下沉到 Observer（执行层不做任何 hit/miss 计算）：会改变现有事件语义与诊断能力，风险较高。

**理由：**
该决策与 `hooks-observability-structure` 的 wants-gated 语义一致，且对外行为不变（仅减少未订阅时的额外开销）。

### Decision B: 为 BatchContext 引入 Dense 存储实现（按批次连续 row_id）

**选择：**
- 保留 `BatchContext` 公开 API 语义，但在内部针对“row_id 连续 int”的批次启用 Dense path：
  - 每个字段使用 list/array-like 存储值（按 `row_id - base_row_id` 索引）。
  - 删除/行级释放为“置空 + 可选稀疏回收”。
  - `OverlayBatchContext` 同步提供 Dense 兼容实现或适配层。

**备选：**
- 继续使用 dict-of-dict，仅做微优化：收益有限，RSS 峰值难显著下降。
- 引入第三方列式结构：破坏 Python 3.6 边界且增加依赖。

**理由：**
批次 `row_id` 由 pipeline 按行顺序分配且连续，Dense path 具备稳定前置条件；实现可控且收益明确（对象数/哈希开销显著下降）。

### Decision C: 增加 sink 写入 fastpath（可选能力，pipeline 优先使用）

**选择：**
- 在 `sink_base` 中定义可选 fastpath：
  - 列式：允许 sink 接收对齐的 `row_ids` + `values`（或等价结构），避免 pipeline 构造 `{row_id: value}` dict。
  - 行式：允许 sink 接收对齐的 `field_keys` + `values`（或等价结构），避免构造 row dict。
- pipeline 在检测到 sink 支持 fastpath 时走 fastpath，否则走现有接口。

**备选：**
- BREAKING 直接替换现有 `write_row/write_column` 签名：会违背 `sinks-contracts` 的接口稳定性要求，且影响外部 sinks。

**理由：**
该路径能在宽表/大批次场景显著降低写出阶段的分配峰值，同时保持现有 sinks 可继续工作。

## Risks / Trade-offs

- [风险] wants-gated 优化可能在“某些 observer 只订阅 on_event 路径”下误判 wants → [缓解] 以 `InstrumentationHub.wants()` 为唯一门控来源，并补充单测覆盖 hook/observer 两条路径。
- [风险] DenseBatchContext 与 OverlayBatchContext 语义偏差（delete/disable_row 等边界）→ [缓解] 以现有 `BatchContext` 行为为基线，增加等价性单测；对关键 API（set/get/delete_row/delete_field/get_field_keys）做参数化测试。
- [风险] fastpath 增加 sink 复杂度与实现成本 → [缓解] fastpath 仅为可选接口；内建 sinks 与关键测试先覆盖；外部 sinks 不强制迁移。
- [风险] 性能基准在不同机器不稳定，CI 门禁易误报 → [缓解] c0 护栏优先采用确定性的“调用次数/分配路径”单测；基准用于趋势与回归定位，CI 仅保留可选或宽松阈值。

## Migration Plan

- 阶段 0（c0 护栏先行）
  - 新增“热路径 wants-gated”确定性单测与基准用例（不依赖机器性能阈值）。
  - 固化性能采集流程：`just bench*` + `just bench-memray*` 的推荐用法与产物位置。
- 阶段 A（hotpath 优化）
  - 逐点落地 wants-gated 的调用点短路，确保未订阅时不发生逐行诊断循环。
- 阶段 B（DenseBatchContext）
  - 引入 Dense 实现并在 pipeline/batch executor 中启用；保留回退路径与等价性测试。
- 阶段 C（sink fastpath）
  - 定义可选接口 + 内建 sinks 适配 + pipeline 选择逻辑；补充回归测试与基准对比。

回滚策略：
- A/B/C 每阶段都可通过 feature flag（仅内部、默认开启/关闭由任务定义）或逐步合入的方式控制风险；若出现回归，优先回滚到上一阶段实现并保留测量数据用于定位。

## Open Questions

1. 性能主场景优先级：以 `tests/bench` 的哪个 group 作为“主 KPI”（relations / full_column / yaml_dsl / workflow）？
2. sink fastpath 的接口形态：选择 “(row_ids, values)” 还是 “MappingView/SequenceView” 等更抽象的载荷协议？
3. 是否需要在 CI 增加“可选 perf job”（例如 nightly）来自动跑 `bench-compare-fail` 与 memray 采样？

