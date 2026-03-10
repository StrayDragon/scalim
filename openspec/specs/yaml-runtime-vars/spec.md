# yaml-runtime-vars Specification

**状态: ✅ 已实现**
## Purpose
为 by_yaml runtime 提供编译期的运行期变量注入入口: 调用方通过 `runtime_vars` 注入任意 Python 对象,并在 `main_source.params` / `sources.<id>.params` 的 kwargs 模板中用 `$runtime.<name>` 占位符引用,由 adapter 在编译期解析并透传给 loader.

## Context
YAML DSL 配置常需要把“运行期参数”(例如 end_dt、用户过滤列表、环境开关等)注入到 loader kwargs 中.若无统一入口,调用方需要额外的 runtime wrapper 来拼装参数并调用 `run/compile`,导致重复的 glue code 与迁移成本.

同时,`cache_mode: preload_forever` 的预加载路径必须与常规 loader 调用保持一致的参数语义,避免 preload/ref-load 两套 params 逻辑漂移.

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/entrypoints.py` (`run`, `compile`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/contracts.py` (`RunOptions.runtime_vars`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/compiler.py` (`compile_ir(..., runtime_vars=...)`)
- `src/IMPL_ROOT/dsl/by_yaml/runtime/_internal/conversion_sources.py` (compile-time placeholder resolve + shared template render)
- `src/IMPL_ROOT/dsl/by_yaml/params_template.py` (`$runtime.*` resolve + opaque literal nodes)
## Requirements
### Requirement: by_yaml runtime accepts `runtime_vars` for loader params injection
系统 SHALL 允许 by_yaml `run/compile` 接收可选的 `runtime_vars: Dict[str, object]`,用于在编译期将运行期变量注入到 loader 参数模板中.

#### Scenario: run 注入 runtime_vars
- **WHEN** 调用方执行 `run(..., runtime_vars={"end_dt": <datetime>})`
- **THEN** adapter 编译后的 loader kwargs 模板中允许出现该运行期值,并在 loader 调用时透传

### Requirement: `$runtime.<name>` placeholder resolves in loader params templates
系统 SHALL 在编译期解析 loader 参数模板中的 `$runtime.<name>` 占位符:
- 解析范围仅包含 `main_source.params` 与 `sources.<id>.params`
- 仅当某个 YAML scalar string 的值 **完全等于** `$runtime.<name>` 时触发替换
- 替换结果为 `runtime_vars[<name>]` 的值(可为任意 Python 对象)

#### Scenario: main_source.params 占位符被解析
- **WHEN** `main_source.params` 包含 `{"params": {"pay_end_datetime": "$runtime.end_dt"}}`
- **AND** 调用方提供 `runtime_vars={"end_dt": <datetime>}`
- **THEN** main source loader MUST 接收到 `params={"pay_end_datetime": <datetime>}` 的 kwargs

#### Scenario: sources.<id>.params 占位符被解析
- **WHEN** `sources.custom_services.params` 包含 `{"params": {"exclude_user_ids": "$runtime.excluded"}}`
- **AND** 调用方提供 `runtime_vars={"excluded": ["1001", "1002"]}`
- **THEN** 该 source 的 loader 调用 MUST 接收到 `params={"exclude_user_ids": ["1001", "1002"]}` 的 kwargs

#### Scenario: 不做字符串子串插值
- **WHEN** `main_source.params` 包含 `{"sql": "and t > $runtime.end_dt"}`
- **AND** 调用方提供 `runtime_vars={"end_dt": "..."}`
- **THEN** adapter MUST NOT 将该字符串做子串替换(值保持原样字符串)

### Requirement: missing runtime var fails fast with a config path
系统 MUST 在编译期对 `$runtime.<name>` 引用缺失执行 fail-fast,并在错误中报告明确的配置路径.

#### Scenario: runtime_vars 缺失导致编译失败
- **WHEN** 配置中出现 `$runtime.end_dt`
- **AND** 调用方未提供 `runtime_vars` 或不包含 key `end_dt`
- **THEN** 编译 MUST 失败
- **AND** 错误 MUST 指向包含该占位符的配置路径(例如 `main_source.params.params.pay_end_datetime`)

### Requirement: substituted runtime values are opaque literals
系统 MUST 将 `$runtime.<name>` 替换后的值视为编译期 literal 节点,后续模板处理不得再次按 `"$keys"`/`"$rows"` 的结构长相识别其中内容.

#### Scenario: runtime var value contains `"$keys"`-shaped mapping
- **WHEN** 调用方提供 `runtime_vars={"payload": {"$keys": {"as": "set"}}}`
- **AND** `sources.demo.params` 中引用 `$runtime.payload`
- **THEN** 编译后的模板 MUST 将该值视为普通 literal dict
- **AND** loader 调用时 MUST 原样透传该 dict
- **AND** 系统 MUST NOT 将其误判为动态指令节点

