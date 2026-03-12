## ADDED Requirements

### Requirement: YAML 支持多输出编排 `outputs`
系统 SHALL 允许在 demand YAML 中声明多个输出目标 `outputs`,用于同一份明细流的多 sheet 分发与派生汇总.

#### Scenario: 多 sheet 分发 + 汇总 sheet
- **GIVEN** 用户在同一个 YAML 中声明多个 outputs
- **WHEN** 两个明细 outputs 通过 `where` 进行分发过滤并写入同一 workbook 的不同 sheet
- **AND** 一个汇总 output 通过 `aggregate` 在同一份明细流上声明派生汇总并写入汇总 sheet
- **THEN** schema 校验 MUST 通过且运行时装配 MUST 生成等价的 `OutputCompositionSpec`(包含明细 targets 与派生汇总 derived targets)

### Requirement: `outputs.*.from` 复用与覆盖
系统 MUST 支持 `outputs.*.from` 复用另一个 output 的字段集合与容器配置,并允许在当前 output 上覆盖 `where`/sheet 名称/汇总配置等.

#### Scenario: `from` 继承字段集合
- **GIVEN** `outputs.base` 声明字段集合与 workbook 容器
- **WHEN** `outputs.daily` 设置 `from: base` 并追加自身的 `where`
- **THEN** `outputs.daily` MUST 继承 `outputs.base` 的字段集合并仅改变自身覆盖项

### Requirement: `where` 过滤表达式的安全边界与依赖注入
系统 MUST 将 `where` 视为受限的安全表达式,并在编译期静态分析其依赖字段,将依赖显式注入到执行层(required fields),避免隐式取值为 `None` 的口径偏差.

#### Scenario: `where` 依赖字段未声明时 fail-fast
- **GIVEN** `where` 表达式依赖字段 `channel`
- **WHEN** `channel` 无法解析为 demand 的已定义字段(field_id)因而无法注入到 required fields
- **THEN** 编译期校验 MUST 失败并提示补齐字段定义/引用
