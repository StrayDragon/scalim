## Context

当前核心链路采用清晰分层(`YAML DSL → IR → planning → execution`)并叠加 workflow DAG 作为上层编排.随着特性增长,少数“上帝模块”开始聚合过多职责,并出现编译期/运行期边界被反向改写的现象,使得:

- 变更半径扩大:任何新增能力都更容易落入同一文件,导致 review 与回归难度上升。
- 边界难以推理:workflow runtime 在运行期回写 DSL compilation 产物(`request`),形成语义回流。
- 并发路径行为易漂移:adaptive fan-out/fan-in 会创建 per-task 子 runtime,若未继承 run-level 配置会导致 `seq` 与 `adaptive` 结果/诊断不一致。

约束:
- 核心运行时必须兼容 Python 3.6:不使用新语法(`X | Y`/`list[T]`/future annotations),类型扩展仅通过 `vendor/compact/typing_extensionsx.py`。
- 运行期契约依赖显式 contracts:不要用 `if TYPE_CHECKING:` 伪造接口;跨 mixin 依赖用 `ABC + @abstractmethod` 表达。
- 以“可回归的小步拆分”推进,优先通过 characterization tests 锁定行为,避免停机重写。

本变更不引入新的提交前入口/commit hook;仅聚焦 runtime seams 与热点模块降熵。

## Goals / Non-Goals

**Goals:**
- 建立 workflow 可见性规则的单一 SSOT(VisibilityIndex),并在 ctx/artifacts 等处复用。
- 消除 workflow 对 compilation 产物的运行期回写:通过显式 overrides 合成 request,保持 compilation 为纯编译结果。
- 修复 adaptive per-task 子 runtime 的关键配置继承,保证 `key_normalization` 在 `seq` 与 `adaptive` 下语义一致。
- 为 typed intermediate store 提供稳定公开导入路径,避免跨层依赖 `_internal` 实现路径。
- 允许将 execution contracts 从 orchestration 拆分,降低热点模块聚合度,并保持稳定入口不变。

**Non-Goals:**
- 不在本变更中完成所有热点模块的彻底拆分(例如 `workflow/execute.py` 的全量拆包);本轮只做“铺 seam + 止血 + 回归网”。
- 不调整 YAML DSL authoring surface,不引入新的 DSL 语法或对外 API 行为变更(除 bug 修复导致的行为一致化)。
- 不变更可观测性事件类型/顺序(仅在保证等价的前提下重构实现)。

## Decisions

### 1) VisibilityIndex 作为可见性闭包 SSOT
**Decision:** 引入一个纯计算/纯数据对象 `WorkflowVisibilityIndex`,输入为 workflow nodes 的 `deps`,输出为 `visible_producer_node_ids(consumer_node_id) -> FrozenSet[str]`.

**Why:** 当前 ctx 与 artifacts 各自维护闭包算法,未来非常容易出现“一个允许传递可见、另一个不允许”的漂移.集中 SSOT 能降低维护面并便于测试.

**Alternatives considered:**
- 继续在各模块复制闭包逻辑:实现快,但长期漂移几乎不可避免。
- 在运行期按需 DFS/BFS 计算:实现简单但容易被误用为热路径;且重复计算不利于可控性。

### 2) 编译产物不可变:用显式 request overrides 合成
**Decision:** workflow runtime 将“运行期注入”(例如 `main_rows`/`capture_in_memory_rows`/per-node viz_config)表达为独立的 overrides 对象,并通过纯函数合成 `ExecutionRequest`,而不是 `replace(compilation, request=...)` 回写 compilation.

**Why:** compilation 属于编译期产物(DSL adapter 的职责),运行期回写会把边界变成隐式协商,导致类型/行为难推理.显式 overrides 也更利于基于 LBYL 的参数校验与错误路径定位.

**Alternatives considered:**
- 保持现状:依赖 compilation 是 dataclass 且允许 replace,但会持续放大耦合与语义回流。
- 将注入逻辑下沉到 DSL compilation 阶段:会让 DSL adapter 反向依赖 workflow runtime 的运行期决策,违反分层。

### 3) adaptive per-task 子 runtime 必须继承 run-level 配置(`key_normalization` + 诊断开关)
**Decision:** 在 adaptive scheduler 创建 per-task `ExecutionRuntime` 时:

- MUST 显式传入父 runtime 的 `key_normalization`(不依赖默认值)。
- MUST 从父 runtime 派生 `HookManager`/`ObserverManager` 的 capture manager(而不是新建默认 manager),以确保 `fallback_logger_enabled`/debugging/loader result 策略等诊断开关在 `seq` 与 `adaptive` 下语义等价。

