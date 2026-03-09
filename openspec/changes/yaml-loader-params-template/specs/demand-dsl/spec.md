## ADDED Requirements

### Requirement: loader params templates support `$runtime.*` placeholders
系统 SHALL 允许在 loader 参数模板中声明 `$runtime.<name>` 占位符,并在编译期将其解析为调用方提供的运行期变量.

占位符解析的适用位置为:
- `main_source.params`
- `sources.<id>.params`

#### Scenario: main_source.params 引用 runtime var
- **WHEN** `main_source.params` 中某个值等于 `$runtime.end_datetime_user`
- **AND** 调用方提供 `runtime_vars={"end_datetime_user": <value>}`
- **THEN** main source loader MUST 接收到解析后的值而不是占位符字符串

