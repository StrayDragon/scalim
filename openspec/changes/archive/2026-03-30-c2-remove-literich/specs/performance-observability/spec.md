## ADDED Requirements

### Requirement: console reports in observability presets MUST follow dependency-free-console-reports

系统 MUST 确保 observability presets（至少包括 `PerformancePresentationLayer` 与 `RelationObserver`）在 `report_format=console` 时的输出满足 `dependency-free-console-reports` 的约束：

- 稳定前缀 `[scalim] <subsystem>:`
- 稳定 kind token（例如 `summary`、`per_source`、`stage`、`loader`）
- 逐行 `k=v` 输出（key 顺序稳定，`None` 省略）
- 不依赖表格渲染器（不得使用 `scalim.vendor.literich`）

#### Scenario: relations console report is line oriented and grep-friendly
- **GIVEN** 用户启用 `RelationObserver` 且 `report_format=console`
- **WHEN** pipeline 结束触发报告输出
- **THEN** 输出 MUST 至少包含一行 kind=`summary` 且包含 `total_lookups=` 与 `hit_rate=` 字段
- **AND** 对每个 source 统计，输出 MUST 以 kind=`per_source` 的重复行表达

#### Scenario: performance console report contains summary and optional breakdown lines
- **GIVEN** 用户启用 `PerformanceObserver` 且 `report_format=console`
- **WHEN** pipeline 结束触发报告输出
- **THEN** 输出 MUST 至少包含一行 kind=`summary` 且包含 `total_duration_s=` 与 `batch_count=` 字段
- **AND** 当存在 stage/loader 统计时，输出 SHOULD 追加 kind=`stage`/`loader` 的逐行明细

### Requirement: changing console formatting MUST NOT change metrics semantics

系统 MUST 将本变更视为 “展示层变更”；任何 console 输出格式的调整 MUST NOT 改变既有 `PerformanceMetrics` / `RelationMetrics` 的统计口径与字段值域。

#### Scenario: JSON/CSV report semantics remain unchanged
- **GIVEN** 用户选择 `report_format=json` 或 `report_format=csv`
- **WHEN** 输出报告
- **THEN** 报告中的字段集合与语义 MUST 与变更前保持一致（仅 console 展示形态变化）
