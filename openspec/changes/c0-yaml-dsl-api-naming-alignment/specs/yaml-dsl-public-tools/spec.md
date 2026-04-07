## REMOVED Requirements

### Requirement: `scalim.dsl.by_yaml.tools` MUST be a curated public module
**Reason**：YAML DSL 的 canonical public facade 已从 `scalim.dsl.by_yaml` 收敛为 `scalim.dsl.yaml_dsl`；tools 模块随之迁移。

**Migration**：使用 `scalim.dsl.yaml_dsl.tools`。

#### Scenario: by_yaml.tools is no longer the canonical tools module
- **WHEN** 维护者在文档/skills/examples 中引用 YAML DSL tools
- **THEN** 引用 MUST 使用 `scalim.dsl.yaml_dsl.tools`
- **AND** MUST NOT 再把 `scalim.dsl.by_yaml.tools` 写成推荐路径

## ADDED Requirements

### Requirement: `scalim.dsl.yaml_dsl.tools` MUST be a curated public module
系统 MUST 提供 `scalim.dsl.yaml_dsl.tools` 作为稳定公开模块,并将其纳入 curated public surface 回归门禁(导入 smoke + `__all__` 白名单断言)。

该模块 MUST 使用显式 `__all__` 白名单控制导出,避免随内部重构意外扩大公共承诺面。

#### Scenario: tools module is importable and uses explicit __all__
- **WHEN** 调用方执行 `import scalim.dsl.yaml_dsl.tools`
- **THEN** 导入 MUST 成功
- **AND** 模块 MUST 定义非空 `__all__` 白名单

## MODIFIED Requirements

### Requirement: tools MUST expose `load_output_config` with a stable dict contract
系统 MUST 通过 `scalim.dsl.yaml_dsl.tools.load_output_config(yaml_path)` 暴露输出配置自省能力。

`load_output_config()` MUST 返回 `dict`(运行期) 且其结构契约 MUST 稳定。该 `dict` 至少包含以下 keys:
- `params`
- `field_name_mapping`
- `output_fields`
- `outputs`

系统 MUST 提供 `OutputConfigDict`(TypedDict) 作为类型层契约,用于描述上述结构。

#### Scenario: load_output_config returns the required keys
- **GIVEN** 一个合法的 demand YAML 文件路径 `yaml_path`
- **WHEN** 调用方执行 `scalim.dsl.yaml_dsl.tools.load_output_config(yaml_path)`
- **THEN** 返回值 MUST 为 `dict`
- **AND** 返回值 MUST 至少包含 keys: `params`, `field_name_mapping`, `output_fields`, `outputs`

### Requirement: tools MUST expose `derive_base_module_path`
系统 MUST 通过 `scalim.dsl.yaml_dsl.tools.derive_base_module_path(yaml_path, sys_path=..., cwd=...)` 暴露相对引用基准推导能力。

该函数的行为 MUST 与现有实现一致: 根据 `yaml_path + sys.path` 推导相对引用的 `base_module_path`。

#### Scenario: derive_base_module_path returns a module path
- **GIVEN** `yaml_path` 位于某个 `sys.path` 前缀目录下
- **WHEN** 调用方执行 `scalim.dsl.yaml_dsl.tools.derive_base_module_path(yaml_path, sys_path=[...], cwd=...)`
- **THEN** 返回值 MUST 为字符串模块路径(允许为空字符串表示根包)
