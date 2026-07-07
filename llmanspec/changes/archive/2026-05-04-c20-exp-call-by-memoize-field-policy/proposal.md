## Why

当派生字段(`call_by`)数量很多且单个字段逻辑较薄时，逐行 Python 调用与依赖读取的固定开销会成为主要瓶颈。对 `ctx-free call_by`（不依赖 `$ctx`）而言，依赖元组在真实业务中常出现“高重复、低基数”的特征，具备通过 LRU 记忆化显著降耗的潜力。

但不同字段的依赖基数差异很大：对高基数字段启用缓存会带来明显的内存开销，甚至变慢。因此需要一个严谨、可控且易用的“字段选择策略”，让用户在不改业务代码的前提下，只对明确受益的字段启用缓存，并能稳定在线评估 ROI。

## What Changes

- 提供实验性配置：允许用户按字段名选择哪些 `ctx-free call_by` 参与 LRU 记忆化、哪些强制不参与（allow/deny filter）。
- 为上述策略提供实验性日志开关：将 `hit/miss/unique/evict/disabled` 等聚合指标输出到 `scalim.performance`，方便仅靠线上日志做投入产出比判断。
- 所有能力均以 `SCALIM_EXP_` 前缀的实验性环境变量提供，默认关闭；不引入任何第三方依赖，运行时保持 Python 3.6 兼容。

## Capabilities

### New Capabilities

- `execution-call-by-memoization`: 为 `ctx-free call_by` 提供可控的 LRU 记忆化与字段级过滤策略（实验性，默认关闭）。

### Modified Capabilities

<!-- 无 -->

## Impact

- 执行层热路径：`execution/executor/operators/compute`（`call_by` 路径）将引入可选缓存与字段过滤判断；需要确保对 `seq`/`adaptive` 模式行为一致且内存有硬上限。
- 可观测性：`scalim.performance` 将新增（可选）聚合统计日志；需要确保不泄露依赖值与业务数据，仅输出计数与命中率等指标。
- 配置治理：需要在项目常量与文档中明确实验性开关的命名、默认值与行为边界（`SCALIM_EXP_` 前缀；后续稳定化再迁移到非 EXP 前缀）。

