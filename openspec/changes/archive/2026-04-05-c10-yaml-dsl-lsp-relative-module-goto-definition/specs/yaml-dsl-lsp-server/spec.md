## MODIFIED Requirements

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
