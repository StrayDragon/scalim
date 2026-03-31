## Why

当前仓库已经同时 vendors 了 `PyYAML` 与 `ruamel.yaml`,但运行时默认入口、统一 loader、错误结构与测试口径仍然围绕 `PyYAML` 风格 API 构建。随着 YAML DSL 持续演进,项目需要一个明确提案来评估并规范化“以 `ruamel.yaml` 作为未来默认 YAML 后端”的迁移边界,以便获得更贴近 YAML 1.2 的语义、后续更强的高级 YAML 操作能力,以及在未来需要时更好地保留注释/格式信息。

## What Changes

- 为 `PyYAML` → `ruamel.yaml` 的默认后端迁移建立正式 OpenSpec 契约,明确这是一个允许分阶段推进的长期 change,而不是要求立即切换。
- 明确 YAML 统一 facade 的目标行为,要求未来切换后继续保持 demand/workflow/CLI validate/imports 的一致解析口径、重复键策略、错误结构与定位能力。
- 明确 vendors 同步场景下的新约束: 运行时仍必须在 Python 3.6 下可用,且不得依赖外部安装 `PyYAML`/`ruamel.yaml`。
- 为迁移任务加入前置“届时深入分析”步骤,覆盖真实代码接入面、3.6 运行边界、语义差异、dump 风格与 notebook/demo 样本回归,避免任务过早绑定到当前代码细节。
- 为未来可能启用的高级 YAML 能力预留设计空间,包括基于 `ruamel.yaml` 的注释保留、round-trip 编辑与更细粒度的 YAML 结构操作,但本 change 不要求在第一阶段立即交付这些高级能力。

## Capabilities

### New Capabilities

- `yaml-backend-migration`: 规定从 vendored `PyYAML` 默认后端迁移到 vendored `ruamel.yaml` 的目标边界、分阶段推进方式、验证要求与非目标。

### Modified Capabilities

- `legacy-vendors-sync`: 更新 vendors 同步后的 YAML 运行时入口约束,从“固定使用 `yamlx.yaml`”调整为“使用仓库定义的 vendored YAML facade/默认后端”,同时保持 Python 3.6 无外部依赖可运行。
- `yaml-dsl-unified-loader`: 更新统一 YAML facade 的要求,允许底层实现切换为 `ruamel.yaml`,同时继续保证 duplicate key、location index、ErrorEnvelope 与各入口一致性。

## Impact

- 受影响代码主要位于 `src/scalim/vendor/yamlx/`, `src/scalim/dsl/by_yaml/config_parsing/`, `src/scalim/dsl/by_yaml/workflow_config/`, `src/scalim/cli/yaml_dsl.py` 与相关 tests。
- 运行时 API 契约可能需要从 `PyYAML` 顶层函数风格适配到仓库自定义 facade,以屏蔽 `ruamel.yaml` 0.18.x 的 API 变化。
- 示例与回归范围包括 `tests/fixtures/*.yaml`, `notebooks/marimo/**/declared_yaml_dsl/*.yaml` 及 Python 3.6 下的 vendored runtime smoke checks。
- 受影响的 SSOT 是 OpenSpec specs 与 `src/scalim/vendor/README.md` / `src/scalim/vendor/yamlx/SOURCE.md`; 不涉及 `.gen.` 文件的手工修改,后续若有 docs 变更应通过现有生成入口刷新。
