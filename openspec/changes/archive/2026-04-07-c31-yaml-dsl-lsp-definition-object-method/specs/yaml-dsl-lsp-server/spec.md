## MODIFIED Requirements

### Requirement: Go to Definition MUST resolve `loader`/`call_by` references statically
系统 MUST 为 `loader`/`call_by` 等 Python 引用字段提供 go-to-definition,且解析 MUST 为静态解析(不执行用户代码):

- 引用格式 MUST 支持 `module:attr` 与 `module.attr`
- 引用格式 MUST 支持相对模块引用（前导 `.`），例如 `.loaders:func` / `..loaders:func`
- 对 `call_by: "pkg.mod:fn(arg=...)"` 形态,definition 至少 MUST 能解析并处理 `pkg.mod:fn`（参数段忽略）
- 定义定位 MUST 基于 project discovery 的 `python_roots` 与文件系统/AST 分析
- 当引用为相对模块时，系统 MUST 基于文档 URI 推导 `yaml_path` 并交由 shared core 在 `yaml_path + python_roots` 上下文内完成规范化与解析
- 对 `module:obj.method` 形态，系统 MUST 复用 shared core 的静态推断能力，尽可能把第一个 location 定位到真实实现（例如 `Klass.method`）
- definition MUST 支持返回多个 locations，且顺序 MUST 稳定：真实实现优先，其后为对象定义/赋值等备选位置
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

