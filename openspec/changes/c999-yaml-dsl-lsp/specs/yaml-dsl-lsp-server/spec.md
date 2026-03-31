## ADDED Requirements

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
- 定义定位 MUST 基于 project discovery 的 `python_roots` 与文件系统/AST 分析
- 解析失败时 MUST 返回空结果且给出可诊断信息(不得 crash)

#### Scenario: definition resolution locates a Python function
- **GIVEN** YAML 中某字段引用 `pkg.mod:func`
- **WHEN** 用户触发 go-to-definition
- **THEN** 系统 MUST 返回 `func` 定义所在文件与范围
