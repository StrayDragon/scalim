# 2026-03-10: yaml-source-normalize

## 变更摘要

这次升级为 lookup `sources.*` 引入源代码级 `normalize`,用于在字段级 `extract` 之前对 `loader` 的整体返回值做一次整体结果归一化。

- 新增 `sources.<id>.normalize`(显式拒绝 `main_source.normalize`)
- 支持 `normalize.kind: index_by_key`:把 `list[row]` 归一化为 `key -> row`
- `on_conflict` 默认 `error`,也可用 `first/last` 显式声明冲突策略
- 归一化发生在 `extract` 之前;`extract` 仍然只负责从“单条 row value”里取字段

OpenSpec 归档变更(含 proposal/design/spec/tasks):
- `openspec/changes/archive/2026-03-10-yaml-source-normalize/`

对应主规范:
- `openspec/specs/demand-dsl/spec.md`
- `openspec/specs/source-cache/spec.md`
- `openspec/specs/yaml-dsl-schema/spec.md`
- `openspec/specs/yaml-dsl-editor-core/spec.md`
- `openspec/specs/yaml-dsl-agent-guidance/spec.md`

## 适用场景

- `loader` 自然返回 `list[row]`(例如小表、外部 API 列表),但关联读取需要 `lookup_key -> row` 形状
- 你不希望再写一个“把 `list` 转 `dict`”的薄包装,只为了满足 DSL 的 lookup 形状

## 写法

### 1) 在 `sources.<id>` 上声明 `normalize`

```yaml
sources:
  payment_methods:
    loader: "myapp.loaders:load_payment_methods"
    key: payment_method_id
    normalize:
      kind: index_by_key
      key_field: payment_method_id
      on_conflict: error
```

约束:

- `key_field` 必填
- `key_field` 必须与 `sources.<id>.key` 一致(目前只支持单字段 key;复合键暂不支持 `index_by_key`)
- 重复 key 默认快速失败;如要覆盖必须显式 `on_conflict: first|last`

### 2) 字段读取仍然用字段级 `extract`

```yaml
sources:
  payment_methods:
    fields:
      payment_method_name:
        extract: payment_method_name
```

说明:
- `normalize` 先把整体结果变成映射
- `extract` 再在每个 lookup key 对应的单条 row 上取字段

## 常见报错

- `main_source.normalize`:
  - 报错: 校验器会指出 `main_source.normalize` 不允许
  - 修复: `normalize` 只能写在 `sources.*`
- 缺少 `key_field` / `key_field` 为空:
  - 修复: 补齐 `normalize.key_field`
- 复合键:
  - 报错: 当前不支持 `sources.<id>.key: [a, b]` 与 `normalize.kind=index_by_key` 同时使用
  - 修复: 保持 `loader` 返回映射,或在 Python 包装函数中完成复合键索引
- 重复 key:
  - 默认 `on_conflict: error` 会直接报错
  - 如业务允许覆盖,显式设为 `first` 或 `last`
