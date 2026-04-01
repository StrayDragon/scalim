## ADDED Requirements

### Requirement: compute 安全引擎 MUST provide a safe `dec(x)` decimal helper
系统 MUST 在 `SecureComputeEngine` 的 builtin functions 中提供 `dec(x)` 作为显式十进制转换入口,并对所有复用该引擎的 YAML 表达式位置保持一致语义。

`dec(x)` MUST 满足:

- 接受 `None` / `bool` / `int` / `float` / `str` / `Decimal`
- 对 `float` MUST 使用 `Decimal(str(x))`,不得使用 `Decimal(x)`
- 对 `Decimal` MUST 原样返回
- 对 `None` MUST 返回 `None`
- 对空白字符串 MUST 返回 `None`
- 对非有限 `float`(`NaN` / `Inf` / `-Inf`)与非法字符串 MUST fail-fast(抛出 `ValueError`)

#### Scenario: dec converts finite float without binary expansion
- **WHEN** 表达式使用 `dec(0.1)`
- **THEN** 结果 MUST 为 `Decimal("0.1")`

#### Scenario: dec rejects invalid decimal text
- **WHEN** 表达式使用 `dec("not-a-number")`
- **THEN** 系统 MUST fail-fast 并报告十进制转换错误

## MODIFIED Requirements

### Requirement: compute 表达式允许使用 `Decimal(...)` 构造器
系统 MUST 在 compute 安全引擎的白名单函数中包含 `Decimal` 与 `dec`,以支持在表达式中使用 `Decimal("0.1")` 或 `dec(0.1)` 等写法显式避免 `float` 精度问题。

#### Scenario: compute 使用 Decimal 字符串字面量
- **WHEN** 派生字段配置 `compute: "Decimal('0.1') + Decimal('0.2')"`
- **THEN** 该表达式校验 MUST 通过且执行结果 MUST 为 `Decimal('0.3')`

#### Scenario: compute 使用 dec helper
- **WHEN** 派生字段配置 `compute: "dec(amount) + dec(tax)"`
- **THEN** 该表达式校验 MUST 通过
- **AND** 运行期 MUST 按 `dec(...)` 的安全十进制语义计算结果

### Requirement: 派生字段执行与错误处理
系统 SHALL 按依赖拓扑顺序计算派生字段;计算异常(TypeError/ValueError/ZeroDivisionError 等)应写入 None 并触发 ErrorEvent.
系统 SHALL 对常量 compute 执行批次内复用: 在单个批次内只计算一次并复用结果,但仍按行触发 FieldComputeEvent/ErrorEvent.
系统 SHALL 保持含依赖或含函数调用的 compute 逐行计算,不使用常量缓存.
系统 MUST 将 `Decimal` 视为顶层派生字段 `compute/call_by` 的合法返回值,并在 runtime 中按 `FieldValue` 继续传递该值。

#### Scenario: 常量表达式复用且逐行触发事件
- **WHEN** compute="1 + 2"
- **THEN** 同一批次内仅计算一次,但每行仍触发 field compute 事件

#### Scenario: 含函数调用或依赖字段不复用
- **WHEN** compute="int(amount)" 或 compute 依赖字段 a
- **THEN** 该字段应按行计算(不缓存)

#### Scenario: top-level compute may return Decimal
- **WHEN** 顶层派生字段 `fields.total.compute` 的运行结果为 `Decimal("0.3")`
- **THEN** 系统 MUST 接受该值
- **AND** 系统 MUST NOT 以“unsupported type”拒绝该结果

#### Scenario: top-level call_by may return Decimal
- **WHEN** 顶层派生字段 `fields.total.call_by` 调用的 Python 函数返回 `Decimal("0.3")`
- **THEN** 系统 MUST 接受该值
- **AND** 系统 MUST NOT 以“unsupported type”拒绝该结果
