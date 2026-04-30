# execution-structure Specification (Delta)

## Purpose
补充 execution 结构性约束：允许在保持语义不变的前提下对 operator 热路径进行性能重写，并明确“默认更快且几乎不增加内存”的边界要求。

## ADDED Requirements

### Requirement: Operator hotpath rewrites are allowed but must be behavior-equivalent
系统 MUST 允许对 execution operator 的内部 hotpath 进行等价性能重写（例如 fastpath），但 MUST 保持：

- 输出值语义一致
- 异常语义一致（异常类型与字段/行定位）
- 可观测性事件边界与顺序一致（阶段 span、field 事件、diagnostic 事件等）

#### Scenario: Hotpath rewrite preserves semantics and events
- **WHEN** execution operator（`compute`/`load_ref` 等）内部实现被替换为 fastpath
- **THEN** 相同输入下的输出值 MUST 与替换前一致
- **AND** 事件序列（相同观测开关配置下）MUST 与替换前保持一致

### Requirement: Performance-oriented caches must be bounded and low-memory by default
当 execution 引入用于性能的内部缓存/预绑定结构（例如预编译表达式、预绑定 getter、预计算写回计划）时，系统 MUST 满足：

- 缓存大小 MUST 有明确上界，且与“字段/表达式/批大小”相关
- 默认路径 MUST NOT 引入与“总行数/row_id 数量”线性增长且跨批/跨 run 常驻的缓存
- 任何会引入显著内存增幅的策略 MUST 通过显式配置（例如后续的 profile/options）才能启用

#### Scenario: Default execution does not create row-linear persistent caches
- **WHEN** 默认配置下处理大量行数据
- **THEN** 执行运行时中 MUST NOT 出现以 `row_id` 为 key 的跨批次常驻缓存结构

