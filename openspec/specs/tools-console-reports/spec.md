# dependency-free-console-reports Specification

## Purpose
TBD - created by archiving change c2-remove-literich. Update Purpose after archive.
## Requirements
### Requirement: console reports MUST be dependency-free and line-oriented

系统 MUST 将 `console` 报告（或等价的 “打印/展示到日志” 输出）实现为仅依赖 Python 标准库 `logging` 的逐行（line-oriented）文本输出。

系统 MUST NOT 依赖 `scalim.vendor.literich`（或任何表格/面板渲染器）来完成 console 报告展示。

#### Scenario: console report does not require rendering dependencies
- **GIVEN** 环境未安装 `rich` 等可选依赖
- **WHEN** 用户启用 observability 并选择 `report_format=console`
- **THEN** console 输出 MUST 正常产生
- **AND** 输出实现 MUST 不要求 `scalim.vendor.literich` 存在

### Requirement: console report lines MUST use stable prefix + kind token + k=v fields

系统 MUST 使用稳定前缀 `[scalim] <subsystem>:` 输出 console 报告行，并在每行前缀后使用稳定 kind token 表示该行语义（例如 `summary`、`per_source`、`loader` 等）。

系统 MUST 以稳定 `k=v` 形式表达诊断字段，且 key 顺序 MUST 稳定（字典序），值为 `None` 的字段 MUST 被省略。

#### Scenario: stable prefix and stable k=v ordering
- **WHEN** 系统输出一行 console 报告并包含字段 `{b: 2, a: 1, skip: None}`
- **THEN** 该行 MUST 以 `[scalim] <subsystem>:` 开头
- **AND** 该行 MUST 包含 kind token（例如 `summary`）
- **AND** `k=v` 文本 MUST 为 `a=1, b=2`（顺序稳定）且不包含 `skip`

### Requirement: console report MUST NOT rely on alignment or box drawing

系统 MUST 将 console 报告视为可被 grep/日志采集处理的文本流，不得将“列对齐/固定宽度”作为信息载体。

实现 MUST NOT 以 “表格边框/对齐空格/等宽假设” 表达语义（例如不得要求用户通过 `│`/`┌─┐` 等 box drawing 或 padding 才能理解字段归属）。

#### Scenario: report remains readable without monospace rendering
- **WHEN** 读者在比例字体/日志系统 UI 中查看 console 输出
- **THEN** 输出中的关键语义 MUST 仍可通过 kind token 与 `k=v` 直接读出
- **AND** 读者不应需要依赖列对齐或边框字符才能理解每条记录

### Requirement: per-entity breakdown MUST be emitted as repeated lines

当报告包含 “按实体拆分”的明细（例如 `per_source` / `per_loader` / `per_stage`），系统 MUST 以重复的逐行输出表达该明细，而不是把其嵌入为对齐表格。

#### Scenario: per_source is emitted as multiple lines
- **GIVEN** 关联命中统计包含多个 `source_id`
- **WHEN** 系统输出 console 报告
- **THEN** 系统 MUST 为每个 `source_id` 输出一行 kind=`per_source` 的记录
- **AND** 每行 MUST 至少包含 `source=<source_id>` 字段

### Requirement: multi-line details MUST be bounded and individually line-oriented

当报告需要输出样本/详情（例如 type mismatch samples），系统 MUST：

- 输出一行 “summary line” 指明 `showing=N`（或等价字段）
- 随后将每条样本作为独立的一行输出（每行仍遵循 prefix/kind/`k=v` 的约定，或以固定缩进并保持 `k=v`）
- 样本数量 MUST 有界（例如仅输出前 N 条）

#### Scenario: samples output is bounded and line oriented
- **GIVEN** 系统收集到 100 条 type mismatch 样本
- **WHEN** 系统输出 console 报告
- **THEN** 系统 MUST 明确输出 `showing=<N>`（N 为有界数，例如 5）
- **AND** 输出 MUST 仅包含 N 条样本行（不应逐条刷屏 100 行）

