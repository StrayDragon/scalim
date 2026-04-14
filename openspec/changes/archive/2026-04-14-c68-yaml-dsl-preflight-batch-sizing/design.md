## Context

当前 YAML DSL 将 `batch_size` 明确定位为 runtime policy：必须通过 Python runtime entrypoints 注入（`RunOptions` / workflow per-run patch），且 YAML 主线 authoring surface 不能声明 `batch_size`（`yaml-dsl-runtime-policy-boundary`）。

真实 workflow 中最优 batch sizing 与以下因素强相关：

- main source 总行数（决定批次数上界与调度开销）
- 关联 source 的数量与类型（per-batch `$keys` 查询的固定开销 vs `preload_forever` 的零批开销）
- 行宽与聚合复杂度（影响 batch 内内存峰值与计算局部性）

但 scalim 核心无法在不执行 loader 的情况下泛化得到总行数：`main_source.loader` 返回的是通用 `Iterable`/generator，不保证 `len()`，也不保证可重复迭代；若强行物化会破坏 streaming 与内存边界。

调用侧（Python 入口）通常可以做到“轻量预检”：例如针对同一窗口执行一次 `COUNT(*)` 或 estimate 查询来估算 `total_rows`，并据此选择 `batch_size`。问题在于：如果每次都在入口脚本里写 run_id → batch_size 映射，就会变成难维护的硬编码；如果把策略塞回 YAML，又违背 runtime-policy boundary，并引入 schema/LSP 维护负担。

因此，本设计放弃 “knob patch/合并” 的抽象，改为扩展既有 hooks/events：引入一个 **policy signal（decision event）** 机制，在进入 `run_ir()` 之前发射 `pre_use_batch_size` 信号，由 hook 捕获并改写候选值，从而把 “预检/估算/策略” 收敛为可组合的 Python hook。

## Goals / Non-Goals

**Goals:**
- 不新增任何 YAML authoring 字段（保持 runtime policy boundary 与 YAML schema 稳定）。
- 在 standalone demand 与 workflow per-run 都提供一个稳定的 pre-run_ir 阶段点，可用于 debug、诊断与 policy 注入。
- v0 仅落地 `pre_use_batch_size` policy signal；设计上为 `max_workers`、`lookup_chunk_size` 等后续扩展预留一致模式。
- 显式 runtime policy 的优先级保持最高：调用方显式设置 `batch_size` 时 MUST 跳过 signal（不执行任何额外 I/O）。
- 组合性：多个 hook 可以按确定性顺序依次处理同一 signal，并能观察到前序改写结果（类似 middleware）。

**Non-Goals:**
- v0 不做运行中动态调整 batch_size（需要重构 pipeline 的切块策略与状态机）。
- v0 不要求 scalim 核心自动推断 total_rows（不做 DB introspection / 不扫描全量 main rows）；total_rows 的获取仍由 hook 决定是否执行 I/O。
- v0 不把 “策略语法” 下沉到 YAML（避免 schema/LSP 与 authoring surface 膨胀）。

## Decisions

### 1) Policy signal：`pre_use_batch_size`（decision event + hook override）

在进入 `run_ir()` 之前，框架发射一个 “即将使用 batch_size” 的 signal：

- 名称：`pre_use_batch_size`
- 触发条件：仅当 effective `batch_size` 未被调用方显式设置时（详见 precedence）
- 处理方式：按 `components` 中 hook 的注册顺序依次调用；hook 可改写候选值

这不是 “观测事件”（observability），而是 “决策事件”（policy）。它的 payload 是一个可改写对象（decision），用于在 hook 之间传递当前候选值与改写历史。

### 2) Trigger point：pre-run_ir，且 compile() 仍保持纯编译

为保证 `compile(...)` 仍是纯编译产物（不触发任何外部 I/O），policy signal 的执行点必须位于 runtime entrypoints：

- standalone demand：`run()` 在 `_compile(...)` 之后、调用 `run_ir(...)` 之前发射 policy signal，并把最终值写入传给 engine 的 `ExecutionRequest`（通过 `replace(request, batch_size=...)` 或等价方式）。
- workflow：每个 node 在 runtime compile 得到 `Compilation` 之后、该 node 进入 `run_ir` 之前发射 policy signal（per-run 具备独立上下文与 per-run patch 口径）。

