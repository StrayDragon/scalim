# yaml-dsl-schema (delta)

## ADDED Requirements

### Requirement: YAML DSL JSON Schema MUST recursively standardize markdownDescription
系统 MUST 在生成 YAML DSL JSON Schema 时，对 schema 中可被 authoring surface 触达的节点递归生成/改写 `markdownDescription`，覆盖范围至少包括：

- demand schema: `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
  - 顶层 `properties.*`
  - `definitions.*` 下的 `properties.*`（以及其后续嵌套节点：`items`、`oneOf/anyOf/allOf` 子节点等）
- workflow schema: `src/IMPL_ROOT/dsl/by_yaml/schema/workflow.gen.json`（同上递归）

`markdownDescription` MUST 使用统一的 Markdown 模板（见下一个 Requirement），以便 IDE/LSP、docs 生成与 agent reference 可以稳定消费。

#### Scenario: every property has a markdownDescription with a path heading
- **WHEN** 维护者执行 `just gen-yaml-dsl-schema`
- **THEN** 生成物中的 `properties.*` 与 `definitions.*.properties.*` MUST 均包含 `markdownDescription`
- **AND** 其 `markdownDescription` MUST 以 `#### ` 开头（标题行）
- **AND** 标题行 MUST 包含可自动推导的“配置路径”（包含上下文；例如 `main_source.loader`、`outputs[*].aggregate.kind`）

### Requirement: markdownDescription MUST follow one of two templates (brief/full)
系统 MUST 将每个配置项的 `markdownDescription` 规范化为两种模板之一，并保持从上到下固定顺序。

#### Template: brief

适用：基础容器节点/无争议字段（例如 `main_source` 这类分组节点）。

```markdown
#### <配置路径>

<短说明(1~3 行)>
```

#### Template: full

适用：枚举/复杂约束/outputs 聚合等需要完整解释与示例的节点。

````markdown
#### <配置路径>

<说明(可多段；包含枚举取值语义、常见坑、迁移提示等)>

##### 字段约束
<由 JSON Schema 自动生成的约束摘要(稳定顺序)>

##### 例子
```yaml
<示例片段>
```
````

说明：
- “配置路径” MUST 包含上下文以减少歧义（例如 `main_source.loader` vs `source.loader`），且 MUST 由生成器自动推导（不得手写维护）。
  - 分隔符使用 `.`；数组 items 用 `[*]`；mapping 动态 key 用 `*`
- “短说明/说明” SHOULD 来自该节点的 SSOT 描述（例如 `schema_meta(desc=...)` / 既有 `description/markdownDescription` 的首行或正文），并可被同步写入 `description`（纯文本）以供非 markdown 消费方使用。

#### Scenario: title line uses auto-generated config path
- **WHEN** 用户在编辑器 hover 任意 YAML 字段
- **THEN** hover 的首行 MUST 为 `#### <配置路径>` 形式
- **AND** 该 `<配置路径>` MUST 由生成器自动推导（不依赖手写维护）

#### Scenario: title disambiguates common field names
- **WHEN** 用户在编辑器分别 hover `main_source.loader` 与 `sources.*.loader`
- **THEN** 两者的标题行 MUST 不同
- **AND** 标题行 MUST 分别包含 `main_source.loader` 与 `source.loader`（或等价的上下文路径表达）

### Requirement: full template MUST include auto-generated constraints
当某节点选择 `full` 模板时，系统 MUST 从生成后的 JSON Schema 节点自动推导并输出“字段约束”摘要（不得手写重复约束文案），至少覆盖：

- required/optional（当上下文可确定时）
- type/oneOf/anyOf/allOf（含 `null` 的可空语义）
- enum/default/pattern/min/max/minItems/maxItems/minProperties/maxProperties/additionalProperties/propertyNames
- `$import` 的 required workaround：
  - 当某 object schema 采用 `anyOf: [required=<core>, required=[$import]]` 允许“仅 `$import`”通过校验时
  - 约束摘要 MUST 将其表达为“满足 core required 集合 **或** 仅提供 `$import`”的二选一语义

