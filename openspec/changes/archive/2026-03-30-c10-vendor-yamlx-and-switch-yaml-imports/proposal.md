## Why

下游存在年老旧项目（Python 3.6、无法随意安装第三方依赖）通过 `scripts/vendor_sync.py` 将 `src/scalim/` vendors 化后直接运行。当前 `scalim` 的 YAML 解析依赖 `PyYAML`（以及可能的 `ruamel.yaml`），在下游“只同步源码、不装依赖”的使用方式下会直接导入失败。

我们需要在 `src/scalim/vendor/yamlx/` 内 vendors 化 YAML 相关依赖，并提供一个对 Python 3.6 友好、可复用的导入入口，使得 `scalim` 在被 vendors 化后仍能稳定解析 YAML DSL。

## What Changes

- 在 `src/scalim/vendor/yamlx/` 中提供一套 bootstrap/导入策略，使其中 vendors 化的两个包（`yaml` 与 `ruamel.yaml`）在无外部依赖安装的场景下可被可靠导入与使用（Python 3.6 兼容）。
- 将 `src/scalim/` 内现有对 `yaml` 的导入替换为使用 `yamlx.yaml`（即通过 `scalim.vendor.yamlx` 访问 vendors 化的 `yaml` 实现），避免下游依赖 `pip install PyYAML`。
- 增补一份探索性对比结论：在 Python 3.6 环境下对比 `PyYAML` 与 `ruamel.yaml` 的可用性/性能/语义差异，为后续是否切换实现提供依据（不承诺本次一定切换到 `ruamel.yaml` 作为默认实现）。

## Capabilities

### New Capabilities

<!-- none -->

### Modified Capabilities

- `legacy-vendors-sync`: vendors 同步后的 `scalim/` MUST 自包含 YAML 解析能力（不依赖下游额外安装 `PyYAML`/`ruamel.yaml`），并在 Python 3.6 下可导入运行。

## Impact

- 受影响代码：`src/scalim/vendor/yamlx/`、YAML DSL 解析与 CLI（`src/scalim/dsl/by_yaml/**`, `src/scalim/cli/yaml_dsl.py`）。
- 受影响运行环境：下游 vendors 方式运行的 Python 3.6 项目；开发环境（Python 3.10+）需确保导入策略不会引入不可控的全局副作用。
