---
depends_on: []
blocks:
- c55-stage-write-attribution
branch: sdd/c50-run-stats-low-drift-observability
base_sha: 8982be89879228f589d050b47c1f4ad34bdb5f71
checkpointed: true
checkpoint_sha: 8982be89879228f589d050b47c1f4ad34bdb5f71
---

# 低漂移 run_stats / bench 自我观测底座

## Why

下游与内部 demo（`.tmp/obs-demo`）证明：用户与框架都需要**正确、可选、可归档**的运行期证据，才能判断优化方向（用户 loader / compute / call_by / relations，或框架自身改动）。现有缺口：

- `PerformanceObserver` / `RelationObserver` 在 **workflow 多 demand 共享实例**时会在下一 `PIPELINE_START` **reset**，末态读数变成「假零」或只剩最后一节点 → **误判**。
- 报告契约分散（console / perf json / 下游自造 `run_stats`），缺少框架级稳定 schema 与 profile。
- 高开销观测（relation per-row、viz-trace、full field_compute）若默开，会污染墙钟与 RSS，导致「优化假象」或「变慢误判」。

目标：把 **低漂移自我观测**做成库的基础能力——证据正确、默认可选、影响大的观测必须警告。

## What Changes

- 引入版本化 **`scalim_run_stats/v1`**（结构化 dataclass SSOT；落盘默认 JSON；可选旁路给 viz）。
- **`WorkflowStatsAccumulator`（或等价）**：在每 demand `PIPELINE_END` 快照，产出 `nodes[]`，避免共享 observer reset 误判。
- **Profiles**：`baseline`（空）/ `bench`（lite 事件 + 可选 psutil）/ `bench_plus` / `debug`；`bench` 为开发推荐默认。
- **高影响观测警告**：启用 `relation_lookup` / `OPERATOR_SPAN` / viz-trace / 全量 batches 等时 MUST 发出明确 warning（含预估开销类别）。
- **Viz**：sibling `run_stats.json`（不嵌入 `viz_snapshot`）；可选 `meta.viz.run_stats` 路径引用。
- **文档**：如何读 stages/loaders/nodes、如何与 baseline 对拍、观测税声明。

非目标（本 change）：

- 不修 write stage 归因（见 `c55-stage-write-attribution`）。
- 不强制生产启用任何 observer。
- 不引入必选新 PyPI 依赖；psutil 保持可选，内存指标开启时 fail-fast（无静默回退）。

## Capabilities

### New Capabilities

- `observability-run-stats`：run_stats 契约、accumulator、profiles、警告、viz sibling 约定。

### Modified Capabilities

- `performance-observability`：澄清 workflow 多节点下 metrics 生命周期；指向 run_stats / nodes[]。
- `hooks-observability-structure`：可选补充「共享 observer + reset」文档约束（若不扩 MUST 则仅 design）。
- `observability-flow-visualization`：允许 sibling run_stats；MUST NOT 破坏现有 snapshot/events 文件名。

## Impact

- **兼容**：默认 `components=[]` 行为不变；新 API / profile 为 opt-in。
- **证据质量**：消除「末节点清空」类假零；为用户与框架优化提供同一套可读证据。
- **性能**：`bench` 目标墙钟税与 demo 同量级（约个位数百分比）；debug 保持显式 opt-in + 警告。

## Ethics

- `ethics.risk_level`: medium（观测契约影响用户判断）
- `ethics.prohibited_actions`: 默认开启高基数事件；静默吞掉 psutil 缺失；用末节点 reset 后的指标冒充全 workflow 结论；把观测税说成引擎加速
- `ethics.required_evidence`: obs-demo sampling_matrix；nodes[] 对拍；CSV 输出等价（有观测 vs baseline）
- `ethics.refusal_contract`: 无法证明低漂移时不得把 profile 标为「默认安全」
- `ethics.escalation_policy`: 若 bench 税在标准 mid shape 上持续 >10%，升级确认是否收紧默认采样

## Open Questions

1. run_stats 公共入口放在 `scalim.ob` 还是 `scalim.ob.presets.run_stats`？
2. `RelationObserver` 跨 pipeline：配置开关 `reset_on_pipeline_start=False` vs 仅靠外部 accumulator？
3. 测试 seam 确认见会话（写 tasks 前）。