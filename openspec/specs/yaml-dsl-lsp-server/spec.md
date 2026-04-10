# yaml-dsl-lsp-server Specification

## Purpose
定义 YAML DSL LSP server 的语义 contract：诊断（diagnostics）与 Python 引用的 definition/hover/completion，并要求 server 侧复用 shared core，
以保证跨编辑器一致、静态无副作用且可诊断降级（不 crash、不退出、不依赖 shell-out CLI）。
## Requirements
### Requirement: YAML DSL LSP server MUST NOT shell out to CLI and MUST reuse scalim library semantics
系统 MUST 定义并支持一个 YAML DSL 语义 LSP server,其实现约束如下:

- LSP server MUST 以 `scalim` 作为 library 依赖复用 validator/schema/解析逻辑
- LSP server MUST NOT 通过 shell-out 调用 `PROJECT_CLI_NAME` 或读取 CLI 文本输出再解析
- LSP server MUST 在缺失可选依赖时降级为可诊断的 warning(而不是崩溃/无响应)

#### Scenario: diagnostics request is served without invoking CLI
- **WHEN** 编辑器请求某个 YAML 的 diagnostics
- **THEN** LSP server MUST 使用 library API 直接返回结构化 diagnostics
- **AND** 不得依赖 CLI 子进程

### Requirement: LSP server MUST avoid polluting non-DSL YAML documents
系统 MUST 在提供 YAML DSL 语义能力前进行 DSL 探测,并满足:

- 对非 DSL YAML,server MUST 发布空 diagnostics
- 对非 DSL YAML,server MUST 对 go-to-definition/hover/completion 返回空结果(不得 crash)
- DSL 探测 MUST 优先依据 schema 顶层 required:
  - 当 YAML 根 mapping 包含键 `workflow` 且其值为 mapping 时,该文件 MUST 被视为 workflow DSL
  - 当 YAML 根 mapping 同时包含键 `name` 与 `main_source` 时,该文件 MUST 被视为 demand DSL
- 当 required 未满足时,server MAY 使用 DSL 专属语法特征作为 permissive fallback（例如 `$import/$init_var`、`loader/call_by`、schema modeline 指向 scalim schema）

#### Scenario: unrelated YAML produces no diagnostics
- **GIVEN** 某 YAML 不满足 schema(required) 且不包含 DSL 专属语法特征
- **WHEN** client 请求 diagnostics
- **THEN** server MUST 返回空 diagnostics

#### Scenario: in-progress DSL YAML still enables editor semantics via fallback
- **GIVEN** 某 YAML 尚未写全 required 字段
- **AND** 其文本包含 DSL 专属语法特征（例如 `loader:` 或 `$import`）
- **WHEN** 用户触发 go-to-definition
- **THEN** server SHOULD 尽最大努力返回可解析的定义位置,失败时 MUST 返回空结果且包含可诊断 warnings

### Requirement: demand diagnostics MUST match CLI validate semantics (path + location)
对 demand YAML,系统 MUST 保证 LSP diagnostics 与 `PROJECT_CLI_NAME yaml-dsl validate` 的语义一致:

- 逻辑路径 MUST 使用 canonical 点号口径(数组索引用数字段)
- diagnostics MUST 能映射到稳定的源码位置 range(尽可能精确到字段/值)
- 对同一错误形态,CLI 与 LSP 的 message SHOULD 保持一致(差异仅限展示格式)

#### Scenario: canonical path and range are produced
- **GIVEN** 某 demand YAML 在语义 validator 下产生一条错误 issue
- **WHEN** 编辑器请求 diagnostics
- **THEN** 返回的 diagnostic MUST 包含 canonical dot path
- **AND** MUST 包含可用于编辑器 underline 的 range

### Requirement: workflow diagnostics v1 MUST be schema-only
对 workflow YAML,v1 MUST 保持与当前实现边界一致,仅提供 schema-only 校验与 unknown-fields 诊断:

- workflow diagnostics MUST 基于 `workflow.gen.json` 与对应的 unknown-fields 规则
- 系统 MUST NOT 在 v1 进行 runtime compile/run 语义诊断(避免引入不稳定的副作用与执行成本)

#### Scenario: workflow schema error yields diagnostics
- **GIVEN** 某 workflow YAML 违反 JSON Schema
- **WHEN** 编辑器请求 diagnostics
- **THEN** LSP server MUST 返回至少一条 schema-based diagnostic

