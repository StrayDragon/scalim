## ADDED Requirements

### Requirement: 扩展可注册 compute/where 的额外函数名与实现
系统 SHALL 允许扩展为安全表达式引擎(`SecureComputeEngine`)注册额外函数(函数名 + Python 实现),使以下表达式可使用这些函数:
- 派生字段 `compute`
- outputs 的 `where`(若使用 compute 表达式形态)

约束:
- 扩展函数注册 MUST 通过 `ExtensionHost` 的编译产物对 validator/compiler/runtime 保持一致(避免 validate/compile/run 漂移)

#### Scenario: compute 表达式可使用扩展函数
- **GIVEN** 扩展注册了函数名 `safe_div`
- **AND** YAML 派生字段包含表达式 `compute: "safe_div(a, b)"`
- **WHEN** 编译并执行该 YAML
- **THEN** 系统 MUST 允许该表达式通过校验与编译,并在执行时使用扩展提供的实现完成求值

#### Scenario: outputs where 可使用扩展函数
- **GIVEN** 扩展注册了函数名 `safe_div`
- **AND** YAML `outputs[0].where: "safe_div(a, b) > 0"`
- **WHEN** 编译并执行该 YAML
- **THEN** 系统 MUST 允许该 where 通过校验与编译(不应因函数名缺失而失败)

### Requirement: compute 依赖推导 MUST 忽略函数名
系统 MUST 在推导 compute/where 的字段依赖时忽略函数名(即 `Call.func`),避免扩展函数名被误判为字段依赖.

#### Scenario: safe_div 不应成为依赖字段
- **GIVEN** 扩展注册了函数名 `safe_div`
- **AND** 表达式为 `safe_div(a, b)`
- **WHEN** 系统推导该表达式的字段依赖
- **THEN** 依赖列表 MUST 仅包含 `a` 与 `b`(不包含 `safe_div`)
