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
