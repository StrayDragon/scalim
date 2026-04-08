## ADDED Requirements

### Requirement: derived field call_by MUST validate argument binding at compile time when possible

当派生字段使用 `call_by: "reference(args...)"` 时,系统 MUST 在编译期执行可推理的参数绑定预检查:

- 系统 MUST 在编译期解析 `call_by` 并解析 `reference` 到具体 callable（受 allowlist/builtin vocabulary 约束）。
- 当 `inspect.signature(reference_callable)` 可用时,系统 MUST 对解析出的 args/kwargs 执行签名绑定校验；绑定失败 MUST 作为编译期错误 fail-fast。
- 当签名不可获取时,系统 MAY 跳过绑定校验,但仍 MUST 保持引用解析与后续运行期错误可观测。

#### Scenario: positional argument to keyword-only signature fails fast
- **GIVEN** `fields._is_valid_group.call_by: "..loaders:is_valid_group(group_name)"`
- **AND** `is_valid_group` 的签名为 `def is_valid_group(*, group_name, **kw): ...`
- **WHEN** 系统编译 demand
- **THEN** 编译 MUST fail-fast 抛出配置/编译错误
- **AND** 错误信息 MUST 指出 keyword-only 不接受位置参数并给出改写提示（例如 `group_name=group_name`）

### Requirement: compute expression builtin calls MUST validate arity when signature is inspectable

系统 MUST 对 `compute` 表达式中的安全内置函数调用（`SecureComputeEngine.SAFE_FUNCTIONS`）执行可推理的“调用形态”预检查:

- 由于表达式已禁止 keyword args,系统至少 MUST 校验位置参数个数是否可绑定到目标函数签名（当 `inspect.signature` 可用时）。
- 当预检查失败时,系统 MUST 在编译期 fail-fast 并将其归类为 compute 编译错误（不得延迟到运行期再被 guardrails 吞掉）。

#### Scenario: compute builtin arity mismatch is rejected early
- **GIVEN** 派生字段配置 `compute: "dec(amount, tax)"`
- **WHEN** 系统编译 demand
- **THEN** 编译 MUST fail-fast 并指出 `dec` 调用参数个数不匹配
