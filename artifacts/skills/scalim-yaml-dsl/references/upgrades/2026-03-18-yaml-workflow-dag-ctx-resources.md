# 2026-03-18: yaml-workflow-dag-ctx-resources

## 变更摘要

本批次扩展 workflow YAML 的 authoring surface,把“多 demand 编排 + 共享输出 + 小体量上下文传递”收敛到可校验的结构化配置:

- **NEW**: `workflow.runs[*].depends_on` 显式声明 runs 间 DAG 依赖(启动前做引用校验与 cycle detection)
- **NEW**: `workflow.runs[*].init_vars` 为 run 对应的 demand 注入编译期 init vars,并支持 `$ctx` 指令节点读取上游默认 ctx keys
- **NEW**: `workflow.options.ctx` 提供 workflow-level ctx guardrails(`max_value_bytes/max_bytes`)
- **NEW**: `workflow.resources.*` 声明 workflow-scope 共享输出资源:
  - `resources.workbooks/csvs`: 共享输出路径
  - `resources.sheetbooks`: in-memory sheetbook + 预算护栏 + 可选导出 `export_xlsx`
- **NEW**: `workflow.runs[*].writes` 声明写入 intents(list): workbook/csv/sheetbook 的 sheet/append 写入（旧 `write_to` 已移除）
- **NEW**: 内置 loader `scalim.dsl.by_yaml.runtime.workflow_loaders:sheetbook_sheet_rows` 支持下游 demand 读取上游 sheetbook sheet rows(受 deps 可见性约束)

OpenSpec 归档变更（含 proposal/design/spec/tasks）:

- `openspec/changes/archive/2026-03-18-c20-workflow-dag-context-passing/`
- `openspec/changes/archive/2026-03-17-c30-workflow-shared-output-containers/`
- `openspec/changes/archive/2026-03-18-c40-workflow-sheetbook-resources/`

对应主规范(节选):

- `openspec/specs/yaml-dsl-workflow/spec.md`
- `openspec/specs/workflow-shared-output-containers/spec.md`
- `openspec/specs/workflow-sheetbook-resources/spec.md`
- `openspec/specs/workflow-observability-bridge/spec.md`

## Migration Checklist

1) 为每个 demand 分配稳定的 `run.id`,并用 `depends_on` 显式表达依赖关系(避免隐式依赖)
2) 需要把上游结果注入下游 demand 时:
   - 先确保下游 run `depends_on` 上游 run
   - 再在 `init_vars` 中用 `$ctx` 指令节点读取上游默认 ctx keys(例如 `output_path/total_rows/duration_secs`)
3) 若启用 workflow-level ctx,遵守边界:
   - 只放小体量 JSON-like 数据
   - 大对象/大结果通过 outputs/resources 路径表达
   - 必要时用 `workflow.options.ctx.max_value_bytes/max_bytes` 调整护栏
4) 若存在共享输出或潜在输出路径冲突:
   - 将共享目标声明到 `workflow.resources.*`
   - 用 `runs[*].writes` 声明写入 intents(每个 run 可声明 0..N 条；每条 intent 恰好一个 intent key)
5) 若使用 sheetbook:
   - 必须声明 `sheetbooks.<id>.budget.max_sheets/max_total_cells`
   - 需要导出为最终 xlsx 时,声明 `export_xlsx.path`(可选 `write_lock`)
6) 校验与编辑器配置:
   - workflow YAML 只支持 schema-only 校验(仓库内建议显式指定 schema):
     - `uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>`
   - 编辑器补全/hover:
     - `uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>`
7) 运行期验证: 用 Python 入口跑一次最小 workflow,验证 DAG/ctx/resources/writes 的运行期 fail-fast 行为是否符合预期
