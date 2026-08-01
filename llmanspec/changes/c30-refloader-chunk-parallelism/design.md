# Design: refloader chunk parallelism

## 问题分层（避免和 adaptive 糊在一起）

```text
parallel_mode=adaptive  →  同一批里，多个独立 LoadRef 之间重叠等待
chunk parallelism(opt) →  同一个 LoadRef 步骤内，lookup_chunk_size 的多片之间重叠等待
seq / 未 opt-in         →  全部串行（今日默认）
```

用户心智：仍然只有「顺序 / 自适应关联并行」；分片并行是 **runtime 上的附加许可**，不是第三种 `parallel_mode` 枚举值（避免模式爆炸）。若实现上发现必须挂在 `adaptive` 下才允许，须在 spec 写清：「仅 `adaptive` + opt-in 时启用」，`seq` 永不 chunk 并行。

## Goals / Non-goals

**Goals**

- 默认 = 串行分片（向后兼容）。
- Opt-in 后合并结果 ≡ 串行分片。
- 显式 `max_chunk_workers`（或复用 `max_workers` 的清晰子集）上限。
- RSS ≤ +10%；每 chunk 可观测。

**Non-goals**

- 新 YAML 键。
- 默认开启。
- 改写用户 loader 签名。
- 派生融合。

## 推荐 API / 池形态（随深挖更新）

- **启用条件（Q1）**：`parallel_mode=adaptive` **且** 显式 opt-in；`seq` 永不 chunk 并行。
- **池（Q2-B′）**：独立 chunk `ThreadPoolExecutor` + **全局 in-flight 帽 = resolved adaptive workers W**；另有 `max_chunk_workers` 限制单步扇出。
- **禁止**：仅因设置了 `lookup_chunk_size` 就自动并行；无帽乘积扇出。

## 合并语义

- 各 chunk 返回的 key→row 映射合并；冲突键策略与今日串行分片 **完全一致**（先写清现行为再并行）。
- 异常：任一 chunk 失败时的 fail 行为与串行一致（不吞掉部分成功除非今日已如此）。

## 评估标准

| 维度 | 门槛 |
|------|------|
| 正确性 | 同 keys/同 chunk_size，串行 vs 并行结果相等 |
| 默认 | opt-in 关闭时与改前 loader 调用顺序/次数可接受（次数相同；顺序可保持串行） |
| 性能 | ≥3 chunks + 模拟 RTT：耗时 ≤ 串行 / 1.5（即 ≥1.5×）或记录未达标并调整阈值 |
| 限流 | workers 上限单测；不会无界扩容 |
| 内存 | 峰值 ≤ +10% |
| 观测 | 每个 chunk 仍有 loader 事件 |
| py3.6 | smoke |
| bench | 无 opt-in 的 seq/adaptive 既有 bench 不回退 |

## 测试 seam（已确认）

- LoadRef 分片路径（`lookup_chunk_size`）+ engine/runtime option
- 对照：`tests/execution/test_adaptive_*`、`load_ref` 既有测试风格
- `.tmp/repro/chunk-parallel/`：可控 `time.sleep` 模拟 RTT

## 与证据目录关系

- 复用 `.tmp/evidence/perf-baseline/` 中 relations_io 结论作背景；本 change 另做「单 ref 多 chunk」专题 MVP。

## Open questions → 推荐收口（已全部决议）

### Q1. chunk 并行是否强制要求 `parallel_mode=adaptive`？ — **已决议：A**

**仅 `adaptive` + 显式 opt-in 时启用；`seq` 永不 chunk 并行。**

- 用户心智：`seq` = 一切可预期串行；`adaptive` = 允许重叠等待。
- 避免 `seq` 下「设了 lookup_chunk_size 却悄悄打爆 DB」。
- Spec MUST：`parallel_mode=seq` 或未 opt-in → 串行分片（今日行为）。

### Q2. 线程池复用 vs 独立小池？ — **已决议：B′**

