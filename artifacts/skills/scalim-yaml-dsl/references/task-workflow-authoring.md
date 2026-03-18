# workflow YAML 编排(多 demand + resources)

## 何时读取

- 用户要新建/修改 workflow YAML(编排多条 demand)
- 用户要加 DAG 依赖(`depends_on`)或跨节点注入 init vars(`init_vars`)
- 用户要用 workflow-level ctx(`$ctx` / `options.ctx`)减少 Python glue
- 用户要声明共享输出资源(`resources.*`)并用 `write_to` 写入(workbook/csv/sheetbook)

## 工作顺序

1. 列出所有要跑的 demand YAML,为每个 demand 分配一个稳定的 `run.id`
2. 画出依赖图: 哪些 runs 必须等上游完成? 用 `depends_on` 明确表达
3. 若需要把上游结果注入下游 demand,用 `init_vars` + `$ctx` 指令节点表达
4. 若需要共享输出(共享 workbook/csv 或 in-memory sheetbook),先声明 `workflow.resources.*`,再在各 run 上声明 `write_to` intent
5. 先跑 schema-only 校验(显式指定 workflow schema),再在 Python 入口中跑一次小规模试运行

## 推荐骨架(带 DAG/ctx/resources/write_to)

```yaml
# $schema: http://localhost:62831/workflow.gen.json

workflow:
  resources:
    sheetbooks:
      report:
        budget:
          max_sheets: 16
          max_total_cells: 2000000
        export_xlsx:
          path: ./out/report.xlsx
          write_lock: true

  runs:
    - id: extract
      demand: ./extract.yaml

    - id: agg
      demand: ./agg.yaml
      depends_on: [extract]
      init_vars:
        extract_output_path: {$ctx: {node: extract, key: output_path}}

    - id: export
      demand: ./export.yaml
      depends_on: [agg]
      write_to:
        sheetbook_sheet:
          sheetbook: report
          sheet: Summary
          output: default
          on_conflict: error

  options:
    max_concurrency: 2
    failure_policy: all_fail
    ctx:
      max_value_bytes: 65536
      max_bytes: 1048576
    cache_pool:
      conflict_policy: error
      release_policy: dag_refcount
      budget:
        max_entries: 16
        over_budget_policy: fail_fast
```

## 关键规则

- `workflow.runs` 必须非空；`runs[*].id` 必须全局唯一
- `runs[*].demand` 相对路径以 workflow 文件所在目录为基准
- `depends_on`:
  - deps 引用的 run id 必须存在
  - 必须无环；有 cycle 会在启动前 fail-fast
- `init_vars`:
  - 语义为“注入到该 run 对应的 demand 编译期 init vars”
  - 需要引用上游结果时,用 `$ctx` 指令节点(对象节点),不要写字符串插值
- `ctx`:
  - 只能传小体量 JSON-like 数据；禁止塞 rows/dataset/大对象
  - 读取必须在依赖闭包内(没声明依赖就不能读上游)
- `resources` + `write_to`:
  - 共享输出资源必须先声明在 `workflow.resources.*`
  - `write_to` 是互斥 intent: 同一个 run 下最多一个 intent key
  - 写入顺序以 `workflow.runs` 声明顺序为准(不依赖并发完成时序),以保证确定性

## 常见模式

### 读取上游 sheetbook 作为下游 demand 的输入

workflow 的 sheetbook 是 workflow scope 的共享资源. 若下游 demand 需要读取上游写入的某个 sheet,可以用内置 loader:

```yaml
main_source:
  loader: "scalim.dsl.by_yaml.runtime.workflow_loaders:sheetbook_sheet_rows"
  params:
    ref:
      node: export
      sheetbook: report
      sheet: Summary
  fields:
    # ...
```

注意: 下游 run 必须 `depends_on` 其引用的上游 run,否则会因为“引用超出 deps 可见范围”而 fail-fast.

## 编写完成后的最小检查

workflow YAML 只支持 schema-only 校验(仓库内建议显式指定 schema 路径):

```bash
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>
```

编辑器补全/hover 建议:

```bash
uv run scalim-cli yaml-dsl schema-serve
uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --schema-path http://localhost:62831 <paths...>
```

