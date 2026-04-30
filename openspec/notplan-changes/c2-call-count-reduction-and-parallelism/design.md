## Status (2026-04-30)

- 本设计已移动到 `openspec/notplan-changes/`：先落地并验收 `c0-execution-hotpath-fastpaths` 的实际收益，再决定是否需要推进本方向（若 `c0` 已足够，则不进入本交付线）。

## Context

在 `c0-execution-hotpath-fastpaths` 已经显著降低 compute / call_by / load_ref 的 per-row 固定开销后，仍有一类 workload 可能继续触顶：

- 字段数量很多、每个字段逻辑很薄（主要是 `call_by` 做格式化/枚举映射/轻量规则）。
- 行数很大，导致“Python 函数调用次数 = 行数 × 字段数”成为主导成本。

进一步的收益通常来自两条路：

1) **减少 call 次数**（batch / memoize / multi-output / fusion）。
2) **利用多核**（并行化）。

但这些能力如果设计不当，容易带来：明显的内存膨胀、语义不一致（尤其是副作用/错误时机）、以及可观测性事件流顺序不稳定。因此本变更将把风险集中收口到显式 opt-in 与 profile 治理下。

约束/前提：

- 运行时必须兼容 Python 3.6（`src/scalim/**`）。
- 不引入任何新增第三方依赖（含 vendor 审核成本高的依赖/扩展）。
- 默认行为（`balanced`）不要求业务 YAML/代码改动；新能力必须是 opt-in 或仅在 `speed` profile 下启用。
- 内存必须有上界：禁止引入与“总行数”线性增长的常驻结构；允许与“批大小/字段数/worker 数/缓存上限”相关的有界结构。
- OpenSpec 工件不得包含真实业务数据；本地复现/benchmark 脚本仅放在 `.tmp/`（不提交）。
  - 注意：`.tmp/` 为 untracked dev artifacts；多 worktree 开发时不会自动出现。若在其他 worktree 实施/验证，请从“主仓库工作目录”的 `.tmp/` 手动复制（或在该 worktree 重新生成同名脚本），且不要提交到 git。

## Goals / Non-Goals

**Goals:**

- 提供一组“减少 call 次数/并行化”的能力，并在可行时与 `c1-runtime-performance-profiles` 的 profile 体系收口治理（若后续引入 `c1`）：
  - `call_by` **batch call**：按批次一次性计算 N 行（避免 `List[Dict]` 打包导致的内存爆炸）。
  - **有界 memoization**：对被用户显式声明为 pure 的 `call_by` 进行有限容量缓存，降低重复调用次数。
  - **可选并行化**：在保持语义与可观测性契约的前提下，把并行执行扩展到 compute/call_by 方向（默认仅在 `speed` 下启用，且严格上界）。
- 默认保持低内存：任何新增结构必须可证明上界，并可由 `memory` profile 关闭。
- 观测与错误语义：对默认路径保持既有语义与事件边界；对 opt-in 能力明确说明其语义差异与限制。

**Non-Goals:**

- 不引入 pandas/arrow/numpy 等外部向量化依赖，也不引入 C/Cython 扩展。
- 不做“自动纯度推断”（无法可靠判断副作用）；不会在未声明 pure 的情况下自动减少 call。
- 不在本变更中把所有 compute/call_by 全面并行化（GIL + 事件顺序 + 上下文写入带来的复杂度过高）；并行化仅作为受控 opt-in 能力提供。

## Decisions

### 1) 治理入口：优先用 `c1` profile 收口（若有），语义型能力仍显式 opt-in

**决策：**

- **语义型能力**（会改变函数调用形态/次数/副作用次数的能力）必须由用户显式 opt-in：
  - `call_by_mode: batch`（函数签名与输入形态改变）。
  - `call_by_pure: true`（允许框架做 memoize/fusion 的前提）。
- **策略型能力**（是否启用 memoize、并发 worker 数、是否 materialize batch inputs）的默认值与上界，推荐由 `c1` profile 统一治理：
  - `memory`：禁用 memoize/并行；batch call 使用“零拷贝 column view”优先。
  - `balanced`：默认禁用 memoize/并行；batch call 允许但不主动 materialize 输入。
  - `speed`：允许启用 memoize/并行；可选 materialize 输入以换取更低的 column access 开销。
  - 若 `c1` 尚未落地，则本方向实现必须保持“默认关闭 + 显式 opt-in + 硬上界”三原则，避免把高风险策略悄悄带入默认路径。

**原因：**

- YAML 属于 authoring，profile 属于 runtime policy；两者边界清晰且易解释。
- batch call 与减少 call 次数在语义层面风险高，不能被 profile “悄悄打开”。

**备选：**

- 仅靠 profile 自动启用 batch/memoize → 风险：可能在用户不知情时改变副作用/错误时机。
- 仅靠 YAML 控制所有细粒度策略 → 风险：把 runtime policy 塞进配置文件，用户认知负担高，且违背 `c1` 的治理目标。

### 2) `call_by` batch call：以“列式视图(零拷贝) + 可选 materialize”实现，不打包 `List[Dict]`

**决策：**

