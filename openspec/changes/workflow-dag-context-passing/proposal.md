## Why

当前 `workflow` YAML 只能将多个独立 demand 做“并发批量执行”(max_concurrency / failure_policy / share_preload_cache)，但无法表达 run 之间的依赖关系与数据/上下文传递。实际落地时，用户往往只能回到 Python glue（手工串行、读写中间文件、拼 runtime_vars），导致：

- 报表“多阶段流水线”难以用 YAML 直观表达与复用
- workflow 语义在 UI（scalim-viz）里也难以被可视化为可读的 DAG

## What Changes

> 本 change 仅做提案，计划标记为 **DELAYED**；先确立方向与需求边界，再决定是否进入实现排期。
> 为通过 `openspec validate`/门禁,本 change 同时提供最小 delta spec 占位(不代表已进入实现阶段)。

- **New**: workflow runs 支持 DAG 编排（依赖关系）
  - 为 `workflow.runs[*]` 增加可选的依赖字段（例如 `depends_on: [run_id, ...]`）
  - 调度语义：只有当依赖 run 成功完成后，当前 run 才会进入可运行队列
  - 需要静态校验：run_id 引用合法、无环（cycle detection）、失败策略在 DAG 场景下的语义明确
  - 确保确定性：即使并发执行，workflow 返回结果仍与声明顺序稳定对齐

- **New**: workflow 级 `ctx`（上下文）传递（将上游 run 的产物用于下游 demand 输入）
  - workflow 在一次执行过程中维护一个“run 级上下文存储”（以 run_id 为命名空间）
  - 允许下游 run 将上游 ctx 注入为本次 demand 的 `runtime_vars`（从而复用 demand 侧现有 `{$runtime: ...}` 能力）
  - **最小化落地优先级建议**（避免过早引入“内存数据集图”复杂度）：
    1) 先支持“标量/小集合”的 ctx（例如 ids、路径、参数、统计摘要）
    2) 大体量数据集（rows/dataset）作为后续扩展候选，需 guardrails（内存上限、序列化边界、可对拍策略）

- **Non-breaking**: 不配置新字段时，保留现有 workflow 行为
  - 仍是“runs 列表 + 并发上限 + 失败策略 + 可选共享 preload_forever cache”

### Recommended Direction (MVP)

- 先把 workflow 的“编排单元”抽象为 **run-level DAG**（仅 demand runs），并把 ctx 传递限定为 JSON-like 的小对象。
- 让 `ctx → runtime_vars` 仍发生在 **编译期**（复用现有 `{$runtime: ...}` 解析规则），因此编译需要做到“按依赖就绪再编译并执行”。
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
      runtime_vars:
        users_csv_path:
          $ctx: extract_users.output_path
  options:
    max_concurrency: 4
    failure_policy: all_fail
    share_preload_cache: true
```

## Capabilities

### New Capabilities
- （本提案优先作为对现有 workflow 能力的扩展，不新增独立 capability；若后续发现需要拆分范围再另起 change。）

### Modified Capabilities
- `yaml-dsl-workflow`: 在现有 workflow 基础上扩展 schema 与语义（新增字段可选且默认不影响旧配置；新增 DAG 与 ctx 传递能力）

## Impact

- YAML authoring surface：
  - workflow YAML 增加少量字段即可表达“多阶段流水线”（更接近用户直觉）
  - demand YAML 本身不需要为 ctx 传递新增入口（优先复用 `runtime_vars` 与 `{$runtime: ...}`）
- Runtime：
  - 需要在 `run_workflow` 调度层引入 DAG 调度与 ctx 生命周期管理（并发安全 + 确定性）
  - 需要增加静态校验（无环、依赖引用合法、失败策略在依赖场景下的规则）
- Tooling / Viz：
  - workflow 的 DAG 结构可直接喂给 scalim-viz 作为“编排层”视图（更利于排障与复用）
- Risk：
  - ctx 传递一旦允许“大数据集”，会引入内存与确定性风险；提案优先限定为“标量/小集合”，大数据集需单独评审与 guardrails