### Requirement: Go to Definition MUST resolve `loader`/`call_by` references statically
系统 MUST 为 `loader`/`call_by` 等 Python 引用字段提供 go-to-definition,且解析 MUST 为静态解析(不执行用户代码):

- 引用格式 MUST 支持 `module:attr` 与 `module.attr`
- 引用格式 MUST 支持相对模块引用（前导 `.`），例如 `.loaders:func` / `..loaders:func`
- 对 `call_by: "pkg.mod:fn(arg=...)"` 形态,definition 至少 MUST 能解析并处理 `pkg.mod:fn`（参数段忽略）
- 定义定位 MUST 基于 project discovery 的 `python_roots` 与文件系统/AST 分析
- 当引用为相对模块时，系统 MUST 基于文档 URI 推导 `yaml_path` 并交由 shared core 在 `yaml_path + python_roots` 上下文内完成规范化与解析
- 对 `module:obj.method` 形态，系统 MUST 复用 shared core 的静态推断能力，尽可能把第一个 location 定位到真实实现（例如 `Klass.method`）
- definition MUST 支持返回多个 locations，且 MUST 稳定排序 + 去重：
  - locations MUST 稳定排序：真实实现优先；同优先级按 path → line 排序
  - locations MUST 去重：同 URI + 同 range 视为同一候选
- 解析失败时 MUST 返回空结果且给出可诊断信息(不得 crash)

#### Scenario: definition resolution locates a Python function
- **GIVEN** YAML 中某字段引用 `pkg.mod:func`
- **WHEN** 用户触发 go-to-definition
- **THEN** 系统 MUST 返回 `func` 定义所在文件与范围

#### Scenario: relative module definition resolution locates a Python function
- **GIVEN** YAML 文件位于某个 `python_roots` 之下
- **AND** YAML 中某字段引用 `.loaders:load_orders`
- **WHEN** 用户触发 go-to-definition
- **THEN** 系统 MUST 返回 `load_orders` 定义所在文件与范围

#### Scenario: go-to-definition returns method location plus object fallback for `obj.method`
- **GIVEN** YAML 中某字段引用 `pkg.mod:some_ref.a_method`
- **AND** 在 `pkg.mod` 中存在 `some_ref = Klass()` 且 `Klass.a_method` 存在
- **WHEN** 用户在引用字符串内触发 go-to-definition
- **THEN** 系统 MUST 返回至少 2 个 locations
- **AND** 第一个 location MUST 指向 `Klass.a_method`
- **AND** 后续 location MUST 包含 `some_ref` 的定义/赋值位置

### Requirement: Go to Definition MUST support `$import` references statically
系统 MUST 为 demand YAML 中的 `$import` 引用提供 go-to-definition，且解析 MUST 为静态解析（不执行用户代码，不 shell-out CLI）：

- `$import` 引用格式 MUST 支持 `<alias>(.<segment>)*`
- 系统 MUST 基于当前文档顶层 `imports` 映射解析 `<alias>` 对应的 fragment 来源
- 系统 MUST 支持 `scalim.yaml` 中的 `import_roots` 重写 imports 路径解析（与 runtime imports 解析一致）
- 若 `$import` 引用可解析为 fragment YAML 文件与目标 mapping 位置，系统 MUST 返回该位置的 `Location`
- 解析失败 MUST 返回空结果且给出可诊断 warnings（不得 crash）

#### Scenario: go-to-definition jumps from `$import` to fragment mapping key
- **GIVEN** demand YAML 顶层声明 `imports: {fragments: ./ecommerce_report_fragments.yaml}`
- **AND** 某 mapping 内声明 `$import: fragments.report_book`
- **WHEN** 用户在 `$import` 引用字符串内触发 go-to-definition
- **THEN** 系统 MUST 跳转到 `ecommerce_report_fragments.yaml` 中 `report_book:` 对应的 key 位置

#### Scenario: unknown `$import` alias yields empty result
- **GIVEN** demand YAML 未声明 `imports.fragments`
- **WHEN** `$import: fragments.report_book`
- **THEN** go-to-definition MUST 返回空结果
- **AND** MUST 提供可诊断 warnings 提示 unknown alias

