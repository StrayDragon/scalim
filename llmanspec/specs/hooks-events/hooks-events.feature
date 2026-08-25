# language: zh-CN
# capability: hooks-events
# purpose: 定义 hooks 和事件系统的事件类型和策略决策信号规范,包括 loader retry 事件和 policy decision signals。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: hooks-events

  @req:r55 @human
  场景: 新增 `loader_retry` 事件用于观测重试尝试
    - 系统 SHALL 新增事件类型 `loader_retry`,用于表达"某次 loader 调用失败且系统决定按 policy 重试". 系统 MUST 在每次 retry runner 决定进入 sleep+下一次尝试之前发出该事件. 系统 MUST NOT 将每次可重试失败当作 `error` 事件;`error` 事件仅用于最终失败(不再重试)或不可重试错误. `loader_retry` payload MUST 至少包含: - `loader_name`(或 `source_id`,两者语义等价) - `callsite`(load/load_ref/preload_forever/main_source 或等价枚举) - `attempt_num`、`max_attempts` - `elapsed_seconds` - `sleep_seconds`(下一次尝试前的等待时长) - `error_type`(异常类型名)与可选的截断 `error_message`

  @req:r299 @human
  场景: runtime MUST emit policy decision signals that hooks can override (pre-run_ir)
    - 系统 MUST 支持一类 "policy decision signals"（不同于纯观测事件），用于在进入 `run_ir()` 之前允许 hook 改写候选 runtime policy 值。 v0 MUST 提供 `pre_use_batch_size` signal，并满足： - 触发时机：MUST 位于 compile 产物就绪之后、调用 `run_ir()` 之前（standalone demand 与 workflow per-run 一致）。 - 生效条件：仅当调用方未显式设置 `batch_size` 时才触发（例如 `RunOptions.batch_size is UNSET` 且 workflow per-run patch 未覆盖）。 - 跳过规则：当调用方显式提供 `RunOptions(batch_size=<int|None>)` 或 workflow per-run patch 显式提供 `batch_size=<int|None>` 时，系统 MUST 跳过该 signal（不得发射；不得执行任何额外预检 I/O）。 - 组合语义：signal MUST 以确定性顺序依次分发给 hooks（按 `components` 注册顺序）。 - 改写语义：payload MUST 为一个可改写的 decision 对象，至少包含： - 当前候选 `value: Optional[int]` - `override(next_value, reason=...)`（用于 hook 改写值） - `history`（记录改写历史，至少包含 hook 标识与原因） - 结果注入：signal 分发完成后，系统 MUST 使用 decision 的最终 `value` 更新传给 engine 的 `ExecutionRequest.batch_size`。 **Note:** 为避免破坏既有 "订阅全部事件的 on_event hooks"，policy decision signals SHOULD 采用 typed dispatch（例如 `on_pre_use_batch_size`）或其它 opt-in 机制；不得默认广播给所有 `on_event` 订阅者。

  @req:r933 @human
  场景: Event envelope event_type MUST be EventType
    - 系统 MUST 使进程内 `Event.event_type` 的类型与运行时值为 `EventType`。构造/emit 路径 MUST 写入 `EventType` 成员。系统 MUST NOT 将进程内 envelope 身份长期表示为作者面 `str`。若存在 `to_dict` 或等价序列化辅助，其输出 MAY 使用 builtin `str`（`.value`），但反序列化回 `Event` 时 MUST 恢复为 `EventType`。

  @req:r934 @human
  场景: New event kinds MUST extend EventType catalog
    - 系统在新增可订阅事件种类时 MUST 向 `EventType`（及事件目录）登记稳定成员，并保持成员取值字符串稳定除非显式 breaking。Hook 与 Observer 的 typed dispatch 映射 MUST 以 `EventType` 成员为键对齐目录，避免并行维护第二套字符串闭集。
  @req:r55 @human
  场景: 可重试失败触发-loader-retry-而非-error
    - 必须成立：当 loader 抛出异常且 `should_retry` 返回 true 且未超过上限；那么 系统 MUST 发出一次 `loader_retry` 事件并进入 sleep+重试
    当 loader 抛出异常且 `should_retry` 返回 true 且未超过上限
    那么 系统 MUST 发出一次 `loader_retry` 事件并进入 sleep+重试
  @req:r299 @human
  场景: explicit-batch-size-skips-policy-signal
    - 必须成立：当 调用方显式传入 `RunOptions(batch_size=8000)`；那么 系统 MUST NOT 发射 `pre_use_batch_size`
    当 调用方显式传入 `RunOptions(batch_size=8000)`
    那么 系统 MUST NOT 发射 `pre_use_batch_size`

  @req:r299 @human
  场景: hook-override-takes-effect-when-batch-size-is-unset
    - 必须成立：假如 调用方未显式提供 `batch_size`（保持为 `UNSET`）；当 某个 hook 在 `pre_use_batch_size` 中调用 `override(20000, reason=...)`；那么 传给 engine 的 `ExecutionRequest.batch_size` MUST 为 `20000`
    假如 调用方未显式提供 `batch_size`（保持为 `UNSET`）
    当 某个 hook 在 `pre_use_batch_size` 中调用 `override(20000, reason=...)`
    那么 传给 engine 的 `ExecutionRequest.batch_size` MUST 为 `20000`

  @req:r299 @human
  场景: multiple-hooks-override-in-deterministic-order
    - 必须成立：假如 调用方未显式提供 `batch_size`；当 hook A `override(8000, reason="A")` 且 hook B `override(10000, reason="B")`；那么 最终 `ExecutionRequest.batch_size` MUST 为 `10000`
    假如 调用方未显式提供 `batch_size`
    当 hook A `override(8000, reason="A")` 且 hook B `override(10000, reason="B")`
    那么 最终 `ExecutionRequest.batch_size` MUST 为 `10000`

  @req:r933 @human
  场景: envelope-holds-enum
    - 必须成立：当 执行层经 hub emit 一条已知目录事件；那么 进程内 `Event.event_type` MUST 为对应 `EventType` 成员
    当 执行层经 hub emit 一条已知目录事件
    那么 进程内 `Event.event_type` MUST 为对应 `EventType` 成员

  @req:r933 @human
  场景: reject-str-as-envelope-identity
    - 必须成立：当 测试或调用方试图以裸 `str` 作为进程内 `Event.event_type` 的长期作者面；那么 类型检查与/或运行时校验 MUST 将其视为不合规（实现至少在公开构造/校验路径 fail-fast 或静态类型拒绝）
    当 测试或调用方试图以裸 `str` 作为进程内 `Event.event_type` 的长期作者面
    那么 类型检查与/或运行时校验 MUST 将其视为不合规（实现至少在公开构造/校验路径 fail-fast 或静态类型拒绝）

  @req:r934 @human
  场景: new-event-updates-catalog
    - 必须成立：当 框架新增一种可订阅事件；那么 MUST 新增 `EventType` 成员与目录条目，且 hooks/ob dispatch 映射引用该成员
    当 框架新增一种可订阅事件
    那么 MUST 新增 `EventType` 成员与目录条目，且 hooks/ob dispatch 映射引用该成员

  @req:r934 @human
  场景: no-parallel-str-closed-set
    - 必须成立：当 审阅 hooks/ob 事件闭集定义；那么 MUST NOT 在 `EventType` 之外再手工维护一份并行的作者面字符串闭集作为 SSOT
    当 审阅 hooks/ob 事件闭集定义
    那么 MUST NOT 在 `EventType` 之外再手工维护一份并行的作者面字符串闭集作为 SSOT
