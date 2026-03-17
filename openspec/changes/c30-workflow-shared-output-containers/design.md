## Context

现状:
- 单 demand 内已经支持多输出/多 sheet(`outputs[*]`)以及共享同一 workbook 容器(`ExcelWorkbookSink`)。
- workflow YAML 已支持 runs 批量执行、并发上限、失败策略与共享 preload cache,但 runs 之间没有依赖图与跨 run 的共享输出容器。
- 仓内已有一个 Python-only 的“多 demand 写入同一 workbook”的工具函数: `src/scalim/execution/workbook_multi_root.py::run_multi_root_workbook()`。

痛点:
- 多 demand 合并到同一个最终 workbook/csv 时,用户只能回到 Python glue 或中间文件拼接。
- 并发下“谁先写、谁后写”若依赖完成顺序会导致不确定性,不利于对拍与可视化排障。

约束/原则:
- 运行时 Python 3.6 兼容。
- 优先复用现有 sink/IR 体系(保持 demand 心智模型),避免引入“workflow 内存数据集图”。
- 文档/生成边界必须在实现前收敛(哪些手写/哪些生成/哪些 injected-block),并给出 drift gate。

与 `c20-workflow-dag-context-passing` 的关系:
- 共享输出容器的“写出节点/资源互斥/确定性顺序”本质上依赖 DAG 编排与确定性调度。
- 推荐将本 change 设计为“在 DAG 调度器之上增加资源管理与写出语义”。

## Goals / Non-Goals

**Goals:**
- 支持多 demand 合并到同一个最终输出容器(workbook/csv),覆盖:
  1) 多 demand → 单 workbook 多 sheet
  2) 多 demand → 单 sheet append(或 csv append)
- workflow 统一管理共享容器生命周期: 创建/关闭/保存/原子替换(commit)。
- 对同一共享容器的写入 MUST 确定性且可配置冲突策略(至少支持 fail-fast)。
- 并发执行时,对同一共享容器的写入 MUST 串行化或等价互斥(避免文件损坏/不确定性)。
- 不配置新字段时保持旧 workflow 行为不变(非 breaking)。

**Non-Goals:**
- 不在 MVP 内实现“run 完成后把 rows 作为 artifact 传给 write 节点”的内存数据集传递。
- 不实现完整的节点类型系统(如需 `write_sheet/append_sheet/ctx_compute` 独立节点,作为后续扩展候选)。
- 不做跨进程缓存/断点续跑/增量写入恢复。

## Decisions

### 1) YAML surface (Recommended MVP): resources + run-level write binding

推荐 MVP 先选择“run 直接写入共享资源”的路线,避免在 workflow 内做 rows 缓冲:

新增 `workflow.resources`:

```yaml
workflow:
  resources:
    workbooks:
      report:
        path: ./out/report.xlsx
    csvs:
      all_rows:
        path: ./out/all.csv
```

在 `workflow.runs[*]` 增加 `write_to`(提案字段名,可讨论):

```yaml
- id: orders
  demand: ./orders.demand.yaml
  write_to:
    workbook_sheet:
      workbook: report
      sheet: Orders
```

append 到同一 sheet/csv 的 MVP 形态(字段名为提案):

```yaml
write_to:
  workbook_sheet:
    workbook: report
    sheet: Orders
    mode: append         # append | replace
    align_by: field_id   # field_id | strict_equal (MVP 可先只做 strict_equal)
    header: once         # once | never | each
```

备选方案:
- A) `writes:` 作为独立节点列表(更贴近“workflow 是 DAG 节点集合”),但需要:
  - demand 的输出要么落盘为中间文件,要么引入 spool sink(避免攒内存)
  - write 节点再读取并写入容器
- B) 专用的 `workbooks:` DSL(类似 `run_multi_root_workbook`),语法更短但通用性弱,不易扩展到 csv/更复杂 DAG。

### 2) Execution model: resource lifecycle + mutual exclusion + deterministic order

推荐行为:
- workflow 启动时解析资源声明,在首次使用时创建资源实例(workbook/csv)并进入“未提交”状态。
- 对同一资源的写入强制互斥:
  - workbook: 同时只允许一个 run 创建/写入 sheet
  - csv: 同时只允许一个 run 追加写入
- 写入顺序确定性:
  - 当多个可写节点同时就绪时,按 workflow 声明顺序稳定选择(由 DAG 调度器保证)
  - 对同一资源,即使并发调度也 MUST 通过互斥确保最终写入顺序可预测
- commit/落盘:
  - 推荐延迟到 workflow 结束统一 commit,并使用原子替换
  - `failure_policy=all_fail` 时默认丢弃未提交资源(避免产出部分落盘文件)
  - `failure_policy=primary_only` 时默认 commit 已成功写入部分(更符合“best-effort 合并输出”直觉),但允许配置为 discard

