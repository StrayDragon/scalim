## MODIFIED Requirements

### Requirement: loader params templates support `{$runtime: <name>}` directives
系统 SHALL 允许在 loader kwargs 模板中声明 `{$init_var: <name>}` 指令节点,并在编译期将其解析为调用方提供的初始化变量.

占位符解析的适用位置为:
- `main_source.params`
- `sources.<id>.params`

#### Scenario: main_source.params 引用 init var
- **WHEN** `main_source.params` 中某个值等于 `{$init_var: end_datetime_user}`
- **AND** 调用方提供 `init_vars={"end_datetime_user": <value>}`
- **THEN** main source loader MUST 接收到解析后的值而不是占位符字符串
