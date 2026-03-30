## Why

随着 Scalim 的 execution/workflow/YAML DSL 能力增长,核心链路出现明显“维护性熵增”信号:

- 少数热点模块承担过多职责,导致改动半径大、review 困难、跨层耦合加深(例如 workflow/execute 与 execution/run_ir 的编排聚合)。
- 编译期产物与运行期需求出现“语义回流”(runtime 反向改写 compilation request),使边界难以推理、测试难以隔离。
- 关键运行期开关在不同执行路径下存在漂移风险(例如 adaptive worker 子 runtime 未继承 run-level 配置),在并发与诊断场景下容易形成隐性行为差异。

需要把这些问题收敛为可回归的小步重构:先建立清晰的 contracts/ports 与状态容器边界,再逐步拆分热点模块,以降低后续演进成本。

## What Changes

- workflow runtime 降熵:
  - 引入统一的可见性索引(VisibilityIndex),作为 ctx/artifacts/cache_pool 等“可见性闭包规则”的单一 SSOT,避免重复实现导致的语义漂移。
  - 将 workflow 对 demand compilation 的“运行期回写”改为显式 request overrides 合成:编译产物保持纯编译结果,运行期注入通过独立对象表达。
- execution runtime 降熵:
  - 明确 execution 的 contracts 与 orchestration 的边界:允许将 `ExecutionRequest/ExecutionResult` 等 DSL-agnostic 契约抽离到独立模块,并保持 `run_ir` 稳定入口。
  - 修复 adaptive worker 子 runtime 的关键 run-level 配置继承,保证 `seq` 与 `adaptive` 在同一 run-level 配置下语义一致(尤其是 `key_normalization`,以及 fallback logger 等诊断开关口径)。
- typed intermediate store 边界收敛:
  - 将 workflow 中间态 `InMemoryRows` 的契约导入路径从 `_internal` 泄漏中收敛到稳定入口 `scalim.sinks.rows`(避免跨层绑定内部实现路径),并保持现有行为与值域约束不变。

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `workflow-runtime-module-organization`: workflow runtime 的职责拆分与可见性规则 SSOT 化,保持稳定入口不变。
- `execution-structure`: execution contracts 与 orchestration 可拆分但稳定入口保持,并强化 DSL-agnostic 边界。
- `parallel-execution`: adaptive 的 worker 子运行时必须继承 run-level 配置,避免并发路径语义漂移。
- `key-normalization`: key normalization 口径在 adaptive worker 路径必须与主运行时一致。
- `workflow-intermediate-store`: typed rows artifact (`InMemoryRows`) 的稳定导入路径与跨层边界治理。

## Impact

- 受影响代码(SSOT):
  - workflow: `src/scalim/workflow/execute.py`、`src/scalim/workflow/ctx.py`、`src/scalim/workflow/loaders.py`
  - execution: `src/scalim/execution/run_ir.py`、`src/scalim/execution/adaptive/_internal/loadref_scheduler_execution.py`
  - sinks/workflow intermediate store: 当前 `InMemoryRows` 的稳定入口与引用点
- 受影响测试: workflow 可见性/ctx refs/数据流注入,adaptive 与 key_normalization 一致性回归,以及 contracts 拆分后的导入/行为等价回归。
- 受影响 specs:
  - SSOT 为 `openspec/specs/<capability>/spec.md`
  - 本 change 的增量规范写入 `openspec/changes/c0-reduce-runtime-entropy/specs/<capability>/spec.md`
  - 提交前运行 `just openspec-check` 做 sanitize + 结构校验。
