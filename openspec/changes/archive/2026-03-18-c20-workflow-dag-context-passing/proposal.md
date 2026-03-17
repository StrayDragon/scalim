## Why

当前 `workflow` YAML 只能将多个独立 demand 做“并发批量执行”(max_concurrency / failure_policy / 可选 cache_pool)，但无法表达 run 之间的依赖关系与数据/上下文传递。实际落地时，用户往往只能回到 Python glue（手工串行、读写中间文件、拼 init_vars），导致：

- 报表“多阶段流水线”难以用 YAML 直观表达与复用
- workflow 语义在 UI（scalim-viz）里也难以被可视化为可读的 DAG

## What Changes

说明: 本 change 预期落到 `workflow-ir-roadmap` 定义的 workflow IR/节点系统之上,而非在现有 `run_workflow()` 直接执行器上持续打补丁；workflow YAML 作为 authoring surface,编译到 IR 后以 node 为粒度调度执行。

- **New**: workflow runs 支持 DAG 编排（依赖关系）
  - 为 `workflow.runs[*]` 增加可选的依赖字段（例如 `depends_on: [run_id, ...]`）
  - 调度语义：只有当依赖 run 成功完成后，当前 run 才会进入可运行队列
  - 需要静态校验：run_id 引用合法、无环（cycle detection）、失败策略在 DAG 场景下的语义明确
  - 确保确定性：即使并发执行，workflow 返回结果仍与声明顺序稳定对齐

- **New**: workflow 级 `ctx`（上下文）传递（将上游 run 的产物用于下游 demand 输入）
  - workflow 在一次执行过程中维护一个 **workflow-level ctx store**（由 `workflow_exec_id` 标识一次调用；对外以 node 命名空间暴露）
  - ctx MUST 以 `workflow_node_id` 为命名空间（对 demand 节点等于 workflow YAML 的 `runs[*].id`），并且 MUST 仅允许访问依赖闭包内的上游 ctx（禁止绕开 deps 读取任意节点）
  - ctx 值 MUST 为 JSON-like 小对象（标量/小 list/dict），并设置大小护栏；严禁把 rows/dataset/大型输出直接塞进 ctx（大对象通过 artifacts/resources 路径解决）
  - 系统 MUST 为 demand 节点提供一组稳定的默认 ctx keys（用于减少 Python glue）：
    - `output_path`（若该 run 写出文件）
    - `total_rows`
    - `duration_secs`
  - 下游 node 允许将上游 ctx 注入为本次 demand 的 `init_vars`（从而复用 demand 侧现有 `{$init_var: ...}` 能力）

- **Non-breaking**: 不配置新字段时，保留现有 workflow 行为
  - 仍是“runs 列表 + 并发上限 + 失败策略 + 可选 cache_pool”

### Recommended Direction (MVP)

- 先把 workflow 的“编排单元”抽象为 **node-level DAG**（MVP 仅 demand 节点；YAML authoring surface 仍沿用 `runs[*]`），并把 ctx 传递限定为 JSON-like 的小对象。
- 让 `ctx → init_vars` 发生在 **物化编译阶段（compile-on-ready）**：当 node 就绪时渲染 `{$ctx: ...}` 得到 `init_vars`，再复用 demand 侧既有的 `{$init_var: ...}` 解析规则完成 Demand 编译与执行。
- 该 change 作为 `workflow-shared-output-containers` 的基础设施：后者的“写出节点/资源互斥/确定性写入”将复用同一套 DAG 调度与 ctx 存储。

### MVP Example (YAML)

```yaml
# yaml-language-server: $schema=../schema/workflow.gen.json

workflow:
  runs:
    - id: extract_users
      demand: ./extract_users.demand.yaml
    - id: report_users
      demand: ./report_users.demand.yaml
      depends_on: [extract_users]
      init_vars:
        users_csv_path: {$ctx: {node: extract_users, key: output_path}}
        users_total_rows: {$ctx: {node: extract_users, key: total_rows}}
  options:
    max_concurrency: 4
    failure_policy: all_fail
    ctx:
      max_value_bytes: 65536
      max_bytes: 1048576
```

## Capabilities

### New Capabilities
- （本提案优先作为对现有 workflow 能力的扩展，不新增独立 capability；若后续发现需要拆分范围再另起 change。）

### Modified Capabilities
- `yaml-dsl-workflow`: 在现有 workflow 基础上扩展 schema 与语义（新增字段可选且默认不影响旧配置；新增 DAG 与 ctx 传递能力）

## Impact

- YAML authoring surface：
  - workflow YAML 增加少量字段即可表达“多阶段流水线”（更接近用户直觉）
  - demand YAML 本身不需要为 ctx 传递新增入口（优先复用 `init_vars` 与 `{$init_var: ...}`）
- Runtime：
  - 需要在 `run_workflow` 调度层引入 DAG 调度与 ctx 生命周期管理（并发安全 + 确定性）
  - 需要增加静态校验（无环、依赖引用合法、失败策略在依赖场景下的规则）
- Tooling / Viz：
  - workflow 的 DAG 结构可直接喂给 scalim-viz 作为“编排层”视图（更利于排障与复用）
- Risk：
  - ctx 传递一旦允许“大数据集”，会引入内存与确定性风险；提案优先限定为“标量/小集合”，大数据集需单独评审与 guardrails

- Spec / schema / docs governance:
  - SSOT:
    - workflow schema DSL 与 hover 文案: `src/scalim/dsl/by_yaml/schema_dsl/**`
    - workflow runtime 行为: `src/scalim/dsl/by_yaml/runtime/**`
  - Generated（禁止手改）：
    - `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（通过 `just gen-yaml-dsl-schema` 生成）
    - docs 中的 `.gen.` 与 injected blocks（通过 `just gen-docs` 生成）
  - Gates:
    - `just qa`
    - `just openspec-check`
