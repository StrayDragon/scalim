## ADDED Requirements

### Requirement: Front-end compilation MUST build ExecutionPlan without importing user code

系统 MUST 提供一个编译前端入口（front-end compilation），将单个 demand YAML 编译到：

- diagnostics（errors/warnings，含稳定 path + range）
- 静态 IR（不包含任何 Python callable）
- ExecutionPlan 与依赖索引（可用于“字段上游依赖展开”等 dev features）

编译前端 MUST 满足：

- MUST NOT 导入/执行任何用户模块（仅允许文件系统读取 + YAML/AST 静态解析）。
- MUST NOT 依赖 allowlist（allowlist 仅属于运行时解析与执行边界）。
- MUST 在失败时降级为可诊断结果（不 crash、不退出）。

#### Scenario: a valid demand YAML produces a plan without allowlist

- **GIVEN** 一个语义正确的 demand YAML（包含 sources/fields/relations 等定义）
- **WHEN** 调用编译前端入口生成 `ExecutionPlan`
- **THEN** 系统 MUST 返回 `ExecutionPlan` 与依赖索引
- **AND** MUST 不需要用户提供 allowlist 才能完成编译

### Requirement: Runtime linking (resolution) MUST be the only phase that imports modules and MUST enforce allowlist

系统 MUST 定义一个显式的运行时 linking（解析）步骤，用于把静态引用解析为可调用对象（loader / params_builder / normalize.call_by 等），并满足：

- MUST 仅在运行时 linking（解析）步骤执行模块导入与 callable 解析。
- MUST 在解析时强制执行 allowlist 约束（不允许隐式放宽）。
- MUST 在解析失败时返回可诊断的错误分类（例如 allowlist violation / resolver error），并 fail-fast 于执行之前。

#### Scenario: allowlist violation fails during runtime resolution (before execution)

- **GIVEN** YAML 中存在一个 Python reference 需要解析为 callable
- **AND** 该 reference 不在 allowlist 允许范围内
- **WHEN** 系统执行运行时 linking（解析）步骤
- **THEN** 系统 MUST 失败并给出可诊断的错误信息
- **AND** MUST 不进入执行阶段
