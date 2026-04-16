## Why

`workflow` 的 `stage_barrier` 调度与 `stage` 归因属于“语义 + 可观测性 + 性能”强耦合的改动：即使当前实现与回归用例已覆盖主要路径，仍可能在真实项目里遇到解释偏差、下游消费破坏或性能印象落差。

本提案用于把这些“暂不在主线 change 中继续推进”的残留风险集中记录下来，形成后续迭代/验收时的 checklist，避免风险分散在讨论记录与 commit message 里。

## What Changes

- 新增一份 risk register（仅文档），记录 `workflow stage scheduling` 的残留风险、触发条件与建议缓解措施。
- 明确当前推荐策略的“默认值与边界”：
  - 默认仍以 `pipeline` 为默认调度策略；`stage_barrier` 为显式 opt-in。
  - `stage` 作为对外单一概念（避免 `wave`/`stage` 概念分叉）。
  - 对内部 write nodes 的 `stage` 归因优先折叠到其输入 demand 的 `stage`（贴近用户视角），同时为调试预留可扩展空间。
  - 事件层字段暴露优先走 `viz snapshot` 扩展，再视稳定性与下游消费情况考虑扩展 workflow node 事件 payload。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- (none)

## Impact

- **代码影响面**：无（本提案仅新增文档）。
- **兼容性**：无（不改变 runtime 行为与事件结构）。
- **交付形态**：作为后续变更的风险对照清单，可在实现/验收时逐条核对。

## Risk Register

### R1: `stage_barrier` 可能导致吞吐下降或 wall time 放大
- **风险**：当 DAG 存在高扇出/慢节点时，严格阶段屏障会把可并行的尾部工作推迟到下一阶段，整体 wall time 可能变长（即便 `max_concurrency` 很高）。
- **触发信号**：`pipeline` 模式下能够形成 overlap，但切到 `stage_barrier` 后出现明显空转/等待。
- **缓解建议**：
  - 保持 `pipeline` 为默认；把 `stage_barrier` 明确标注为“可解释性优先”的 opt-in。
  - 在可观测数据中提供阶段级等待/阻塞的解释字段（至少能看出“卡在哪个 stage 的 barrier”）。

### R2: 内部 write nodes 的 `stage` 折叠可能隐藏执行细节
- **风险**：对外仅暴露折叠后的 `stage` 更贴近业务视角，但 power users 可能希望看到内部写入/落盘步骤的真实拓扑层级；折叠可能让排障时“感觉少了一层”。
- **触发信号**：用户在 viz 里无法解释“为什么某些内部节点看起来没有独立阶段”。
- **缓解建议**：
  - 保持对外默认折叠，但在调试视图/诊断数据中预留额外维度（例如节点 `kind`、或未来引入 `internal_stage` 之类字段）。
  - 文档明确：`stage` 是用户心智模型下的阶段，而不是内部执行步骤计数器。

### R3: 可观测字段扩展的兼容性风险（`viz snapshot` vs event payload）
- **风险**：扩展 workflow node 事件 payload 可能影响下游消费方（解析器/存储/告警规则），一旦字段被依赖，后续迭代成本更高。
- **触发信号**：已有下游对事件 payload 做强 schema 绑定；或事件被外部系统长期存档。
- **缓解建议**：
  - 优先在 `viz snapshot` 增加字段（更接近“可视化/诊断用途”，对结构稳定性要求可控）。
  - 仅当字段被证实需要“事件流强消费”时，才扩展事件 payload，并为字段稳定性/版本策略留出约束。

### R4: 术语漂移导致概念分叉（`wave` vs `stage`）
- **风险**：同一语义被两个词描述会导致文档、代码与用户材料出现分叉，增加沟通与维护成本。
- **触发信号**：文档/代码中同时出现 `wave_*` 与 `stage_*` 并指向相同概念。
- **缓解建议**：
  - 对外只保留 `stage`（含 `stage_barrier`）；`wave` 仅作为历史讨论词汇，不进入公共表面。
  - 对外枚举值/字段名一旦确定，避免再二次命名。

### R5: “性能印象”评估容易被误当作严谨基准
- **风险**：notebook 或 demo 级对比往往反映的是“印象/趋势”，但容易被误读为可复现的 benchmark 结论。
- **触发信号**：对比样本过小、数据分布偏置、机器/并发环境不可控。
- **缓解建议**：
  - 明确区分：notebook 用于“直观对比与排障复现”，benchmark 需要独立的基准套件、固定数据与隔离环境。
  - 在报告中强制写清楚样本规模、环境、局限性与不确定性来源。