#### Scenario: fragment path escapes allowed roots yields empty result
- **GIVEN** `imports.fragments` 指向的 fragment 文件解析后越界（不在 allowed roots 内）
- **WHEN** 用户触发 go-to-definition
- **THEN** go-to-definition MUST 返回空结果
- **AND** MUST 提供可诊断 warnings 提示 path escapes allowed roots

### Requirement: Hover MUST provide docstring for resolvable Python references and degrade gracefully
系统 MUST 为 Python 引用字段提供 hover（docstring），且失败时 MUST 降级为“空结果 + warnings”（不得 crash）：

- hover MUST 在可解析时返回 docstring（PlainText 即可）
- hover MUST 支持相对模块引用（前导 `.`），其 base 推导与 go-to-definition 一致
- 解析失败 MUST 返回空 hover，并包含可诊断 warnings

#### Scenario: hover returns docstring
- **GIVEN** YAML 中某字段引用 `pkg.mod:func`
- **WHEN** 用户触发 hover
- **THEN** 若可解析,系统 MUST 返回 `func` 的 docstring

#### Scenario: hover returns docstring for relative module reference
- **GIVEN** YAML 文件位于某个 `python_roots` 之下
- **AND** YAML 中某字段引用 `.loaders:load_orders`
- **WHEN** 用户触发 hover
- **THEN** 若可解析,系统 MUST 返回 `load_orders` 的 docstring

### Requirement: Hover MUST explain resolvable `$import` references and degrade gracefully
系统 MUST 为 `$import` 引用提供 hover，并满足：

- 若 `$import` 引用可解析，hover MUST 返回 PlainText（至少包含解析后的 fragment 来源文件路径与 ref logical path）
- 若引用不可解析，hover MUST 返回空结果并提供可诊断 warnings（不得 crash）

#### Scenario: hover returns resolved fragment source path
- **GIVEN** demand YAML 顶层声明 `imports.fragments: ./ecommerce_report_fragments.yaml`
- **AND** 某 mapping 内声明 `$import: fragments.report_book`
- **WHEN** 用户对 `$import` 引用触发 hover
- **THEN** 系统 MUST 返回包含 fragment 真实文件路径的 hover 文本

### Requirement: Completion MUST provide minimal symbol completions within Python reference strings
系统 MUST 为 Python 引用字段提供最小 completion,并满足：

- completion MUST 仅在光标位于引用字符串范围内触发（避免误触发）
- completion MUST 支持相对模块引用（前导 `.`），其 base 推导与 go-to-definition 一致
- 失败 MUST 降级为“空结果 + warnings”（不得 crash）

#### Scenario: completion suggests symbols in module
- **GIVEN** YAML 中某字段引用 `pkg.mod:`
- **WHEN** 用户在引用字符串内触发 completion
- **THEN** 系统 SHOULD 返回 `pkg.mod` 下的可用符号候选

#### Scenario: completion suggests symbols in module for relative module reference
- **GIVEN** YAML 文件位于某个 `python_roots` 之下
- **AND** YAML 中某字段引用 `.loaders:`
- **WHEN** 用户在引用字符串内触发 completion
- **THEN** 系统 SHOULD 返回 `.loaders` 规范化后的目标模块下的可用符号候选

### Requirement: LSP server MUST delegate editor semantics to shared core library
系统 MUST 在 LSP server 内统一复用抽离后的 editor semantics core（`scalim-yaml-dsl-lsp`），作为 diagnostics/definition/completion 的语义 SSOT，避免在 server 层复制实现细节。

#### Scenario: server uses shared core for diagnostics
- **WHEN** LSP server 收到 diagnostics 请求
- **THEN** server MUST 调用 shared core 的 diagnostics API 产生结果
- **AND** MUST NOT 在 server 层重复实现 validator/schema 规则

### Requirement: LSP server MUST support codeAction and executeCommand
系统 MUST 支持：

- `textDocument/codeAction`
- `workspace/executeCommand`

并且 MUST：

- 通过 `WorkspaceEdit` 应用编辑
- 在执行失败时返回可诊断信息（不得 crash）

#### Scenario: codeAction returns an executable fix
- **GIVEN** 当前文档存在一条可修复的 discovery/diagnostics 问题
- **WHEN** client 请求 codeAction
- **THEN** server MUST 返回可执行的 fix（edit 或 executeCommand）

### Requirement: executeCommand MUST support dumping discovery summary as JSON
系统 MUST 通过 `workspace/executeCommand` 暴露一个可用于排障的 discovery dump command：

