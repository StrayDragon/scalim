## 1. Schema 生成器：统一允许 merge key

- [x] 1.1 在 `packages/scalim-misc/src/scalim_misc/yaml_schema_generator.py` 增加递归 post-process：对所有 `propertyNames` 注入 `{"const": "<<"}`（若已允许则保持不变）。
- [x] 1.2 为该 post-process 增加单测：覆盖 `pattern` / `anyOf` / `enum` / `$ref` 等典型形态，并断言幂等性（重复执行不应改变结果）。

## 2. 覆盖三份 YAML DSL schema

- [x] 2.1 将 post-process 应用于 demand/workflow/scalim_yaml 的 schema 生成入口（仅改生成链路；禁止手改任何 `*.gen.json`）。
- [x] 2.2 运行 `just gen-yaml-dsl-schema` 重新生成：
  - `src/scalim/dsl/yaml_dsl/schema/demand.gen.json`
  - `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`
  - `src/scalim/dsl/yaml_dsl/schema/scalim_yaml.gen.json`

## 3. 门禁与验收

- [x] 3.1 增强/新增治理测试：遍历三份生成物的所有 `propertyNames`，断言均允许 `<<`（回归保护）。
- [x] 3.2 以最小 YAML + 本地 `yaml-language-server` 回归验证：`<<` 不再触发 `propertyNames` pattern mismatch；并确认未引入新的 schema drift。
- [x] 3.3 运行 `just qa` 与 `just openspec-check` 作为最终验收。