**Why:** `key_normalization` 影响 lookup 命中与诊断,属于 run-level 配置.子 runtime 回退默认值会造成 `seq` 与 `adaptive` 的结果差异,属于不可接受的语义漂移。与此同时,诊断开关与事件元信息(run_id 等)若在 per-task runtime 漂移,会让 adaptive 路径出现“看起来没开诊断/行为不同”的隐性差异,同样不可接受。

**Alternatives considered:**
- 让子 runtime 读取全局/模块级配置:隐式且不可测试,违反显式契约。
- 在 normalize/emit 函数里额外读取父 runtime:仍然隐式耦合,且容易遗漏其它需要继承的配置项。
- 为子 runtime 新建 `HookManager`/`ObserverManager` 默认实例:实现快但会导致 fallback logger/诊断开关漂移,并破坏 capture+replay 的可推理性。

### 4) typed artifact (`InMemoryRows`) 公开入口收敛到稳定 facade 子模块
**Decision:** 为 `InMemoryRows` 提供稳定公开导入路径 `scalim.sinks.rows`,并替换 workflow/execution 对 `sinks._internal.*` 的直接依赖.

同时 `scalim.sinks.rows` SHOULD 作为一组“成熟可用”的稳定入口,导出 `InMemoryRows` 的必要配套类型/工具(例如 `InMemoryRowsSink`/`in_memory_rows_to_in_memory_csv`/`iter_in_memory_rows_as_main_rows`)。

**Why:** `_internal` 模块不作为契约,跨层依赖会把内部实现路径固化为事实 API,放大未来重构成本.另外,此前已做过 `scalim.sinks` 包根导出面收敛,本变更选择稳定子模块而不是把符号放回包根,以避免 public surface 反复膨胀。

**Alternatives considered:**
- 继续使用 `_internal` 导入:短期最省,长期会反噬(与 module-organization/specs 目标冲突)。
- 将稳定入口放回 `scalim.sinks` 包根:迁移成本更低但会扩大包根导出面,与既有收敛方向冲突。
- 将类型挪到 workflow 包:execution 也需要该类型,会导致 execution 依赖 workflow,破坏分层。

### 5) execution contracts 与 orchestration 可拆分但保持稳定入口
**Decision:** 允许把 `ExecutionRequest/ExecutionResult` 等 contracts 抽到独立模块,并在 `execution/run_ir.py` 保持稳定 re-export 与行为入口.

**Why:** contracts 是跨层共享契约,应尽量纯净(无副作用/少依赖);orchestration 则负责装配 sinks/hooks/observers 与异常语义.拆分能降低耦合并提升可测试性.

**Alternatives considered:**
- 保持单文件:继续累积熵与导入面,进一步加剧改动半径。

## Risks / Trade-offs

- [回归风险] 重构 workflow 编排与 request 合成可能影响边界行为 → 缓解:先补 characterization tests(可见性/ctx refs/main_rows 注入/capture+release)再改实现。
- [并发风险] adaptive worker runtime 继承配置可能暴露此前隐藏的行为差异 → 缓解:以 spec 为准统一 `seq`/`adaptive` 语义,并新增针对 `key_normalization` 的回归用例。
- [API surface 风险] 导出 `InMemoryRows` 可能扩大 public surface → 缓解:通过显式 `__all__` 与 public api manifest 门禁控制导出,并在 spec 中限定其语义/值域。

## Migration Plan

1) Tests-first:
   - 为 `parallel_mode=adaptive` + `key_normalization` 添加回归测试(确保命中/诊断与 `seq` 等价)。
   - 为 workflow 可见性闭包与 ctx refs 校验添加单测(覆盖传递可见与不可见报错 path)。
2) Fix + seam:
   - 修复 adaptive per-task runtime 继承 `key_normalization`。
   - 引入 `WorkflowVisibilityIndex` 并让 ctx/artifacts 复用。
3) Boundary cleanup:
   - 引入 workflow request overrides 合成,替换 compilation 回写。
   - 提供 `InMemoryRows` 稳定导入路径并替换引用点。
4) Hotspot split (small step):
   - 抽离 execution contracts,保持 `run_ir` 稳定入口不变。
5) Verification:
   - `just quick-qa-only-py` 或 `just qa` 做全量回归。
   - `just openspec-check` 确保工件可归档/可发布。

<!-- Open Questions resolved in Decisions 3/4 -->