- command id MUST 为 `scalim.dumpDiscovery`
- command arguments MUST 至少包含一个 document URI（作为 discovery 的入口）
- 返回值 MUST 为可 JSON 序列化的 discovery 摘要（不得回显 YAML 正文）

discovery 摘要 MUST 至少包含：

- project_root
- scalim_yaml_path（可为空）
- python_roots
- allowed_yaml_roots

#### Scenario: dumpDiscovery returns a JSON-serializable discovery payload
- **GIVEN** client 提供一个已打开文档的 URI
- **WHEN** client 调用 `workspace/executeCommand` 执行 `scalim.dumpDiscovery`
- **THEN** server MUST 返回包含 `project_root/scalim_yaml_path/python_roots/allowed_yaml_roots` 的 JSON payload

### Requirement: YAML entity id references MUST support definition/completion/hover (single-file)

对同一 YAML 文件内的实体 ID 引用（例如 `fields.*.source`、`fields.*.relation`、`relations.*.steps[*].from/to`）,LSP server MUST 提供：

- definition：跳转到被引用实体的声明点（缺失时返回空并给出可诊断提示）
- completion：补全当前文件内已声明的可用实体 ID
- hover：展示被引用实体的只读摘要信息（静态，无副作用）

#### Scenario: fields.*.source can go to definition
- **GIVEN** YAML 声明 `sources.customers: ...`
- **AND** 某字段引用 `fields.customer_segment.source: customers`
- **WHEN** 用户在 `customers` 上触发 `textDocument/definition`
- **THEN** server MUST 跳转到 `sources.customers` 的 key 位置

#### Scenario: unknown entity id does not crash and provides a hint diagnostic
- **GIVEN** 某字段引用 `fields.x.source: not_exist`
- **WHEN** 用户触发 definition/hover/completion
- **THEN** server MUST 返回空结果（无 locations / 无 hover）
- **AND** MUST 提供 hint 级 diagnostic（例如 “Unknown source id: not_exist”）

### Requirement: LSP server MUST provide field intelligence for aggregate output field references
系统 MUST 在 `outputs[*].aggregate` 相关结构中，为所有 field-id 引用点提供 completion/hover/definition，并满足：

- completion MUST 支持 Ctrl+Space 手动触发（包含空 scalar 与空 list item 场景）
- definition MUST 能跳转到字段声明位置（跨 imports 展开仍可定位）
- hover SHOULD 展示字段摘要（与现有字段卡片一致），不可解析时 MUST 返回空但不得崩溃

覆盖范围至少包括：

- `outputs[*].aggregate.group_by[*]`
- `outputs[*].aggregate.group_by[*][*]`（复合 key 内层 token）
- `outputs[*].aggregate.fields.*.*.field`
- `outputs[*].aggregate.fields.*.*.fields[*]`
- `outputs[*].aggregate.fields.*.(row_number|rank|dense_rank).by`
- `outputs[*].aggregate.fields.*.(row_number|rank|dense_rank).partition_by[*]`
- `outputs[*].aggregate.fields.*.(row_number|rank|dense_rank).order_by[*]`
- `outputs[*].aggregate.fields.*.score_by_rank.rank_field`

completion MUST 返回分层候选并稳定排序（按优先级从高到低）：
1) `outputs[*].aggregate.fields` 的 out_field_id（mapping key）
2) `outputs[*].aggregate.group_by` 的 field_id
3) 全局可见 field_id（低优先 fallback；MUST 以 detail/label 明确标注来源，避免误导）

definition MUST 支持多 locations，并满足稳定排序：
- 若 token 命中 out_field_id，则该 out_field 的定义点 MUST 为第一个候选
- 其余候选（如全局 field_id 定义）MUST 作为后续候选稳定排序+去重

#### Scenario: completion works for empty aggregate group_by list item
- **GIVEN** 某 demand YAML 存在 `outputs[*].aggregate.group_by` 且光标位于空 list item（例如 `- <cursor>`）
- **WHEN** 用户在该位置触发 completion（Ctrl+Space）
- **THEN** 系统 MUST 返回非空 field-id 候选列表

#### Scenario: definition resolves a field_id referenced by an aggregate metric
- **GIVEN** 某 demand YAML 中存在 `aggregate.fields.*.*.field: some_field_id`
- **WHEN** 用户对 `some_field_id` 触发 go-to-definition
- **THEN** 系统 MUST 跳转到 `fields.some_field_id` 的声明位置（或 imports 展开后的真实声明位置）

