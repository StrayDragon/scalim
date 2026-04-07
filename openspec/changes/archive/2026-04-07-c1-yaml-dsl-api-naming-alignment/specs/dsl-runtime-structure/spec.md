## REMOVED Requirements

### Requirement: `IMPL_ROOT.dsl.by_yaml` MUST be the preferred public facade
**Reason**：`by_yaml` 是实现细节命名，不利于建立稳定用户心智；本仓库选择将 canonical public facade 重命名为 `IMPL_ROOT.dsl.yaml_dsl`。

**Migration**：将所有用户材料与示例导入从 `IMPL_ROOT.dsl.by_yaml` 迁移到 `IMPL_ROOT.dsl.yaml_dsl`。

#### Scenario: public guidance no longer prefers the by_yaml facade
- **WHEN** 维护者编写/更新 YAML DSL 的官方导入示例
- **THEN** 示例 MUST 使用 `IMPL_ROOT.dsl.yaml_dsl`
- **AND** MUST NOT 把 `IMPL_ROOT.dsl.by_yaml` 写成推荐用户路径

### Requirement: YAML DSL 官方入口为 `IMPL_ROOT.dsl.by_yaml`
**Reason**：canonical public facade 已从 `IMPL_ROOT.dsl.by_yaml` 收敛为 `IMPL_ROOT.dsl.yaml_dsl`。

**Migration**：使用 `IMPL_ROOT.dsl.yaml_dsl` 导入 `run/compile/run_workflow` 与 `RunOptions/RunOverrides/...` 等运行期契约。

#### Scenario: official facade import path switches to yaml_dsl
- **WHEN** 调用方执行 `from IMPL_ROOT.dsl.yaml_dsl import run, compile, run_workflow`
- **THEN** 导入 MUST 成功

## ADDED Requirements

### Requirement: `IMPL_ROOT.dsl.yaml_dsl` MUST be the preferred public facade
系统 MUST 将 `IMPL_ROOT.dsl.yaml_dsl` 作为 YAML DSL 的首选公开 facade，用于承载用户最常见且受支持的运行入口与运行期契约。

系统可以保留 `by_yaml` 作为内部实现包，但用户材料 MUST NOT 再推荐该路径。

#### Scenario: public guidance prefers yaml_dsl facade over internals
- **WHEN** 用户查阅 YAML DSL 的官方导入示例
- **THEN** 示例 MUST 优先使用 `IMPL_ROOT.dsl.yaml_dsl`
- **AND** 不得把 `IMPL_ROOT.dsl.yaml_dsl.runtime.*` 或旧的 `IMPL_ROOT.dsl.by_yaml.*` 写成默认推荐入口

### Requirement: YAML DSL 官方入口为 `IMPL_ROOT.dsl.yaml_dsl`
系统 MUST 提供 `IMPL_ROOT.dsl.yaml_dsl` 作为 YAML DSL 的官方入口(导入路径),用于承载调用方最常用的稳定接口.

该官方入口 MUST 以“受控 re-export”方式提供最小 facade,并 MUST 导出以下符号:
- 运行入口: `run` / `compile` / `run_workflow`
- 运行期契约: `UNSET`、`ResolverTrustedMode`、`RunOptions`、`RunOverrides`、`Compilation`、`RunResult`

#### Scenario: caller can import facade entrypoints and contracts from yaml_dsl
- **WHEN** 调用方执行 `from IMPL_ROOT.dsl.yaml_dsl import run, compile, run_workflow`
- **AND** 调用方执行 `from IMPL_ROOT.dsl.yaml_dsl import RunOptions, RunOverrides, ResolverTrustedMode`
- **THEN** 导入 MUST 成功且行为与实现一致