### 3) Binding demand outputs into shared resources

基于现有实现,推荐 MVP 只支持“把 run 的单输出(primary)写入目标容器”:
- workflow runner 在执行该 run 时:
  - 按编译得到的 `export_layout.field_ids/header_names` 创建目标 sheet/csv writer
  - 覆盖该 run 的输出: 将 `ExecutionRequest.sink` 指向 writer,并将 `output.path` 置空(避免 demand 自己落盘)

对多输出 demand(`outputs[*]`)的处理(需定案):
- MVP 方案 A: 暂不支持(遇到多输出则 fail-fast),要求此类需求先在 demand 内做多 sheet,workflow 只负责多 demand 合并。
- MVP 方案 B: 允许 `write_to.*.output_target` 指定一个输出目标 id(只绑定一个)。

### 4) Merge semantics for append

MVP 建议先做“严格字段集合一致”以降低复杂度:
- `align_by: strict_equal`(默认): 所有追加段的 `field_ids` 必须完全相同,否则 fail-fast
- 作为扩展候选再做:
  - `align_by: field_id`(union): 以声明的列集合为准,缺失字段填空
  - `align_by: header`(不推荐): 受本地化表头/别名影响更大,不利于对拍

header 策略:
- `header: once`(默认): 只在首次创建 sheet/csv 时输出 header
- `header: never`: 从不输出 header
- `header: each`: 每段都输出 header(仅少数场景需要)

### 5) Doc / generation boundary & drift gates (MUST)

实现时必须遵循既有治理:
- JSON Schema 为生成物:
  - `src/scalim/dsl/by_yaml/schema/workflow.gen.json` + 前端分发文件(按脚本生成)
- docs/示例:
  - 统一在 `docs/doc/yaml-dsl/workflow.md` 补充共享资源与写出示例
  - canonical demo 需要回归: `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
- gates:
  - `just gen-docs` / `just qa` / `just openspec-check`

## Risks / Trade-offs

- [资源互斥会降低并行度] → 允许不同资源并行;同一资源串行是为了确定性与避免文件损坏。
- [all_fail 丢弃输出可能影响排障] → 允许通过资源配置切换为“保留部分输出用于诊断”(但默认不产出半成品)。
- [多输出 demand 与 workflow 合并语义叠加复杂] → MVP 先限制(只支持单输出或只选一个 output_target),后续再扩展。
- [append 合并字段对齐复杂] → MVP 先 strict_equal;后续再做 union/填空模式。

## Migration Plan

建议分阶段落地:

1) 只做 workbook 多 sheet(多 demand → 单 workbook 多 sheet),不做 append
2) 增加 append-to-sheet 与 csv append(严格字段一致)
3) 增加更宽松的对齐策略(field_id union)与更多冲突策略
4) 如有需要,再引入独立 `write_sheet/append_sheet` 节点与 spool sink(支持“并发 compute + 串行写出”)

## Open Questions

- YAML 形态: `write_to` 绑定 vs 独立 `writes` 节点列表(可视化/确定性/实现复杂度的权衡)？
- `failure_policy` 下的默认 commit 行为: all_fail 是否默认 discard,primary_only 是否默认 commit partial？
- 多输出 demand 的 MVP 支持边界: 禁止 vs 选择一个 output_target vs 全量映射？
- 是否需要显式的“资源写入顺序”字段,还是完全依赖 DAG/声明顺序？

## MVP Examples

### Example A: multi demand → one workbook, multi sheets

```yaml
workflow:
  resources:
    workbooks:
      report:
        path: ./out/report.xlsx
  runs:
    - id: orders
      demand: ./orders.demand.yaml
      write_to:
        workbook_sheet:
          workbook: report
          sheet: Orders
    - id: customers
      demand: ./customers.demand.yaml
      write_to:
        workbook_sheet:
          workbook: report
          sheet: Customers
  options:
    max_concurrency: 4
    failure_policy: all_fail
```

### Example B: append to one sheet with deterministic order

```yaml
workflow:
  resources:
    workbooks:
      report:
        path: ./out/report.xlsx
  runs:
    - id: orders_cn
      demand: ./orders_cn.demand.yaml
      write_to:
        workbook_sheet:
          workbook: report
          sheet: Orders
          mode: append
          align_by: strict_equal
          header: once
    - id: orders_us
      demand: ./orders_us.demand.yaml
      write_to:
        workbook_sheet:
          workbook: report
          sheet: Orders
          mode: append
          align_by: strict_equal
          header: once
  options:
    max_concurrency: 8
    failure_policy: primary_only
```