#### Scenario: rank.by resolves aggregate out_field_id first, then global field fallback
- **GIVEN** 某 demand YAML 中存在 `outputs[0].aggregate.fields.sum_amount: {sum: {field: order_amount}}`
- **AND** 存在 `outputs[0].aggregate.fields.rank: {dense_rank: {by: sum_amount, order: desc}}`
- **WHEN** 用户对 `by: sum_amount` 的 `sum_amount` 触发 go-to-definition
- **THEN** 系统 MUST 首选跳转到 `outputs[0].aggregate.fields.sum_amount` 的 key 位置
- **AND** 系统 MAY 返回额外候选（例如同名全局 field 定义），但必须排在后面且稳定排序

### Requirement: LSP server MUST provide field intelligence for field-id tokens inside `call_by` kwargs values
系统 MUST 在 `call_by` 字符串参数段内，为 kwargs 的 `=` **右侧** field-id token 提供 field 智能（completion/hover/definition），并满足：

- definition MUST 跳转到字段声明（含跨 imports 展开的真实声明位置）
- hover SHOULD 展示字段摘要（与 compute/where 的字段卡片一致），不可解析时 MUST 返回空但不得崩溃
- completion MUST 支持 Ctrl+Space 手动触发，并能在 `x=` 的空值场景返回候选列表
- `=` 左侧 kwargs 名称 MUST NOT 被当作 field-id（hover/definition 返回空）

覆盖 callsite 至少包括：
- `fields.*.call_by`
- `outputs[*].aggregate.fields.*.call_by`
- builtin callable：`call_by: "^<id>(...)"`（head 为 builtin id）

completion MUST 返回分层候选并稳定排序（按优先级从高到低），并以 detail/label 标注候选来源：
- 在 `fields.*.call_by`：全局可见 field_id 为主集合
- 在 `outputs[*].aggregate.fields.*.call_by`：out_field_id（`aggregate.fields` key）→ group_by field_id → 全局 field_id（低优先 fallback）

definition MUST 支持多 locations：
- 若 token 在 aggregate.call_by 中命中 out_field_id，则该 out_field 的定义点 MUST 为第一个候选
- 其余候选（如全局 field_id 定义）MUST 作为后续候选稳定排序+去重

#### Scenario: go-to-definition resolves a kwargs value field_id
- **GIVEN** YAML 声明 `fields.order_amount: ...`
- **AND** 存在 `call_by: "pkg.mod:fn(order_amount=order_amount)"`
- **WHEN** 用户对 `order_amount=order_amount` 的右侧 `order_amount` 触发 go-to-definition
- **THEN** 系统 MUST 跳转到 `fields.order_amount` 的声明位置

#### Scenario: completion works for empty kwargs value
- **GIVEN** 存在 `call_by: "pkg.mod:fn(order_amount=)"`
- **WHEN** 用户在 `=` 右侧触发 completion（Ctrl+Space）
- **THEN** 系统 MUST 返回非空 field-id 候选列表

#### Scenario: aggregate.call_by completion prefers out_field_id candidates
- **GIVEN** 存在 `outputs[0].aggregate.fields.rank: {dense_rank: {by: sum_amount}}`
- **AND** 存在 `outputs[0].aggregate.fields.score: {call_by: "^score_by_rank(rank=rank, base=100, step=3)"}`
- **WHEN** 用户在 `rank=` 的右侧触发 completion（Ctrl+Space）
- **THEN** completion MUST 将 `rank`（out_field_id）作为高优先候选返回

### Requirement: YAML DSL LSP server MUST keep user-facing behavior stable via contract tests

YAML DSL LSP server 的用户侧行为（diagnostics、definition/hover/completion、code actions）在重构前后 MUST 保持稳定，且该稳定性 MUST 由协议级 contract tests 覆盖。

#### Scenario: definition/hover/completion baseline is preserved

- **GIVEN** 一个包含 imports 与内联 Python reference 的 YAML workspace
- **AND** 该 workspace 在 baseline 版本上能得到预期的 definition/hover/completion 结果
- **WHEN** 进行内部重构（不改变对外行为）
- **THEN** 运行 LSP contract tests MUST 仍然通过（同一组 fixtures 与断言）

