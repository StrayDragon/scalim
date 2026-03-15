## Why

当前 canonical JSON Schema (`src/scalim/dsl/by_yaml/schema/demand.gen.json`) 顶层 `additionalProperties: false`,因此:

- schema-only 校验/编辑器会把 `extensions` 视为未知字段
- runtime loader 在加载 YAML 后触发 jsonschema 校验时也会直接失败

为了落地 “trusted YAML + allowlist 解析” 的扩展方案,需要先把 `extensions` 作为顶层显式命名空间写入 schema,并允许在其内部承载扩展自定义配置。

## What Changes

- 在 canonical schema(`DemandConfig`) 中新增可选顶层对象 `extensions`,提供最小可提示形状(含 `api/enabled/bundles/analyze/compute/components/outputs/aggregates/transform/conflicts`)
- `extensions` 内部支持 dynamic keys 与自由 `config/options`(避免每个扩展点都绑架 schema 发版)
- loader/validator 在 schema 校验阶段接受 `extensions`(含额外键),不触发 `additionalProperties` error
- **保持顶层严格**: 除 `extensions` 外,其它未知顶层键仍应被 schema/unknown-fields 检测到(避免“为扩展而放开全局 additionalProperties”)
- 同步前端 schema 镜像并保持 `just qa` 的 drift gate 可用

示例(本 change 只保证 schema/loader 可接受,不保证扩展会被执行):

```yaml
extensions:
  enabled: true
  api: 1
  compute:
    functions:
      safe_div: myapp.scalim_ext.compute:safe_div
```

## Capabilities

### Modified Capabilities

- `yaml-dsl-schema`

## Impact

- 影响 schema 生成与分发: `src/scalim/dsl/by_yaml/schema_dsl/**`, `scripts/gen-yaml-dsl-schema.py`, `frontend/**/schema/*.gen.json`
- **不引入** 扩展执行语义: 本 change 只做 schema/loader “可承载” 的基础设施(不导入/执行用户 Python 引用)
