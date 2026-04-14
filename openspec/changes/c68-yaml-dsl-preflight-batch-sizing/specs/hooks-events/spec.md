# hooks-events (delta) Specification

## ADDED Requirements

### Requirement: runtime MUST emit policy decision signals that hooks can override (pre-run_ir)

系统 MUST 支持一类 “policy decision signals”（不同于纯观测事件），用于在进入 `run_ir()` 之前允许 hook 改写候选 runtime policy 值。

v0 MUST 提供 `pre_use_batch_size` signal，并满足：

- 触发时机：MUST 位于 compile 产物就绪之后、调用 `run_ir()` 之前（standalone demand 与 workflow per-run 一致）。
- 生效条件：仅当调用方未显式设置 `batch_size` 时才触发（例如 `RunOptions.batch_size is UNSET` 且 workflow per-run patch 未覆盖）。
- 跳过规则：当调用方显式提供 `RunOptions(batch_size=<int|None>)` 或 workflow per-run patch 显式提供 `batch_size=<int|None>` 时，系统 MUST 跳过该 signal（不得发射；不得执行任何额外预检 I/O）。
- 组合语义：signal MUST 以确定性顺序依次分发给 hooks（按 `components` 注册顺序）。
- 改写语义：payload MUST 为一个可改写的 decision 对象，至少包含：
  - 当前候选 `value: Optional[int]`
  - `override(next_value, reason=...)`（用于 hook 改写值）
  - `history`（记录改写历史，至少包含 hook 标识与原因）
- 结果注入：signal 分发完成后，系统 MUST 使用 decision 的最终 `value` 更新传给 engine 的 `ExecutionRequest.batch_size`。

**Note:** 为避免破坏既有 “订阅全部事件的 on_event hooks”，policy decision signals SHOULD 采用 typed dispatch（例如 `on_pre_use_batch_size`）或其它 opt-in 机制；不得默认广播给所有 `on_event` 订阅者。

#### Scenario: explicit batch_size skips policy signal
- **WHEN** 调用方显式传入 `RunOptions(batch_size=8000)`
- **THEN** 系统 MUST NOT 发射 `pre_use_batch_size`
- **AND** 传给 engine 的 `ExecutionRequest.batch_size` MUST 为 `8000`

#### Scenario: hook override takes effect when batch_size is UNSET
- **GIVEN** 调用方未显式提供 `batch_size`（保持为 `UNSET`）
- **WHEN** 某个 hook 在 `pre_use_batch_size` 中调用 `override(20000, reason=...)`
- **THEN** 传给 engine 的 `ExecutionRequest.batch_size` MUST 为 `20000`

#### Scenario: multiple hooks override in deterministic order
- **GIVEN** 调用方未显式提供 `batch_size`
- **AND** hook A 先注册，hook B 后注册
- **WHEN** hook A `override(8000, reason="A")` 且 hook B `override(10000, reason="B")`
- **THEN** 最终 `ExecutionRequest.batch_size` MUST 为 `10000`
- **AND** decision.history MUST 记录 A 与 B 的改写历史

