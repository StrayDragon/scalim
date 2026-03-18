## Why

下游典型报表会在同一个 demand 内同时产出多份输出（例如 `metrics` 聚合表 + `detail` 明细行），并希望在一次 workflow 执行中把它们写入同一个 workbook/sheetbook 的不同 sheet，最终只导出一次 xlsx。

但当前 workflow 的 `runs[*].write_to` 是**互斥 intent**：同一个 run 最多只能声明一个写入意图。再叠加 sheetbook 的 reserved-path 规则（禁止 demand 直接写 sheetbook export 的 xlsx 路径），导致“多 output demand + sheetbook 管理同一路径”场景无法表达，被迫回退到：
- 每个 output 写独立 xlsx → Python 入口合并（复杂、慢、丢 streaming 优势）
- 或 demand 直接写到最终 export 路径 → 被 reserved-path 检查阻止（语义上也不安全）

因此需要升级 workflow 写节点的 authoring surface：允许同一个 run 声明**多条写入意图**，让“一个 run 多 output → 同一共享资源多 sheet”成为一等能力。

## What Changes

- **BREAKING**: 将 `workflow.runs[*].write_to` 升级为 `workflow.runs[*].writes: [ ... ]` 列表：
  - `writes` 为 0..N 条写入意图；
  - 每条写入意图仍是当前五类之一：`workbook_sheet/workbook_append/sheetbook_sheet/sheetbook_append/csv_append`；
  - 单条写入意图的字段结构与含义保持不变（仅从 `write_to.<kind>` 迁移到 `writes[*].<kind>`）。
- workflow 编译期将 `writes` 列表编译为多个 write nodes（每条意图一个节点），并保持对同一资源的写入互斥与确定性顺序（runs 声明顺序 + writes 列表顺序）。
- 更新 workflow JSON Schema、用户文档与升级指引，使 editor/validate 与运行期行为一致。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `workflow-shared-output-containers`: `write_to` 互斥 intent → `writes` 列表；确定性写入顺序规则扩展为“run 顺序 + writes 顺序”。
- `workflow-sheetbook-resources`: sheetbook 写入 intent 从 `write_to.sheetbook_*` 迁移到 `writes[*].sheetbook_*`，并允许同一 run 写入多个 sheet（满足多 output demand 场景）。

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/workflow.py`（workflow YAML 解析：`write_to` → `writes`）
  - `src/scalim/dsl/by_yaml/schema_dsl/builder.py`（生成 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`）
  - `src/scalim/dsl/by_yaml/runtime/workflow_entrypoints.py`（IR 编译：多 write nodes；依赖/顺序）
- 受影响文档：
  - 手写 SSOT：`docs/doc/yaml-dsl/workflow.md`
  - 生成物：`src/scalim/dsl/by_yaml/schema/workflow.gen.json`、`docs/doc/yaml-dsl/schema-reference.gen.md`、`docs/doc/yaml-dsl/upgrades/*.gen.md`（需通过生成入口刷新，不手改）
- 测试影响：
  - 需要新增/调整 workflow 解析与 write nodes 的测试覆盖（多 writes、确定性顺序、sheetbook 多 output）。

