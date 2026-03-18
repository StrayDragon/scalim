## ADDED Requirements

### Requirement: schema 覆盖 `outputs.*.container.path` 的 `{$init_var: <name>}` 语法
系统 MUST 在 YAML DSL JSON Schema 中对 `outputs.*.container.path` 支持以下两种写法:
- 静态路径字符串: `./output/report.xlsx`
- 运行时注入指令节点: `{$init_var: output_path}`

其中 `{$init_var: <name>}` 在 schema 层的结构 MUST 满足:
- YAML 值为 object(mapping)
- object MUST 仅包含 key `"$init_var"`
- `"$init_var"` 的 value MUST 为非空字符串
- object MUST `additionalProperties=false`

#### Scenario: `outputs.*.container.path` oneOf 接受 string 或 init_var object
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `outputs.*.container.path` MUST 通过 `oneOf` 接受 string 或 `{$init_var: <name>}` object

#### Scenario: schema hover 明确范围与非插值语义
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `outputs.*.container.path` 的 `markdownDescription` MUST 明确:
  - `{$init_var: <name>}` 是对象节点(不是字符串插值)
  - 该指令节点仅在编译期解析一次,并替换为调用方提供的 `init_vars[<name>]`
