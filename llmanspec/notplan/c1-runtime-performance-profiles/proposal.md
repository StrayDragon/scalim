## Status (2026-04-30)

> 一句话描述: 引入可解释的运行时性能档位（`memory`/`balanced`/`speed`），把零散性能开关收敛为统一 profile 以显式表达时间/内存/观测取舍。

- 本提案已从 `openspec/changes/` 移至 `openspec/notplan-changes/`，等待 `c0-execution-hotpath-fastpaths` 合入并通过真实基准验收后再评估是否需要推进。
- 若 `c0` 默认路径已能覆盖主要瓶颈，则 `c1` 不转正；仅当需要对“更激进/可选策略”（例如并行、缓存、materialize 等）做统一治理与上界裁剪时再进入正式变更流程。

## Why

在不同 workload 下，“更省内存”和“更省时间”往往互相拉扯；如果所有优化都固定写死在默认路径里，会导致：要么默认仍然偏慢，要么为了速度引入不可控内存波动。我们需要一个对用户可解释、对框架可治理的“性能档位”来显式表达取舍。

## What Changes

- 引入一个运行时可选的性能档位（profile），把零散的开关收敛为少量可解释的模式：
  - `memory`：以低峰值内存为第一目标（更少缓存/预构造；更严格的上下文/审计策略）。
  - `balanced`：默认档位；在不明显增加内存的前提下开启安全的 fastpaths。
  - `speed`：允许用一定内存或可观测性细节换取时间（可选启用更激进的缓存/并行/懒构造）。
- API 形态以“统一用户认知”为目标：
  - 对外提供单一的具名 profile（字符串/枚举语义），作为最推荐、最易交流的入口（默认 `balanced`）。
  - 同时为高级用户提供一个纯标准库的配置对象（dataclass）承载细粒度开关，并提供 `classmethod factory`（如 `balanced()` / `memory()` / `speed()`）作为文档示例初始化方式；该对象用于“写清楚我到底打开了哪些策略”，避免散落参数。
- 明确每个 profile 对语义/事件/guardrails 的承诺边界：默认保持语义不变；仅当用户主动选择更激进 profile 时才允许放宽某些“诊断细节”或“中间结构构造”策略。
- 将 `c0` 提供的合成复现入口作为 profile 对比的本地基线（无业务数据，临时文件）：
  - `.tmp/repro/scalim_hotpath_overhead/repro-execution-hotpath-overhead.py`

## Capabilities

### New Capabilities
- `runtime-performance-profiles`: 运行期可选的性能档位，用显式契约描述时间/内存/观测之间的取舍，并提供稳定的默认行为。

### Modified Capabilities
- `runtime-policy-normalization`: 允许把性能相关策略纳入统一的运行期 policy 归一化与校验（避免用户配置碎片化）。

## Impact

- 影响入口可能在 `ScalimEngine(...)`/workflow 入口与 guardrails/policy 组合处（具体实现落在 design/tasks）。
- 需要补充文档说明每个 profile 的适用场景与限制，并确保默认 profile 与历史版本兼容（语义不变）。
- 不引入任何新增第三方依赖；所有 profile/策略收敛均以纯 Python 标准库实现为前提（严格环境可用）。
