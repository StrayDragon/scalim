## ADDED Requirements

### Requirement: dynattr usage MUST be inventoryable by an explicit scanner
系统 MUST 提供一个可重复运行的扫描入口,用于清点 `src/IMPL_ROOT/` 中的 `getattr` / `setattr` / `hasattr` 调用,并输出可审阅的报告.

报告 MUST 至少包含:
- 文件路径
- 行列位置
- 调用类型
- 属性表达式摘要
- 当前是否被 allow

#### Scenario: scanner produces a reviewable baseline report
- **WHEN** 开发者运行 `uv run scripts/check-dynattr.py --report ...`
- **THEN** 系统 MUST 输出 `dynattr` 命中清单与汇总统计

### Requirement: dynattr exceptions MUST be explicit and local
系统 MUST 要求所有 `dynattr` 例外均通过显式注释声明,不得依赖隐式白名单或隐藏规则.

系统 MUST 支持以下两类例外:
- 行级 `# pragma: allow-dynattr <reason>`
- 文件级 `# pragma: allow-dynattr-file <reason>`

文件级例外 SHOULD 仅用于框架型、反射型、整文件动态职责明显的模块;普通业务逻辑 SHOULD 优先使用局部 allow 或重构为静态访问.

#### Scenario: explicit allow suppresses only declared hits
- **WHEN** 某个 `dynattr` 调用所在行带有 `# pragma: allow-dynattr <reason>`
- **THEN** 扫描器 MUST 将该命中标记为 allow

#### Scenario: file-level allow marks the file as allowed
- **WHEN** 文件头注释区包含 `# pragma: allow-dynattr-file <reason>`
- **THEN** 扫描器 MUST 将该文件内命中标记为 allow

### Requirement: dynattr gate MUST be promotable into `just qa`
系统 MUST 提供 `--check` 模式,使 `dynattr` 扫描器可在存在未 allow 命中时返回非零退出码,从而接入 `quick-check-only-py` / `just qa`.

#### Scenario: unallowed dynattr causes non-zero exit
- **WHEN** 开发者运行 `uv run scripts/check-dynattr.py --check`
- **THEN** 若存在未 allow 的 `dynattr` 命中,命令 MUST 失败