该阶段点既满足 “进入 engine 前可 debug”，也避免污染 validate/compile-only 流程。

### 3) Precedence：显式 batch_size 时跳过 signal（不执行预检 I/O）

Precedence（高→低）：

1. 调用方显式提供 `RunOptions(batch_size=<int|None>)`（即不为 `UNSET`）
2. workflow per-run patch 显式提供 `batch_size=<int|None>`
3. default/config 候选值 + `pre_use_batch_size` signal 经 hook 改写后的结果

规则：
- 当 1/2 生效时，框架 MUST 跳过 `pre_use_batch_size`（不发射 signal；也不应执行任何预检 I/O）。
- `None` 必须被视为合法显式值：表示 no-chunking，并同样跳过 signal。

### 4) Decision payload：可改写 + 可诊断（history）

`pre_use_batch_size` 的 payload 需要同时满足：
- 可改写：hook 能把候选值从 `5000` 改为 `8000` 或 `None`
- 可诊断：能在 pre-run_ir 阶段输出 “为什么最终是 8000”（来源、原因、策略输入）

建议 payload 提供（概念上）：
- `value`: 当前候选 `Optional[int]`
- `override(value, *, reason: str)`: 改写值并记录原因
- `history`: 记录每次改写（hook 名称、原值→新值、reason）
- `context`: run_id / yaml_path / demand 结构摘要（用于 debug）

注：具体字段名可以按代码风格调整；设计重点是 “可改写 + 有可解释历史”。

### 5) 错误语义：policy signal 默认 fail-fast；需要容错时由 hook 自己吞异常

policy signal 的目标是改变行为；若 hook 在此阶段抛出异常，吞掉异常会导致 “策略未生效但用户不知情”。

因此建议：
- policy signal 默认 fail-fast：任意 handler 异常直接终止本次 run（更符合直觉）。
- 若调用侧需要 “warn-and-skip 并回退默认值”，应在 hook 内部捕获异常并自行记录 warning（例如通过日志或 `DiagnosticWarningEvent`）。

### 6) 扩展路径：更多 pre_use_* signals，而不是引入通用 knob patch

后续若需要在同一阶段注入更多 runtime policy，可采用同一模式新增 signals：
- `pre_use_max_workers`（候选值来自 `RunOptions.max_workers`；可能需要补充“显式 vs 默认”的判定约定，例如 `0` 视作 auto/unset）
- `pre_use_lookup_chunk_size`（更可能是 per-source signal；需要明确是改写 config/IR 还是 executor 层使用值）

关键原则：
- 每个 signal 对应一个明确语义点（“即将使用某个值”）
- 改写的目标对象明确（`ExecutionRequest` 字段或某个 source/operator 的参数）
- 不引入 “通用 patch 合并” 的复杂冲突规则；组合性来自 hook 顺序与 decision.history

## Example (concept)

Python 侧挂载 hook（仅示意）：

- hook 里执行一次轻量 `COUNT(*)` 得到 `total_rows`
- 按策略（例如 max_batches=10 + clamp）推导 batch_size
- `event.override(...)` 写回

该 hook 可被 workflow 全局挂载，也可通过 workflow per-run patch 的 `components` 机制只对特定 run 生效。

## Risks / Trade-offs

- **[可预测性]** 多个 hook 都可能改写同一 decision，顺序影响结果  
  缓解：定义确定性顺序（按注册顺序），并记录 decision.history；必要时在调试模式中输出完整 history。

- **[额外 I/O 开销]** 如果 hook 做 COUNT/estimate，会增加一次 DB 查询  
  缓解：显式 batch_size 时跳过 signal；hook 可做缓存/dedupe；并通过 history/日志可见化成本。

- **[边界清晰度]** 观测事件 vs 决策事件可能被混用  
  缓解：明确命名 `pre_use_*`，并把它们定位为 policy signals；对外文档强调 “只有这些事件允许改写 payload”。

## Open Questions

- policy signal 是否需要独立于现有 HookManager 的异常处理策略（目前 hooks 默认吞异常并 warning；policy signal 更适合 fail-fast）？
- 对 `max_workers` 这类非三态字段，如何在不破坏现有契约的情况下表达 “显式设置 vs 默认/auto”？
- 是否要提供一个内置的参考 hook（例如基于 loader 协议自动调用 `count_*`）作为最佳实践模板？

