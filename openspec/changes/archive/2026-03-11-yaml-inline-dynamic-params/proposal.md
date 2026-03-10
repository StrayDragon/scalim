## Why

当前 YAML DSL 把 loader 调用参数拆成两部分:

- `sources.<id>.params`: 静态 kwargs
- `bind/use_keys` 与 `bind/use_rows`: 从运行时上下文注入 keys/rows 的“动态参数构造器”

这种拆分在概念上不直觉,并且 `bind.use_keys.param` 只能做顶层 kwarg 注入(`kwargs[param]=...`),无法表达 ET 等大量 loader 的常见签名形态 `kwargs.get("params", {})` 的 nested params 写法(例如 `kwargs["params"]["order_id_set"]=...`). 结果是需要为“整形入参”专门写一层薄 wrapper,导致 loader 复用困难、YAML 下沉受阻。

## What Changes

- 与 `yaml-loader-params-template` 合并一并落地: 共享同一份 params template IR/渲染器与校验边界,避免 preload/ref-load 两套语义漂移。
- 在 `main_source.params` 与 `sources.<id>.params` 中引入“入参模板 + 内联动态节点”的 declarative 语义,允许在任意嵌套位置注入运行时值:
  - `{$keys: {as: set|list}}`: 注入当前 `LoadRef(keys)` 的 lookup keys(支持稳定顺序 list)
  - `{$rows: {cache_mode: batch|none}}`: 注入当前 `LoadRef(rows)` 的 batch rows 上下文(并保留 rows barrier/缓存语义)
- 编译阶段将 `params` 模板编译为共享的 typed template IR,供 preload/ref-load 共用:
  - ref loader 侧仍复用现有执行路径(即 binding/build_params/call_loader_with_binding),但 `BindingIr.params_builder` 只作为共享模板渲染器的轻量适配层.
  - preload loader 与 ref loader 共享同一份编译后的 params template,避免出现两套 params 语义与 instrumentation 漂移.
  - 模板渲染对非法场景 fail-fast(例如 preload callsite 或非 ref loader 使用 `$keys/$rows`).
- `bind/to_bind` 从 YAML authoring surface 中移除:
  - 新写法以 `params` 模板为唯一稳定入口;旧写法直接按迁移错误处理(校验阶段 fail-fast),不保留兼容分支.
  - 仓库内示例、文档与 skill 文档应统一升级为新写法,并在 validator/schema 中给出迁移提示.

## Capabilities

### New Capabilities
- `yaml-inline-dynamic-params`: YAML `params` 支持内联动态节点(`$keys/$rows`)并在嵌套位置注入运行时值,以模板方式完整描述 loader kwargs。

### Modified Capabilities
- `demand-dsl`: 扩展 `main_source.params` / `sources.*.params` 的语义为“可渲染模板”,并定义 `$keys/$rows` 指令节点的行为与错误边界。
- `source-relations`: 将 ref loader 的 keys/rows 绑定能力从 `bind/to_bind.param` 迁移为 `params` 模板内联指令(同时保持 rows barrier 与缓存语义不变)。
- `deterministic-ordering`: 将“keys list 顺序稳定”的要求扩展到 `$keys: {as: list}` 形式。
- `yaml-dsl-agent-guidance`: 更新 `artifacts/skills/scalim-yaml-dsl/` 的示例与迁移指引,将旧的 `bind/use_keys.param` 写法升级为 `params` 模板内联指令写法。
- `yaml-dsl-schema`: 更新 schema 的 hover/文档描述,解释 `params` 中可用的 `$keys/$rows` 指令节点与常见示例。

## Impact

- 影响 YAML DSL 编译链路与校验边界: `dsl/by_yaml/runtime/_internal/conversion_*.py`、相关 validator/diagnostics 需要新增对指令节点的解析与 fail-fast 报错路径。
- 影响执行语义的可观测性与调度: `$rows` 必须继续触发 rows barrier,并参与 relation signature/批次复用语义。
- 需要同步更新文档与示例: `docs/doc/yaml-dsl/*`、以及 `artifacts/skills/scalim-yaml-dsl/**`(用户明确要求)。
- 需要新增回归测试覆盖: nested params 注入、keys(list)稳定性、rows cache_mode 与 barrier、非法场景报错信息。
