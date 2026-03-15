## Context

本 change 专注于 “transformers 的编译管线落点”:

- raw transformer 必须发生在 validator 前,否则宏/默认值注入无法与校验一致
- config/ir/request transformers 必须有稳定 stage,便于对拍与排障

umbrella 设计见:

- `openspec/changes/archive/2026-03-15-yaml-dsl-extensibility-preproposal/design.md`

## Decisions

1) stage 划分:
- `raw`: imports 展开后,validator 前
- `config`: DemandConfig 解析后
- `ir`: DemandIr 构造后
- `request`: ExecutionRequest 装配后

2) 执行顺序(全局):

- stage 顺序固定为: `raw` → `config` → `ir` → `request`
- 仅当 `extensions.enabled=true` 且 `ExtensionHost` 中存在对应 transformers 时才会执行

3) 顺序与确定性(单 stage 内):
- direct config transformers 先于 bundles transformers(同 `ExtensionHost` merge 规则)
- 每个 stage 内按声明顺序执行

4) Stage contracts(输入/输出约定):

- raw transformers:
  - 输入: imports 展开后的 raw mapping(dict)
  - 输出: 变换后的 raw mapping(可以原地修改并返回自身,或返回新 dict;实现侧必须把最终结果传给 validator)
- config transformers:
  - 输入/输出: `DemandConfig`(可返回新对象或 replace 后的对象)
- ir transformers:
  - 输入/输出: `DemandIr`
- request transformers:
  - 输入/输出: `ExecutionRequest`

说明:
- 实现上建议统一为 `callable(value, ctx) -> value` 风格,并允许 transformer 不接收 `ctx`(复用 host-core 的通用调用策略)

5) 护栏与诊断:

- transformer 异常必须包装 `yaml_path/ref/stage` 上下文
- raw transformers SHOULD NOT 修改 `extensions` 自身(避免自举与不可控漂移);实现侧不保证支持“通过 raw transformer 改写 extensions 再重建 host”的语义

## Non-Goals

- 不在本 change 中引入新扩展点语义(输出/聚合/compute 函数等由其它 changes 处理)
