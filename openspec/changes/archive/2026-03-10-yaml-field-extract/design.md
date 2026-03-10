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

- 给源字段新增 declarative `extract` 配置,并将其作为唯一稳定的字段取值入口,用于从“当前 key 对应的 row value”读取值。
- 明确 `extract` 的起点只省略最外层 `lookup_key -> value` 包装,不会再隐式跳过 value 内部第一层。
- 一次性升级仓库内 YAML: `fields.*.field` 退出稳定 YAML authoring surface,不保留兼容分支。
- 让 schema / editor / docs / skill 对这套认知给出一致说明,尤其是 JSON Schema 的 `description` / `markdownDescription`。
- 为未来 `extract_fn` 预留干净命名空间。

**Non-Goals:**

- 不在本变更中引入 source-level whole-result normalize;该能力由 `yaml-source-normalize` 单独负责。
- 不在本变更中开放任意 Python 函数型 extractor.
- v1 不支持数组下标、通配符、JSONPath 或更通用的表达式语法;`[1]` 永远表示 “key=1”,不是 list index。

## Decisions

### 1) Public YAML surface uses `extract` only; remove legacy `field`

新增 `sources.<id>.fields.<field_id>.extract` 与 `main_source.fields.<field_id>.extract`,并将其作为**唯一稳定**的字段取值入口。

语义:

- `extract` 可写顶层 key rename 或路径表达式(见 Decision 3)。
- 若未声明 `extract`,默认等于 `field_id`(即顶层同名 key)。
- 历史 `field: ...` 在校验/转换阶段 MUST fail-fast 并给出迁移提示: “请改用 extract: ...”。

这样做的直接好处:

- 单一心智模型: YAML 作者只需要理解 `extract` 一种取值语法。
- 字面量 dotted key / 特殊 key 不再需要 `field` 逃生口,统一用 `extract: [\"a.b\"]` 形式表达(见 Decision 3)。

备选方案:

- 保留 `field` 作为 raw flat selector
- 直接复用 `field` 承载点语法

拒绝原因:

- `field`/`extract` 双轨会引入长期学习成本与文档漂移风险(尤其当业务 loader 结果形状差异很大时)。
- 将点路径叠加到 `field` 会把 “rename” 与 “path” 混在一个字段里,更不利于长期维护。

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

### 3) `extract` uses a dot+bracket path expression (typed, no implicit cast)

`extract` 是字符串 path expression,由一串 segment 组成:

- 点号 `a.b.c`: string segment(标识符)。
- 方括号:
  - `[1]`: int key segment(用于 `row[1]` 这类非字符串 key)。
  - `["a.b"]` / `['a.b']`: string key segment(用于字面量含点号/空格/特殊字符的 key)。

核心约束:
- 系统 MUST NOT 做 `"1" -> 1` 或 `1 -> "1"` 的自动转换,避免 `\"1\"` 与 `1` 同时存在时的歧义。
- v1 MUST NOT 支持数组下标语义:`[1]` 永远表示 “key=1”,不是 list index(即使中间值是 list/tuple,也不得把 `[1]` 当索引)。
- bracket int segment 仅支持非负十进制(`[0-9]+`),不允许符号位或空白(例如 `[-1]`、`[ 1 ]` 都是非法表达式)。
- bracket string segment 支持最小转义,用于表达包含引号或反斜杠的 key(例如 `\\`/`\"`/`\'`),其它转义应 fail-fast(避免引入更复杂的字符串语义)。

逐段规则:

- 任一 segment 解析失败即返回 `None`
- 不支持空 segment / 连续点 / 首尾点 / 非法括号表达式
- v1 不支持通配符、JSONPath、表达式求值

读取策略(与现有 `extract_field(...)` 一致风格):
- 每段优先按 mapping key 读取
- string segment 允许回退到对象属性读取
- 最后回退到 `__getitem__`

这样可以在保持现有 getter 认知的前提下,用最小增量覆盖 nested row 与非字符串 key 场景,消除“只为取值写 wrapper”的成本。

### 4) Compile `extract` into a canonical parsed representation; do not overload `data_key` string parsing

为避免把 “路径语法解析” 分散到多个运行时 callsite,编译阶段 MUST 将 `extract` 解析为 canonical representation(例如 `Tuple[Union[str, int], ...]` 的 segments)并在运行时直接消费。

理由:

- `extract` 中存在 `["a.b"]` 这类“单段但包含点号”的合法写法,不能仅靠字符串里是否包含 `.` 来推断是否路径;
- `extract` 允许 typed segments(`[1]`),运行时必须保留类型信息,不能做隐式 cast;
- 单一的 canonical representation 可确保主加载与 ref-load 两条路径完全一致。

实现提示:
- 仍可在 IR 层保留 `FieldIr.data_key` 作为“显示/诊断友好的原始表达”(例如原始 extract 字符串或其规范化文本)；
- 但运行时读取 MUST 基于解析后的 segments,而不是对 `data_key` 再做 ad-hoc 解析。

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

- [引入 bracket 语法] → 用最小语法覆盖非字符串 key 与字面量特殊 key,并在 schema hover / skill 中给出“模板化例子”(例如 `'[1].x'`、`'["a.b"]'`)。
- [语法解析错误影响体验] → 编译/校验阶段 fail-fast 且错误包含配置 path,并给出修复建议(例如 “数字 key 请写 `[1]`,字符串 key 请写 `["1"]`”)。
- [路径读取失败静默为 `None`] → 保持与当前 flat getter 缺失即 `None` 的语义一致,并通过 guardrails/required_fields 继续兜底。

## Migration Plan

1. 在 source field schema/model/parser/validator 中新增 `extract` 并移除 `field`(出现 `field` 即 fail-fast 并给迁移提示)。
2. 在 YAML → IR 编译链路中将 `extract` 解析为 canonical segments;未声明 `extract` 时默认等于 `field_id`。
3. 扩展执行期字段读取 helper,支持 dot+bracket segments 的逐段读取,并确保主加载与 ref-load 两条路径一致。
4. 更新 schema / editor / docs / `scalim-yaml-dsl` skill: 以 `extract` 作为唯一取值写法,补齐 bracket 示例与常见反例。
5. 升级仓库内 YAML 示例/fixtures/notebooks/skill 产物,并通过 drift/validate/test 确认升级完成。

## Open Questions

- `extract_fn` 未来是字符串引用、受 allowlist 约束的 Python 引用,还是受限 declarative preset?
- v2 是否需要支持数组索引或转义点号,还是继续鼓励业务把这类结构保留在 wrapper/normalize?
