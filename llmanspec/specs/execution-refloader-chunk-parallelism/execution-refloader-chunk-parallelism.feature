# language: zh-CN
# capability: execution-refloader-chunk-parallelism
# purpose: 在 keys 模式由 Python `LookupChunking.sized` 产生的分片路径上提供 nested parallel opt-in；默认串行；合并语义与 `ir-source-relations` r694 串行分片一致。分片大小 SSOT 见 `yaml-dsl-runtime-policy-boundary` r1003（不再用 YAML `lookup_chunk_size`）。 [c30-refloader-chunk-parallelism][c40-yaml-runtime-policy-boundary]
# scope: src/scalim/

功能: execution-refloader-chunk-parallelism

  @req:r970 @human
  场景: Chunk parallelism is opt-in and adaptive-only
    - 系统 MUST 仅在同时满足以下条件时对同一 `LoadRef(keys)` 步骤内由 `LookupChunking.sized` 产生的多片 loader 调用启用并行：(1) `parallel_mode=adaptive`；(2) 该 source 的 effective chunking 为 `LookupChunking.sized(..., parallel=True)`（或兼容窗内映射到 sized parallel 的旧平铺布尔）。当 `parallel_mode=seq`、`sized(..., parallel=False)` / `off()`、或仅配置了 size 而未开 parallel 时系统 MUST 保持串行分片。系统 MUST NOT 新增 YAML 键作为并行开关；分片大小与 parallel 嵌套 MUST 由 `yaml-dsl-runtime-policy-boundary` r1003 约束，本条只约束并行启用条件与护栏。

  @req:r971 @human
  场景: Chunk merge equals serial first-wins
    - opt-in 并行路径的 key-row 合并结果 MUST 与串行分片路径完全一致：按 keys 列表上的 chunk offset 升序应用各片结果；同 key 冲突时先写入者胜（与 `ir-source-relations` r694 / 今日 `_load_ref_chunked` 一致）。系统 MUST NOT 改为 last-wins、随机序合并或因冲突失败除非另开 breaking change。

  @req:r972 @human
  场景: Global in-flight cap equals resolved adaptive workers
    - 并行分片 MUST 使用独立于 adaptive LoadRef fan-out 池的 chunk 执行器（避免同池嵌套 wait 死锁）。任意时刻进程内 in-flight ref-loader 调用数 MUST ≤ resolved adaptive workers W；单步扇出另受可选 `max_chunk_workers` 限制。系统 MUST NOT 因在途 LoadRef 与 max_chunk_workers 无帽乘积而无限扩容。

  @req:r973 @human
  场景: Chunk failures and timeout follow parent LoadRef
    - 任一 chunk 失败时的异常传播与部分结果处理 MUST 与串行分片一致：传播的异常类型/消息、以及 MUST NOT 将半份 merged 映射当作成功返回、MUST NOT 写入半份 `load_ref_cache`。超时与取消 MUST 跟随父 LoadRef / adaptive `task_timeout_s`（见 `execution-adaptive-guardrails`）；系统 MUST NOT 新增独立 chunk timeout 配置。超时或取消时 MUST 尽力取消未完成 chunk futures。说明：并行路径下，失败 offset 之前/之后**已提交且仍在运行**的 chunk MAY 仍会执行完成，因此错误路径上的 loader 调用次数 MAY 高于串行分片（串行在首个失败处即停止后续片）；成功路径的调用次数 MUST 与串行一致。

  @req:r974 @human
  场景: Cache write once after merge
    - 分片期间（含并行 workers）MUST NOT 写入 `load_ref_cache`；全部 chunk 合并完成后 MUST 至多写一次（与今日串行一致）。`bind.mode=rows` MUST 继续强制不分片（因而也无 chunk 并行）。

  @req:r975 @human
  场景: Loader call events carry chunk_offset
    - 每个 chunk 的 `loader_call` 事件 MUST 仍发出（条数 = chunk 数；`lookup_key_count` 为当片大小）。并行路径下事件完成序 MAY 与 offset 升序不同；框架 MUST NOT 为排序缓冲整批事件。每条相关事件 MUST 携带可排序身份字段 `chunk_offset`（与 keys 切片起点一致）；串行分片 MAY 同样填充该字段。订阅方若需稳定序 MUST 自行按 `chunk_offset` 排序。当分片 LoadRef 未运行于 adaptive capture 任务中（例如该层按阈值退化为串行）时，这些 `loader_call` 回调 MAY 直接在分片工作线程上并发执行；系统 MUST NOT 承诺主线程单线程回调（`parallel-execution` r735 对本路径的例外）。因此 opt-in 的订阅方（hook / observer / sink）MUST 自行保证线程安全，且该约束 MUST 在用户文档中显式说明。

  @req:r976 @human
  场景: Preload remains orthogonal
    - 当 source 已 `preload_forever`（或等价预加载命中）导致 LoadRef 早退时系统 MUST NOT 因开启 chunk 并行而额外调用 ref loader。chunk 并行 MUST NOT 改变 preload / workflow cache 层语义。

  @req:r977 @human
  场景: Default and memory bounds
    - 未开 parallel 时行为 MUST 与串行分片比特级兼容（调用次数相同；顺序保持串行）。parallel 路径峰值 RSS 相对串行分片 MUST 满足变更门槛（≤ +10%）。外部 QPS 风险 MUST 在文档中说明：`LookupChunking.sized(size=...)`  alone 不是并行开关；并行仅由 nested `parallel=True`（及 adaptive）启用。
  @req:r970 @human
  场景: seq-never-parallelizes-chunks
    - 必须成立：假如 parallel_mode=seq 且 LookupChunking.sized(size=N parallel=True)；当 执行 keys LoadRef 分片；那么 系统 MUST 串行调用各 chunk loader
    假如 parallel_mode=seq 且 LookupChunking.sized(size=N parallel=True)
    当 执行 keys LoadRef 分片
    那么 系统 MUST 串行调用各 chunk loader

  @req:r970 @human
  场景: adaptive-without-opt-in-stays-serial
    - 必须成立：假如 parallel_mode=adaptive 但 sized 未设 parallel=True（或仅 sized 默认串行）；当 执行多 chunk LoadRef；那么 系统 MUST 串行分片
    假如 parallel_mode=adaptive 但 sized 未设 parallel=True（或仅 sized 默认串行）
    当 执行多 chunk LoadRef
    那么 系统 MUST 串行分片

  @req:r970 @human
  场景: sized-alone-not-a-parallel-switch
    - 必须成立：假如 仅 LookupChunking.sized(size=N) 且 parallel 未开；当 执行；那么 系统 MUST NOT 并行 chunk
    假如 仅 LookupChunking.sized(size=N) 且 parallel 未开
    当 执行
    那么 系统 MUST NOT 并行 chunk
  @req:r971 @human
  场景: parallel-merge-equals-serial
    - 必须成立：假如 同 keys 与同 chunk size；当 串行与 sized(parallel=True) 各跑一次；那么 合并后的映射 MUST 完全相等
    假如 同 keys 与同 chunk size
    当 串行与 sized(parallel=True) 各跑一次
    那么 合并后的映射 MUST 完全相等

  @req:r971 @human
  场景: first-wins-by-chunk-offset
    - 必须成立：假如 两 chunk 对同一 key 返回不同值；当 合并结果；那么 MUST 等于 offset 较小 chunk 的值
    假如 两 chunk 对同一 key 返回不同值
    当 合并结果
    那么 MUST 等于 offset 较小 chunk 的值
  @req:r972 @human
  场景: inflight-capped-by-W
    - 必须成立：假如 resolved W=2 且单步可扇出更多 chunk；当 执行并行分片；那么 任意时刻 in-flight loader 调用数 MUST ≤ 2
    假如 resolved W=2 且单步可扇出更多 chunk
    当 执行并行分片
    那么 任意时刻 in-flight loader 调用数 MUST ≤ 2
  @req:r973 @human
  场景: chunk-error-matches-serial
    - 必须成立：假如 某一 chunk loader 抛错；当 并行路径失败；那么 语义 MUST 与串行分片一致且不得返回半份成功 merged / 半份 cache
    假如 某一 chunk loader 抛错
    当 并行路径失败
    那么 语义 MUST 与串行分片一致且不得返回半份成功 merged / 半份 cache

  @req:r973 @human
  场景: error-path-inflight-chunks-may-still-run
    - 必须成立：假如 sized(parallel=True) 且某一 chunk 失败时已有其它 chunk 在途；当 观察 loader 调用与返回；那么 已在途 chunk MAY 仍被调用（调用次数 MAY > 串行）但异常与无半份成功 MUST 与串行一致
    假如 sized(parallel=True) 且某一 chunk 失败时已有其它 chunk 在途
    当 观察 loader 调用与返回
    那么 已在途 chunk MAY 仍被调用（调用次数 MAY > 串行）但异常与无半份成功 MUST 与串行一致
  @req:r974 @human
  场景: cache-written-once-after-merge
    - 必须成立：假如 启用 batch cache 的 keys 分片并行路径；当 执行一次 LoadRef；那么 `load_ref_cache` MUST 仅在合并后写入一次
    假如 启用 batch cache 的 keys 分片并行路径
    当 执行一次 LoadRef
    那么 `load_ref_cache` MUST 仅在合并后写入一次

  @req:r974 @human
  场景: rows-mode-never-chunks
    - 必须成立：假如 `bind.mode=rows` 且配置了 LookupChunking.sized(...)；当 执行 LoadRef；那么 系统 MUST 单次 loader 调用（不分片或不并行）
    假如 `bind.mode=rows` 且配置了 LookupChunking.sized(...)
    当 执行 LoadRef
    那么 系统 MUST 单次 loader 调用（不分片或不并行）
  @req:r975 @human
  场景: each-chunk-emits-loader-call-with-offset
    - 必须成立：假如 N 个 chunk 的并行分片且订阅 `loader_call`；当 执行；那么 系统 MUST 发出 N 条事件且每条携带 `chunk_offset`
    假如 N 个 chunk 的并行分片且订阅 `loader_call`
    当 执行
    那么 系统 MUST 发出 N 条事件且每条携带 `chunk_offset`

  @req:r975 @human
  场景: opt-in-callbacks-may-run-on-chunk-worker-threads
    - 必须成立：假如 sized(parallel=True) 且该 LoadRef 未运行于 adaptive capture 任务中；当 订阅方接收 `loader_call`；那么 回调 MAY 发生在分片工作线程上而非主线程（订阅方 MUST 线程安全）
    假如 sized(parallel=True) 且该 LoadRef 未运行于 adaptive capture 任务中
    当 订阅方接收 `loader_call`
    那么 回调 MAY 发生在分片工作线程上而非主线程（订阅方 MUST 线程安全）
  @req:r976 @human
  场景: preload-hit-skips-chunk-loaders
    - 必须成立：假如 source 已 preload 命中且 parallel 开启；当 执行批次 LoadRef；那么 热路径 MUST 不调用 ref loader
    假如 source 已 preload 命中且 parallel 开启
    当 执行批次 LoadRef
    那么 热路径 MUST 不调用 ref loader
  @req:r977 @human
  场景: no-opt-in-matches-pre-change-serial
    - 必须成立：假如 未开 parallel 的分片路径；当 与串行对照；那么 loader 调用次数与合并结果 MUST 一致
    假如 未开 parallel 的分片路径
    当 与串行对照
    那么 loader 调用次数与合并结果 MUST 一致
