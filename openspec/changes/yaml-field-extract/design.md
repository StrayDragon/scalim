## Context

当前 YAML 源字段的读取语义只有一层:

- `SourceFieldConfig.field`
- `FieldIr.data_key`
- `extract_field(data, data_key)`

其中 `data` 的运行时起点已经不是整个 `loader_result`,而是当前 key 对应的单条 value:

- 主加载路径读取 `result[row_id]`
- 关联加载路径读取 `result[lookup_key]`

这意味着“从当前 row value 继续向下取嵌套值”本质上是字段级读取问题,而不是 source-level whole-result normalize 问题。当前因为 YAML 没有这层 declarative 能力,一旦下游 loader 返回 `{"CustomerMark": {...}}` 这种嵌套对象,用户就被迫写薄 wrapper 先拍平结果。

同时仓库里已经存在另一个相邻概念:

- `LoaderIr.extractor`: source 级、per-key 的结果提取器

如果不把两者拆开,后续 `extract`/`normalize`/`extract_fn` 的命名和实现都会互相污染。

## Goals / Non-Goals

**Goals:**

- 给源字段新增 declarative `extract` 配置,用于从“当前 key 对应的 row value”读取值。
- 明确 `extract` 的起点只省略最外层 `lookup_key -> value` 包装,不会再隐式跳过 value 内部第一层。
- 保持现有 YAML 的兼容面: 现有 `field` 写法继续工作,但其语义保持为 raw flat selector。
- 让 schema / editor / docs / skill 对这套认知给出一致说明,尤其是 JSON Schema 的 `description` / `markdownDescription`。
- 为未来 `extract_fn` 预留干净命名空间。

**Non-Goals:**

- 不在本变更中引入 source-level whole-result normalize;该能力由 `yaml-source-normalize` 单独负责。
- 不在本变更中开放任意 Python 函数型 extractor.
- v1 不支持数组下标、转义点号、JSONPath 或更通用的表达式语法。

## Decisions

### 1) Public YAML surface uses `extract`; legacy `field` remains the raw flat selector

新增 `sources.<id>.fields.<field_id>.extract` 与 `main_source.fields.<field_id>.extract`.

语义:

- `extract` 是新的稳定 authoring surface,可写平铺键名或点路径。
- `field` 保留既有含义: 表示当前 row value 顶层的 raw key / 列名,不承担点路径语义。
- `field` 与 `extract` MUST 互斥;同时出现时 fail-fast。
- 若二者都未声明,默认仍为 `field_id`.

这样做有两个直接好处:

- 现有 YAML 不破坏;
- 若 row value 顶层真的存在字面量键名 `\"a.b\"`,用户仍可通过 `field: a.b` 读取,不会被 `extract` 的点语法误拆。

备选方案:

- 直接复用 `field` 承载点语法
- 对外暴露 `data_key`

拒绝原因:

- `field` 已在现有 DSL 中稳定表示“字段来源列名/键名”,强行叠加点路径会破坏认知并和现有 schema 文案冲突。
- `data_key` 是合适的内部/IR 名词,但对 YAML 作者不够直观,也不利于未来扩展到 `extract_fn`.

### 2) `extract` is resolved relative to the current row value

`extract` 的根节点定义为“当前 key 对应的 normalized row value”,而不是外层 `loader_result` 映射。

等价运行时形态:

- 主加载: `data = result[row_id]`
- 关联加载: `data = result[lookup_key]`

因此:

- `extract: CustomerMark.clearn_reason_level` 从 `data["CustomerMark"]["clearn_reason_level"]` 开始解析;
- 若 `data` 其实是 `{"payload": {...}}`,则必须显式写 `extract: payload.CustomerMark.clearn_reason_level`;
- 系统 MUST NOT 再隐式跳过 `payload` 这一层。

这条认知必须原样进入 JSON Schema `description` / `markdownDescription`,避免作者误以为 `extract` 可以相对整个 `loader_result` 或自动忽略内部包裹层。

