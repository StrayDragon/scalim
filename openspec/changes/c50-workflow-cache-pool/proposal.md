## Why

当前 workflow 只有一个开关 `options.share_preload_cache: bool` 用于“跨 runs 共享 `cache_mode: preload_forever` 的预加载缓存”。该设计过于窄化,把以下多个维度揉成了一个二元开关:

- **共享范围**: 哪些 source 该共享? 共享到 workflow 末尾还是“用完即释放”?
- **一致性/冲突策略**: 当不同 run 的 preload 规格不一致时是 fail-fast、warn,还是隔离为不同缓存项?
- **内存策略**: 缓存容量与生命周期如何控制(尤其是宽表/大维表,或未来 dataset/index 工件)?

随着 `c10-workflow-ir-roadmap` 推进 workflow IR + DAG/compile-on-ready,现有 `share_preload_cache` 的强假设会逐渐不成立:
- 当前实现要求“执行任一 run 前先编译全部 runs 并做全量 preload 规格冲突预检查”,但 DAG/ctx 注入会让部分 signature 在启动时不可得。
- 共享缓存的生命周期当前近似“整场 workflow 常驻”,无法在无引用后释放,对大规模 workflow 不友好。

因此需要一个更通用的 **workflow-scope cache pool** 抽象: 既能覆盖现有的 preload 复用,又能为未来 dataset/index/工件复用提供一致的生命周期与内存治理。

## What Changes

> 本 change 仅提出方向与边界,不在 proposal 阶段锁死 YAML 语法细节；workflow YAML 作为 frontend,最终应编译到 workflow IR 上的 cache pool 配置。

- **New**: workflow-scope cache pool (缓存池)概念
  - workflow runtime 维护一个 cache pool,作为跨节点/跨 run 的共享缓存容器
  - cache pool 负责:
    - 缓存条目的 key/signature 计算(避免复用错误数据)
    - 生命周期管理(引用计数/释放时机)
    - 容量与内存策略(预算/淘汰/观测)

- **New**: 缓存条目 signature 与冲突策略
  - 对 preload_forever 等缓存条目,系统 MUST 以“可复现的 signature”作为缓存 key 的一部分(例如: `source_id + loader_ref + rendered_params + normalize + loader_call_context`)
  - 提供可配置的冲突策略(提案级方向):
    - `error`(默认/严格): 与当前行为一致,发现同 `source_id` 不同 signature 则 fail-fast
    - `separate`: 允许同 `source_id` 存在多个 signature,互不复用(适合渐进迁移/避免误伤)
    - `warn`: 继续执行但记录可观测告警(仅用于 debug/迁移窗口)

- **New**: 生命周期与“无引用自动释放”
  - cache pool SHOULD 支持基于 workflow DAG 的引用计数:
    - 当某个缓存条目被某个 run 获取时计数 +1
    - 当该 run 结束且其后续不再需要该条目时计数 -1
    - 计数归零后,缓存条目可被释放(或进入 LRU 等待淘汰)
  - 提供 `pin`/`release_policy` 等策略控制(例如固定到 workflow 结束,或按 refcount 释放)

- **New**: 容量/内存策略(guardrails)
  - cache pool SHOULD 支持预算配置(例如 `max_entries`/`max_bytes`/`max_value_bytes`)
  - 当预算超限时,系统 MUST 有明确策略:
    - fail-fast(严格护栏),或
    - 淘汰(例如 LRU,且仅淘汰 refcount=0 的条目)

- **BREAKING (planned)**: `options.share_preload_cache` 演进为 `options.cache_pool`(或等价 IR 字段)
  - 旧字段会被移除,并在仓内一次性升级 workflow YAML(不保留兼容兜底)
  - `share_preload_cache=true` 的能力由 cache pool 的默认配置覆盖(例如 preload compartment 开启共享 + 严格冲突策略)

- **Non-goals (for this change)**:
  - 不引入跨进程/跨机器的分布式缓存
  - 不在本 change 内落地 dataset/rows 工件复用(由 `c60-workflow-artifact-datasets` 负责),但 cache pool 将作为其内存治理底座

## Capabilities

### New Capabilities
- `workflow-cache-pool`: 定义 workflow-scope cache pool 的配置、signature/冲突策略、生命周期(引用计数/释放)与内存预算/淘汰/可观测性

### Modified Capabilities
- `yaml-dsl-workflow`: 将 `options.share_preload_cache` 升级为更通用的 cache pool 配置入口,并更新“冲突预检查/确定性/错误诊断”的规范边界

## Impact

- YAML authoring:
  - workflow YAML 将从单一 bool 开关演进为结构化的 cache pool 配置(并提供明确的迁移路径)
  - demand YAML 尽量不引入新概念: preload/cache 仍由 demand 侧 `cache_mode` 等声明驱动,workflow 只提供缓存治理

- Runtime/code:
  - 新增 workflow-scope cache pool 运行时模块,并改造 `run_workflow()` 的共享缓存传递方式(从“单一 PreloadCache”升级为“池化 + 生命周期/预算/观测”)
  - 预加载冲突校验将从“启动前一次性全量预检”演进为可配置策略(严格 fail-fast / warn / signature separate),并适配 DAG/compile-on-ready

- Schema/Docs (SSOT / generated):
  - SSOT:
    - workflow schema DSL 与 hover 文案: `src/scalim/dsl/by_yaml/schema_dsl/**`
    - workflow runtime 行为: `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`
  - Generated (禁止手改):
    - `src/scalim/dsl/by_yaml/schema/workflow.gen.json` (由 `scripts/gen-yaml-dsl-schema.py`/`just gen-yaml-dsl-schema`)
    - docs 中的 `.gen.` 与 injected blocks (由 `just gen-docs`)
