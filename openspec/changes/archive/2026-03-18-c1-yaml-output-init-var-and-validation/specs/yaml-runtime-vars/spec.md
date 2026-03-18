## MODIFIED Requirements

### Requirement: `{$runtime: <name>}` directive resolves in loader params templates
系统 SHALL 在编译期解析 loader 参数模板中的 `{$init_var: <name>}` 指令节点:
- 解析范围包含:
  - `main_source.params`
  - `sources.<id>.params`
  - `outputs.*.container.path`
- 替换结果为 `init_vars[<name>]` 的值(可为任意 Python 对象;对 path 场景最终 MUST 可被解析为非空字符串)

#### Scenario: main_source.params 指令节点被解析
- **WHEN** `main_source.params` 包含 `{"params": {"pay_end_datetime": {"$init_var": "end_dt"}}}`
- **AND** 调用方提供 `init_vars={"end_dt": <datetime>}`
- **THEN** main source loader MUST 接收到 `params={"pay_end_datetime": <datetime>}` 的 kwargs

#### Scenario: sources.<id>.params 指令节点被解析
- **WHEN** `sources.custom_services.params` 包含 `{"params": {"exclude_user_ids": {"$init_var": "excluded"}}}`
- **AND** 调用方提供 `init_vars={"excluded": ["1001", "1002"]}`
- **THEN** 该 source 的 loader 调用 MUST 接收到 `params={"exclude_user_ids": ["1001", "1002"]}` 的 kwargs

#### Scenario: outputs.container.path 指令节点被解析
- **WHEN** `outputs[0].container.path` 等于 `{$init_var: output_path}`
- **AND** 调用方提供 `init_vars={"output_path": "./output/report.xlsx"}`
- **THEN** 编译后的输出规范 MUST 使用 `"./output/report.xlsx"` 作为最终输出路径

#### Scenario: 不做字符串子串插值
- **WHEN** `main_source.params` 包含 `{"sql": "and t > $init_var.end_dt"}`
- **AND** 调用方提供 `init_vars={"end_dt": "..."}`
- **THEN** adapter MUST NOT 将该字符串做子串替换(值保持原样字符串)

### Requirement: missing runtime var fails fast with a config path
系统 MUST 在编译期对 `{$init_var: <name>}` 引用缺失执行 fail-fast,并在错误中报告明确的配置路径.

#### Scenario: init_vars 缺失导致编译失败
- **WHEN** 配置中出现 `{$init_var: end_dt}`
- **AND** 调用方未提供 `init_vars` 或不包含 key `end_dt`
- **THEN** 编译 MUST 失败
- **AND** 错误 MUST 指向包含该指令节点的配置路径(例如 `main_source.params.params.pay_end_datetime`)

#### Scenario: outputs.container.path 缺失导致编译失败
- **WHEN** `outputs[0].container.path` 等于 `{$init_var: output_path}`
- **AND** 调用方未提供 `init_vars` 或不包含 key `output_path`
- **THEN** 编译 MUST 失败
- **AND** 错误 MUST 指向 `outputs.0.container.path`

