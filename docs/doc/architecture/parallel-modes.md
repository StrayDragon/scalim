# 执行并行模式: `seq` 与 `adaptive`

??? note "适用读者"
    - 需要选择/调优并行模式的使用方开发者
    - 需要排查 `LoadRef` 调度行为的项目贡献者

这两个模式的区别只影响一件事:

- 批次内 `LoadRef(keys)` 怎么跑

其他部分依然是顺序批处理: 一个批次跑完再跑下一个;算子仍按计划顺序推进.

??? note "维护提示"
    本页内容通常会在以下变更后需要同步检查:

    - `LoadRef` 分层/去重/提交点的语义调整
    - `bind.use_rows` 的 barrier 判定逻辑变更
    - `max_workers` 的解析策略与池创建条件调整
    - `adaptive` backend 的选择/回退策略调整(`thread`/`process`/`async`)
    - `process` 后端的兼容性检查与失败策略(reason / fail_fast / fallback_to_serial)调整
    - hook/observer 的捕获与回放边界调整(影响确定性与可观测性)

## 1. `seq`: 顺序执行

`seq` 是默认模式,可预测、方便排查.

### 1.1 一图看懂: 一个批次怎么执行

```mermaid
flowchart TD
  A[准备 BatchContext] --> B[按计划执行 operators]
  B --> C[Load]
  B --> D[LoadRef]
  B --> E[Compute / Write / Release]

  D --> S[LoadRef 按算子顺序串行执行]
```

### 1.2 批次内“关联复用”(同 relation 只跑一次)

在同一个批次内,如果多个字段共享同一条 relation(同一份 relation signature),框架会尽量复用:

```mermaid
flowchart LR
  O1[LoadRef: field_a] --> F[填充同组字段<br/>field_a / field_b / ...]
  O2[LoadRef: field_b] --> SKIP[同 relation 已执行<br/>跳过/复用]
```

这能减少重复 loader 调用,也让同一条 relation 的“提交点”更清晰.

适合的场景:

- 需要可预测的逐步执行、便于断点/日志定位
- `bind.use_rows` 较多(见下文的 barrier)
- 并发会放大外部系统压力,需要更保守的节奏

## 2. `adaptive`: 批次内 `LoadRef(keys)` 自适应并发

### 2.1 一图看懂: 并行范围

`adaptive` 的并发范围很窄,只覆盖**批次内的 `LoadRef` 段**,其它算子仍是串行.

```mermaid
flowchart TD
  subgraph P[每个批次的执行主干]
    A[按计划执行 operators] --> B[LoadRef 段]
    B --> C[其它算子<br/>Load / Compute / Write / Release]
  end

  subgraph M1[parallel_mode = seq]
    B --> S[LoadRef 串行执行]
  end

  subgraph M2[parallel_mode = adaptive]
    B --> Q{adaptive_pool 已创建?}
    Q -->|否| S
    Q -->|是| X[自适应调度<br/>分层 → fan-out → fan-in]
  end
```

要点:

- 批次之间仍然不并发
- `adaptive_pool` 没创建出来(或并发数解析后 <= 1)时,行为会退化成 `seq`

### 2.2 为什么是 “fan-out / fan-in”

自适应调度器把一个 `LoadRef` 段拆成多层(layer),每层是一组“在依赖上可以并行”的关联任务.

- fan-out: 同一层里的任务并发提交到执行池
- fan-in: 任务完成后,在提交点把结果归并到主 `BatchContext`,再进入下一层

下面是调度决策的主流程(只画关键分支):

