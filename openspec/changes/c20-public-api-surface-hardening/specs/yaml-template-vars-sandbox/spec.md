## MODIFIED Requirements

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
