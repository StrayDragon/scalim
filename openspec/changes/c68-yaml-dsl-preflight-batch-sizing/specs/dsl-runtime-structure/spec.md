# dsl-runtime-structure (delta) Specification

## MODIFIED Requirements

### Requirement: runtime 编译链路保持 batch_size 的 None 语义
yaml_dsl runtime compiler MUST 将运行期的 `batch_size` 编译为 `ExecutionRequest.batch_size: Optional[int]`,并保持 `None` 语义可穿透 execution.
编译链路 MUST NOT 使用 truthy fallback(例如 `a or b`)决定 `batch_size`,以避免吞掉显式 `None`.

当需要决定 effective batch_size 时,系统 MUST 使用显式空值判断,并在 `batch_size` 未显式提供时允许通过 policy signal（hook override）推导:

- 若调用方显式提供 `RunOptions(batch_size=<int|None>)`(即不为 `UNSET`),系统 MUST 使用该显式值。
- 否则,系统 MUST 在进入 engine 前发射 `pre_use_batch_size` policy signal,允许 hook 改写候选值并使用其最终结果。
- 若无任何 hook 改写,系统 MUST 使用框架默认/配置候选 `batch_size`。
- `None` 必须被视为合法值并保留给 execution 层解释为 no-chunking。

#### Scenario: explicit None disables chunking and skips policy signal
- **WHEN** 调用方显式传入 `RunOptions(batch_size=None)`
- **THEN** compiler/entrypoint 产出的 `ExecutionRequest.batch_size` MUST 为 `None`
- **AND** 系统 MUST 跳过 `pre_use_batch_size` policy signal

#### Scenario: policy signal override batch_size is used when batch_size is UNSET
- **GIVEN** 调用方未显式提供 `batch_size`(保持为 `UNSET`)
- **WHEN** 某个 hook 在 `pre_use_batch_size` signal 中将候选值改写为 `20000`
- **THEN** 传给 engine 的 `ExecutionRequest.batch_size` MUST 为 `20000`
