## MODIFIED Requirements

### Requirement: Python reference resolution MUST be filesystem + AST based
系统 MUST 支持对 Python 引用进行静态解析并定位定义位置：

- 引用格式 MUST 支持 `module:attr` 与 `module.attr`
- 引用格式 MUST 支持相对模块引用（前导 `.`），例如 `.loaders:func` / `..loaders:func`
- 当引用为相对模块时，系统 MUST 基于 `yaml_path`（文档路径）与 project discovery 的 `python_roots` 推导 `base_module_path`，并将其规范化为绝对模块路径后再进行解析
- 定位 MUST 基于 `python_roots` + 文件系统模块解析 + AST 符号索引
- 对 class-style 的多段属性路径（例如 `module.path:obj.method`），系统 MUST 在不执行用户代码的前提下尝试静态推断 `obj` 的候选类（例如来自 `obj = Klass()` / `obj: Klass = ...` / 简单 import/alias），并在可推断时优先定位到真实实现（例如 `Klass.method`）
- 当 `obj.method` 可推断时，definition MUST 返回 **多个** locations，且顺序 MUST 稳定：第一个为推断到的真实实现，其后为 `obj` 的定义/赋值等备选位置（用于回溯引用来源）

#### Scenario: definition resolution locates a Python function
- **GIVEN** YAML 中某字段引用 `pkg.mod:func`
- **WHEN** 用户触发 go-to-definition
- **THEN** 系统 MUST 返回 `func` 定义所在文件与范围

#### Scenario: relative module definition resolution locates a Python function
- **GIVEN** YAML 文件位于某个 `python_roots` 之下
- **AND** YAML 中某字段引用 `.loaders:load_orders`
- **WHEN** 用户触发 go-to-definition 且 core 收到 `yaml_path + python_roots`
- **THEN** 系统 MUST 将 `.loaders` 规范化为绝对模块路径
- **AND** MUST 返回 `load_orders` 定义所在文件与范围

#### Scenario: relative module resolution degrades when base cannot be derived
- **GIVEN** YAML 文件不在任何 `python_roots` 条目下
- **AND** YAML 中某字段引用 `.loaders:load_orders`
- **WHEN** 用户触发 go-to-definition
- **THEN** 系统 MUST 返回空 locations
- **AND** MUST 返回至少一条 warning 指出无法推导相对引用的 base（并提示补充 `python_roots` 或改用绝对引用）

#### Scenario: object method resolution locates class method and returns fallback location
- **GIVEN** Python 模块 `pkg.mod` 内存在 `class Klass` 且其定义 `def a_method(self)`（可调用实现）
- **AND** 模块内存在 `some_ref = Klass()`（模块级对象赋值）
- **WHEN** YAML 中某字段引用 `pkg.mod:some_ref.a_method`
- **THEN** definition MUST 返回至少 2 个 locations
- **AND** 第一个 location MUST 指向 `Klass.a_method` 的定义位置
- **AND** 后续 location MUST 包含 `some_ref` 的定义/赋值位置

#### Scenario: object method resolution follows simple imports
- **GIVEN** Python 模块 `pkg.mod` 内存在 `from pkg.other import Klass`
- **AND** 模块内存在 `some_ref = Klass()`
- **AND** Python 模块 `pkg.other` 内存在 `class Klass` 且其定义 `def a_method(self)`
- **WHEN** YAML 中某字段引用 `pkg.mod:some_ref.a_method`
- **THEN** 第一个 location MUST 指向 `pkg.other.Klass.a_method` 的定义位置

#### Scenario: object method resolution degrades when class cannot be inferred
- **GIVEN** Python 模块 `pkg.mod` 内存在 `some_ref = factory()`（返回类型未知）
- **WHEN** YAML 中某字段引用 `pkg.mod:some_ref.a_method`
- **THEN** definition MUST NOT crash
- **AND** MUST 返回空结果或仅返回 `some_ref` 的定义/赋值位置
- **AND** MUST 返回至少一条 warning 指出无法静态推断目标实现

