## Why

当前 `lookup_cast` 的 YAML 写法为扁平对象 `{name, sep?}`。这会导致在语法层面允许不合理组合（例如 `name: int` 但仍可填写 `sep`），并把错误延迟到更后面的转换/运行阶段才暴露，既不直觉也不利于 fail-fast。

我们希望把 `lookup_cast` 变为“分支式 one-of 结构”，让 schema/校验器在 authoring 阶段就能拒绝无效组合，同时保持运行期语义不变（仍然只在关联/lookup 前对 key 做归一化）。

## What Changes

- **BREAKING**：调整 YAML DSL 的 `lookup_cast` 写法，移除旧语法 `lookup_cast: {name: <auto|int|str|sep_first>, ...}`，统一升级为 one-of 分支结构：
  - `lookup_cast: {auto: {}}`
  - `lookup_cast: {int: {}}`
  - `lookup_cast: {str: {}}`
  - `lookup_cast: {sep_first: {sep: ","}}`（`sep` 可省略，默认 `","`）
- demand JSON Schema 适配：`lookup_cast` 改为 `oneOf`，并且只允许 `sep_first` 分支携带 `sep`，其它分支出现 `sep` 必须 schema-only 直接报错。
- YAML 解析/校验与 IR 转换适配：解析新语法并保持 IR (`LookupCastSpecIr`) 与运行期行为一致（`auto/int/str/sep_first` 语义不变；`auto` 仍拒绝 float 以避免歧义）。
- 文档/示例/测试同步升级：更新 `docs/doc/yaml-dsl/user-guide.md` 与相关 fixtures；并通过既有生成入口刷新生成物（不手工修改 `.gen.` 文件/注入块/站点输出）。

## Capabilities

### New Capabilities
- （无）

### Modified Capabilities
- `yaml-dsl-schema`: demand schema 对 `lookup_cast` 施加 one-of 结构约束（分支互斥 + `sep` 仅对 `sep_first` 合法），并提供更直觉的 hover/补全。
- `ir-source-relations`: relation steps 的 `lookup_cast` authoring 示例与约束更新为新语法；lookup 语义与诊断策略保持不变。
- `ir-key-normalization`: 文档中对 relations `lookup_cast` 的引用示例更新为新语法；`key_normalization` 与显式 cast 的优先级规则保持不变。

## Impact

- YAML authoring 破坏性变更：影响 `sources.*.lookup_cast` 与 `relations.*.steps[*].lookup_cast`（以及字段内联 steps 的同名节点）。
- 影响运行期代码路径：YAML schema_dsl SSOT、YAML 解析器/校验器、IR 转换与快照/签名（但 IR 结构不变，主要是 authoring surface 变化）。
- 受影响的 SSOT 与生成物：
  - SSOT：`src/scalim/dsl/yaml_dsl/schema_dsl/**`（schema 元数据）、`docs/doc/yaml-dsl/user-guide.md`（用户文档）
  - 生成物：`src/scalim/dsl/yaml_dsl/schema/demand.gen.json`、`docs/doc/yaml-dsl/schema-reference.gen.md`、`docs/site/**` 等（通过 `just gen-yaml-dsl-schema` / `just gen-docs` 刷新，禁止手改）
