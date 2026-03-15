**状态: TODO**

## 1. Schema: `extensions` namespace

- [ ] 1.1 在 `src/scalim/dsl/by_yaml/schema_dsl/models/demand.py` 为 `DemandConfig` 增加可选 `extensions` 字段(仅承载;不执行)
- [ ] 1.2 为 `extensions` 增加最小 schema 形状(含 `api/enabled/bundles/analyze/compute/components/outputs/aggregates/transform/conflicts`)
- [ ] 1.3 `extensions` 对象层级支持 `additionalProperties: true`(允许扩展自定义键),但顶层仍保持严格(`additionalProperties: false`)
- [ ] 1.4 运行 `just gen-yaml-dsl-schema` 并确认更新 `src/scalim/dsl/by_yaml/schema/demand.gen.json`
- [ ] 1.5 同步前端 schema 镜像并通过 drift gate:
  - `just gen-yaml-dsl-editor-schema`
  - `just qa` 中的 schema/editor/viz checks

## 2. Tests (acceptance + regressions)

- [ ] 2.1 新增测试: YAML 顶层包含 `extensions`(含额外键)时,`YamlDemandLoader.load_string(...)` 不因 jsonschema/unknown-fields 失败
- [ ] 2.2 新增测试: 顶层未知键(非 `extensions`)仍会被 schema/unknown-fields 捕获(避免“放开顶层 additionalProperties”)

## Gates

- [ ] `just gen`
- [ ] `just qa`
- [ ] `just openspec-check`
