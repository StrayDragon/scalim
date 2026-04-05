## MODIFIED Requirements

### Requirement: Python reference resolution MUST be filesystem + AST based
系统 MUST 支持对 Python 引用进行静态解析并定位定义位置：

- 引用格式 MUST 支持 `module:attr` 与 `module.attr`
- 引用格式 MUST 支持相对模块引用（前导 `.`），例如 `.loaders:func` / `..loaders:func`
- 当引用为相对模块时，系统 MUST 基于 `yaml_path`（文档路径）与 project discovery 的 `python_roots` 推导 `base_module_path`，并将其规范化为绝对模块路径后再进行解析
- 定位 MUST 基于 `python_roots` + 文件系统模块解析 + AST 符号索引

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
