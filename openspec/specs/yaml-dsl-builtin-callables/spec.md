# yaml-dsl-builtin-callables Specification

## Purpose
为 `YAML DSL` 中的 loader/call_by/... 等 Python 可调用对象引用点提供一套 **稳定、受控、无需扩大 allowlist** 的内置 callable 引用语法,避免下游依赖 `scalim.*` 内部模块路径。
## Requirements
### Requirement: YAML MUST support `^<id>` as a builtin callable reference
系统 MUST 支持在所有“期待 Python callable 引用”的字段中使用 `^<id>` 语法,作为 `module.path:function` / `module.path:obj.method` 的并列替代。

该语法 MUST 为 plain string(不使用 YAML tag),以避免自定义 YAML parser/tag 带来的歧义与风险。

#### Definition: builtin callable vocabulary
系统 MUST 定义一份“builtin callable 词表”(vocabulary),用于将 `<id>` 映射为具体可调用对象:

- 词表为显式白名单(仅允许词表中出现的 `<id>`)
- `<id>` MUST 为稳定命名,推荐使用 `/` 分段表示命名空间(例如 `workflow/book_sheet_rows`)
- 词表 MUST 支持调用方自定义(可扩展/覆盖默认词表),以满足下游集成的受控扩展点需求

#### Scenario: builtin callable reference parses in loader fields
- **WHEN** `main_source.loader` 为 `^<id>`
- **THEN** 解析/校验 MUST 视其为合法 callable 引用(不以 “引用格式非法” 失败)

#### Scenario: builtin callable reference parses in call_by fields
- **WHEN** `fields.*.call_by` 或 `sources.*.normalize.call_by` 为 `^<id>(...)`
- **THEN** 解析/校验 MUST 视其为合法 callable 引用(不以 “引用格式非法” 失败)

### Requirement: builtin callables MUST be resolved via an explicit vocabulary (registry)
系统 MUST 通过一份显式词表(vocabulary)将 `<id>` 映射为具体 callable,并满足:
- vocabulary MUST 为显式白名单(仅允许预注册 id)
- vocabulary MUST 支持调用方注入/自定义(不要求只能依赖框架内置固定集合)
- unknown `<id>` MUST fail-fast,并给出可操作的错误信息
- vocabulary MUST 可以在内部重构时更新默认映射,而不要求下游 YAML 变更

#### Scenario: unknown builtin id fails fast
- **WHEN** YAML 中出现 `^unknown/id`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 明确指出 unknown id 并提示如何查找/列出可用 id

### Requirement: builtin callable resolution MUST bypass allowlist checks
系统 MUST 将 `^<id>` 视为框架内置能力,其解析与执行 MUST 不要求在 allowlist 中声明 `scalim.*` 模块或函数。

同时,系统 MUST 保持既有安全语义:
- 对 `module.path:*` / 点式引用等 Python 引用,仍必须遵循 allowlist 校验
- 缺失 allowlist 的运行入口仍 MUST fail-fast(不允许通过 builtin scheme 隐式绕过)

#### Scenario: builtin callable works without adding scalim.* to allowlist
- **GIVEN** allowlist 未包含 `scalim` 相关模块前缀
- **WHEN** YAML loader/call_by 引用使用 `^<id>`
- **THEN** 引用解析 MUST 成功(不因 allowlist 拒绝)

### Requirement: builtin_callables vocabulary values MUST obey allowlist when expressed as Python references
当调用方通过 `builtin_callables` 词表配置将 `<id>` 映射为 Python 引用字符串(例如 `module.path:function`)时,系统 MUST 使用与主 resolver 一致的 allowlist 策略解析该引用(不得进入“仅 denylist”或“任意模块”解析模式).

#### Scenario: builtin_callables reference string is rejected if not allowlisted
- **GIVEN** 调用方提供 `builtin_callables={"x": "pkg.mod:fn"}`
- **WHEN** allowlist 未允许 `pkg.mod`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 可操作(提示配置 allowlist 或直接传入 callable)

#### Scenario: builtin_callables accepts direct callables without allowlist expansion
- **GIVEN** 调用方提供 `builtin_callables={"x": <callable>}`
- **WHEN** YAML 引用 `^x`
- **THEN** 系统 MUST 解析成功且不要求将 `scalim.*` 加入 allowlist

### Requirement: default vocabulary MUST include workflow book sheet rows loader id
系统 MUST 至少提供一个可用的内置 callable id,用于 workflow 场景的内置 loader:

- `^workflow/book_sheet_rows` → workflow book sheet rows loader (`scalim.workflow.loaders:book_sheet_rows`)

#### Scenario: workflow book sheet rows loader id is available
- **WHEN** 调用方在 YAML 中声明 `loader: ^workflow/book_sheet_rows`
- **THEN** 解析与运行期 callable 解析 MUST 成功