- 为派生字段新增可选 authoring 字段（DSL 侧）：
  - `call_by_mode: "row" | "batch"`（默认 `"row"`）。
- 当 `call_by_mode="batch"` 时，执行期按批次调用一次 `calculator`，把依赖字段以**列式视图**传入：
  - positional args：由 `Sequence[FieldValue]` 组成（每个 dep 一列）。
  - kwargs：同理（每个 dep 一列）。
  - 返回值：要求为长度等于批次行数的 iterable（`list/tuple/generator` 均可），逐行消费并写回。
- 输入列的物化策略由 profile 治理：
  - 默认（`balanced/memory`）：传入零拷贝 `ColumnView`（按需 `__getitem__` 从 `BatchContext` 取值）。
  - `speed`：允许在运行期策略中选择“materialize inputs”（将列提取为 `list`）以减少重复查找。

**原因：**

- `List[Dict]` 会引入 `O(batch_size × deps)` 的额外对象分配与内存峰值，与框架“低内存”目标冲突。
- `ColumnView` 让 batch call 的内存增幅接近 0，同时仍能把“函数调用次数”从 N 行降为 1 次/批。

**语义与错误处理约定（batch mode）：**

- 若 batch 函数抛出异常：视为该字段本批次所有行的计算异常，按既有 `handle_compute_error` 路径写入 `None` 并发出 ErrorEvent（保持错误可观测，但调用时机不同于逐行）。
- 若返回 iterable 的长度与行数不匹配：作为运行期错误（配置/实现错误），同样按全批次错误处理并给出可操作提示（期望长度、实际长度/提前耗尽）。
- `value_ops`/transform：按元素逐行应用（与 row mode 一致）。

**关于 `$ctx`（阶段性收敛）：**

- **阶段 1（本变更交付范围）**：`call_by_mode="batch"` 时**禁止** `$ctx`（编译期 fail-fast）。
  - 含义：batch 模式下用户函数只会被调用一次，因此没有“单行”的 `row_id`/`values` 语义；若继续允许 `$ctx`，就会出现两种不可接受的实现：
    - **为每行构造一个 ctx 列表传入** → 这会引入 `O(batch_size)` 的对象分配与额外引用，违背“低内存/低分配”目标。
    - **让 `$ctx.row_id` 在 batch 模式下变成 list** → 破坏类型与用户心智（同一字段在 row/batch 模式下 `$ctx.row_id` 类型不同），且难以静态校验/诊断。
  - 推荐替代：batch call 优先用于“纯格式化/映射/轻逻辑”，避免依赖行号等上下文；如确实需要行号，优先在业务侧把所需信息变为普通依赖字段（让函数只依赖入参）。
- **阶段 2（可选扩展，不在本变更强制交付）**：如业务迁移确实需要 ctx，则新增独立的 batch 上下文类型，并保持名称语义稳定：
  - 新增 `BatchComputeCallContextIr`（纯标准库 dataclass），属性建议最小集合：`batch_num`、`field_id`、`deps`、`row_ids`、`values`。
  - `row_ids`: `Sequence[Hashable]`（与批次行顺序对齐）。
  - `values`: `Mapping[str, Sequence[FieldValue]]`（列式视图；默认 `ColumnView`，`speed` 可选 materialize 为 `list`）。
  - call_by parser allowlist 只新增 `$ctx.row_ids`（不复用 `$ctx.row_id` 名称），并对 batch/row 两种 ctx 类型在编译期做一致性校验（避免运行时才暴露类型不匹配）。

**备选：**

- 让 batch 函数接收 `List[Dict[str, FieldValue]]` → 内存风险不可控。
- 自动根据函数签名猜测是否 batch → 可靠性差、调试困难。

### 3) 有界 memoization：只对显式 pure 的 `call_by(row)` 启用，并在 key 构造上强约束

**决策：**

- 新增可选 authoring 字段（DSL 侧）：`call_by_pure: bool`（默认 `false`）。
- memoization 本身由 profile 决定是否启用，以及上限参数（例如 `max_entries`）。
- memoization 仅适用于：
  - `call_by_mode="row"`（逐行调用），且
  - `call_by_pure=true`，且
  - 该 `call_by` 不包含 `$ctx`（ctx 引用会破坏可缓存性与确定性）。
- 缓存键（key）构造采用“保守可缓存”策略：
  - 仅当 args/kwargs 全部为可哈希且体量可控的标量/短元组（例如 `None/bool/int/str/Decimal`）时才缓存；
  - 对不可哈希/大对象/容器字面量直接跳过缓存（而不是尝试深拷贝/序列化）。

**原因：**

- memoize 会改变调用次数与副作用次数；必须建立在用户显式声明 pure 的前提下。
- key 构造若不保守，容易把“大对象引用”放入缓存导致内存失控。

**备选：**

- 对所有 call_by 默认 memoize → 破坏副作用语义，且 key 构造不可控。
- 使用 `repr/serialize` 作为 key → 开销大且可能泄露敏感值形态（尽管不出 OpenSpec，但仍不推荐默认）。

### 4) 并行化：复用现有 “overlay + capture + commit” 模式，先聚焦 coarse-grained 的 batch call

