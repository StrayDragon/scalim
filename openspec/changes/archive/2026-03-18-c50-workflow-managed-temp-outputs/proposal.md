## Why

在 workflow + shared resources(write nodes) 的用法里，很多 demand outputs 本质上只是“中间产物”（例如 CSV），最终会被 `writes` 写入共享 workbook/sheetbook 并在 workflow commit 时一次性导出。

但当前 demand 输出容器 `container.path` 是必填，这会迫使下游为了“只给 write nodes 消费”的 outputs 仍然手写一个真实路径，常见结果是：
- Python 入口做字符串替换/生成 `.runtime.demand.yaml` 临时文件 → 执行后清理（胶水多、且有泄漏风险）
- 或把路径散落在各个 demand YAML，缺少统一生命周期管理

我们希望提供一个更符合 Scalim 初衷（省内存、流式、确定性）的折中：仍使用磁盘 CSV 作为 artifacts，但由 workflow 统一托管“临时输出路径”的生成与清理。

## What Changes

- 新增 workflow 托管的临时输出能力（managed temp outputs）：
  - 当某个 demand output 仅用于 workflow write nodes 消费时，允许其 `outputs[*].container.path` 省略/为空（仅限 `type: csv`）。
  - workflow 在 node 物化编译前为这些 outputs 分配 run-scoped 的临时 CSV 路径，并在 workflow commit/discard 后统一清理。
- 强约束与 fail-fast：
  - workbook 类型输出仍必须显式提供 path（不支持 pathless workbook）。
  - 若某个 pathless CSV output 未被任何 write intent 引用，系统 MUST fail-fast（避免“悄悄写临时文件但没人消费”的漏配）。
- 同步 schema 与文档：
  - demand JSON schema/hover 需允许该写法并明确“仅 workflow 托管场景可用”的边界；
  - 文档补齐推荐用法与清理语义。

## Capabilities

### New Capabilities
- `workflow-managed-temp-outputs`: workflow 托管临时 CSV artifacts 的生成、可见性与清理语义（避免 Python glue 与临时文件泄漏）。

### Modified Capabilities
- `workflow-shared-output-containers`: write nodes 允许消费 pathless CSV outputs（由 workflow 托管分配实际路径）。
- `yaml-dsl-schema`: 允许 `outputs.*.container.path` 在受限场景下省略/为空，并在 schema hover 中写清楚约束与推荐用法。

## Impact

- 受影响代码（预期）：
  - schema/model：`src/scalim/dsl/by_yaml/schema_dsl/models/outputs.py`（container.path 约束与文案）
  - compiler/runtime：`src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`（生成/校验 outputs path）
  - workflow：`src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`（为 node 分配 managed temp dir + 清理）
- 生成物影响（禁止手改）：
  - `src/scalim/dsl/by_yaml/schema/demand.gen.json`（由 `scripts/gen-yaml-dsl-schema.py` 生成）
  - docs 中的 `.gen.md` 与 injected blocks（由 `just gen-docs` 刷新）
- 测试影响：
  - 新增 workflow 集成测试覆盖“pathless CSV output → write nodes 消费 → commit/discard 清理”。