```mermaid
flowchart TD
  IN[LoadRef 段 ops] --> LAYERS[按依赖拆 layer]

  LAYERS --> L1[处理一层]
  L1 --> DEDUP[按 relation 去重<br/>构造 tasks]

  DEDUP --> BARRIER{含 use_rows 绑定?}
  BARRIER -->|是| SERIAL1[本层串行执行<br/>保持语义边界]
  BARRIER -->|否| POOL{pool 可用且 worker>1?}

  POOL -->|否| SERIAL2["本层串行执行<br/>(退化为 seq)"]
  POOL -->|是| THRESH{阈值允许并行?}

  THRESH -->|否| SERIAL3["本层串行执行<br/>(工作量太小)"]
  THRESH -->|是| FANOUT[fan-out<br/>并发提交 tasks]
  FANOUT --> COLLECT[等待结果]
  COLLECT --> FANIN[fan-in<br/>提交点归并 overlay<br/>回放事件]

  SERIAL1 --> NEXT[下一层]
  SERIAL2 --> NEXT
  SERIAL3 --> NEXT
  FANIN --> NEXT
```

### 2.3 adaptive backend: `thread` / `process` / `async`

`adaptive` 模式除了“每层是否并行”之外,还有一个更底层的选择: **并发任务跑在什么后端上**.

这里的 backend 只影响一件事:

- 当某一层决定并行时,`LoadRef` 任务是提交到线程池、进程池,还是提交到一个托管事件循环的执行器

backend 的选择由 `AdaptivePolicy.choose_backend(...)` 决定;默认策略固定返回 `thread`.

#### 2.3.1 backend 选择 + 池创建(含回退)

```mermaid
flowchart TD
  START["parallel_mode = adaptive ?"] -->|否| NOP["不创建 adaptive_pool<br/>LoadRef 按 seq 行为执行"]
  START -->|是| WORKERS["解析 max_workers<br/>(resolved_workers)"]
  WORKERS -->|"resolved_workers <= 1"| NOP
  WORKERS -->|"resolved_workers > 1"| PICK["policy.choose_backend()<br/>→ backend"]

  PICK --> ASYNCQ{"backend == async ?"}
  ASYNCQ -->|否| SETRT["runtime.adaptive_backend = backend"]
  ASYNCQ -->|是| PYQ{"Python < 3.7 ?"}
  PYQ -->|是| WARN["warn 一次<br/>backend 回退为 thread"]
  PYQ -->|否| SETRT
  WARN --> SETRT

  SETRT --> PROCQ{"backend == process ?"}
  PROCQ -->|是| SETPM["runtime.adaptive_process_failure_mode<br/>= choose_process_failure_mode()"]
  PROCQ -->|否| EXEC
  SETPM --> EXEC["创建 adaptive_pool(Executor)"]

  EXEC --> MAP{"backend"}
  MAP -->|"thread"| T["ThreadPoolExecutor<br/>(overrides.adaptive_executor_cls)"]
  MAP -->|"process"| P["ProcessPoolExecutor<br/>(overrides.adaptive_process_executor_cls)"]
  MAP -->|"async"| A["ThreadLoopExecutor<br/>(overrides.adaptive_async_executor_cls)"]
```

说明:

- 如果池没创建出来(例如 `resolved_workers <= 1`),`adaptive` 会在运行时退化成 `seq` 行为.
- `async` backend 在 Python 3.6 上会直接回退为 `thread`(并发能力仍来自线程池).

#### 2.3.2 scheduler 侧 backend 取值

调度器在执行 `LoadRef` 段时,会优先使用 `runtime.adaptive_backend`;若为空才会再次调用策略的 `choose_backend(...)`.

这保证了: **只要池创建阶段已经确定了 backend,后续调度不会“每段变一次”**.

#### 2.3.3 三种 backend 的语义差异(按当前实现)

- `thread`(默认)
    - 任务在同一进程内并发执行.
    - 每个任务使用独立的 `ExecutionRuntime(parallel_mode="seq")`,并通过捕获管理器收集 hook/observer 事件,在提交点统一回放.
    - 对任务函数/上下文没有 pickling 要求.
