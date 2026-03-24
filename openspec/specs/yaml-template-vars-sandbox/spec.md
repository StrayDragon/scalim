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

### Requirement: legacy behavior MUST require explicit non-public opt-in
系统 MUST NOT 在默认公共 API 上继续暴露 legacy/信任模式模板沙箱开关。

当且仅当调用方进入显式的非公共、不安全语义入口时，系统才允许 legacy 行为放宽；默认公共入口 MUST 只允许 safe sandbox。

并且：

- `_`/`__dunder__` 属性访问 MUST 仍然被禁止（不提供放宽开关）
- 公共入口收到 `template_sandbox="legacy"`（或等价 legacy opt-in）时 MUST fail-fast，并给出迁移提示
- 若后续保留 legacy 能力，系统 MUST 通过显式 `unsafe` 语义的专用入口承载，而不是继续挂在默认 facade 上

#### Scenario: public run API rejects legacy sandbox
- **WHEN** 调用方通过官方公开入口启用 `template_sandbox="legacy"`
- **THEN** 系统 MUST fail-fast
- **AND** 错误信息 MUST 同时满足:
  - 指出默认公共入口仅允许 safe sandbox（legacy 已不再支持）
  - 给出明确迁移动作（例如“移除 `template_sandbox` 参数或显式改为 safe 模式”）
  - 若仍需 legacy 能力,提示其必须转入显式 `unsafe` 语义的非公共入口（而非继续使用默认 facade）

#### Scenario: safe sandbox remains the only public template mode
- **WHEN** 调用方通过官方公开入口提供 `template_vars`
- **THEN** 系统 MUST 继续在 YAML parse 前执行 safe sandbox 预编译
- **AND** 不得再通过公共入口放宽为 legacy 模式

#### Scenario: legacy mode allows method calls with warnings (unsafe entrypoint)
- **WHEN** 调用方通过显式 `unsafe` 语义的非公共入口启用 legacy 模式
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
