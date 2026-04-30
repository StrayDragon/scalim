# execution-hotpath-fastpaths Specification

## Purpose
在不要求业务改动的前提下，降低 execution 热路径（`compute` / `call_by` / `load_ref`）的 per-row 固定开销，并保持既有语义、可观测性与低内存特性。

## Related Concepts
- `SecureComputeEngine` / `SecureComputeCalculator`
- `DerivedFieldIr.compute_expr` / `DerivedFieldIr.call_by`
- `ComputeCallContextIr`
- execution operators: `compute` / `load_ref`
- guardrails / instrumentation events

## ADDED Requirements

### Requirement: Fastpaths are default-on and behavior-preserving
系统 MUST 默认启用面向执行热路径的 fastpaths，并保持对外语义不变（值、异常、事件顺序/边界）。

#### Scenario: Same inputs yield same outputs
- **WHEN** 使用同一份 `DemandIr`、同一批 main rows 与相同 runtime bindings 执行
- **THEN** 目标字段的值 MUST 与 fastpath 引入前一致
- **AND** 发生错误时抛出的异常类型与错误上下文（字段/行定位）MUST 与 fastpath 引入前一致

### Requirement: Compute evaluation preserves name shadowing semantics
在 `compute` 表达式中，依赖字段名与安全函数名冲突时（例如 `len` / `sum`），系统 MUST 保持“字段值优先”的解析语义不变。

#### Scenario: Field name shadows builtin function name
- **GIVEN** 表达式依赖字段名为 `len`，且表达式引用 `len`
- **WHEN** 运行 `compute` 求值
- **THEN** 求值 MUST 使用字段 `len` 的值而不是安全函数 `len`

### Requirement: Compute audit mode semantics remain unchanged
系统 MUST 保持既有 compute 审计模式语义不变：

- `audit_mode="none"`：不记录字段值/结果
- `audit_mode="redacted"`：仅记录表达式 hash、字段名与结果类型，不记录字段值与结果原文
- `audit_mode="full"`：仅在显式解锁条件满足时启用，并可能记录敏感数据

#### Scenario: Full audit requires explicit unlock
- **WHEN** compute 以 `audit_mode="full"` 初始化且未设置解锁环境变量
- **THEN** 系统 MUST fail-fast 并拒绝启动 full 模式

### Requirement: call_by ctx injection is conditional and minimal
系统 MUST 将 `$ctx` / `$ctx.<attr>` 作为“受控且可选”的上下文注入能力：

- 当 `call_by` 参数中未使用 `$ctx` / `$ctx.<attr>` 时，系统 MUST NOT 要求用户函数接受 `ctx` 参数，也 MUST NOT 在执行期 per-row 构造 ctx 对象。
- 当 `call_by` 参数中使用 `$ctx` / `$ctx.<attr>` 时，系统 MUST 提供 `ComputeCallContextIr`，且仅暴露白名单属性：`row_id` / `batch_num` / `field_id` / `deps` / `values`。

#### Scenario: call_by without ctx does not require ctx argument
- **GIVEN** call_by 仅使用字段参数（不包含 `$ctx`/`$ctx.<attr>`）
- **WHEN** 执行派生字段计算
- **THEN** 用户函数 MUST 可采用不包含 `ctx` 的签名并成功运行

#### Scenario: call_by with ctx receives ComputeCallContextIr
- **GIVEN** call_by 参数包含 `$ctx` 或 `$ctx.<attr>`
- **WHEN** 执行派生字段计算
- **THEN** 系统 MUST 传入 `ctx=ComputeCallContextIr(...)`
- **AND** `ctx.values` MUST 为只读映射（用户侧写入 MUST 失败）

### Requirement: Fastpaths keep memory overhead bounded and non-row-linear
系统 MUST 在默认 fastpath 下保持低内存特性：

- 常驻缓存 MUST 与“字段数/表达式数/批大小”等固定规模相关
- 系统 MUST NOT 引入按 `row_id`/总行数线性增长且跨批/跨 run 存活的额外缓存或索引结构

#### Scenario: No persistent per-row caches are introduced
- **WHEN** 执行处理大量行数据的报表
- **THEN** 执行运行时中 MUST NOT 出现以 `row_id` 为 key 的跨批次常驻缓存结构

