# workflow-stage-scheduling-residual-risks Specification

## Purpose
将 `workflow stage scheduling`（`pipeline` / `stage_barrier`）相关的“残留风险”收敛为稳定、可检索、可复核的 risk register，并明确在后续迭代/验收中必须检查的边界与可观测性约束。

本 spec 不引入新的 runtime 行为；其目标是把“真实项目里可能遇到的解释偏差、下游消费破坏或性能印象落差”显式化，作为后续变更的 checklist。

## Requirements

### Requirement: workflow stage scheduling residual risks MUST be tracked as a stable risk register
系统 MUST 提供一份稳定可发现的 risk register，用于记录 `workflow stage scheduling` 的残留风险、触发条件与缓解建议，并避免风险仅存在于：

- 临时讨论记录
- commit message
- 单次 change proposal（归档后难以被后续变更发现）

risk register MUST 至少覆盖以下风险条目（ID 稳定，便于引用）：

- **R1**：`stage_barrier` 可能导致吞吐下降或 wall time 放大
- **R2**：内部 write nodes 的 `stage` 折叠可能隐藏执行细节（诊断视角的“少一层”感受）
- **R3**：可观测字段扩展的兼容性风险（`viz snapshot` vs workflow node event payload）
- **R4**：术语漂移导致概念分叉（`wave` vs `stage`）
- **R5**：性能“印象”评估容易被误当作严谨 benchmark

risk register 的每个条目 MUST 至少包含：

- **Risk**：风险描述（面向维护者/使用方）
- **Signals**：触发信号/观测证据（从哪里看、怎么看）
- **Mitigations**：建议缓解措施（含默认策略/边界）
- **Touchpoints**：相关的 spec / 代码位置（用于快速定位）

#### Scenario: maintainers can use the risk register as a release/acceptance checklist
- **GIVEN** 维护者计划修改 `workflow` 的 scheduler preset、`stage` 归因或相关可观测字段
- **WHEN** 维护者准备实现或验收该变更
- **THEN** 维护者 MUST 对照 risk register 逐条确认影响与缓解
- **AND** 如果出现新的残留风险或触发条件变化，维护者 MUST 更新 risk register

### Requirement: recommended defaults and semantic boundaries MUST be explicitly stated
risk register MUST 明确写清楚以下默认值与边界（避免在后续变更中被“顺手改掉”或发生概念分叉）：

- 默认调度 preset MUST 为 `pipeline`；`stage_barrier` MUST 为显式 opt-in（并明确其 trade-off）
- 对外公开概念 MUST 统一为 `stage`（不得引入 `wave` 等同义概念作为公共表面）
- 对内部 write nodes：对外暴露的 `stage` MUST 折叠到其输入 demand 的 `stage`（避免把内部写入步骤误解为新的业务阶段）

#### Scenario: default and boundary statements are discoverable without reading code
- **WHEN** 维护者仅阅读 spec（不打开源码）
- **THEN** MUST 能明确知道 `pipeline` 是默认值、`stage_barrier` 是 opt-in
- **AND** MUST 能明确知道对外统一使用 `stage`，以及 write nodes 的 `stage` 会被折叠

### Requirement: observability extensions MUST prefer viz snapshot first, event payload second
当为 `workflow stage scheduling` 增加新的诊断字段时，系统 MUST 优先通过 `viz snapshot` 扩展字段：

- `viz snapshot` 更接近“可视化/诊断用途”，字段稳定性约束可控
- workflow node 事件 payload 可能被下游强 schema 消费（解析器/存储/告警规则），扩展成本更高

只有当字段被证实需要“事件流强消费”时，系统才 SHOULD 扩展 workflow node 事件 payload，并 MUST 明确字段稳定性与版本策略。

#### Scenario: new stage-scheduling diagnostics land in snapshot before event payload
- **GIVEN** 维护者需要新增一个与 `stage_barrier` 相关的诊断字段（例如 stage 间等待解释）
- **WHEN** 维护者落盘该字段
- **THEN** 该字段 MUST 首先出现在 `viz snapshot`
- **AND** workflow node 事件 payload 的扩展必须是显式决策（有理由、有兼容性评估）

### Requirement: performance impression artifacts MUST be labeled as non-benchmark
当仓库提供用于对比 `pipeline` 与 `stage_barrier` 的性能材料（notebook/demo/report）时，系统 MUST 明确区分：

- **Impression / Trend**：用于直观对比、排障复现
- **Benchmark**：需要固定数据集、隔离环境、可重复的基准套件

并且 MUST 在材料中写清楚样本规模、环境与局限性，避免结论被误读为严谨 benchmark。

#### Scenario: maintainers can tell impression vs benchmark at a glance
- **WHEN** 维护者打开性能对比材料
- **THEN** MUST 能在开头看到“非 benchmark”的声明与局限性说明

