# yaml-dsl-editor-semantics-core Specification

## Purpose
TBD - created by archiving change c50-yaml-dsl-editor-semantics-lsp-core. Update Purpose after archive.
## Requirements
### Requirement: Editor semantics core MUST expose project discovery
系统 MUST 提供 project discovery 能力，用于为 editor/LSP 侧推导：

- `project_root`
- `scalim_yaml_path`（可为空）
- `allowed_yaml_roots`
- `python_roots`

#### Scenario: nearest-wins scalim.yaml yields discovery payload
- **GIVEN** 某 `YAML` 文件位于项目子目录，且父目录链上存在 `scalim.yaml`
- **WHEN** editor 调用 project discovery
- **THEN** 返回的 `project_root` MUST 为最近的 `scalim.yaml` 所在目录
- **AND** 返回的 roots MUST 为绝对路径且可 JSON 序列化

### Requirement: Editor semantics core MUST expose diagnostics without invoking CLI
系统 MUST 提供 diagnostics API，且 MUST 直接复用 library 语义（schema/validator/unknown-fields），不得通过 shell-out 调用 CLI。

#### Scenario: diagnostics are computed without spawning a subprocess
- **WHEN** editor 请求某 YAML 的 diagnostics
- **THEN** 系统 MUST 返回结构化 diagnostics（errors/warnings + path + range）
- **AND** MUST NOT 依赖 CLI 子进程

### Requirement: Editor semantics core MUST be static and side-effect free
系统 MUST 保证 editor 语义为静态解析：

- MUST NOT 执行用户代码（仅允许文件系统读取与 AST 解析）
- MUST NOT 修改进程级全局状态（例如 `sys.path`、`sys.meta_path`）

#### Scenario: resolving definitions does not mutate process globals
- **GIVEN** editor 触发 go-to-definition
- **WHEN** core 解析某 Python 引用
- **THEN** 解析过程 MUST NOT 改写进程级全局搜索路径
- **AND** 解析失败时 MUST 返回空 locations + 可诊断 warnings

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

#### Scenario: object method resolution follows imported object single hop
- **GIVEN** Python 模块 `pkg.mod` 内存在 `from pkg.other import some_ref`
- **AND** Python 模块 `pkg.other` 内存在 `some_ref = Klass()` 且 `Klass.a_method` 存在
- **WHEN** YAML 中某字段引用 `pkg.mod:some_ref.a_method`
- **THEN** definition MUST 返回至少 3 个 locations
- **AND** 第一个 location MUST 指向 `Klass.a_method` 的定义位置
- **AND** 后续 location MUST 包含 `pkg.mod` 中的 import 绑定位置与 `pkg.other` 中 `some_ref` 的定义/赋值位置

#### Scenario: object method resolution degrades when class cannot be inferred
- **GIVEN** Python 模块 `pkg.mod` 内存在 `some_ref = factory()`（返回类型未知）
- **WHEN** YAML 中某字段引用 `pkg.mod:some_ref.a_method`
- **THEN** definition MUST NOT crash
- **AND** MUST 返回空结果或仅返回 `some_ref` 的定义/赋值位置
- **AND** MUST 返回至少一条 warning 指出无法静态推断目标实现

### Requirement: Editor semantics core MUST support extracting Python references by cursor position
系统 MUST 提供一个基于 `yaml_text + position` 的抽取能力，用于把编辑器光标映射到 YAML DSL 内的 Python 引用字段。

抽取结果 MUST 至少包含：

- 命中的 YAML 字段路径（canonical dot path）
- 命中的 Python 引用字符串（raw value 或经 `call_by` 头部解析后的 reference）
- 命中范围 `range`（以 1-based 表示，供 server 转换为 LSP range）
- 失败时的可诊断 warnings（不得抛出未捕获异常）

支持字段集合 v1 MUST 至少覆盖：

- `loader`
- `call_by`
- `retry.should_retry`（包含常见嵌套路径下的该字段）

#### Scenario: cursor inside a scalar string yields extracted reference + range
- **GIVEN** 某 demand YAML 包含 `loader: "pkg.mod:func"` 且光标位于该字符串值内部
- **WHEN** editor semantics core 执行光标抽取
- **THEN** MUST 返回 `yaml_path` 指向该字段
- **AND** MUST 返回 `reference` 等于 `pkg.mod:func`
- **AND** MUST 返回的 `range` MUST 精确覆盖该 reference 的文本范围

#### Scenario: call_by reference with args yields head reference
- **GIVEN** 某 demand YAML 包含 `call_by: "pkg.mod:fn(a=1)"` 且光标位于 `pkg.mod:fn` 区间
- **WHEN** editor semantics core 执行光标抽取
- **THEN** MUST 返回 `reference` 等于 `pkg.mod:fn`
- **AND** 返回的 `range` MUST 覆盖 `pkg.mod:fn`（不得包含参数段）

#### Scenario: parse failure degrades to empty result with warnings
- **GIVEN** 某 YAML 语法不完整或无法被解析
- **WHEN** editor semantics core 执行光标抽取
- **THEN** MUST 返回空结果
- **AND** MUST 提供至少一条 warning 用于排障

### Requirement: expression identifier tokens MUST be resolvable to field definitions

在 `compute`/`where` 等安全表达式字符串内,当光标位于某个 identifier token 上时,semantics core MUST 能静态解析该 token 并用于 editor 语义能力:

- semantics core MUST 能抽取该 token 的精确 range（仅覆盖 token）。
- semantics core MUST 能将 token 解析为字段引用（在当前上下文作用域内），用于 hover/definition/completion。

#### Scenario: compute expression token resolves to field definition
- **GIVEN** YAML 声明 `fields.a: ...` 且存在 `fields.sum.compute: \"a + 1\"`
- **WHEN** 光标位于表达式中的 token `a` 上并触发 definition/hover
- **THEN** token MUST 解析为对 `fields.a` 的引用
- **AND** definition MUST 指向 `fields.a` 的声明位置

