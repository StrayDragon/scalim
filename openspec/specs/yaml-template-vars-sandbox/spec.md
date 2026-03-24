# yaml-template-vars-sandbox Specification

## Purpose
TBD - created by archiving change c20-yaml-template-vars-sandbox. Update Purpose after archive.
## Requirements
### Requirement: template precompile MUST run in a sandbox by default
当且仅当调用方显式提供 `template_vars`（非 `None`）时，系统 MUST 在 YAML parse 前执行 LiteJinja2 文本预编译。

当启用预编译时，系统 MUST 默认启用 sandbox 策略并满足：

- MUST 禁止无参方法调用语法（例如 `x.y()`），不得在渲染阶段执行用户对象方法
- MUST 禁止访问以下划线开头的属性（包括 `__dunder__`），避免对象自省链路被滥用
- MAY 允许对 dict/list/tuple 的 key/index 访问，以满足常见模板替换需求

#### Scenario: method calls are rejected by default
- **WHEN** YAML 文本包含 `x: {{ p.open().read() }}`
- **AND** 调用方提供 `template_vars={"p": <pathlib.Path("/etc/hosts")>}`（或等价带能力对象）
- **THEN** 模板渲染 MUST fail-fast
- **AND** 错误信息 MUST 可诊断地指出“method call 在 sandbox 下被禁止”（或等价表述）

### Requirement: legacy behavior MUST require explicit opt-in
系统 MUST 提供显式的“信任模式/legacy 模式”开关（例如 `template_sandbox="legacy"`），仅当调用方显式 opt-in 时才允许：

- 属性访问（含非 `_` 属性）
- 无参方法调用

并且：

- `_`/`__dunder__` 属性访问 MUST 仍然被禁止（不提供放宽开关）

当启用 legacy 模式时，系统 MUST 以强提示告知风险（至少 warning 级日志；可选诊断事件）。

#### Scenario: legacy mode allows method calls with warnings
- **WHEN** 调用方显式启用 legacy 模式
- **AND** YAML 文本包含 `x: {{ p.open().read() }}`
- **THEN** 模板渲染 MUST 成功并产生渲染后的 YAML 文本
- **AND** 系统 MUST 发出明确的风险告警（warning）

### Requirement: template_vars MUST be JSON/YAML-like by default
系统 MUST 对 `template_vars` 提供输入护栏（默认策略），以降低误把“带副作用能力对象”注入模板的风险。

默认策略 MUST 满足：

- 仅允许 JSON/YAML-like 类型：`None/bool/int/float/str/list/tuple/dict`
- v1（窄版本）：dict key MUST 为 `str`
- 发现不允许的类型 MUST fail-fast，且错误信息 MUST NOT 泄露具体值内容

#### Scenario: non-JSON-like template_vars fails fast
- **WHEN** 调用方提供包含非 JSON/YAML-like 类型的 `template_vars`（例如 `{"p": <pathlib.Path(...)>}`）
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 指出不允许的类型与变量路径
- **AND** 错误信息 MUST NOT 泄露该对象的具体值内容（例如实际文件路径文本）

