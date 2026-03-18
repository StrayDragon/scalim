# yaml-runtime-vars Specification

**状态: ✅ 已实现**
## Purpose
为 by_yaml runtime 提供编译期的运行期变量注入入口: 调用方通过 `runtime_vars` 注入任意 Python 对象,并在 `main_source.params` / `sources.<id>.params` 的 kwargs 模板中用 `{$runtime: <name>}` 指令节点引用,由 adapter 在编译期解析并透传给 loader.

## Context
YAML DSL 配置常需要把“运行期参数”(例如 end_dt、用户过滤列表、环境开关等)注入到 loader kwargs 中.若无统一入口,调用方需要额外的 runtime wrapper 来拼装参数并调用 `run/compile`,导致重复的 glue code 与迁移成本.

同时,`cache_mode: preload_forever` 的预加载路径必须与常规 loader 调用保持一致的参数语义,避免 preload/ref-load 两套 params 逻辑漂移.

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/entrypoints.py` (`run`, `compile`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/contracts.py` (`RunOptions.runtime_vars`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/compiler.py` (`compile_ir(..., runtime_vars=...)`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/_internal/conversion_sources.py` (compile-time runtime directive resolve + shared template render)
- `src/IMPL_ROOT/dsl/by_yaml/params_template.py` (`$runtime` directive resolve + opaque literal nodes)
## Requirements
### Requirement: by_yaml runtime accepts `runtime_vars` for loader params injection
系统 SHALL 允许 by_yaml `run/compile` 接收可选的 `init_vars: Dict[str, object]`,用于在编译期将初始化变量注入到 loader 参数模板中.

#### Scenario: run 注入 init_vars
- **WHEN** 调用方执行 `run(..., init_vars={"end_dt": <datetime>})`
- **THEN** adapter 编译后的 loader kwargs 模板中允许出现该初始化值,并在 loader 调用时透传

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

### Requirement: substituted runtime values are opaque literals
系统 MUST 将 `{$init_var: <name>}` 替换后的值视为编译期 literal 节点,后续模板处理不得再次按 `"$keys"`/`"$rows"` 的结构长相识别其中内容.

#### Scenario: init var value contains `"$keys"`-shaped mapping
- **WHEN** 调用方提供 `init_vars={"payload": {"$keys": {"as": "set"}}}`
- **AND** `sources.demo.params` 中引用 `{$init_var: payload}`
- **THEN** 编译后的模板 MUST 将该值视为普通 literal dict
- **AND** loader 调用时 MUST 原样透传该 dict
- **AND** 系统 MUST NOT 将其误判为动态指令节点

### Requirement: legacy `{$runtime: <name>}` directive is rejected
系统 MUST 在编译期拒绝 loader params 模板中的 legacy `{$runtime: <name>}` 指令节点,并提示迁移为 `{$init_var: <name>}`.

#### Scenario: `$runtime` directive node fails fast with a migration hint
- **WHEN** `main_source.params` 或 `sources.<id>.params` 中出现 `{$runtime: end_dt}`
- **THEN** 编译 MUST 失败
- **AND** 错误 MUST 指向包含该指令节点的配置路径(例如 `main_source.params.params.pay_end_datetime`)
- **AND** 错误 MUST 提示迁移为 `{$init_var: end_dt}`
