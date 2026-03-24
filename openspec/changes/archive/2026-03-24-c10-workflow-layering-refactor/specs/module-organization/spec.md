## ADDED Requirements

### Requirement: workflow framework MUST NOT import DSL modules
系统 MUST 保持核心层级依赖方向可审计且单向；workflow runtime/framework 层 MUST NOT 反向依赖 DSL 层实现符号（例如 `IMPL_ROOT.dsl.by_yaml` 及其子模块）。

该约束 MUST 由自动化门禁守护（例如 pytest 的 AST 扫描 + 文本扫描等价工具）,并在回归时 fail-fast。

补充约束: workflow 层 MUST NOT 通过动态导入绕开该限制（例如 `importlib.import_module("...dsl...")` 或等价字符串导入）。

#### Scenario: workflow does not import dsl
- **WHEN** 运行模块依赖方向检查
- **THEN** 结果 MUST 不出现 `workflow -> dsl` 的反向依赖
- **AND** 结果 MUST 不出现通过动态导入引入 `dsl` 的行为