- `process`(实验性)
    - 任务会被提交到 `ProcessPoolExecutor`.
    - **不兼容 hooks/observers**: 只要运行时注册了 hook 或 observer,就不会进入进程并发.
    - **要求可 pickling**: 共享上下文与每个任务的关键对象必须可序列化,否则无法提交到子进程.
    - 子进程内会创建新的 `ExecutionRuntime(parallel_mode="seq")`,并使用空的 Hook/Observer 管理器: hook/observer 不会跨进程执行,也不会回放事件.
- `async`(实验性)
    - 任务提交到 `ThreadLoopExecutor`(独立线程托管事件循环).
    - 若提交的任务返回 coroutine,执行器会在该事件循环上 `await`.
    - 若返回非 coroutine,会在 loop 线程直接执行并 warning 一次(可能阻塞事件循环).
    - **当前自适应调度器提交的是同步任务**,因此启用 `async` backend 会触发该 warning,并不会自动获得 `asyncio` 的并发收益.

### 2.4 `process` backend 的回退/失败策略(按当前实现)

`process` backend 有两类“硬性边界”,会导致这一层直接按串行执行(或直接抛错):

1. **hooks/observers 不兼容**
2. **对象无法 pickling**

失败策略由 `choose_process_failure_mode(...)` 决定:

- `fail_fast`(默认): 直接抛错中止
- `fallback_to_serial`: 回退到本层串行执行,继续跑后续层

```mermaid
flowchart TD
  IN["本层准备并行<br/>(backend=process)"] --> MODE["failure_mode = choose_process_failure_mode()"]
  MODE --> HOOKQ{"hooks/observers 已注册 ?"}
  HOOKQ -->|是| FAILHOOK["reason = process_backend_incompatible_hooks"]
  FAILHOOK -->|fail_fast| ERR1["抛 ValueError"]
  FAILHOOK -->|fallback_to_serial| SERIAL1["本层串行执行"]

  HOOKQ -->|否| PKQ{"共享上下文 + 任务可 pickling ?"}
  PKQ -->|否| FAILPK["reason = process_backend_unpicklable_task"]
  FAILPK -->|fail_fast| ERR2["抛 TypeError"]
  FAILPK -->|fallback_to_serial| SERIAL2["本层串行执行"]

  PKQ -->|是| SUBMIT["提交到 ProcessPoolExecutor<br/>_run_task_in_process(...)"]
  SUBMIT --> DONE["并发执行并收集 overlay<br/>(无 hook/observer 事件)"]
```

### 2.5 fan-out / fan-in 的“结果归并 + 事件回放”

每个并发任务不会直接往主 `BatchContext` 写数据,而是写到自己的 overlay,任务完成后再统一提交.

```mermaid
sequenceDiagram
  participant BE as BatchExecutor
  participant SCH as AdaptiveScheduler
  participant POOL as ExecutorPool
  participant T as LoadRefTask(OverlayContext)
  participant CTX as BatchContext

  BE->>SCH: execute LoadRef segment
  SCH->>SCH: 分层 + task 去重

  loop 每层
    SCH->>POOL: submit(task1/task2/...)
    alt backend = thread/async
      POOL-->>T: run LoadRef (task runtime + capture)
      T-->>POOL: 返回 overlay + 捕获的事件
      POOL-->>SCH: 收集所有 task 结果
      SCH->>CTX: fan-in 提交 overlay(按算子顺序)
      SCH->>SCH: 回放 hook/observer 事件
    else backend = process
      POOL-->>T: run LoadRef (child process runtime)
      T-->>POOL: 仅返回 overlay
      POOL-->>SCH: 收集所有 task 结果
      SCH->>CTX: fan-in 提交 overlay(按算子顺序)
    end
  end
```

说明:

- 任务内仍是串行执行 `LoadRef`(只是多个 relation 并发跑)
- 提交点会把 overlay 归并回主上下文,并把捕获的事件集中回放
- `process` 后端不会捕获/回放 hook/observer 事件(且在 hooks/observers 存在时可能回退或失败)

