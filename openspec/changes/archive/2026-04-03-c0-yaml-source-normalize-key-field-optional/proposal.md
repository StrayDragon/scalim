## Why

`sources.*.normalize.kind=index_by_key` 目前要求显式填写 `normalize.key_field`，并且该字段还必须等于 `sources.<id>.key`。
这会导致两个问题:

1) **强冗余**：绝大多数场景下 `key_field` 与 `key` 完全相同，用户不得不重复写两次，造成 YAML 噪音与 diff 噪音。
2) **心智负担与误配风险**：用户会把 `key`/`key_field` 当成两套概念，实际却必须保持一致；当两者不一致时只会得到 fail-fast 错误，且这个错误本质上是“配置重复导致的自相矛盾”。

此外，当前 YAML JSON Schema 层面 `key_field` 并不是 required，但 validator + YAML→IR conversion 又把它当作 required，
导致“编辑器提示/Schema”与“真实校验行为”存在不一致。

本变更把 `index_by_key` 的 `key_field` 从“必填重复字段”收敛为“可选字段(默认推导)”，减少配置面积并降低误配率。

## What Changes

### 1) `normalize.key_field` 变为可选(仅 `index_by_key`)

当 `sources.<id>.normalize.kind == "index_by_key"` 时:

- 若 `normalize.key_field` 为非空字符串:
  - **继续沿用**该值作为 effective `key_field`
  - 并且 **继续强约束** `normalize.key_field == sources.<id>.key`（避免 relation/lookup 语义漂移）
- 若 `normalize.key_field` 缺失或为空字符串:
  - 系统 MUST 将 effective `key_field` 推导为 `sources.<id>.key`

> 说明：这里的 “用户可自定义” 指用户仍然可以显式写 `key_field`（用于可读性/显式性），但仍需与 `key` 保持一致；
> 不引入 “key 与 key_field 可不一致” 的新语义（那会改变 relation lookup contract，属于另一个更大提案）。

### 2) 约束与边界保持不变

- `sources.<id>.key` 为复合键(tuple/list)时:
  - `normalize.kind=index_by_key` 仍 MUST 被拒绝（现状不支持 composite key indexing）
- 其它 normalize kind (`take_first` / `project_fields` / `map_values`) 的行为不变:
  - `key_field` 仍只对 `index_by_key` 有意义；其它 kind 出现 `key_field` 仍应被拒绝（避免无效配置静默通过）

### 3) YAML→IR conversion MUST 填充 effective key_field

为避免 “validator 放宽但 conversion 仍报错”，conversion MUST 按上述规则计算 effective `key_field`，并写入 `SourceNormalizeIr(kind="index_by_key", key_field=...)`。

## Example

### Before

```yaml
sources:
  payment_methods:
    loader: "mypkg.loaders:load_payment_methods"
    key: payment_method_id
    normalize:
      kind: index_by_key
      key_field: payment_method_id
      on_conflict: error
```

### After

```yaml
sources:
  payment_methods:
    loader: "mypkg.loaders:load_payment_methods"
    key: payment_method_id
    normalize:
      kind: index_by_key
      on_conflict: error
```

## Capabilities

### Modified Capabilities

- `yaml-source-normalize`:
  - `normalize.kind=index_by_key` 的 `normalize.key_field` 从“必填”改为“可选”
  - 缺省时默认取 `sources.<id>.key`（仅当 `key` 为单字段时）
- `yaml-dsl-schema`/validator:
  - validator 与 conversion 对该缺省行为达成一致；保持其它 kind 的 key_field 禁用约束

## Impact

- 影响面(实现侧):
  - YAML validator: `src/scalim/dsl/by_yaml/_internal/config_parsing/validators/sources.py`
  - YAML -> IR conversion: `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`
  - Tests: `tests/yaml_dsl/test_yaml_source_normalize.py`（以及涉及 normalize 的 YAML fixtures / demo YAML）
  - Docs/hover: `docs/doc/yaml-dsl/user-guide.md` 及 schema hover 文案需显式强调 “`index_by_key` 下 `key_field` 可省略且缺省取 `sources.<id>.key`” 并给出示例

- 风险与边界:
  - 该变更对现有 YAML 完全向后兼容：显式填写 `key_field` 的配置不受影响
  - 仅减少 required 字段与重复字段，默认行为不引入 silent behavior drift