## Risk Register (Current)

### R1: `stage_barrier` 可能导致吞吐下降或 wall time 放大

**Risk**

当 DAG 存在高扇出/慢节点时，严格阶段屏障会把可并行的尾部工作推迟到下一阶段，整体 wall time 可能变长（即便 `max_concurrency` 很高）。

**Signals**

- `pipeline` 模式下可以形成跨 stage overlap，但切到 `stage_barrier` 后出现明显空转/等待
- 在 workflow replay/viz 里能观察到 stage 之间存在较长 gap（下一 stage 迟迟不启动）

**Mitigations**

- 保持 `pipeline` 为默认；把 `stage_barrier` 明确标注为“可解释性优先”的 opt-in
- 诊断字段优先通过 `viz snapshot` 扩展（例如 stage 间等待解释/指标），避免过早扩展事件 payload

**Touchpoints**

- 调度语义：`src/scalim/workflow/execute_controller.py`（stage barrier 推进 + ready-queue 过滤）
- 默认 preset：`src/scalim/dsl/yaml_dsl/workflow_types.py`、`src/scalim/dsl/yaml_dsl/workflow_compile.py`
- 可运行对照（非 benchmark）：`notebooks/marimo/workflow_stage_scheduling_perf/demo_main.py`

### R2: 内部 write nodes 的 `stage` 折叠可能隐藏执行细节

**Risk**

对外仅暴露折叠后的 `stage` 更贴近业务视角，但 power users 可能希望看到内部写入/落盘步骤的真实拓扑层级；折叠可能让排障时“感觉少了一层”。

**Signals**

- 用户在 viz 里无法解释“为什么某些内部节点看起来没有独立阶段”
- 用户反馈“看起来内部节点被算进了上游 stage”，但需要区分是 stage 归因折叠还是调度策略导致

**Mitigations**

- 保持对外默认折叠（`stage` = 用户心智模型）；在诊断视图/快照中预留额外维度扩展空间（例如 `kind`、或未来引入 `struct_level`/`internal_stage`）
- 明确文档：`stage` 是用户侧阶段归因，而非内部执行步骤计数器

**Touchpoints**

- 归因规则：`src/scalim/workflow/stage_attribution.py`
- snapshot 投影：`src/scalim/ob/presets/viz/workflow.py`（节点 `data.level`）

### R3: 可观测字段扩展的兼容性风险（`viz snapshot` vs event payload）

**Risk**

扩展 workflow node 事件 payload 可能影响下游消费方（解析器/存储/告警规则）。一旦字段被依赖，后续迭代成本更高，且难以回收字段或调整语义。

**Signals**

- 已有下游对事件 payload 做强 schema 绑定；或事件被外部系统长期存档
- 引入字段后出现“看似小改动却触发下游联动”的反馈

**Mitigations**

- 优先在 `viz snapshot` 增加字段（更接近“可视化/诊断用途”，结构稳定性要求可控）
- 仅当字段被证实需要“事件流强消费”时才扩展事件 payload，并为字段稳定性/版本策略留出约束

**Touchpoints**

- workflow node 事件契约：`src/scalim/events/_events.py`、`src/scalim/workflow/execute_controller.py`
- snapshot 结构：`src/scalim/ob/presets/viz/workflow.py`

### R4: 术语漂移导致概念分叉（`wave` vs `stage`）

**Risk**

同一语义被两个词描述会导致文档、代码与用户材料出现分叉，增加沟通与维护成本；并可能在后续演进中形成不可逆的外部契约差异。

**Signals**

- 文档/代码中同时出现 `wave_*` 与 `stage_*` 并指向相同概念
- 使用方在沟通中开始混用两套词汇

**Mitigations**

- 对外只保留 `stage`（含 `stage_barrier`）；`wave` 仅作为历史讨论词汇，不进入公共表面
- 对外枚举值/字段名一旦确定，避免再二次命名

**Touchpoints**

- 术语入口：`openspec/specs/workflow-stage-scheduling/spec.md`
- 仓库搜索（回归时建议扫描）：`rg -n \"\\\\bwave\\\\b|wave_\"`

### R5: “性能印象”评估容易被误当作严谨 benchmark

**Risk**

notebook 或 demo 级对比往往反映的是“印象/趋势”，但容易被误读为可复现的 benchmark 结论，进而在决策或宣发中被过度引用。

**Signals**

- 对比样本过小、数据分布偏置、机器/并发环境不可控
- 结论缺少环境/样本描述，却被引用为“性能证明”

**Mitigations**

- 明确区分：notebook 用于“直观对比与排障复现”，benchmark 需要独立的基准套件、固定数据与隔离环境
- 在报告中写清楚样本规模、环境、局限性与不确定性来源

**Touchpoints**

- 可运行对照材料：`notebooks/marimo/workflow_stage_scheduling_perf/demo_main.py`
