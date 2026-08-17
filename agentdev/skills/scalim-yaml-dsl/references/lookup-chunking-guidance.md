# LookupChunking：何时用、如何自证

> Agent / 维护者卡。人类叙事 SSOT：`docs/doc/yaml-dsl/user-guide.md` §4.4.3  
> Upgrade：`references/upgrades/2026-08-09-lookup-chunking-python-ssot.md`  
> 可运行 oracle：`notebooks/marimo/example_public_api_suite/chapters/ch164_public_api_lookup_chunking.py`

## 何时读取

- 用户问 keys lookup 要不要设分片、chunk 会不会更快、YAML 还能不能写 `lookup_chunk_size`
- 下游 SQL `IN (...)` / HTTP payload / 供应商批次有硬上限
- 要用 Observer/Hook 核对分片有没有真的发生

## 硬边界

- YAML **禁止** `sources.*.lookup_chunk_size`（再写 fail-fast）
- Python SSOT：`DemandRunRuntimeOptions.lookup_chunking={id: LookupChunking.off()|sized(...)}`
- 未配置 ≡ `off()` ≡ 单次 loader 调用（通常延迟最优）
- `sized(N)` **不是**并行开关；片间并行只允许 `sized(N, parallel=True)` 且 `parallel_mode=adaptive`
- `batch_size` 切主行；`LookupChunking` 切单次 keys LoadRef。两者正交
- `$rows` 模式不分片
- `sized(N)` 仅当 `N < unique_keys` 才真正切分；`N >= unique_keys` 观测上 ≡ `off`（`chunk_offset is None`）

## 何时设 sized

| 场景 | 做法 |
|------|------|
| 进程内 / 低 RTT / 无批次上限 | **不要设**（默认 off） |
| 下游有硬上限（IN 长度、payload、API batch） | `sized(上限的 50–80%)`，取允许的最大安全值 |
| 单 ref 超大键集且 RTT 主导 | 先 sized 分片；确认 QPS 后再 `parallel=True` + `adaptive` |
| 只想省内存 | **不要**靠更小 chunk；顺序分片墙钟 ≈ `ceil(keys/N) × RTT` |

自证：订阅 `EventType.LOADER_CALL`，看 `payload.lookup_key_count` / `payload.chunk_offset` / `payload.params["ids"]`。并行下事件是完成序，按 `chunk_offset` 排序；回调可能在 chunk worker 线程，订阅方须线程安全。

## 目录 SSOT（实现）

运行时策略写在 `DemandIr.sources[id]`。`LookupStepIr.to_source` 只是图句柄。LoadRef 经 `ExecutionRuntime.resolve_lookup_source(step)` 按 `source_id` 回目录，禁止把嵌套快照当 live 策略。