**独立 chunk 小池 + 全局并发帽 = resolved adaptive workers（W）。**

- 避免「adaptive 池内再 submit 同池 chunk 并 wait」的嵌套死锁。
- 避免无帽时 `在途 LoadRef × max_chunk_workers` 乘积打爆 DB。
- 有效并发：任意时刻 in-flight loader 调用 ≤ W（与今日 adaptive 心智一致）；单步 chunk 并发另受 `max_chunk_workers` 与剩余帽槽限制。
- 实现：chunk 任务进独立 `ThreadPoolExecutor`；获取/释放全局 semaphore（或等价限流）容量为 W；`max_chunk_workers` 仍作单步扇出上限。

### Q3. Opt-in 挂在哪？ — **已决议：A**

**`DemandRunRuntimeOptions` / `PipelineOverrides` 布尔（如 `parallelize_lookup_chunks`）+ 可选 `max_chunk_workers`；无新 YAML 键。**

- 符合 YAML=authoring、Python=runtime policy。
- **禁止**「有 lookup_chunk_size 就自动并行」。
- 既有 YAML `lookup_chunk_size`（分片大小）保持；并行许可只在 Python。

### 已决议回顾

- 默认关；合并 ≡ 串行；RSS ≤10%；不与 c10/c20 混提。
- **Q1**：仅 `adaptive` + opt-in；`seq` 永不 chunk 并行。
- **Q2**：独立 chunk 池 + 全局帽=W（B′）。
- **Q3**：opt-in 挂 `DemandRunRuntimeOptions` / `PipelineOverrides`（A）。

### 延后（非本 change）

YAML 非编排字段迁 Python：draft change **`c40-yaml-runtime-policy-boundary`**（调研 R1–R3），不塞进 c30。

## 边界深挖（合并 / 超时 / rows）— 2026-08-01

### 键合并（串行今日行为 → 并行必须 ≡）

`_load_ref_chunked` 合并为：

```text
for each chunk result:
  for key, value in result:
    if key not in merged:
      merged[key] = value   # 先写入者胜；同 key 后续 chunk 忽略
```

并行时：**不得**改成 last-wins / 抛错，除非另开 breaking change。实现须保证「按 chunk 在 keys 列表上的偏移顺序」应用合并（先处理完 offset 小的 chunk 再合并，或等价：按 offset 排序后归并），与串行 for-loop 一致。

### rows binding

`_resolve_lookup_chunk_size`：若 `binding.mode == "rows"` → **强制不分片**（返回 `None`）。  
⇒ chunk 并行 **只可能** 出现在 **keys** 模式（且 cache 启用、chunk_size 有效）。rows 路径不在 c30 并行范围内；测例钉死「rows + lookup_chunk_size 仍一次 loader」。

### 取消 / 超时

- adaptive 层已有 `AdaptiveTuning.task_timeout_s` + `submission_unit` 等待/cancel（整步 LoadRef 任务）。
- chunk 并行若挂在某 LoadRef 任务内：父任务超时/取消时，**SHOULD** 取消未完成 chunk futures，且失败语义与「串行做到一半抛错」对齐（不留下「半份 merged 当成功」）。
- **推荐收口（Q4）**：复用父任务超时；chunk 层不另发明独立 timeout 配置；cancel 尽力而为（线程无法强杀，与 adaptive 池 shutdown 注释一致）。

### Q4. chunk 是否单独配 timeout？ — **已决议：A**

**只跟父 LoadRef / adaptive `task_timeout_s`；不新增 chunk timeout 选项。** 超时/取消时尽力 cancel 未完成 chunk futures；不得把半份 `merged` 当成功返回。

### Cache / 事件深挖（2026-08-01）

**Cache（无需新决议）**

