## Context

当前 by_yaml runtime 只支持用 `RunOverrides` 覆盖 `output/viz` 等运行策略,但没有“把运行期变量注入到 loader 参数模板”的入口.
这导致调用方需要额外包一层 runtime wrapper 来拼装参数并调用 `run/compile`.

此外,`cache_mode: preload_forever` 的预加载路径当前会以零参调用 loader,并忽略 `sources.<id>.params`:
即使配置中声明了静态 preload 参数(例如 `group_by=...`),也无法透传给 loader,从而迫使业务侧继续写薄 wrapper.

约束:
- by_yaml runtime 必须保持“纯 adapter/编译器”定位,不引入任意 Python 执行或自定义 params_builder.
- 运行时兼容 Python 3.6.
- YAML `params` 允许放入任意静态结构,运行期注入值可能是 `datetime`、列表等非 JSON 类型(来自 Python 调用方).

## Goals / Non-Goals

**Goals:**
- 允许 Python 调用方提供 `runtime_vars: Dict[str, object]` 并在编译期注入到 loader 参数模板中.
- 支持在 `main_source.params` 与 `sources.<id>.params` 中用 `$runtime.<name>` 占位符引用运行期变量.
- 让 `preload_forever` 预加载调用与常规 loader 调用保持一致: 预加载时也透传 `sources.<id>.params`.
- 缺失 runtime var 时 fail-fast,并给出明确配置路径.

**Non-Goals:**
- 不在本 change 中讨论/落地 nested params 的 keys/rows 绑定语法与更通用的 declarative params builder.
- 不在本 change 中引入 result_adapter/loader.extractor 的 YAML 入口.
- 不在本 change 中推进多输出/多 sheet.

## Decisions

### Decision: Add `runtime_vars` to by_yaml run/compile as compile-time input

在 `IMPL_ROOT.dsl.by_yaml.runtime.entrypoints.run/compile` 与 `RunOptions` 中新增可选字段:
- `runtime_vars: Optional[Dict[str, object]]`

理由:
- `runtime_vars` 影响的是“配置到 IR 的编译结果”(loader kwargs 模板),属于编译输入,不属于 output/viz overrides.
- 放入 `RunOptions` 可复用现有 compiler stage 链路,保持 runtime 结构一致.

备选方案:
- 把 runtime vars 放进 `RunOverrides`

拒绝原因:
- overrides 语义是“mask 覆盖 YAML 输出与 viz 等运行策略”,而 runtime vars 是配置模板注入,不应混入 overrides.

### Decision: Placeholder substitution is exact-match and restricted to loader params templates

占位符语法:
- 仅当某个 YAML scalar string 的值 **完全等于** `$runtime.<name>` 时才触发替换.
- `<name>` 视为简单标识符,用于从 `runtime_vars[name]` 取值.

替换范围:
- `main_source.params` 递归遍历字典/列表并替换值
- `sources.<id>.params` 递归遍历字典/列表并替换值

不做的事情:
- 不支持在字符串中做子串插值(例如 `"and t > $runtime.end_dt"`),避免误伤 SQL/模板文本.
- 不在其它字段(例如 `output.path`, `compute`)中启用 `$runtime.*`.

缺失行为:
- 若配置引用 `$runtime.<name>` 但 `runtime_vars` 缺失或不包含该 key,编译 MUST fail-fast 并报告路径(例如 `main_source.params.params.pay_end_datetime`).

### Decision: Apply runtime substitution after YAML parsing/validation and before IR conversion

链路位置:
1. `load_config(yaml_path)` 得到 `DemandConfig`
2. 对 `DemandConfig.main_source.params` 与 `DemandConfig.sources[*].params` 执行占位符替换
3. `compile_ir(config)` 将替换后的配置转换为 IR

理由:
- YAML loader/validator 维持原有职责,不需要理解 runtime vars.
- IR 中的静态 params 可直接持有运行期对象(例如 `datetime`)并透传到 loader.

### Decision: Preload loader calls pass `sources.<id>.params` (semantic convergence)

将 `cache_mode: preload_forever` 的预加载调用从“零参 loader()”改为:
- 若 `sources.<id>.params` 非空: `loader(**sources.<id>.params)`
- 若为空: 保持零参调用

实现上需要让 execution 侧的 preload 阶段拿到静态 params 模板.为此:
- 扩展 `SourceIr` 增加 `params: StaticParams`(与 `MainSourceIr.params` 对齐),由 YAML adapter 在 IR 转换时填充.
- `Pipeline._preload_cached_sources()` 使用 `source.params` 构造调用.

理由:
- 不引入额外的 `preload_params` 字段,直接收敛 `params` 为 loader kwargs 模板的心智模型.
- 保留“params 为空时仍零参调用”以减少对无参 loader 的影响面.

## Risks / Trade-offs

- [BREAKING: preload 行为改变] → 只有当 YAML 中声明了 `sources.<id>.params` 时才会新增 kwargs;缺失/空 params 时保持旧行为.
- [runtime vars 误替换 SQL 片段] → 采用 exact-match 替换,不做子串插值.
- [错误诊断不清晰] → 在占位符解析时携带路径并在异常中输出,同时补测试覆盖典型缺失路径.

## Migration Plan

1. 扩展 by_yaml runtime API: `RunOptions/runtime.entrypoints` 支持 `runtime_vars`.
2. 实现 `$runtime.*` 占位符替换逻辑并补回归测试.
3. 扩展 `SourceIr` 携带 `params`,并让 preload 调用透传 params;补回归测试.
4. 更新 schema hover 与 DSL reference 文档中关于 `params` 与 preload 的说明,并更新生成产物.

