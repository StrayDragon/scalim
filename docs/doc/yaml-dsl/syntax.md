# YAML DSL 语法总览

??? note "适用读者"
    - 写 YAML 配置并需要快速对齐语法边界的使用方
    - 需要排查 schema/校验行为的开发者

本页聚焦 YAML DSL 的整体结构、容易误解的约束与排错入口.字段级别的完整说明与示例请看 [用户指南](user-guide.md).维护 schema 与编辑器补全请看 [Schema Meta 参考](schema-meta.md).

??? note "维护提示"
    本页内容通常会在以下变更后需要同步检查:

    - JSON Schema 结构/默认值/枚举调整
    - 语义校验规则变更(unknown fields、约束收紧/放宽)
    - `relations` / `bind` / `output.fields` 等关键语义调整
    - Python 引用解析与 allowlist 规则调整(影响 `loader` / `call_by`)

## 1. 语法的事实来源在哪里

YAML DSL 的语法有两层来源:

1. JSON Schema(结构与类型)
   - CLI: `scalim-cli yaml-dsl schema show` / `scalim-cli yaml-dsl schema path`
2. 内置 validator(语义规则,超出 schema 的部分)
   - 入口: `scalim-cli yaml-dsl validate ...`

如果两者出现不一致,以 `validate` 的运行时行为为准.

## 2. 顶层结构(骨架)

顶层 key 的顺序在 schema 里是固定的(只是展示顺序,不影响解析). 当前 schema 要求:

- 必填: `name`, `main_source`
- 可选: `_templates`, `description`, `batch_size`, `retry`, `sources`, `fields`, `relations`, `guardrails`, `output`, `observability`

一个“只展示结构”的骨架长这样:

```yaml
name: my_report

_templates: {}          # 可选: YAML anchor 模板集合(只为复用服务)
description: ""         # 可选
batch_size: 1000        # 可选: null 或 >=1
retry: {}               # 可选: 全局 loader retry 默认策略

main_source: {}         # 必填
sources: {}             # 可选: 不包含 main_source.source_id
relations: {}           # 可选: 命名 relation 模板(供 YAML alias 复用)
fields: {}              # 可选: 仅派生字段(必须 compute/call_by 二选一)

guardrails: {}          # 可选
output: {}              # 可选
observability: {}       # 可选
```

提示:

- 顶层 `output` **可省略**.当把 `YAML` 当作模板使用时,推荐在 Python 调用侧使用 `overrides.output.*`(例如 `overrides.output.path`)决定输出策略.
- 若存在跨 source 同名 `field_id`,则需要显式 `output.fields` 进行消歧(即使顶层未声明 `output`,也可能因为字段歧义而被要求补充 `output.fields`).

## 3. YAML 复用: anchors、alias、`_templates`

### 3.1 anchors / alias 是 YAML 特性,不是 Scalim “语法糖”

仓库内有带 anchors 的示例配置: `tests/fixtures/order_report.yaml`.

- 在字段对象上打 anchor: `order_id: &order_id {...}`
- 在别处引用该对象: `- *order_id` 或 `relation: *orders_to_customers`

这类复用的好处是: 语法层面几乎不需要框架支持,减少“文档讲了但实现没跟上”的风险.

### 3.2 `_templates` 的定位

`_templates` 是 schema 里专门留给“模板/锚点集合”的顶层节点,用途是把常用片段集中放置,避免散落在业务配置里.

目前 `_templates` 只对少数 key 赋予明确语义,其余内容主要用于 anchors/alias 复用:

目前 `_templates` 明确支持:

- `_templates.retry.<name>`: 可复用的 retry policy 对象集合

除此之外 `_templates` 允许出现额外 key(用于 YAML anchors),但这些 key 不会被框架当成“有语义的字段”读取.

### 3.3 一个容易踩的点: YAML merge(`<<`)

`output.fields` 的文案里明确提示了 merge 的副作用:

- YAML merge 会生成新对象,丢失 alias 身份
- merge 产物必须仍然包含 `field_id` 或 `field` 作为选择器

## 4. 引用 Python: loader / call_by

YAML 里引用 Python 的地方主要有两类:

- `main_source.loader` / `sources.<id>.loader`: loader 引用
- `fields.<id>.call_by`: 派生字段函数调用

注意: `allowed_modules`/`allowed_functions` 是运行时参数,不是 YAML 字段.

## 5. relations 与 relation 引用方式

### 5.1 relation 的基本形态

`relations` 是一个命名映射,每个条目是一个 `steps` 数组,每步至少包含:

- `from`: `<source_id>.<field_id>`
- `to`: `<source_id>.<field_id>`

### 5.2 relation 在字段里怎么引用

源字段里用 `relation` 指定“从 main_source 到当前字段 source”的链路,只支持两种写法:

1. YAML alias 引用(指向一个已定义的 relation 对象)
2. 内联 `steps: [...]`

要点:

- 不支持用字符串 relation_id 来引用
- 使用 alias 时,alias 必须先在 `relations` 里定义(这是 YAML 的约束)

## 6. bind: `use_keys` vs `use_rows`

bind 的 schema 是一个二选一结构:

- `use_keys`: 传入 lookup keys
- `use_rows`: 传入批次行上下文

执行语义上,`use_rows` 会影响调度边界:

- `parallel_mode="adaptive"` 时,调度器会把 `use_rows` 视为 barrier,该层直接串行执行(见 [并行模式](../architecture/parallel-modes.md)).

## 7. output.fields: 为什么必须是对象/alias

`output.fields` 用来明确导出字段顺序,并在字段存在歧义时做选择与覆盖.

当前实现不支持在 `output.fields` 里直接写纯字符串列表,每一项必须是:

- 显式对象(包含 `field_id` 或 `field` 选择器,必要时加 `source`)
- 或 YAML alias(指向一个字段对象)

## 8. 校验与排错: 先用什么命令

推荐顺序:

1. 结构校验(JSON Schema):

```bash
scalim-cli yaml-dsl schema validate path/to/file.yaml --strict --verbose
```

2. 语义校验(内置 validator,会做更多规则检查):

```bash
scalim-cli yaml-dsl validate path/to/file.yaml --strict --verbose
```

如果你看到 “legacy field 不允许” 这类错误,通常来自 CLI 的兼容性限制.

## 下一步

- [用户指南](user-guide.md)
- [编辑器](editor.md)
