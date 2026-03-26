## ADDED Requirements

### Requirement: cast usage MUST be inventoryable by an explicit scanner
系统 MUST 提供一个可重复运行的扫描入口,用于清点仓库中 `cast(...)` 的使用位置,并输出可审阅报告.

报告 MUST 至少包含:
- 文件路径
- 行列位置
- `cast` 来源摘要(例如 `typing.cast`、直接导入 `cast` 或别名)
- 当前是否被 allow

#### Scenario: scanner produces a reviewable cast baseline
- **WHEN** 开发者运行 `uv run scripts/check-cast-usage.py --report ...`
- **THEN** 系统 MUST 输出 `cast` 命中清单与汇总统计

### Requirement: no-cover pragmas MUST be explicit and reviewable
系统 MUST 提供一个可重复运行的扫描入口,用于清点 `# pragma: no cover` 的使用位置,并要求这些位置具备显式、局部、可审阅的理由说明.

系统 MUST NOT 允许无理由的 `# pragma: no cover` 作为默认写法长期扩散.

#### Scenario: scanner reports no-cover locations and justification state
- **WHEN** 开发者运行 `uv run scripts/check-no-cover.py --report ...`
- **THEN** 系统 MUST 输出 `# pragma: no cover` 的命中位置
- **AND** 系统 MUST 标记该位置是否具备允许该例外的显式理由

### Requirement: cast and no-cover exceptions MUST use explicit local allow markers
系统 MUST 要求 `cast` 与 `# pragma: no cover` 的例外均通过显式注释声明,不得依赖隐式白名单或 review 口头约定.

系统 SHOULD 支持与 `dynattr` 治理风格一致的局部 allow 机制,优先行级,谨慎使用文件级.

#### Scenario: explicit allow suppresses a justified cast hit
- **WHEN** 某个 `cast(...)` 调用所在行带有 `# pragma: allow-cast <reason>`
- **THEN** 扫描器 MUST 将该命中标记为 allow

#### Scenario: explicit allow marks a justified no-cover hit
- **WHEN** 某个 `# pragma: no cover` 命中携带 `# pragma: allow-no-cover <reason>` 或等价的局部允许标记
- **THEN** 扫描器 MUST 将该命中标记为 allow

### Requirement: guardrail checks MUST be promotable into just qa
系统 MUST 为 `cast` 与 `# pragma: no cover` 检查提供稳定的 `just` 命令入口与非零退出码模式,以便后续接入 `quick-check-only-py` / `just qa`.

#### Scenario: unallowed cast or no-cover usage causes check failure
- **WHEN** 开发者运行相应的 `check` 命令
- **THEN** 若存在未 allow 的 `cast` 或 `# pragma: no cover` 命中,命令 MUST 失败
