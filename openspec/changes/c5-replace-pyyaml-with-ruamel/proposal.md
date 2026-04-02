## Why

仓库已经同时 vendors 了 `PyYAML` 与 `ruamel.yaml`,但 `src/scalim/` 的运行时 YAML 解析仍以 `PyYAML` 风格 API 为默认入口,且 YAML 解析/定位/duplicate key/error 逻辑分散在多个模块(需求 loader、workflow loader、CLI validate、validator、project config)。这导致:

- YAML 1.1/1.2 语义边界不明确,后续升级风险高(尤其是 bool-like 标量解析差异)。
- 同一份 YAML 在不同入口可能出现 parse 行为漂移与重复实现,维护成本上升。
- 工具链无法稳定使用 round-trip 能力对 YAML 做“保留注释/anchors/格式”的编辑(例如 schema modeline 的批量更新)。

本 change 目标是一步到位把默认 YAML backend 切换到 vendored `ruamel.yaml`(YAML 1.2 语义),并在不引入全新包层级的前提下优化现有架构: 将 YAML 解析/定位/错误与 round-trip 编辑能力收敛为单一事实来源,以降低复杂度并为后续编辑能力铺路。

## What Changes

- **BREAKING**: 将 `src/scalim/` 运行时 YAML 解析默认后端从 vendored `PyYAML` 切换为 vendored `ruamel.yaml`(`YAML(typ=\"safe\")`,YAML 1.2 语义)。
- 保留 vendored `PyYAML` 源码与扩展在 `src/scalim/vendor/yamlx/` 以满足 vendors 同步审计与后续排障需要,但运行时入口不再依赖 `yamlx.yaml`。
- 在现有架构中收敛 YAML 解析实现,确保以下入口复用同一套 parse/duplicate key/location/error 口径:
  - demand loader / workflow loader
  - CLI validate / validator helper
  - imports fragments / project config
  - effective YAML dump
- 将 `yaml-dsl upsert-lsp-comment` 的写入实现切换为基于 `ruamel.yaml` round-trip(`typ=\"rt\"`) 的编辑,并引入字节级幂等门禁:
  - no-op round-trip(`load` 后立刻 `dump`) MUST 产出与输入文本完全一致
  - upsert 仅允许修改 schema modeline 所在行,不得无意义重排正文

## Capabilities

### New Capabilities

- `yaml-backend-migration`: 定义默认 backend 切换到 vendored `ruamel.yaml`(YAML 1.2) 的契约,以及 round-trip editing 的稳定性门禁。

### Modified Capabilities

- `legacy-vendors-sync`: vendors 同步后的 YAML 运行时入口约束从“固定使用 `yamlx.yaml`(PyYAML)”调整为“默认使用 vendored `ruamel.yaml`”,同时保持 Python 3.6 无外部依赖可运行。
- `yaml-dsl-unified-loader`: 统一 YAML facade 的要求更新为 ruamel-only: 所有入口 MUST 复用同一 ruamel-based facade,并继续保证 duplicate key、location index、ErrorEnvelope 与各入口一致性。

## Impact

- 受影响代码主要位于:
  - `src/scalim/vendor/yamlx/`(依赖边界与 vendors 入口)
  - `src/scalim/dsl/by_yaml/_internal/config_parsing/`(统一 loader/facade)
  - `src/scalim/dsl/by_yaml/workflow_config/`
  - `src/scalim/cli/yaml_dsl.py` 与 `src/scalim/cli/yaml_dsl_lsp.py`
  - 相关 tests 与 py36 docker checks
- 语义风险集中在 YAML 1.1→1.2 的标量解析差异、duplicate key 处理与 dump/round-trip 稳定性;本 change 将以 corpus parity + py36 gate + round-trip no-op gate 缓解。
- 受影响的 SSOT 包括本 change 的 OpenSpec 工件、`src/scalim/vendor/README.md` 与 `src/scalim/vendor/yamlx/SOURCE.md`。任何 `.gen.` 文件或 `BEGIN/END AUTOGEN` 注入区块均不得手改;若实现影响 docs,应通过 `just gen-docs` 刷新生成物。
