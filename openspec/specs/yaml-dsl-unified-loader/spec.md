# yaml-dsl-unified-loader Specification

## Purpose
TBD - created by archiving change c30-yaml-dsl-rigor-ssot. Update Purpose after archive.

## Requirements
### Requirement: YAML load MUST be centralized behind a single facade

系统 MUST 提供一个统一的 YAML load facade,并要求 DSL 的所有入口复用该 facade（至少覆盖：CLI validate、compile/run、workflow validate、imports fragments）.

该 facade 至少 MUST 支持：
- duplicate key 检测（默认启用）
- location index 构建（用于行列定位）
- 统一的结构化错误输出（见 ErrorEnvelope 要求）

#### Scenario: CLI and runtime share identical parse behavior
- **WHEN** 同一份 YAML 文本在 CLI validate 与 runtime compile/run 被解析
- **THEN** 两者对 duplicate key 的处理 MUST 一致
- **AND** 两者的错误结构 MUST 一致（同一错误码/同一路径与定位口径）

### Requirement: YAML parse errors MUST use a stable ErrorEnvelope

系统 MUST 以可机器消费的稳定结构表达 YAML parse/validate 错误（ErrorEnvelope）.

ErrorEnvelope 至少 MUST 包含：
- `code`（短码）
- `message`
- `source_path`（文件路径或逻辑来源）
- `loc`（行/列,若可得）
- `path`（YAML 路径,若可得）

#### Scenario: errors contain location without leaking sensitive values
- **WHEN** YAML parse 失败
- **THEN** 错误 MUST 包含 `source_path` 与 `loc`
- **AND** 错误 MUST NOT 回显完整 YAML 文本或敏感值正文