**决策：**

- compute/call_by 的并行化不直接在共享 `BatchContext` 上并发写入；而是复用 `execution/adaptive` 既有模式：
  - 每个并行任务使用 `OverlayBatchContext` 写入 overlay；
  - 为任务创建独立 `ExecutionRuntime(parallel_mode='seq')`，并通过 `HookCaptureManager`/observer capture 收集事件；
  - 主线程按确定顺序 commit overlay，并回放事件，保持事件流顺序稳定。
- 初期并行化仅考虑 **batch call_by**（coarse-grained）：
  - row mode 的 per-row 任务粒度太细，线程池调度成本可能抵消收益，且 GIL 对纯 Python 计算不友好。
- **硬约束（避免误用变慢）**：即使在 `speed` profile + `parallel_mode="adaptive"` 下，也只允许并行化 `call_by_mode="batch"` 的派生字段（以及既有的 load_ref 并行能力）；row-mode compute/call_by 一律保持串行。
- 开启条件由 profile 与运行时并行策略共同决定（推荐仅 `speed`）：
  - `runtime.parallel_mode="adaptive"` 且 `resolved_workers > 1`。
  - 层内任务数达到阈值（复用 tuning：`min_parallel_tasks_per_layer`）。

**原因：**

- 现有 load_ref 并行化已证明 overlay/capture/commit 能在不破坏语义与观测顺序的情况下提供并发能力。
- 将并发限制在 coarse-grained batch call 上更容易获得净收益，同时将额外内存（overlay × workers）保持为有界。

**备选：**

- 直接在共享 `BatchContext` 上并发写入 compute 结果 → 存在竞态（`BatchContext._data` 不是线程安全容器），且事件顺序不可控。
- 多进程并行 → pickling/启动开销与内存放大明显，不符合严格环境与低内存目标。

### 5) Drift gates：以 `.tmp` 合成复现作为本地回归基线；CI 仍以语义测试为主

**决策：**

- 本地合成复现继续以 `.tmp/repro/...` 作为基线（不提交、不在 CI 执行），用于对比：
  - row vs batch 的 walltime 与阶段占比；
  - memoize 开关对重复输入 workload 的收益与内存上界；
  - 并行化在 I/O-bound/释放 GIL 的函数上的收益（仅定性观察，避免在 CI 固化数值门禁）。
- CI/质量门禁仍以语义测试与 `just qa` 为主；OpenSpec 在共享前运行 `just openspec-check`。

## Risks / Trade-offs

- **[风险] batch call 让用户函数必须处理列式输入与长度一致性** → **缓解**：编译期校验 `call_by_mode` 与 `$ctx` 组合；运行期对输出长度做强校验并给出可操作错误提示。
- **[风险] memoize 在 pure 声明错误时会隐藏副作用/改变结果** → **缓解**：默认 `call_by_pure=false`；仅在 `speed`/显式启用 memoize 时生效；文档强调“pure = 无副作用且仅依赖入参”。
- **[风险] memoize key 构造导致意外内存膨胀** → **缓解**：保守 key 策略（不可哈希/容器/大对象直接不缓存）；并且 LRU 必须有严格 `max_entries` 上界。
- **[风险] 并行化导致事件顺序/上下文一致性漂移** → **缓解**：复用 overlay + capture + commit；并行任务内部 `parallel_mode='seq'`；主线程确定顺序回放。
- **[权衡] 线程并行对纯 Python CPU-bound 计算收益有限（GIL）** → **缓解**：并行化聚焦 coarse-grained batch call，并把是否启用收敛到 `speed` profile。

## Migration Plan

- 默认无迁移：不修改业务 YAML/代码即可继续运行（`balanced`）。
- batch call（显式 opt-in）：
  - YAML：为目标字段增加 `call_by_mode: batch`。
  - Python：将被引用函数升级为“列式输入 → 列式输出”的实现（或在函数内部自行迭代列）。
- memoize（显式 opt-in + profile 治理）：
  - YAML：为目标字段增加 `call_by_pure: true`（用户承担纯度契约）。
  - 运行时：选择 `speed` profile 或在 profile 配置对象中显式启用 memoize（并设置 `max_entries` 上界）。
- 回滚策略：
  - batch call：移除 `call_by_mode: batch`（恢复 row mode）。
  - memoize/并行：切回 `balanced/memory` profile（或显式关闭对应策略）。

## Open Questions

- **是否需要 batch ctx（阶段 2）进入本次交付**：本变更 v1 计划在 `call_by_mode="batch"` 下编译期禁止 `$ctx`（低内存/低分配 + 语义一致性优先）。
  - 若迁移过程中发现大量 `call_by` 强依赖 `row_id/values` 等上下文信息，优先评估 `openspec/notplan-changes/c0-call-by-multi-output-fusion/` 是否已覆盖“减少 call 次数且保留 row ctx 语义”的需求。
  - 只有在明确需要“列式 batch API + 上下文信息”的场景下，再引入 `BatchComputeCallContextIr` + `$ctx.row_ids`（建议作为独立变更推进，以避免扩大 `c2` 的改动面与风险收敛难度）。
