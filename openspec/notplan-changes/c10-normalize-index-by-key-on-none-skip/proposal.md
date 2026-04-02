## Why

`normalize.kind=index_by_key` 当前在遇到 `key_field` 为 `None` 的行时会直接 fail-fast，这在真实数据里很常见(上游数据不完整/占位行/部分回填)。
结果是用户不得不在每个使用点手写 `where` 过滤或自定义 `call_by` 清洗，语义分散且容易漏掉。

本变更提供一个显式、可审计的策略开关 `normalize.on_none: skip`，把“缺 key 如何处理”收敛到 source 层做一次。

## What Changes

- 为 `normalize.kind=index_by_key` 增加配置项 `on_none`：
  - 默认 `raise`(保持现有行为)
  - 可选 `skip`(跳过 `key_field` 为 `None` 的行)
- `on_none` 仅影响 “`key_field` 存在但值为 `None`” 的情况:
  - `key_field` 缺失(当前为 `KeyError`)仍 fail-fast
  - `key_field` 非 hashable(当前为 `TypeError`)仍 fail-fast
- YAML schema/validator 增加约束:
  - 只有在 `normalize.kind=index_by_key` 时允许设置 `on_none`
  - 其它 normalize kind 设置 `on_none` MUST 被拒绝(避免静默无效配置)

### Example

一个典型场景: loader 返回的列表里混入了占位/不完整行,我们只希望对有 `order_id` 的行建索引。

```yaml
sources:
  orders:
    kind: lookup
    loader:
      call_by: mypkg.load_orders
    normalize:
      kind: index_by_key
      key_field: order_id
      on_conflict: last
      on_none: skip  # NEW: 忽略 {"order_id": None, ...}
fields:
  order_score:
    from: sources.orders
    lookup_key: order_id
    extract: score
```

假设 loader 返回:

```python
[
  {"order_id": 101, "score": 0.9},
  {"order_id": None, "score": 0.0},  # 占位/不完整
  {"order_id": 102, "score": 0.7},
]
```

期望 normalized 结果为:

```python
{
  101: {"order_id": 101, "score": 0.9},
  102: {"order_id": 102, "score": 0.7},
}
```

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `yaml-source-normalize`: `normalize.kind=index_by_key` 增加 `on_none: raise|skip`，默认 `raise`，`skip` 时忽略 `key_field is None` 的行。
- `yaml-dsl-schema`: YAML schema/hover/validation 允许 `normalize.on_none` 且仅在 `index_by_key` 生效。

## Impact

- 影响面(实现侧):
  - YAML schema/model: `src/scalim/dsl/by_yaml/schema_dsl/models/source.py` (`NormalizeConfig`)
  - YAML validator: `src/scalim/dsl/by_yaml/_internal/config_parsing/validators/sources.py`
  - YAML -> IR conversion: `src/scalim/dsl/by_yaml/runtime/_internal/conversion_sources.py`
  - IR normalize runtime: `src/scalim/spec/ir/_sources.py` (`_normalize_index_by_key_extract_key`/loop)
- 风险与边界:
  - `on_none=skip` 会吞掉部分行，属于显式 opt-in；默认行为不变，因此是安全扩展。
  - 该能力不改变 `key_field` 缺失的错误边界(仍 fail-fast)，避免把 schema/data contract 问题静默化。

