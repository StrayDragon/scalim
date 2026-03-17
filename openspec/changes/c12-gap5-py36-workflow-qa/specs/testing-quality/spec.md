## ADDED Requirements

### Requirement: py36-typingext-check MUST include workflow import smoke test
系统 MUST 在 `py36-typingext-check`（docker 的 Python 3.6 + `typing-extensions==4.1.1` 隔离环境）中执行以下门禁:

- 对 `src/scalim/` 执行 `compileall`
- 对关键入口与 workflow 实现模块执行 import smoke test（至少覆盖 `scalim.dsl.by_yaml.runtime.workflow_entrypoints`）

该门禁 MUST 能在 “import 时炸（例如注解求值不兼容）” 的场景下 fail-fast。

#### Scenario: import-time annotation incompatibility fails the gate
- **WHEN** 任一关键模块在 Python 3.6 import 阶段因注解求值/语义差异抛错
- **THEN** `py36-typingext-check` MUST 失败

