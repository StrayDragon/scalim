# yaml-dsl-import-aliases-and-presets Specification

## MODIFIED Requirements

### Requirement: Imports MUST support scalim.yaml configured aliases and allowed roots
系统 MUST 支持可选的项目级配置文件 `scalim.yaml`，用于治理 YAML DSL 的 imports 路径解析。

当配置存在时：

- 系统 MUST 支持 `yaml_dsl.import_roots` 列表：
  - 每个条目 MUST 为 mapping
  - 条目 MUST 包含 `path`（目录路径；建议相对 `scalim.yaml` 所在目录）
  - 条目 MAY 包含 `alias`（例如 `@` / `fragments`）
- 系统 MUST 在解析 `imports.<alias>` 路径时先应用 alias（例如 `@/x.yaml` 或 `fragments:/x.yaml`），再执行后续的相对路径归一化与安全校验
- 当调用方未显式提供 `allowed_yaml_roots` 时，系统 MUST 将 `import_roots[*].path` 作为默认 allow-roots 的扩展输入；越界 MUST fail-fast

#### Scenario: alias @ maps to project root and imports can use @/x.yaml
- **GIVEN** 项目存在 `scalim.yaml` 且配置 `yaml_dsl.import_roots: [{path: \"./\", alias: \"@\"}]`
- **WHEN** demand YAML 配置 `imports.common: \"@/fragments/common.yaml\"`
- **THEN** imports MUST 将 `@/fragments/common.yaml` 解析到项目根下对应文件并成功加载

#### Scenario: imports outside allowed roots is rejected
- **GIVEN** `scalim.yaml` 配置了 `yaml_dsl.import_roots`
- **WHEN** imports 解析后的目标路径落在 allowed roots 之外
- **THEN** 系统 MUST fail-fast 并给出可诊断错误信息（至少包含解析基准与目标绝对路径）

