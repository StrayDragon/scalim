# YAML DSL Schema Meta 参考

??? note "适用读者"
    - 维护 YAML DSL JSON Schema 的项目贡献者
    - 维护编辑器补全/hover 体验的开发者

本页说明 `_schema_meta(...)` 的约定与能力边界,用于保持生成的 JSON Schema 风格一致.

??? note "维护提示"
    本页内容通常会在以下变更后需要同步检查:

    - `_schema_meta` / `_schema_omit` 的语义调整
    - `SchemaBuilder.META_KEY_MAP` 的映射变更
    - meta 展开逻辑变更(影响 hover/choices/examples 等)

    代码入口:
    - meta payload: `src/scalim/dsl/yaml_dsl/schema_dsl/constants.py::_schema_meta`
    - meta 展开: `src/scalim/dsl/yaml_dsl/schema_dsl/builder.py::SchemaBuilder._expand_meta`

## 1) `_schema_meta` 是什么

`_schema_meta(**kwargs)` 会把 `kwargs` 放入 dataclass field metadata,并在生成 JSON Schema 时展开为字段 schema 的一部分.

典型用途:
- 为字段补充 hover 说明: `md`/`desc`
- 为枚举提供选项: `choices`
- 为数字/数组/对象补充约束: `min/max/min_items/...`
- 为 LSP/示例补充 examples: `example`/`examples`

## 2) 特殊 key(不走 META_KEY_MAP)

以下 key 在生成过程中具有特殊语义,不通过 `META_KEY_MAP` 映射:

- `schema_name`:
  - 用于重命名 schema 中的 property key(默认使用 dataclass 字段名)
  - 例: `metadata=_schema_meta(schema_name="use_rows", ...)`
- `ref`:
  - 生成 `{"$ref": "#/definitions/<ref>"}` 或 `{"allOf": [{"$ref": ...}], ...meta...}`
- `schema`:
  - 直接使用给定 schema dict 作为字段 schema(用于高度定制的结构)

> 另外 `_schema_omit(...)` 会设置 `schema_omit: True`,用于从生成物中跳过该字段.

## 3) Shorthand keys → JSONSchema keys 映射表

`SchemaBuilder.META_KEY_MAP` 支持下表中的 shorthand keys(含别名). 推荐优先使用 **Canonical** 列中的写法.

| Canonical | Aliases | JSONSchema key | 说明 |
|---|---|---|---|
| `desc` | - | `description` | 简短描述 |
| `md` | `markdown` | `markdownDescription` | Markdown hover 描述(推荐 `md`) |
| `choices` | - | `enum` | 枚举选项 |
| `min` | - | `minimum` | 数字最小值 |
| `max` | - | `maximum` | 数字最大值 |
| `min_items` | - | `minItems` | 数组最小长度 |
| `max_items` | - | `maxItems` | 数组最大长度 |
| `min_props` | - | `minProperties` | 对象最小属性数 |
| `max_props` | - | `maxProperties` | 对象最大属性数 |
| `pattern` | - | `pattern` | 字符串正则约束 |
| `default` | - | `default` | 默认值 |
| `type` | - | `type` | 强制类型(谨慎使用,通常由类型推断生成) |
| `items` | - | `items` | 数组 items schema |
| `one_of` | - | `oneOf` | union schema |
| `any_of` | - | `anyOf` | union schema |
| `all_of` | - | `allOf` | schema 组合 |
| `additional_props` | - | `additionalProperties` | 支持 bool/对象/或字符串(会被展开为 `$ref`) |
| `const` | - | `const` | 常量值 |
| `deprecated` | - | `deprecated` | 标注弃用 |
| `items_choices` | - | `items.enum` | 数组元素枚举(便捷写法) |
| `example` | - | `examples` | 若值不是 list,会自动包装为 `[value]` |

生成器还会做两个小的 UX 兼容:
- 若未提供 `markdownDescription` 但提供了 `description`,会自动复制一份作为 `markdownDescription`
- 若提供的是 `example=<scalar>`,会自动转换为 `examples=[<scalar>]`

## 4) 推荐写法(Canonical)

- 优先使用 `md` 而不是 `markdown`
- 优先使用 `desc` 而不是直接写 `description`
- 枚举统一用 `choices`,避免同时出现 `choices`/`enum`
- examples 统一用 `example`(单值)或 `examples`(列表),避免手写不同结构

## 5) 示例

### 示例 1: hover 描述 + 枚举 + examples

```py
from dataclasses import dataclass, field

# `_schema_meta` 是内部 helper,见:
# - `src/scalim/dsl/yaml_dsl/schema_dsl/constants.py::_schema_meta`


@dataclass(frozen=True)
class Demo:
    mode: str = field(
        default="quiet",
        metadata=_schema_meta(
            md="运行模式: quiet / fast_fail",
            choices=["quiet", "fast_fail"],
            example="quiet",
        ),
    )
```

### 示例 2: 重命名字段(schema_name)

```py
from dataclasses import dataclass, field

# `_schema_meta` 是内部 helper,见:
# - `src/scalim/dsl/yaml_dsl/schema_dsl/constants.py::_schema_meta`


@dataclass(frozen=True)
class BindConfig:
    # schema 中希望 key 为 use_rows,而不是 dataclass 字段名 rows
    rows: object = field(metadata=_schema_meta(schema_name="use_rows"))
```

### 示例 3: 数组 items_choices

```py
from dataclasses import dataclass, field
from typing import List

# `_schema_meta` 是内部 helper,见:
# - `src/scalim/dsl/yaml_dsl/schema_dsl/constants.py::_schema_meta`


@dataclass(frozen=True)
class Demo:
    formats: List[str] = field(metadata=_schema_meta(items_choices=["csv", "excel"]))
```

## 6) 允许直接透传 JSONSchema key 吗?

可以. `META_KEY_MAP` 之外的 key 会原样写入生成 schema.

但为了治理与可维护性:
- 新增/使用非 canonical key 时,在变更说明中写清原因
- 若引入新的 shorthand/别名,应同步更新本参考文档
