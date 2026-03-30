## ADDED Requirements

### Requirement: public API suite MUST be paired with a pytest public_api suite
系统 MUST 将 public API catalog 的回归覆盖分为两条互补链路,并要求二者同时存在:
- `notebooks/marimo/example_public_api_suite/`：教学/叙事型示例套件（由 `just examples` gate 执行）
- `tests/public_api/`：用户侧最小闭环 pytest 套件（由默认 pytest 非 bench gate 执行）

两者 MUST 覆盖同一份 public API catalog,并提供可自动化的漂移检测;当覆盖集合不一致时,门禁 MUST fail-fast 并输出差异.

#### Scenario: suite and pytest stay aligned on the public API catalog
- **WHEN** 维护者运行 `just examples` 与默认 pytest 非 bench 套件
- **THEN** public API suite 与 pytest public_api suite MUST 覆盖同一份 public API catalog
- **AND** 若存在差异,对应门禁 MUST 失败并输出差异列表

### Requirement: public API suite MUST demonstrate events and sinks via stable facades
public API suite MUST 以用户侧稳定入口演示 `events` 与 `sinks` 的最小可用用法,并将其纳入 `just examples` gate 的确定性回归范围:
- 事件常量/目录查询入口（例如 `scalim.events` 的稳定导入与基本使用）
- 常用 sinks（例如 `scalim.sinks` 的稳定导入与最小写入闭环）

#### Scenario: events and sinks are exercised in the suite
- **WHEN** 开发者运行 public API suite
- **THEN** suite MUST 执行一个覆盖 `scalim.events` 与 `scalim.sinks` 的章节/用例
- **AND** 该章节/用例 MUST 通过并输出可定位的 summary
