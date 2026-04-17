# yaml-dsl-lsp-server (delta) Specification

## MODIFIED Requirements

### Requirement: Go to Definition MUST resolve `loader`/`call_by` references statically
系统 MUST 为 `loader`/`call_by` 等 Python 引用字段提供 go-to-definition,且解析 MUST 为静态解析(不执行用户代码):

- 引用格式 MUST 支持 `module:attr` 与 `module.attr`
- 引用格式 MUST 支持相对模块引用（前导 `.`），例如 `.loaders:func` / `..loaders:func`
- 对 `call_by: "pkg.mod:fn(arg=...)"` 形态,definition 至少 MUST 能解析并处理 `pkg.mod:fn`（参数段忽略）
- 对 YAML block scalar（`|`/`>` 及其变体）中的 multiline `loader/call_by`，definition MUST 仍可在光标命中 token 时工作（range 可为“当前行内 token range”）
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

#### Scenario: go-to-definition works for call_by head reference in a block scalar
- **GIVEN** YAML 包含：
  - `call_by: |`
  - `  pkg.mod:fn(`
  - `    x=1,`
  - `  )`
- **WHEN** 用户在 `pkg.mod:fn` 上触发 go-to-definition
- **THEN** 系统 MUST 返回 `fn` 定义所在文件与范围

### Requirement: Hover MUST provide docstring for resolvable Python references and degrade gracefully
系统 MUST 为 Python 引用字段提供 hover（docstring），且失败时 MUST 降级为“空结果 + warnings”（不得 crash）：

- hover MUST 在可解析时返回 docstring（PlainText 即可）
- hover MUST 支持相对模块引用（前导 `.`），其 base 推导与 go-to-definition 一致
- 对 YAML block scalar 中的 multiline `loader/call_by`，hover MUST 仍可在光标命中 token 时工作（range 可为“当前行内 token range”）
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

#### Scenario: hover works for a block scalar reference
- **GIVEN** YAML 包含：
  - `loader: |`
  - `  pkg.mod:func`
- **WHEN** 用户在 `pkg.mod:func` 上触发 hover
- **THEN** 若可解析,系统 MUST 返回 `func` 的 docstring

### Requirement: Completion MUST provide minimal symbol completions within Python reference strings
系统 MUST 为 Python 引用字段提供最小 completion,并满足：

- completion MUST 仅在光标位于引用字符串范围内触发（避免误触发）
- completion MUST 支持相对模块引用（前导 `.`），其 base 推导与 go-to-definition 一致
- 对 YAML block scalar 中的 multiline `loader/call_by`，completion MUST 仍可在光标命中 token/value_range 时工作
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

#### Scenario: completion suggests symbols for a block scalar reference
- **GIVEN** YAML 包含：
  - `loader: |`
  - `  pkg.mod:`
- **WHEN** 用户在 `pkg.mod:` 后触发 completion
- **THEN** 系统 SHOULD 返回 `pkg.mod` 下的可用符号候选

### Requirement: LSP server MUST provide field intelligence for field-id tokens inside `call_by` kwargs values
系统 MUST 在 `call_by` 字符串参数段内，为 kwargs 的 `=` **右侧** field-id token 提供 field 智能（completion/hover/definition），并满足：

- definition MUST 跳转到字段声明（含跨 imports 展开的真实声明位置）
- hover SHOULD 展示字段摘要（与 compute/where 的字段卡片一致），不可解析时 MUST 返回空但不得崩溃
- completion MUST 支持 Ctrl+Space 手动触发，并能在 `x=` 的空值场景返回候选列表
- `=` 左侧 kwargs 名称 MUST NOT 被当作 field-id（hover/definition 返回空）
- 该能力 MUST 支持 multiline `call_by`（含 YAML block scalar）与 Python 风格 `#` 注释（不在 string literal 内）

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

#### Scenario: completion works for empty kwargs value in a block scalar call_by
- **GIVEN** YAML 包含：
  - `call_by: |`
  - `  pkg.mod:fn(`
  - `    order_amount=, # comment`
  - `  )`
- **WHEN** 用户在 `=` 右侧触发 completion（Ctrl+Space）
- **THEN** 系统 MUST 返回非空 field-id 候选列表

