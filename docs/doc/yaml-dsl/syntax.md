# YAML DSL 语法总览

??? note "适用读者"
    - 写 YAML 配置并需要快速对齐语法边界的使用方
    - 需要排查 schema/校验行为的开发者

本页聚焦 YAML DSL 的整体结构、容易误解的约束与排错入口.字段级别的完整说明与示例请看 [用户指南](user-guide.md).维护 schema 与编辑器补全请看 [Schema Meta 参考](schema-meta.md).

??? note "维护提示"
    本页内容通常会在以下变更后需要同步检查:

    - JSON Schema 结构/默认值/枚举调整
    - 语义校验规则变更(unknown fields、约束收紧/放宽)
    - `relations` / `params` / `outputs` 等关键语义调整
    - Python 引用解析与 allowlist 规则调整(影响 `loader` / `call_by`)

## 1. 语法的事实来源在哪里

YAML DSL 的语法有两层来源:

1. JSON Schema(结构与类型)
   - CLI: `scalim-cli yaml-dsl schema show` / `scalim-cli yaml-dsl schema path`
   - 参考页: [YAML Schema 参考(生成)](schema-reference.gen.md)
2. 内置 validator(语义规则,超出 schema 的部分)
   - 入口: `scalim-cli yaml-dsl validate ...`

如果两者出现不一致,以 `validate` 的运行时行为为准.

## 2. 顶层结构(骨架)

顶层 key 的顺序在 schema 里是固定的(只是展示顺序,不影响解析). 当前 schema 要求:

- 必填: `name`, `main_source`
- 完整字段集合与 `required` 边界见: [YAML Schema 参考(生成)](schema-reference.gen.md)

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
meta: false             # 可选: true 或对象(写入 meta sheet)
audit: false            # 可选: true 或对象(写入 audit sheet)
outputs: []             # 可选: 多输出编排(有序列表)
failure_policy: all_fail             # 可选: all_fail/primary_only
include_full_error_message: false    # 可选
observability: {}       # 可选
```

提示:

- 顶层已不再支持旧写法 `output:`(会 fail-fast).请使用 `outputs:`(有序列表)描述输出编排.
- `outputs` 可省略.省略时默认不写文件;如需写文件,请在 YAML 中声明 `outputs` 或在 Python 调用侧使用 `overrides.outputs` 显式指定(整体替换,replace).
- `field_id` 必须全局唯一(不再支持 `source.field_id` 消歧).

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

`outputs.*.to` / `outputs.*.write` / `resources.files.*` 等 mapping 节点非常适合用 YAML merge(`<<`)复用基础配置:

- YAML merge 会生成新对象,丢失 alias 身份
- merge 产物必须仍然满足 schema 与语义校验(例如 `resources.files.*.kind/path` 必填; 多 sheet 共享 workbook 时每个 output 需显式 `to.sheet`)

### 3.4 跨文件复用: `imports` / `$import` (V1: 同级文件)

当一个 demand 配置变大后,常见做法是把 `sources/relations/fields` 等片段拆分成多个文件复用.为此 Scalim 提供编译期 `imports/$import` 展开能力:

- 顶层新增 `imports: {<alias>: <fragment.yaml>}` 映射
- 在任意 mapping 节点内允许 `$import`(string 或 string list):
  - `$import: common.sources`
  - `$import: [common.sources, other.sources]`
- `$import` 引用格式: `<alias>(.<segment>)*`(点路径下钻)
- 合并规则(确定性):
  - mapping: deep-merge
  - list: replace(本地覆盖导入)
  - 类型不匹配: fail-fast
- **V1 路径限制**: `imports.*` 仅允许同级文件名: `x.yaml|x.yml` 或 `./x.yaml|./x.yml`(禁止绝对路径/父目录/子目录/alias 前缀)
- **仅文件路径入口支持**: `scalim.dsl.by_yaml.run/compile(yaml_path)` / `scalim-cli yaml-dsl validate <file.yaml>` 等会先展开再校验;纯文本入口会 fail-fast 并提示改用文件路径入口

一个最小示例:

```yaml
imports:
  common: common.yaml

sources:
  $import: common.sources
  my_source:
    loader: "myapp.loaders:load_x"
    key: id
```

## 4. 引用 Python: loader / call_by

YAML 里引用 Python 可调用对象的地方主要有两类:

- `main_source.loader` / `sources.<id>.loader`: loader 引用
- `fields.<id>.call_by`: 派生字段函数调用

### 4.1 Python 引用格式(absolute/relative)

- 绝对引用:
  - 点式引用: `module.path.function`
  - 类式引用: `module.path:ClassName` / `module.path:obj.method`
- 相对引用:
  - 以 `.` / `..` 开头的 module path,相对 YAML 文件所在目录对应的模块路径
  - 运行期会先归一化为绝对引用,再做 allowlist 校验

### 4.2 内置 callable 快捷方式: `^<id>`

`^<id>` 是一类 **plain string** 的内置引用,用于在 `loader` / `call_by` 等位置通过“受控词表”(vocabulary)稳定引用一批可调用对象:

- Python 引用仍受 allowlist 约束
- `^<id>` 的解析与执行 **不要求**把其目标模块加入 allowlist(unknown id 会 fail-fast 并提示一份保守的可用 id 列表)
- `<id>` 为可定制的词表 key,推荐使用 `/` 分段表示命名空间(例如 `workflow/book_sheet_rows`)
- 默认词表仅提供少量 Scalim 内置 id(保守暴露);下游可在 `run/compile(..., builtin_callables=...)` 中注入/扩展词表

示例(loader):

```yaml
main_source:
  loader: ^workflow/book_sheet_rows