### 2.6 barrier: 遇到 `bind.use_rows` 会强制串行

调度器会把 `bind.use_rows` 视为层级屏障(barrier),直接把这一层按串行执行:

```mermaid
flowchart LR
  A[本层 tasks] --> B{含 use_rows?}
  B -->|是| C[强制串行<br/>不进入 pool]
  B -->|否| D["可并行(视阈值)"]
```

这也是为什么 `adaptive` 主要针对 `LoadRef(keys)`——它依赖 `keys` 绑定来维持“批次内可并行”的语义边界.

## 3. 如何开启与基础调参

### 3.1 YAML DSL 入口

YAML 文件本身不声明 `parallel_mode`. 需要在调用 YAML 运行入口时传入:

- `parallel_mode="adaptive"`
- `max_workers=0`(自动)或指定一个正整数上限

相关背景与运行入口参数说明见: [YAML DSL 使用指南](../yaml-dsl/user-guide.md)

### 3.2 IR / Engine 入口

如果你不是从 YAML DSL 入口执行,也可以在 Engine/IR 入口传入同名参数(`parallel_mode` / `max_workers`).

### 3.3 `max_workers` 的语义

`max_workers` 是一个“并发上限提示”:

- `0`/负数: 自动,按 CPU 等信息解析出上限,并保证 `>= 1`
- 解析后 `<= 1`: 不会创建池,`adaptive` 会退化成 `seq` 行为(仍走同一条串行路径)

## 4. 深度调参(需要 Python/IR 注入)

如果你要调的不是“并发上限”,而是“每层是否并行 / 资源池怎么分 / 用哪种后端”,需要走 `PipelineOverrides`.

可调项一览:

- `PipelineOverrides`
  - `adaptive_min_parallel_tasks`: 每层最小并行任务数阈值(默认 2)
  - `adaptive_tuning`: `AdaptiveTuning`(池/阈值/全局上限等)
  - `adaptive_policy`: `AdaptivePolicy`(决策/后端/池选择)

重要约束:

- `AdaptiveTuning` 刻意不进入 YAML DSL: 只能通过 Python/IR 入口(例如 `ScalimEngine(pipeline_overrides=...)`)注入.

## 5. 不同场景的选择建议(按当前实现)

这些建议只基于当前实现的语义边界,不承诺任何具体性能提升:

- 优先 `seq`
    - 你在排查数据问题/关联链路,希望执行路径尽量直观
    - 你的关联大量使用 `bind.use_rows`(调度会频繁触发 barrier,最终还是串行)
    - 你需要严格控制外部系统的并发压力

- 尝试 `adaptive`
    - 批次内存在较多相互独立的 `LoadRef(keys)` 任务
    - loader 主要是 I/O 等待(HTTP/DB/远程服务),并发能隐藏等待时间
    - 你能接受并发带来的外部压力,并愿意用 `max_workers` 做上限

- backend 选择(只在 `adaptive` 下生效)
    - 默认 `thread`: 最少限制,也是默认策略的唯一选择
    - `process`: 需要接受“hooks/observers 不可用 + 必须可 pickling + 可能 fail_fast”的边界
    - `async`: 当前调度器提交的是同步任务,启用后会触发 warning;除非你明确需要该实验执行器的语义,否则建议保持 `thread`

## 6. 如何观察调度决策(排查用)

自适应调度器可按需发出决策事件,用于解释为什么某一层串行/并行.

事件里会带:

- `decision`: `serial` / `parallel`
- `backend`: `thread` / `process` / `async`
- `reason`: 串行原因(例如 `rows_binding_barrier` / `single_worker` / `below_min_parallel_tasks`)
- 可选的 pool 等待统计(开启该事件订阅后才会收集)

## 下一步

- [可视化工具](../viz/scalim-viz.md)
- [基准测试](../benchmark/index.md)
