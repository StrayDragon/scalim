## Context

当前 YAML DSL 的 `sources.*.normalize` 采用“`kind + 扁平参数空间`”的写法：

```yaml
normalize:
  kind: index_by_key
  on_conflict: error
  on_none: raise
```

并且在 `map_values` 场景下进一步引入了 step 级 `kind`：

```yaml
normalize:
  kind: map_values
  steps:
    - kind: take_first
      on_empty: miss
    - kind: project_fields
      on_missing: error
      fields: { ... }
```

现状评估：

- schema SSOT (`src/scalim/dsl/yaml_dsl/schema_dsl/constants.py`) 已使用 `allOf + oneOf + not` 对 `normalize.kind` 与相关字段做了较强的互斥/必填约束；
- runtime validator (`src/scalim/dsl/yaml_dsl/_internal/config_parsing/validators/sources.py`) 也会对不支持的字段组合给出 fail-fast；
- 但 authoring 体验仍然不够直觉：同一扁平空间里容纳多个分支参数，补全/hover 很难按 `kind` 收敛，阅读时也需要不断“把字段映射回 kind”。

本变更的目标是仅调整 YAML authoring surface，使“选择哪一种 normalize”体现在 YAML 结构上，同时保持 IR 与运行期语义不变。

约束：

- 破坏性升级：不做兼容层，不再支持旧写法 `normalize.kind: ...` 与 `normalize.steps[*].kind: ...`。
- 运行期需保持 Python 3.6 兼容（`src/scalim/`）。
- 文档/Schema 生成物不得手工修改：`.gen.` / `BEGIN/END AUTOGEN` / `docs/site/**` 均需通过生成入口刷新。

## Goals / Non-Goals

**Goals:**

- 将 `sources.*.normalize` 升级为分支 one-of 结构（分支互斥），把 kind 选择变为 YAML 结构：
  - `normalize: {index_by_key: {...}}`
  - `normalize: {take_first: {...}}`
  - `normalize: {project_fields: {...}}`
  - `normalize: {map_values: {...}}`
- `map_values.steps[*]` 同步升级为 step 分支 one-of 结构：
  - `steps: [{take_first: {...}}, {project_fields: {...}}]`
- schema-only（JSON Schema）与 runtime validator 同步表达约束：
  - normalize 必须且只能选择一个分支；
  - 分支对象仅允许该分支支持的字段（例如 `on_none` 仅对 `index_by_key` 合法）；
  - step 分支同理。
- 提供清晰的 fail-fast 迁移报错：检测到 legacy 形态时，给出可照抄的替换片段。
- 全量升级 docs/fixtures/tests，并通过既有入口刷新生成物，避免 drift。

**Non-Goals:**

- 不改变 normalize 的运行期语义（四种 kind 的行为与默认值保持一致）。
- 不新增 normalize kind、不调整 kind 命名。
- 不引入 `dsl_version` 或并行 parser/validator/schema。
- 不在本变更中扩张到其它配置对象（例如 `resources.*.write_defaults` 等类似 “mode + 参数” 形态的收敛，留作独立讨论/变更）。

## Decisions

### Decision: keep outer key `normalize`, switch inner shape to one-of keyed object

选择：

- 保持概念名 `normalize`（与现有文档与 IR 对齐）。
- 移除 `normalize.kind` 字段，改为由分支 key（`index_by_key` / `take_first` / `project_fields` / `map_values`）表达选择。

理由：

- YAML 结构自描述：用户不再需要在扁平参数空间里“先选 kind 再筛字段”。
- schema 更容易做到“分支字段只在分支内出现”，从而让补全/hover 在分支内部更准确。
- 与近期 `lookup_cast` 的 one-of 分支写法保持一致，形成可复用的 authoring 直觉。

备选方案：

- 保持 `{kind, ...}` 形态，仅优化 editor/LSP 补全：schema 复杂度更高且对外部工具依赖更强，且 YAML 本身仍不直觉。
- `{kind: ..., params: {...}}`：统一“分支参数都放 params”但更啰嗦，并且仍需要额外互斥/必填约束表达。

### Decision: keep `normalize.call_by` as a common sibling field (optional)

选择：

- `normalize.call_by` 仍保持在 `normalize` 对象的扁平层（不下沉进分支），以减少变更面与既有诊断路径漂移；
- `call_by` 与分支 key 共存：`normalize` 在语义上“必须选择一个分支”，并且 MAY 同时声明 `call_by`。

示例：

```yaml
normalize:
  call_by: "myapp.normalizes:normalize_source_x"
  index_by_key:
    on_conflict: error
```

理由：

- `call_by` 是受控扩展点，现有大量错误路径/签名校验/文档引用了 `sources.*.normalize.call_by`；保留路径能显著降低迁移成本与误差风险。
- 仍可获得主要收益：kind-specific 字段不再混在同一层扁平空间里。

### Decision: change `map_values.steps[*]` to one-of keyed step object

选择：

- 将 step 从 `{kind: take_first, on_empty: ...}` 变为 `{take_first: {on_empty: ...}}`。

理由：

- 复用同一 authoring 直觉，避免一处升级一处保留导致的混乱。
- step 级配置更短、更适合 YAML 列表阅读。

### Decision: schema MUST fail-fast; validator provides targeted legacy migration hints

即使 schema-only 校验已经会因为 `oneOf` 不匹配而失败，runtime validator 仍应在检测到 legacy 形态时给出更直接的迁移提示（包含可照抄的替换片段）。

理由：

- `oneOf` 报错往往对用户不够可读，且不同编辑器的错误呈现差异较大；
- runtime validator 是最终 fail-fast 边界，提供更精确的错误路径与建议能显著降低迁移摩擦。

## Risks / Trade-offs

- [BREAKING] 旧 YAML 将无法通过校验 → 通过明确的 legacy 检测 + 迁移提示 + 文档/fixtures 同步升级缓解。
- [Drift risk] schema 与 docs 生成物漂移风险较高 → 明确 SSOT 边界，并通过 `just gen-yaml-dsl-schema` / `just gen-docs` / `just qa` 门禁兜底。
- [Editor variance] 不同 JSON Schema/LSP 实现对 `oneOf` 的补全收敛能力不同 → 设计上尽量把分支字段下沉到分支对象内部，降低对“动态收敛”的依赖。

## Migration Plan

1. 修改 schema SSOT：将 `NORMALIZE_SCHEMA` 与 `_NORMALIZE_STEP_SCHEMA` 从 `kind` 形态升级为分支 one-of 形态，并同步更新 hover 文案与示例。
2. 修改 YAML 解析/校验：解析新形态，并对 legacy `normalize.kind` / `steps[*].kind` 给出显式错误与迁移提示。
3. 保持 IR/运行期语义一致：转换产物仍为同一 normalize IR（kind 仍为 `index_by_key|take_first|project_fields|map_values`），默认值与行为不变。
4. 全量升级 docs/fixtures/tests，运行生成入口刷新生成物并通过 `just qa` / `just openspec-check`。
