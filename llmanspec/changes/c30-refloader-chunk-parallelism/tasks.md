# Tasks: c30-refloader-chunk-parallelism

> 规划壳；已 `change start`（`sdd/c30-refloader-chunk-parallelism`）。决策收口见 `design.md`。

## 已决议（Apply 前钉死）

| ID | 决议 |
|----|------|
| Q1 | 仅 `parallel_mode=adaptive` **且** 显式 opt-in 才 chunk 并行；`seq` 永不 |
| Q2 | 独立 chunk 池 + **全局 in-flight 帽 = W**（resolved adaptive workers）；另有 `max_chunk_workers` |
| Q3 | 开关挂 `DemandRunRuntimeOptions` / `PipelineOverrides`；**无新 YAML**；既有 `lookup_chunk_size` 仍表示分片大小 |
| Q4 | 超时/取消跟父 LoadRef（adaptive `task_timeout_s`）；**不**另加 chunk timeout |
| Q5 | `loader_call` 完成序直发 + 携带 `chunk_offset`；框架不缓冲排序 |

## 0. Specs landing（start 之后）

- [x] 0.1 新建 live `llmanspec/specs/execution-refloader-chunk-parallelism/spec.toon`：MUST 默认关、仅 `adaptive`+opt-in、合并≡r694 串行、全局帽=W、`loader_call.chunk_offset`、完成序不排序
- [x] 0.2 `parallel-execution` 增交叉引用（层次关系）；`ir-source-relations` / `execution-adaptive-guardrails` 按需轻量交叉引用；`llman sdd validate` strict

## 1. 选项面（Python policy）

- [ ] 1.1 `parallelize_lookup_chunks` + `max_chunk_workers`（命名以实现时最小公开面为准）
- [ ] 1.2 `seq` 或未 opt-in → 代码路径与今日一致（测试锁定）
- [ ] 1.3 adaptive 但未 opt-in → 仍串行分片

## 2. 分片并行实现（垂直切片）

- [ ] 2.1 `_load_ref_chunked`：opt-in 时 fan-out 独立池；合并 ≡ 串行（含键冲突「先到先得」语义）
- [ ] 2.2 全局 semaphore/帽 = W；单测：在途 ≤ W；无嵌套同池死锁
- [ ] 2.3 异常语义 ≡ 串行；每 chunk `loader_call` 仍发出（完成序；载荷含 `chunk_offset`）；框架不排序缓冲
- [ ] 2.4 cache：分片 worker 不写 `load_ref_cache`；合并后单次写入；测例钉死
- [ ] 2.5 `LoaderCallEvent`（或等价 meta）增加可选 `chunk_offset`；串行分片亦可填（便于统一）

## 3. 护栏

- [ ] 3.1 workers / 帽上限；拒绝无界
- [ ] 3.2 文档：外部 QPS 风险与推荐用法；`lookup_chunk_size` ≠ 并行开关
- [ ] 3.3 合并 ≡ 串行 first-wins（按 chunk offset 序）；rows 模式不分片单测
- [ ] 3.5 文档一句：adaptive 跨 relation **不**共享 `load_ref_cache`（per-task 隔离）；热维表用 `preload_forever`；与 c30 正交（不在本 change 做跨 task dedup）

## 4. 证据与回归

- [ ] 4.1 `.tmp/repro/chunk-parallel/` A/B（sleep RTT）+ RSS ≤10%
- [ ] 4.3 交叉：`preload_forever` + `lookup_chunk_size` + opt-in → LoadRef 热路径零 ref-loader；preload 阶段仍只 load 一次
