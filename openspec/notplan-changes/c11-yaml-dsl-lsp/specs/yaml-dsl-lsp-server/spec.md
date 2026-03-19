# yaml-dsl-lsp-server Specification

**状态: ⏳ 规划中**

## ADDED Requirements

### Requirement: LSP server 以 stdio 方式提供服务

LSP server MUST 支持以 stdio 方式运行（供 VSCode 扩展启动与管理）。

#### Scenario: stdio 启动
- **WHEN** 用户或 VSCode 扩展以 `python -m <server> --stdio` 启动
- **THEN** server 通过 stdin/stdout 进行 LSP 通讯并保持进程常驻

### Requirement: demand Diagnostics 复用 `scalim` 内部校验逻辑（不调用 CLI）

对 demand 类型 YAML 文件，LSP server MUST 复用 `scalim` 包内部解析/校验与定位逻辑生成 Diagnostics。

#### Scenario: demand 语义诊断与定位
- **WHEN** 打开或保存一个 demand YAML 文件
- **THEN** server 解析 YAML 并运行内部校验器生成 issues
- **AND** server 将 issue path 映射到行列范围并输出 LSP diagnostics（range + message + severity）

### Requirement: workflow Diagnostics v1 仅做 schema-only 校验

对 workflow 类型 YAML 文件，LSP server v1 MUST 仅做 schema-only 校验（以 `workflow.gen.json` 为输入）。

#### Scenario: workflow schema-only 校验
- **WHEN** 打开或保存一个 workflow YAML 文件
- **THEN** server 使用 `workflow.gen.json` 做 JSON Schema 校验并输出 diagnostics

### Requirement: Go to Definition 仅对引用字段生效

LSP server MUST 仅在特定键的 string value 上提供 Definition 能力，避免与 YAML 扩展冲突。

#### Scenario: loader 引用跳转
- **WHEN** 光标位于 `loader: "<python reference>"` 的引用字符串范围内
- **THEN** server 解析引用并返回目标 Python 文件与符号定义位置（若可解析）

#### Scenario: call_by 引用跳转
- **WHEN** 光标位于 `call_by: "<python reference>(...)"` 的引用字符串范围内
- **THEN** server 解析引用并返回目标 Python 文件与符号定义位置（若可解析）

### Requirement: 引用解析必须静态完成（不执行 import）

LSP server MUST 以静态方式完成引用解析（filesystem + `ast`），禁止执行 import 或运行用户代码。

#### Scenario: 静态定位模块与符号
- **WHEN** 解析 `module.path:function` / `module.path:obj.method` / dotted style 引用
- **THEN** server 在 `python.roots` 下尝试解析到 `.py` 或 `__init__.py` 文件并用 `ast` 定位符号

