## Context

`PreloadCache.get_or_load()` 当前使用 per-`source_id` 的 `threading.Lock` 去重，但在持锁临界区内直接执行用户提供的 `load_fn()`（`src/scalim/execution/preload_cache.py`）。这会把“互斥去重”扩大成“互斥执行外部回调”，从而：

- 放大死锁/卡死风险（重入、自死锁、锁顺序反转等）
- 拉长锁持有时间（I/O、网络、第三方库等），降低并发可预测性

同时该对象有运行时约束：

- 运行时需兼容 Python 3.6
- `adaptive` 的 `process` 后端会 pickle `preloaded_cache`，因此 `PreloadCache` 必须可 pickle；当前通过 `__getstate__`/`__setstate__` 仅序列化 `_data` 来保证锁可重建

## Goals / Non-Goals

**Goals:**

- `load_fn()` 的执行 MUST 不在任何用于保护 `_data`/缓存状态的互斥锁临界区内发生
- 并发下保持 “同一 `source_id` 最多一次真实 `load_fn()`” 的 inflight 去重语义
- 等待方在 inflight 完成后获得一致的结果或一致的异常（失败不写入半成品）
- 失败后清理 inflight 状态，允许后续重试
- 保持 `PreloadCache` 可 pickle（仅序列化 `_data`；inflight/locks 不序列化）
- 用可验证的并发回归测试覆盖核心死锁/卡死风险

**Non-Goals:**

- 不新增/修改对外 API（例如不新增 timeout 参数；不改变 `get_or_load(source_id, load_fn)` 签名）
- 不承诺解决“业务逻辑循环依赖”导致的互相等待（例如两个 `load_fn` 彼此调用对方 key 的 `get_or_load`）；该类循环本质上不可自动消解
- 不扩展 `MutableMapping` 其它操作的并发语义（`__setitem__` 等仍保持现状）

## Decisions

### 1) 引入非序列化的 inflight 状态以去重并发加载

在 `PreloadCache` 内新增 `_inflight: Dict[str, _InFlight]`（仅进程内有效；不参与 pickle）。`_InFlight` 至少包含：

- `done: threading.Event`：表示加载完成（成功/失败都会 set）
- `owner_ident: int`：创建 inflight 的线程 ident，用于检测同线程自循环
- `value: Optional[LoaderResultMapping]`
- `error: Optional[BaseException]`

并在 `__setstate__` 中重置 `_inflight`，确保反序列化后状态干净。

### 2) 仍使用现有 per-key `Lock` 保护状态，但锁内只做“建档/提交”

继续复用 `_lock_for(source_id)` 返回的 per-key `Lock` 来保护 `_data/_inflight` 的一致性更新，但将行为拆分为两段：

1. **锁内（短临界区）**：读 `_data`、创建或读取 inflight 占位符、提交结果/异常到 `_data/_inflight` 的快照字段
2. **锁外**：执行 `load_fn()`，以及等待 `Event`

这样避免“外部回调在锁内执行”的根因，同时保持 per-key 争用最小化。

### 3) 明确成功/失败语义与清理顺序

- 成功：loader 线程在锁内写入 `_data[source_id] = value`，再标记 inflight `value`，随后 `done.set()`；等待方读取 `_data`（或 inflight.value）并返回同一结果。
- 失败：loader 线程捕获异常并在锁内写入 inflight.error，确保等待方看到一致异常；然后 `done.set()`；最后从 `_inflight` 移除该 key（允许后续重试）。失败时 **不得** 写入 `_data`。

### 4) 同线程自循环（重入同 key）做 fail-fast 护栏（避免自死锁）

在调用方提供的 `load_fn` 内部直接或间接重入 `get_or_load(source_id, ...)` 时，新的 inflight 语义如果“盲等”会导致线程等待自己永远无法完成的 inflight（自死锁）。

因此当检测到：

- `_inflight[source_id]` 存在，且其 `owner_ident == threading.get_ident()`

则直接抛出一个明确的 `RuntimeError`（或更具体的内部异常类型）提示“检测到递归 preload（同 key）”，从而把“无声卡死”转为“可定位错误”。

这不会限制正常用户用法（合理的 `load_fn` 不应依赖同 key 的 preload 值），并且与 c0 风险优先级一致：避免整个 CI/服务因偶发循环而挂死。

### 5) 异常对象的跨线程传播：优先语义一致，其次 traceback 一致

目标是“等待方收到一致异常（类型/信息一致）”。实现上有两种可选策略：

- **A（推荐，简单）**：等待方直接 `raise error`（异常对象可能被多线程重复 raise，traceback 可能互相覆盖，但类型/信息一致且实现简单）
- **B（更严谨）**：为每个等待方构造一个“等价异常实例”（例如 `copy.copy(error)` 或基于 `error.__class__(*error.args)` 的 best-effort 克隆），避免共享同一异常对象导致 traceback 互相覆盖；若克隆失败则回退到 A

建议先采用 B（best-effort clone + fallback），并通过单测覆盖“等待方抛出的异常类型一致”。若后续发现克隆导致兼容性问题，再回退到 A。

## Risks / Trade-offs

- [循环依赖等待] 两个 `load_fn` 之间形成跨 key 的逻辑循环仍可能互相等待 → 通过同线程自循环 fail-fast + 测试/文档提示；跨线程循环依赖不在本变更范围内。
- [异常 traceback 可读性] 多线程共享同一异常实例会导致 traceback 互相覆盖 → 采用 best-effort clone；并在设计上优先保证异常类型/信息不变。
- [实现复杂度提升] 从“简单锁 + 直接执行”变为“锁内建档 + 锁外执行 + 等待” → 通过集中封装 `_InFlight` 与清晰的状态机/单测降低维护成本。

## Migration Plan

- 实现仅影响内部并发行为，API 不变；按以下顺序落地并通过 `just qa` 验收：
  1. 重构 `PreloadCache.get_or_load()`：新增 inflight 状态，锁外执行 `load_fn`
  2. 新增并发回归测试：并发去重、异常一致、同线程重入 fail-fast（避免卡死）
  3. 运行 `just qa` 确保 py36 smoke 与全量测试通过

## Open Questions

1. 是否需要为等待 inflight 增加“超时 + 明确诊断”的可选路径（不改 public API 的前提下，例如仅在测试/调试模式启用）？
   - 推荐：本变更先不引入默认超时，以避免行为变更；仅在测试中用 `join(timeout=...)` 做护栏，后续如需诊断再通过独立变更引入。

