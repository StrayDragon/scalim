## Why

当前对用户来说有两个明显的摩擦点:

1) **YAML-first 无法闭环**: 现有 `scalim-cli yaml-dsl` 主要覆盖 `validate/schema` 等工具链能力,但缺少“直接运行 demand/workflow YAML”的官方入口,导致用户不得不写一层 Python wrapper 才能把配置跑起来,同时被迫理解 allowlist/runtime policy 等内部概念。
2) **Python 入口参数爆炸**: `scalim.dsl.by_yaml.run/compile/run_workflow` 的参数面已经很大,新增能力往往只能继续加参数,这会让 API 越来越不直觉、也越来越难演进(每个参数都变成长期兼容负担)。

## What Changes

- 新增 **CLI runner**（YAML-first 闭环）:
  - `scalim-cli yaml-dsl run <demand.yaml>`: 运行单个 demand YAML
  - `scalim-cli yaml-dsl workflow run <workflow.yaml>`: 运行 workflow YAML
  - 支持从 `scalim.yaml` 读取项目级默认值(例如 allowlist、allowed_yaml_roots、template_sandbox 等),并允许 CLI flags 覆盖
- 收敛 **Python 运行入口**（API 可演进）:
  - 引入/强化“单对象参数”入口: `run/compile(..., options=RunOptions)`（或等价门面）,避免继续扩大函数签名
  - 保留少量 `RunOverrides.*` 工厂方法作为常用场景的直觉入口(例如 csv/xlsx 单输出编排)
- 文档与示例对齐（以代码实现为准）:
  - 文档/示例更新以当前实现为事实来源(避免以旧 spec/旧文档反推实现)
  - 注意生成物治理: `*.gen.*` 与 `BEGIN/END AUTOGEN` 区块不手改,走对应生成入口

## Capabilities

### New Capabilities

- `yaml-dsl-cli-runner`: 提供 demand/workflow YAML 的 CLI 运行入口,并支持项目级默认配置与可复现的运行参数注入。

### Modified Capabilities

- `dsl-runtime-structure`: by_yaml runtime entrypoints 收敛为“options-object”风格入口,减少公开签名膨胀并维持可扩展性。
- `yaml-dsl-project-config-schema`: 扩展 `scalim.yaml` 的 `yaml_dsl` 配置能力,用于承载 CLI runner 所需的项目级默认值(不污染 demand YAML 主线)。

## Impact

- 受影响代码:
  - CLI: `src/scalim/cli/yaml_dsl.py`（新增 run 子命令与参数解析/输出约定）
  - YAML runtime entrypoints/contracts: `src/scalim/dsl/by_yaml/runtime/entrypoints.py`, `src/scalim/dsl/by_yaml/runtime/contracts.py`, `src/scalim/dsl/by_yaml/__init__.py`
  - 项目配置: `src/scalim/dsl/by_yaml/_internal/config_parsing/project_config.py`（`scalim.yaml` 扩展）
- 受影响文档/示例:
  - 需要确保所有示例以当前实现为准,且不手改任何 `*.gen.*` 或 AUTOGEN 区块(必要时通过 `just gen-docs` / 相关 generator 更新)。
