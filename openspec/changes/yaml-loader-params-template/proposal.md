## Why

当前 YAML DSL 无法把“运行期变量”注入到 loader 参数中,导致需要额外的 runtime wrapper(例如 `load_paid_order_rows()` 之类)来拼装参数并调用 `run`.
同时 `cache_mode: preload_forever` 的预加载路径会以零参调用 loader,使得静态 preload 参数(例如 `group_by=...`)无法透传,进一步放大了 wrapper/薄封装的数量,阻碍 loader 复用.

## What Changes

- 与 `yaml-inline-dynamic-params` 合并一并落地: 共用同一份 compiled params template representation,确保 preload/ref-load 调用语义一致且不漂移。
- 新增 by_yaml runtime 入口 `runtime_vars`(dict) 语义,用于在单次运行中注入运行期变量.
- 支持在 `main_source.params` 与 `sources.<id>.params` 中使用 `$runtime.<name>` 占位符,并在编译期将其解析为 `runtime_vars[name]` 的值.
- 与 `yaml-inline-dynamic-params` 共用同一份编译后的 params template representation:
  - `$runtime.*` 在模板编译期落成 literal 节点
  - preload 与 ref loader 共用同一份编译结果,避免维护两套 params 语义
- **BREAKING**: `cache_mode: preload_forever` 的预加载调用语义收敛:
  - 若 `sources.<id>.params` 非空: 预加载时透传 `sources.<id>.params` 作为 kwargs(在完成 `$runtime.*` 解析之后)
  - 若为空: 预加载时保持零参调用,以减少对无参 loader 的影响面
- 诊断策略: 当 `$runtime.<name>` 引用缺失时,编译/校验阶段 fail-fast 并给出明确路径(例如 `main_source.params.params.pay_end_datetime`).

## Capabilities

### New Capabilities
- `yaml-runtime-vars`: 允许 by_yaml runtime 在编译期解析 `$runtime.*` 占位符,将运行期变量注入到 loader kwargs 模板中.

### Modified Capabilities
- `dsl-runtime-structure`: 扩展 `run/compile` 的运行期契约以接收 `runtime_vars`,并在 adapter 编译阶段完成占位符解析.
- `demand-dsl`: 明确 `main_source.params` 与 `sources.<id>.params` 作为 loader kwargs 模板的解析与失败语义(包含 `$runtime.*` 占位符).
- `source-cache`: `preload_forever` 预加载路径的 loader 调用参数语义调整为透传 `sources.<id>.params`(与常规调用一致).
- `yaml-dsl-schema`: 更新 schema 文档与 markdownDescription 中关于 `sources.<id>.params` 的说明(移除“preload_forever 不透传 params”的旧描述,补充 `$runtime.*` 用法说明).

## Impact

- 运行入口 API: by_yaml `run/compile` 增加可选 `runtime_vars` 参数(不影响未使用者).
- 行为变更: `preload_forever` 将对既有 loader 产生额外 kwargs 调用(**破坏性变更**);需要升级依赖零参 preload 的 loader 或配置.
- 代码影响面: YAML runtime contracts/compiler、preload 逻辑(`Pipeline._preload_cached_sources`)以及相关可观测事件中的 params 记录.
- 测试/文档: 需要新增回归测试覆盖 `$runtime.*` 解析与 preload params 透传,并更新 DSL 参考文档与 schema 生成产物.