### 3) Path traversal is segment-wise and reuses existing getter semantics

`extract` 采用 `a.b.c` 点语法,编译后按 segment 逐层读取。

单段读取沿用当前 flat getter 的优先级:

1. `Mapping[key]`
2. `getattr(obj, key)`
3. `obj[key]`

逐段规则:

- 任一 segment 解析失败即返回 `None`
- 不支持空 segment / 连续点 / 首尾点
- v1 不支持数组索引、转义点号、通配符

这样可以最大化复用现有 `extract_field(...)` 的认知和运行时兼容面,而不是为字段级路径引入一套全新取值器。

### 4) Internal IR keeps a normalized effective selector instead of adding a broad new field model

为控制变更面,v1 不强制扩展 `FieldIr` 为全新 extractor IR.

编译时生成一个“effective selector”:

- `extract` 优先
- 否则 `field`
- 否则 `field_id`

该 effective selector 继续落入现有 `FieldIr.data_key`,运行时读取器负责识别是否包含点路径并逐段解析。

理由:

- 降低 IR / planner / executor 的横向改动;
- 与现有 output resolver、field index、diagnostics 更容易保持兼容;
- 未来若要增加 `extract_fn`,仍可在不破坏当前 YAML surface 的前提下再引入更显式的 IR 节点。

代价:

- `data_key` 这个内部名字在实现上会承载“平铺键名或路径选择器”的更宽语义;
- 但这是可接受的内部折衷,公开 YAML 仍统一使用 `extract`.

### 5) `output.fields` selector semantics stay unchanged in v1

本变更不修改 `output.fields` 中显式 `{field: ...}` 选择器的语义。

理由:

- `yaml-field-extract` 的目标是字段读取,不是输出选择器重构;
- 若让 `{field: ...}` 同时匹配 `extract`,会把“字段提取能力”扩成“输出选择器语义变更”,影响面过大;
- 仓库已经推荐优先用 `field_id` / alias 选择输出字段,因此 `extract` 字段不需要强行复用 `{field: ...}` 入口。

v1 约束:

- `output.fields` 的 `{field: ...}` 继续按既有 raw flat selector / data_key 语义工作
- 使用 `extract` 的字段若需要在 `output.fields` 中显式选择,应优先使用 `field_id` 或 alias
- 如后续确有需要扩展 `{field: ...}` 去匹配 `extract`,应作为单独 change 讨论

## Risks / Trade-offs

- [`field` / `extract` 双轨并存带来学习成本] → 通过 schema hover 和 skill 明确区分: `field` 是 raw flat selector,`extract` 是新的稳定 declarative 提取语法。
- [点语法无法表示字面量 dotted key] → 保留 `field` 的 raw flat 语义作为逃生口。
- [内部 `data_key` 语义变宽] → 在 design/spec 中明确这是内部兼容折衷,公开 authoring surface 统一用 `extract`。
- [路径读取失败静默为 `None`] → 保持与当前 flat getter 缺失即 `None` 的语义一致,并通过 guardrails/required_fields 继续兜底。

## Migration Plan

1. 在 source field schema/model/parser/validator 中新增 `extract`,并建立与 `field` 的互斥校验。
2. 在 YAML → IR 编译链路中生成 effective selector(`extract` > `field` > `field_id`),暂存到现有 `FieldIr.data_key`.
3. 扩展执行期字段读取 helper,支持对 dotted selector 按 segment 逐层读取。
4. 更新 output-field resolver/index,使 `{field: ...}` 仍能匹配 effective selector.
5. 更新 schema / editor / docs / `scalim-yaml-dsl` skill,明确 `extract` 的 current-row-relative 语义与常见反例,并说明 `output.fields` 仍优先使用 `field_id` / alias。

## Open Questions

- `extract_fn` 未来是字符串引用、受 allowlist 约束的 Python 引用,还是受限 declarative preset?
- v2 是否需要支持数组索引或转义点号,还是继续鼓励业务把这类结构保留在 wrapper/normalize?
