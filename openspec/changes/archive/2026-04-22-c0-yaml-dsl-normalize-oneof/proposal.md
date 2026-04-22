## Why

当前 `sources.*.normalize` 的 YAML 写法为“`kind + 扁平参数空间`”：

```yaml
normalize:
  kind: index_by_key
  on_conflict: error
  on_none: raise
```

虽然现有实现已经在 schema 与 runtime validator 中表达了较强的互斥/必填约束（`allOf + oneOf + not`），但在 authoring 体验上仍然不够直觉：

- 用户需要记忆“不同 kind 对应哪些字段”，并在同一扁平空间里做心理匹配；
- 编辑器补全/hover 常表现为“把所有可选字段都列出来”，很难在输入 `kind` 后收敛到有效字段集合；
- `map_values` 的 `steps[*]` 也复用了同样的 `kind + 参数` 风格，进一步放大了阅读与编写负担。

我们希望把 `normalize` 的 authoring surface 也升级为“分支式 one-of 结构”，让“选择哪一种 normalize”体现在 YAML 结构上，减少心智负担，并让无效组合更早、更明确地被 schema/validator 拒绝。

## What Changes

- **BREAKING**：调整 YAML DSL 的 `sources.*.normalize` 写法，移除旧语法 `normalize: {kind: <...>, ...}`，升级为 one-of 分支结构（分支互斥）：
  - `normalize: {index_by_key: {...}}`
  - `normalize: {take_first: {...}}`
  - `normalize: {project_fields: {...}}`
  - `normalize: {map_values: {...}}`
- `normalize.call_by` 保持为可选公共字段（路径保持 `sources.*.normalize.call_by`），并与上述分支 key 并存。
- **BREAKING**：`normalize.map_values.steps[*]` 也从 `{kind: ..., ...}` 升级为 one-of step 分支结构：
  - `steps: [{take_first: {...}}, {project_fields: {...}}]`
- schema 适配：demand JSON Schema 中 `normalize` 与 `normalize.steps[*]` 改为分支 oneOf，确保：
  - `normalize` 必须且只能选择一个分支；
  - 分支对象仅允许该分支支持的字段（例如 `on_none` 只能出现在 `index_by_key` 分支）。
- YAML 解析/校验与 IR 转换适配：解析新语法，并保持运行期语义不变（仍是 whole-result normalization；各 kind 行为与默认值保持一致）。
- 文档/示例/测试同步升级：更新用户文档与所有 fixtures/tests；并通过既有生成入口刷新生成物（禁止手工修改 `.gen.` 文件/注入块/站点输出）。

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `demand-dsl`: `sources.*.normalize` authoring 语法升级为分支 one-of（移除 `normalize.kind` 写法）。
- `yaml-dsl-schema`: demand JSON Schema 对 `normalize` 与 `normalize.steps[*]` 的分支互斥与字段约束表达升级，并同步更新 hover 文案中的示例。
- `yaml-dsl-agent-guidance`: `scalim-yaml-dsl` skill 中关于“何时使用 normalize”的推荐写法更新为新语法。
- `execution-source-cache`: 规范中的 preload + normalize 示例从 `normalize.kind=...` 更新为新语法（语义不变）。

## Impact

- YAML authoring 破坏性变更：影响 `sources.*.normalize`（以及 `normalize.map_values.steps[*]`）的所有用例与文档示例。
- 影响运行期代码路径：schema_dsl SSOT、解析器/校验器、IR 转换与相关测试（但 normalize 的运行期语义与 IR 结构保持不变，主要是 authoring surface 变化）。
- 受影响的 SSOT 与生成物：
  - SSOT：`src/scalim/dsl/yaml_dsl/schema_dsl/**`、`docs/doc/yaml-dsl/user-guide.md`、`agentdev/skills/scalim-yaml-dsl/**`
  - 生成物：`src/scalim/dsl/yaml_dsl/schema/demand.gen.json`、`src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`、`docs/doc/yaml-dsl/schema-reference.gen.md`、`docs/site/**` 等（通过 `just gen-yaml-dsl-schema` / `just gen-docs` 刷新，禁止手改）
