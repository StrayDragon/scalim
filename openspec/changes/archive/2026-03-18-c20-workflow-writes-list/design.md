## Context

当前 workflow YAML 支持 `workflow.resources` 声明共享输出资源(workbook/csv/sheetbook)，并通过 `workflow.runs[*].write_to` 声明写入 intent。实现上，`_compile_workflow_ir()` 会为每个 run（demand node）最多创建一个 write node，并在同一资源维度上用显式 deps 串行化写入，保证确定性与冲突安全。

该模型在“单个 run 只有一个 output 需要写入共享资源”时工作良好，但对典型报表不够表达力：
- 一个 demand 往往同时产出 `metrics` 与 `detail` 等多个 outputs；
- 用户希望在一次 workflow commit 内把多个 outputs 写到同一本 workbook/sheetbook 的多个 sheet（一次性落盘/导出）；
- 但 `write_to` 是互斥 intent：同一 run 只能写一个 output；其余 outputs 只能让 demand 自己写 xlsx（又会触发 reserved-path/collision 规则或导致覆盖写风险），或回退到 Python 合并文件。

因此需要把“写入 intent”从单个映射升级为列表，使一个 run 可以声明多条写入意图。

## Goals / Non-Goals

**Goals:**
- 允许同一个 run 声明 0..N 条写入意图，使多 output demand 能写入同一个共享 workbook/sheetbook。
- 保持写入确定性与冲突安全：对同一资源的写入互斥且顺序稳定可复现。
- 维持 Scalim 的“省内存”路线：write nodes 仍以 CSV 文件 artifacts 为输入（不引入大表纯内存传递）。

**Non-Goals:**
- 不在本提案中引入“无路径/内存型 output”或流式 pipe 直连 write node（见后续提案）。
- 不在本提案中放开 demand 直接写 sheetbook export xlsx 路径；reserved-path 规则保持。
- 不做运行期兼容层：升级采用“直接改写配置 + 刷新 schema/docs”路线（旧写法直接升级为新写法）。

## Decisions

### D1. 用 `writes` 列表替代 `write_to`（BREAKING）

决定：移除 `workflow.runs[*].write_to`，新增 `workflow.runs[*].writes`：
- `writes` 为数组；缺省/空数组表示无写入意图；
- 每个 item 为一个“单 intent 对象”，且 MUST 恰好包含一个 intent key（仍为五类之一）。

示例（同一 run 写两份 output 到同一个 sheetbook 的不同 sheet）：
```yaml
workflow:
  runs:
    - id: report
      demand: ./report.demand.yaml
      writes:
        - sheetbook_append: {sheetbook: report, sheet: Metrics, output: metrics}
        - sheetbook_sheet:  {sheetbook: report, sheet: 明细,   output: detail}
```

替代方案（不选）：
- 维持 `write_to`，额外允许 `write_to` 内出现多个 keys：会破坏现有“一 key = 一 intent”的校验与数据结构，不利于扩展与清晰错误定位。
- 采用 `{kind: ..., ...}` 的扁平对象：作者体验更好，但需要整体重塑 schema/解析器；当前优先在最小行为变化下提升表达力。

### D2. IR 编译：为每条 intent 生成一个 write node

决定：`_compile_workflow_ir()` 在编译 demand nodes 后，遍历 `runs[*].writes`，为每条 intent 生成一个 write node：
- write node `deps` 至少包含其输入 demand node id；
- node_id 采用稳定且可诊断的命名（例如 `__wf__write.<run_id>.<write_idx>`）；
- node 的 `decl_order` 按 nodes 追加顺序递增，确保 ready-node tie-break 与日志顺序稳定。

### D3. 写入互斥与确定性：按资源链式串行化

决定：沿用现有 per-resource 链式 deps：
- 以 `(resource_type, resource_id)` 为 key；
- 对同一 key 的所有 write nodes 建立显式链（后一个依赖前一个），避免依赖并发完成时序；
- 由于编译遍历顺序为：runs 列表顺序 → writes 列表顺序，故同一资源上的写入顺序自然等价于“run 顺序 + writes 顺序”。

### D4. sheetbook 读屏障：对 direct dependents 保守加依赖

当前实现为了让下游 demand 能用内置 loader 读取上游 sheetbook，会将“producer run 的 direct dependents”额外依赖到 producer 的 sheetbook write node，确保读取时已写入。

升级后同一 run 可能存在多个 sheetbook 写入节点。决定采用保守策略：
- 对每个 producer run，收集其所有 `resource_type=sheetbook` 的 write node ids；
- 将这些 write node ids 全部追加到该 producer 的 direct dependents 的 deps 中。

权衡：
- 好处：无需精确分析下游 demand 实际读取哪个 sheetbook，避免漏依赖导致读到未完成数据。
- 代价：可能降低部分并发（但只影响依赖边上的节点，且符合“正确优先”）。

## Risks / Trade-offs

- [BREAKING] 旧配置需一次性升级：`write_to: {<kind>: ...}` → `writes: [{<kind>: ...}]`；缓解：提供明确迁移指引与 schema 校验错误提示。
- [节点数增加] 多 output 场景会生成更多 write nodes；缓解：写节点轻量，且能替代 Python 合并与多次落盘。
- [保守依赖降低并发] `D4` 可能让部分下游节点等待额外写入完成；缓解：仅对 sheetbook 相关链路生效，且避免不确定/难排查的读取竞态。

## Migration Plan

1) 将 workflow YAML 中：
- `runs[*].write_to` 替换为 `runs[*].writes` 列表；
- 单 intent 迁移规则：`write_to: {<kind>: <cfg>}` → `writes: [{<kind>: <cfg>}]`。

2) 运行 schema-only 校验：
`uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json path/to/workflow.yaml`

3) 刷新生成物（禁止手改生成物）：
- schema 生成入口：`scripts/gen-yaml-dsl-schema.py`
- docs 生成入口：`just gen-docs`

