## Why

我们近期在 `validate_unique_field_names` 上再次遇到“修成 workaround”的典型症状：生命周期分层不够硬，导致 runtime-only policy 容易被 `compile/preload` 阶段“借道”提前消费；修复往往表现为“在某个调用点记得传 `False`”，可读性差、维护成本高，并且非常容易在未来的重构/新增入口中回归。

虽然我们已经落地了 workflow `preflight`（policy-aware 的最早边界），但当前代码组织仍然存在这些结构性风险：

- 同一语义在多个层重复实现（compile/preload、preflight、runtime compile），长期容易 drift；
- “阶段/边界”更多靠约定和 review，而不是由代码结构强约束开发者；
- loader/parser/validator 与 runtime-only diagnostics 的职责边界不够清晰，导致“配置解析”与“运行期诊断”混杂在同一个调用入口里。

我们希望做一次更激进的重构：用 **phase pipeline/builder** 让 workflow 生命周期“可读、可控、可迭代”，并把 demand 侧的解析与运行期诊断彻底解耦（parser-only），从架构层面降低未来再出现 workaround 的概率。

## What Changes

- 引入一个显式的 workflow lifecycle `pipeline`（阶段对象/结果对象链式推进），将 `run_workflow(...)` 的关键阶段变成一等公民：
  - `parse`（workflow YAML）
  - `compile/preload`（结构预加载，仅结构信息）
  - `merge effective options`（形成 per-run effective `RunOptions`）
  - `preflight`（runtime-only 但可推理的 diagnostics；fail-fast + 直接 raise）
  - `execute`（engine 调度/运行；包含 lazy runtime compile）
- 需求侧(`demand`)解析改为 **parser-only**：
  - **BREAKING**：移除/禁止任何“依赖 runtime policy 的语义校验”在 parser/loader 中发生（例如 `validate_unique_field_names` 这类 runtime-only diagnostics）
  - runtime-only diagnostics 统一由 diagnostics runner 在 `preflight` 或 `runtime compile` 边界执行
- 语义收敛：
  - effective outputs/resources 的计算与“是否触发某个 inferable check”的判定逻辑收敛为单一 SSOT helper，供 preflight/runtime compile 复用，减少 drift
- 代码组织整体更强调“阶段边界不可误用”：
  - 早期阶段对象不暴露后期阶段方法，降低“在错误阶段顺手加逻辑”的概率
  - 通过模块依赖方向与最小上下文对象，减少 compile/preload 触达 runtime policy 的机会

## Capabilities

### New Capabilities
- `yaml-dsl-workflow-lifecycle-pipeline`: 定义 workflow/demand 的阶段化生命周期模型（phase pipeline），以及各阶段允许/禁止的动作边界（尤其是 runtime-only diagnostics 的最早生效边界）。

### Modified Capabilities
- `yaml-dsl-workflow`: 将 workflow lifecycle 的阶段化实现与 `preflight` 失败语义（独立于 `failure_policy`）固化为长期可维护的结构约束。
- `yaml-dsl-runtime-policy-boundary`: 强化 runtime-only policy 的边界治理：parser/compile-preload 不得消费 runtime-only diagnostics；policy-aware 边界由 effective merge + preflight/runtime compile 承担。
- `workflow-preflight-runtime-only-diagnostics`: preflight 从“功能点实现”提升为生命周期 pipeline 的稳定阶段，并约束其 check 的可推理子集原则。

## Impact

- 影响面主要在 `src/scalim/dsl/by_yaml/` 的 workflow 与 runtime compile 组织：
  - `workflow_entrypoints.py` 将被重构为“阶段对象串联”的可读实现（而非长函数堆叠）
  - `workflow_compile.py` 将更明确为 structural preload（不触达 runtime-only diagnostics）
  - demand 解析相关模块将拆分为 parser 与 diagnostics/compile 两条链路
- 测试会有较大重排（但目标是更清晰的分层覆盖），并且允许破坏性重构升级仓内旧写法（不做兼容分支）。

