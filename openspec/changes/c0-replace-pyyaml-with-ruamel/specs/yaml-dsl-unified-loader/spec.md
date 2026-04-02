## MODIFIED Requirements

### Requirement: YAML load MUST be centralized behind a single facade

系统 MUST 提供一个统一的 YAML load facade,并要求 DSL 的所有入口复用该 facade（至少覆盖：CLI validate、compile/run、workflow validate、imports fragments）。

该 facade 至少 MUST 支持：
- duplicate key 检测（默认启用）
- location index 构建（用于行列定位）
- 统一的结构化错误输出（见 ErrorEnvelope 要求）
- 对底层 vendored YAML backend 的封装,使业务层不直接依赖 `PyYAML` / `ruamel.yaml` 的顶层 API 细节

#### Scenario: CLI and runtime share identical parse behavior
- **WHEN** 同一份 YAML 文本在 CLI validate 与 runtime compile/run 被解析
- **THEN** 两者对 duplicate key 的处理 MUST 一致
- **AND** 两者的错误结构 MUST 一致（同一错误码/同一路径与定位口径）

#### Scenario: backend swap does not leak third-party parser APIs into business call sites
- **GIVEN** 统一 facade 的内部实现从一个 vendored YAML backend 切换到另一个
- **WHEN** 维护者运行 demand/workflow/CLI/imports 等既有入口
- **THEN** 这些入口 MUST 继续通过统一 facade 工作
- **AND** `src/scalim/` 业务层 MUST NOT 依赖某个第三方 parser 特有的顶层函数、loader 类名或 removed API
