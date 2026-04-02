## MODIFIED Requirements

### Requirement: YAML load MUST be centralized behind a single facade

系统 MUST 提供一个统一的 YAML load facade,并要求 DSL 的所有入口复用该 facade(至少覆盖: CLI validate、compile/run、workflow validate、imports fragments、project config)。

该 facade 至少 MUST 支持：
- 使用 vendored `ruamel.yaml` 作为唯一解析实现,并显式启用 YAML 1.2 语义边界
- duplicate key 检测（默认启用）
- location index 构建（用于行列定位）
- 统一的结构化错误输出（见 ErrorEnvelope 要求）
- 对底层 parser API 的封装,使业务层不直接依赖 `PyYAML` / `ruamel.yaml` 的顶层符号或节点类型

#### Scenario: CLI and runtime share identical parse behavior
- **WHEN** 同一份 YAML 文本在 CLI validate 与 runtime compile/run 被解析
- **THEN** 两者对 duplicate key 的处理 MUST 一致
- **AND** 两者的错误结构 MUST 一致（同一错误码/同一路径与定位口径）

#### Scenario: all entry points use the ruamel-based facade
- **WHEN** demand/workflow/CLI/imports/project-config 等入口解析 YAML 文本
- **THEN** 这些入口 MUST 仅通过统一 facade 完成解析
- **AND** MUST 使用 vendored `ruamel.yaml` 完成解析(不得依赖外部安装包)