#### Scenario: constraints reflect required vs optional and import workaround
- **WHEN** 维护者查看 `demand.gen.json` 中某必填字段与某可选字段的 hover
- **THEN** “字段约束”小节 MUST 明确其 required/optional
- **AND** 若该节点支持 `$import` 且存在 required workaround，摘要 MUST 明确其二选一语义

### Requirement: full template MUST include examples sourced from schema + fixture snippets
当某节点选择 `full` 模板时，系统 MUST 在 `markdownDescription` 的“例子”小节输出可直接用于 YAML authoring 的示例，来源优先级如下：

1. schema 节点的 `examples`
2. 从可运行 canonical YAML fixtures 中提取的 **局部片段**（通过 YAML comment 行 `# <!-- BEGIN/END AUTOGEN:<id> -->` 标记块提取；避免手写片段导致漂移/不可运行；保持 YAML 可运行）
3. 兜底：生成一个最小合法示例骨架（能够通过 schema-only 校验），并明确其为最小示例

#### Scenario: examples are present and rendered as YAML
- **WHEN** schema 节点存在 `examples`
- **THEN** “例子”小节 MUST 至少包含一个 YAML code block
- **AND** 该 code block 中的示例 MUST 与 `examples` 保持语义一致（允许格式化差异）

#### Scenario: fixture snippets are used when examples are absent
- **GIVEN** 某 schema 节点缺少 `examples` 但存在 snippet 提取配置
- **WHEN** 维护者执行 `just gen-yaml-dsl-schema`
- **THEN** 该节点的 “例子” 小节 MUST 包含由 snippet 提取生成的 YAML code block

### Requirement: enum fields MUST use full template and document per-choice behavior
对于包含 `enum` 的字段（含 `items.enum`），系统 MUST 使用 `full` 模板，并在“说明”部分明确列出每个枚举值的行为/结果差异（取值语义），以避免仅有 `enum=...` 的约束摘要但缺少可理解的语义。

#### Scenario: enum docs list every value and explain behavior
- **GIVEN** 某字段 schema 包含 `enum: ["a", "b", ...]`
- **WHEN** 维护者执行 `just gen-yaml-dsl-schema`
- **THEN** 该字段的 `markdownDescription` “说明”部分 MUST 以反引号引用每个枚举值（例如 `a`/`b`）
- **AND** 对每个枚举值 MUST 给出简短的行为/结果说明（可以是一行）

### Requirement: snippet extractor MUST support nested blocks and remove nested markers
系统用于从 fixtures 提取示例片段的 extractor MUST 支持不同 snippet id 的嵌套，并满足：

- 对某个外层 snippet 提取时，内层 snippet 的 BEGIN/END marker 行 MUST 被移除（不应出现在最终例子 code block 中）
- 性能 MUST 为单次扫描（单文件 O(N)），不得按 snippet id 对文件重复扫描

#### Scenario: nested snippet extraction yields clean YAML
- **GIVEN** 某 fixture 中存在嵌套的 snippet blocks
- **WHEN** 提取外层 snippet
- **THEN** 输出片段 MUST 不包含任何 `# <!-- BEGIN/END AUTOGEN:... -->` marker 行

### Requirement: schema doc generation MUST be zero-cost to runtime
系统 MUST 确保上述文档标准化逻辑仅发生在 schema 生成阶段（`just gen-yaml-dsl-schema`），并满足：

- runtime compile/validate/runs 的关键链路不依赖该逻辑
- 不引入额外的 runtime 热路径开销（时间/内存）

#### Scenario: runtime behavior is unchanged
- **WHEN** 用户仅运行 YAML DSL runtime（compile/validate/run/workflow run）
- **THEN** 系统行为 MUST 与变更前一致（仅 schema 文案与编辑器 hover 改善）
