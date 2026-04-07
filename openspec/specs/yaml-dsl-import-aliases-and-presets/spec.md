# yaml-dsl-import-aliases-and-presets Specification

## Purpose
TBD - created by archiving change c80-yaml-dsl-import-aliases-and-presets. Update Purpose after archive.
## Requirements
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
- **WHEN** demand YAML 配置 `imports.common: "@/fragments/common.yaml"`
- **THEN** imports MUST 将 `@/fragments/common.yaml` 解析到项目根下对应文件并成功加载

#### Scenario: imports outside allowed roots is rejected
- **GIVEN** `scalim.yaml` 配置了 `yaml_dsl.import_roots`
- **WHEN** imports 解析后的目标路径落在 allowed roots 之外
- **THEN** 系统 MUST fail-fast 并给出可诊断错误信息（至少包含解析基准与目标绝对路径）

### Requirement: Project config discovery MUST be deterministic and support explicit override
系统 MUST 提供确定性的 `scalim.yaml` 定位规则，并支持调用方显式 override（用于 CI/容器等场景）。

- 当调用方提供显式 `scalim.yaml` 路径（或 project root）override 时，系统 MUST 以 override 为准（不得再向上查找）。
- 当调用方未提供 override 时，系统 MUST 使用 nearest-wins（从 demand YAML 所在目录向上查找最近的 `scalim.yaml`）。

#### Scenario: explicit scalim.yaml override disables upward search
- **GIVEN** 调用方显式指定 `scalim.yaml` override
- **WHEN** 解析 demand YAML 的 imports
- **THEN** 系统 MUST 仅使用 override 指定的项目配置（不得使用向上查找的其它配置）

### Requirement: Imports MUST support scalim:// presets as local-only built-in fragments
系统 MUST 支持 `scalim://...` 形式的 imports 路径，用于引用 scalim 包内置的 YAML presets（fragments）。

- `scalim://` 引用 MUST 只读本地已安装的 scalim 包资源（离线，不得走网络）
- 系统 MUST 限制可引用范围（建议白名单/注册表），避免变成“任意读包内路径”
- `render` 输出 MUST 可以展开 `scalim://...` 为 effective YAML，并在可选 explain 输出中记录来源（preset id / 资源路径）

#### Scenario: scalim:// preset can be imported and expanded during render
- **GIVEN** demand YAML 配置 `imports.std: "scalim://yaml-dsl/presets/common.yaml"`
- **WHEN** 调用方执行 `load_effective_demand_yaml(<demand.yaml>)`
- **THEN** render MUST 成功展开该 preset，并输出不包含 `imports/$import` 的 effective YAML
