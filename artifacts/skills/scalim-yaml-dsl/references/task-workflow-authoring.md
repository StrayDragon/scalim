# workflow YAML 编排(多 demand + books)

## 何时读取

- 用户要新建/修改 workflow YAML(编排多条 demand)
- 用户要加 DAG 依赖(`depends_on`)或跨节点注入 init vars(`init_vars`)
- 用户要用 workflow-level ctx(`$ctx` / `options.ctx`)减少 Python glue
- 用户要声明 workflow-scope 共享输出资源(`workflow.resources.books`)

## 工作顺序

1. 列出所有要跑的 demand YAML,为每个 demand 分配一个稳定的 `run.id`
2. 画出依赖图: 哪些 runs 必须等上游完成? 用 `depends_on` 明确表达
3. 若需要把上游结果注入下游 demand,用 `init_vars` + `$ctx` 指令节点表达
4. 若需要共享输出(多个 demand 共享同一个 `.xlsx` 或同一个内存 book),优先在 `workflow.resources.books` 统一声明 book 资源,再由各 demand 的 outputs 绑定到 `to.book/to.sheet`
5. 先跑 schema-only 校验(显式指定 workflow schema),再跑 workflow-level validate,最后在 Python 入口中做一次小规模试运行

## 推荐骨架(带 DAG/ctx/resources)

```yaml
# yaml-language-server: $schema=.../workflow.gen.json
# $schema: .../workflow.gen.json

workflow:
  resources:
    books:
      report:
        kind: xlsx_memory
        budget: {max_sheets: 16, max_total_cells: 2000000}
        export_xlsx: {path: ./out/report.xlsx, write_lock: true}

  runs:
    - id: extract
      demand: ./extract.yaml

    - id: agg
      demand: ./agg.yaml
      depends_on: [extract]
      init_vars:
        extract_output_path: {$ctx: {node: extract, key: output_path}}

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
- `workflow.resources.books`:
  - workflow-scope 的共享 book 资源入口(Excel 输出的目标/中间态)
  - `kind: xlsx_file|xlsx_memory`；`xlsx_memory` 必须声明 `budget.max_sheets/max_total_cells`
  - Excel 输出通过 demand 的 `outputs[*].to` 绑定到 book+sheet；workbook 写入策略以 `resources.books.*.write_defaults` 为 SSOT,`outputs[*].write` 仅用于 output-local header 行为

demand YAML(示意): 绑定输出到 workflow 声明的 book:

```yaml
outputs:
  - name: summary
    to: {book: report, sheet: Summary}
    fields: [order_id, amount_yuan]
```

## 常见模式

### 读取上游 book sheet rows 作为下游 demand 的输入

workflow 的 `books.kind=xlsx_memory` 是 workflow scope 的共享资源. 若下游 demand 需要读取上游写入的某个 sheet,可以用内置 loader:

```yaml
main_source:
  loader: "scalim.workflow.loaders:book_sheet_rows"
  params:
    ref:
      node: agg
      book: report
      sheet: Summary
  fields:
    # ...
```

注意: 下游 run 必须 `depends_on` 其引用的上游 run,否则会因为“引用超出 deps 可见范围”而 fail-fast.

## 编写完成后的最小检查

workflow YAML 推荐分两步校验:

1) workflow-level full validate(静态/编译期;递归校验 demands;不执行 workflow):

```bash
uv run scalim-cli yaml-dsl validate --type workflow <workflow.yaml>
```

2) schema-only 校验(结构/unknown-fields;仓库内建议显式指定 schema 路径):

```bash
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>
```

编辑器补全/hover 建议:

```bash
uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>
```
