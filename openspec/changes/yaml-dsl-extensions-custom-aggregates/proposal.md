## Why

派生聚合(derived outputs)是扩展性需求的核心:用户希望在不等待框架发版的情况下,快速试验新的聚合口径与输出形态。

为此,`outputs[*].aggregate` 需要支持通过 extensions 注入自定义 kind/ref,并在编译期生成可执行的聚合描述,同时保证 required 字段闭包与并发边界可对拍/可校验。

## What Changes

- YAML `outputs[*].aggregate` 支持:
  - 内置 `group_by`(保持现状)
  - 自定义 `kind/ref` + `options/config`
- 自定义 aggregate 工厂编译为“编译产物”(至少包含 `IDerivedAggregationSpec` + `output_field_ids`)
- custom aggregate 的 `required_fields()` 必须在字段裁剪前注入 required 闭包,避免 composed outputs 运行期缺字段
- 并发边界校验: 自定义聚合在 `parallel_mode` 不支持时必须 fail-fast
- 回归测试: 自定义聚合端到端产生派生输出行

## Capabilities

### Modified Capabilities

- `derived-outputs`
- `yaml-dsl-schema`

## Impact

- 影响 outputs/aggregate 的编译与运行: `src/scalim/dsl/by_yaml/**`, `src/scalim/execution/**`

## Dependencies

- 依赖 `yaml-dsl-extensions-host-core`: aggregate kind/ref registry 来源为 `ExtensionHost`
- 依赖 `yaml-dsl-extensions-schema`: schema/loader 需要先能承载 `outputs[*].aggregate.kind/ref` 与 `options/config`
- 依赖 `yaml-dsl-extensions-transformers`: 为了在字段裁剪前拿到 custom aggregate 的 `required_fields()`,需要先完成 extensions-aware 的编译管线编排