- 分片期间 **不写** `load_ref_cache`；全部合并后 **写一次**（与今日串行一致）；并行实现 MUST 保持。
- 不必为 chunk 并行单独禁用 cache；rows 仍不分片。
- adaptive 下各 LoadRef task 使用独立 `ExecutionRuntime`（独立空 cache）；chunk 并行发生在单 task 内，不跨 task 抢写同一 cache dict。
- GIL 注释仍适用；不借 c30 引入 free-threaded 锁方案。

**loader_call 事件**

- 串行：每 chunk 一条 `LOADER_CALL`（miss），顺序 = chunk offset 递增。
- 并行：完成序直发 + `chunk_offset`（Q5-B）。

### preload / workflow cache（2026-08-01）— **无新决议**

```text
Pipeline 启动
  → preload_forever → preloaded_cache[source_id]（全表）
  →（workflow）可选 WorkflowCachePool 跨 node dedup

每批 LoadRef
  → 若 is_source_cached？→ 内存查表早退（零 loader）
  → 否则 → load_ref_cache / _load_ref_once | _load_ref_chunked（c30 只动这里）
```

| 层 | 作用 | 与 c30 |
|----|------|--------|
| `WorkflowCachePool` | 跨 workflow node 复用 preload | 正交；chunk 并行不碰 |
| `preloaded_cache` | demand 内全表只读 | LoadRef **早退**，永不进 `_load_ref_chunked` |
| `load_ref_cache` | 非 preload 的 keys 批次 dedup | 分片期不写、合并后写一次（已钉） |

**结论**：`preload_forever` + 打开 chunk opt-in → loader 仍只在 preload 阶段调用；与 `lookup_chunk_size` / 并行 **正交**。Apply 时加一条交叉测例即可；不必为 preload 另开开关或禁并行。

### 非 preload × adaptive：`load_ref_cache` 重复 loader（2026-08-01）— **不进 c30**

| 事实 | 含义 |
|------|------|
| adaptive 并行 task 各建空 `load_ref_cache`，fan-in **不回写**主 runtime | 跨 relation 打同一 source 可能 **各调一次 loader**（今日已有，非 c30 引入） |
| 注释「多线程抢同一 dict」对 **今日并行路径基本不成立**（per-task 隔离）；更贴 c30 单 task 内 chunk、或未来 free-threaded | spec r434 与实现略漂移 → 文档/另案对齐 |
| c30 叠加 | cache 竞态 **不恶化**；外部 QPS 可能因 chunk 重叠上升（已有全局帽 W） |

**处置**：c30 **不**做跨 task dedup。热维表继续推 `preload_forever`。跨 task 共享 batch cache / in-flight dedup → **另开 change（按需）**；文档可补一句（apply 文档任务）。显式锁 → 既有 notplan `c10-adaptive-cache-explicit-locks`。

### Q5. chunk 并行时 `loader_call` 事件顺序？ — **已决议：B（带 offset 元数据）**

**按完成序直接发出（框架不做缓冲排序）；每条事件 MUST 携带可排序的 chunk 身份（推荐 `chunk_offset` 或 `chunk_index`，与 keys 列表切片起点一致）。**

- viz / 外部订阅方若要稳定序，自行按该字段排序。
- 动机：避免为排序再持有一整批事件缓冲（内存）。
- 条数仍 = chunk 数；`lookup_key_count` 仍为当片大小。
- Specs landing：在 `refloader-chunk-parallelism` / 观测交叉引用中写清「顺序不保证；offset 字段保证可重建串行观感」。

### 已决议回顾

- **Q1**：仅 `adaptive` + opt-in；`seq` 永不 chunk 并行。
- **Q2**：独立 chunk 池 + 全局帽=W（B′）。
- **Q3**：opt-in 挂 `DemandRunRuntimeOptions` / `PipelineOverrides`（A）。
- **Q4**：超时/取消跟父任务；无独立 chunk timeout（A）。
- **Q5**：完成序直发 + 事件带 `chunk_offset`；不缓冲排序（B）。
- **preload**：与 c30 正交；交叉测例即可。
