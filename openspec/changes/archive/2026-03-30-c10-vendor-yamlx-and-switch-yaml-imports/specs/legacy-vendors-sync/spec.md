## ADDED Requirements

### Requirement: vendors synced scalim MUST be able to parse YAML without external installs
当 `src/scalim/` 通过 `scripts/vendor_sync.py` 被镜像到下游 `vendors/libs/scalim/` 导入链路后,系统 MUST 在 Python 3.6 环境中具备可用的 YAML 解析能力,且 MUST 不依赖下游额外安装 `PyYAML`/`ruamel.yaml`。

#### Scenario: downstream vendors runtime imports YAML DSL successfully
- **GIVEN** 下游工程仅 vendors 化同步了 `src/scalim/` 源码,且运行环境为 Python 3.6
- **AND** 下游环境未安装任何名为 `yaml`/`ruamel.yaml` 的第三方包
- **WHEN** 下游导入并执行 YAML DSL 的解析入口(例如 `scalim.cli.yaml_dsl` 或 `scalim.dsl.by_yaml.config_parsing.yaml_load`)
- **THEN** 导入与 YAML 解析 MUST 成功

#### Scenario: scalim YAML parsing uses vendored yamlx implementation
- **GIVEN** `src/scalim/vendor/yamlx/` 内包含 vendors 化的 YAML 实现
- **WHEN** `scalim` 在运行时解析 YAML 文本
- **THEN** 系统 MUST 使用 `yamlx.yaml` 作为 YAML 解析实现入口,不得依赖 `require_optional_dependency("yaml")` 走外部安装包