```

示例(call_by):

```yaml
fields:
  rows:
    call_by: "^workflow/book_sheet_rows(ref)"
```

### 4.3 allowlist 是运行时参数

注意: `allowed_modules`/`allowed_functions` 是 Python 运行入口参数,不是 YAML 字段.

## 5. relations 与 relation 引用方式

### 5.1 relation 的基本形态

`relations` 是一个命名映射,每个条目是一个 `steps` 数组,每步至少包含:

- `from`: `<source_id>.<field_id>`
- `to`: `<source_id>.<field_id>`

### 5.2 relation 在字段里怎么引用

源字段里用 `relation` 指定“从 main_source 到当前字段 source”的链路,支持三种写法:

1. string ref 引用: `relation: <relation_id>` (引用 `relations.<relation_id>`)
2. YAML alias 引用(指向一个已定义的 relation 对象)
3. 内联 `steps: [...]`

要点:

- 推荐优先使用 string ref,减少对 YAML anchors/alias 的依赖
- 使用 alias 时,alias 必须先在 `relations` 里定义(这是 YAML 的约束)

## 6. params 模板: `$keys` / `$rows` / `{$init_var: ...}`

Scalim 把 loader 的调用参数统一收敛到 `params` kwargs 模板:

- `main_source.params`: 直接以 kwargs 传给 main source loader
  - 支持 `{$init_var: <name>}` 指令节点(编译期解析)
  - 禁止 `$keys/$rows`
- `sources.<id>.params`: loader kwargs 模板
  - 支持 `{$init_var: <name>}` 指令节点(编译期解析;单键映射;不做子串插值)
  - 支持 `$keys` 注入 lookup keys(可出现在任意嵌套位置):
    - `{$keys: {as: set|list}}`(默认 set)
    - `$keys.as=list` 会输出稳定顺序列表; composite key 注入为 tuple 元素
  - 支持 `$rows` 注入批次行上下文(可出现在任意嵌套位置):
    - `{$rows: {cache_mode: batch|none}}`(默认 batch)
    - `$rows.cache_mode=none` 会禁用批次内 relation 复用(每个字段各自调用 loader)

指令节点范围约束(稳定 authoring surface):

| 位置 | `{$init_var: ...}` | `{$keys: ...}` | `{$rows: ...}` |
|---|---|---|---|
| `main_source.params` | ✅ | ❌ | ❌ |
| `sources.<id>.params` | ✅ | ✅ | ✅ |
| `resources.files.<id>.path` | ✅ | ❌ | ❌ |

补充:

- `{$init_var: <name>}` 是**对象节点**(单键 mapping),仅在编译期解析一次为 `init_vars[<name>]`。
- 系统不会对字符串做任何子串替换(例如 `"x=$init_var.end_dt"` 会保持原样字符串).

执行语义上,`$rows` 会影响调度边界:

- `parallel_mode="adaptive"` 时,调度器会把 `$rows` 视为 barrier,该层直接串行执行(见 [并行模式](../architecture/parallel-modes.md)).

## 7. outputs: 多输出编排(有序)

`outputs` 是 demand YAML 的“多输出编排”入口(有序列表):

- 每个 output 必填唯一 `name`(供 `from` 引用)
- `to` 描述输出目标绑定:
  - `to.file` 绑定到 `resources.files.<file_id>`
  - `to.book` / `to.sheet` 绑定到 `resources.books.<book_id>`
- 输出路径写在 `resources.files.*.path` / `resources.books.*.(path|export_xlsx.path)`;支持静态 string 或 `{$init_var: <name>}`(对象节点;仅编译期解析一次;不做子串插值)
- 明细输出使用 `fields: [field_id, ...]` 指定导出列顺序
- `where` 是安全表达式,用于分发过滤;其依赖字段会在编译期注入 required fields
- 派生汇总输出使用 `aggregate`(与 `fields` 互斥)
- `from` 可复用另一个 output 的字段集合与 `to/write` 编排(未声明则继承; `where/aggregate` 不继承)

辅助配置:

- 顶层 `failure_policy` / `include_full_error_message` 控制 composed outputs 的失败策略与错误信息脱敏
- 顶层 `meta` / `audit` 可开启额外 sheet(默认写入 primary Excel 输出的 book)
- 若运行时没有任何 Excel 输出可作为默认 book,则 `meta/audit` 可能被跳过；如需强制输出,请显式设置 `meta.path` / `audit.path`

一个最小示例:

```yaml
meta: true
audit: true

resources:
  books:
    report:
      kind: xlsx_file
      path: ./out.xlsx
      write_lock: true

_templates:
  report_to: &report_to {book: report}

outputs:
  - name: detail
    to: {<<: *report_to, sheet: 明细}
    fields: [order_id, customer_name, amount_yuan]

  - name: direct
    from: detail
    to: {<<: *report_to, sheet: 直客明细}
    where: "channel == 'direct'"

  - name: by_channel
    to: {<<: *report_to, sheet: 渠道汇总}
    aggregate:
      group_by: [channel]
      fields:
        order_cnt: {count: {}}
        sum_amount: {sum: {field: amount_yuan}}
```

## 8. 校验与排错: 先用什么命令

推荐顺序:

1. 结构校验(JSON Schema):

```bash
scalim-cli yaml-dsl schema validate path/to/file.yaml --verbose
```

2. 语义校验(内置 validator,会做更多规则检查):

```bash
scalim-cli yaml-dsl validate path/to/file.yaml --verbose
```

如果你看到 “legacy field 不允许” 这类错误,通常来自 CLI 的兼容性限制.

## 下一步

- [用户指南](user-guide.md)
- [编辑器](editor.md)
