## Context

当前 workflow YAML 只能把多个独立 demand 做“并发批量执行”（max_concurrency / failure_policy / 可选 cache_pool），但无法表达：

- run/node 之间的显式依赖（多阶段流水线）
- 在依赖边上向下游传递小体量上下文（例如上游输出路径、统计摘要、参数映射）

落地时用户只能回到 Python glue：手工串行、读写中间文件、拼 init_vars，导致 YAML 无法成为可复用的编排入口，也使得 workflow 在可视化（scalim-viz）里难以表达为可读 DAG。

本 change 建立在 `workflow-ir-roadmap` 的“结构编译 + 物化编译（compile-on-ready）”边界之上：先把 workflow YAML 编译为 DAG，再在节点就绪时渲染 ctx 并编译/执行该节点。

## Goals / Non-Goals

**Goals:**

- 为 workflow YAML 增加 `depends_on` 语义，支持 DAG 编排与静态校验（合法引用、无环）
- 引入 workflow-level ctx store（JSON-like 小对象，按 node 命名空间隔离）
- 定义 `$ctx` 指令语法，用于将上游 ctx 注入下游 `init_vars`
- 实现 compile-on-ready：节点 deps 满足且 ctx 可得时才物化编译 demand（避免启动前全量编译假设）
- 明确失败传播/取消语义（依赖失败导致下游 cancelled，原因可诊断且可观测）

**Non-Goals:**

- 不支持把 rows/dataset/大型输出直接塞进 ctx（大对象通过 artifacts/resources 解决）
- 不引入新的 demand DSL 概念（优先复用 `init_vars` 与 `{$init_var: ...}`）
- 不实现共享输出资源与写出节点（由 `workflow-shared-output-containers` 负责）

## Decisions

### 1) DAG：`depends_on` 是唯一依赖声明入口（v0）

- `workflow.runs[*].depends_on` 可选，类型为 run id 列表
- 结构编译阶段静态校验：引用必须存在、图无环、错误需包含可读摘要（例如 cycle 路径）

### 2) Workflow ctx v0（最终形态 / SSOT）

ctx 是 **workflow-level context store**，但必须按 node 命名空间隔离：

- key space：`ctx[workflow_node_id][key] -> JSONLike`
- `workflow_node_id` 对 demand 节点等于 YAML 的 `runs[*].id`；未来非-demand 节点来自 Workflow IR 的 node id
- 类型与大小护栏：
  - 值 MUST 为 JSON-like（null/bool/int/float/str + 小 list/dict）
  - MUST 设置大小上限（单 key 与总量）；超限 fail-fast
  - 禁止 DataFrame/rows/dataset 等大型对象进入 ctx
- 依赖可见性：
  - 下游 node 只能读取其依赖闭包内 nodes 的 ctx
  - 读取越界 MUST fail-fast（避免隐式全局共享状态）
- 并发安全：ctx store MUST 线程安全

**默认 ctx keys（demand node completion 时发布）：**

- `output_path`（若存在文件输出）
- `total_rows`
- `duration_secs`

### 3) `$ctx` 指令语法：对象节点（避免字符串插值）

为避免转义/误伤/IDE 提示困难，`$ctx` 与 `$keys/$rows/$init_var` 一样采用对象节点：

```yaml
init_vars:
  users_csv_path: {$ctx: {node: extract_users, key: output_path}}
```

规则：

- `$ctx` MUST 作为指令节点被解析（不是字符串替换）
- `$ctx` 在物化编译阶段渲染为字面值，再注入 demand 编译期 `init_vars`

### 4) compile-on-ready：以 node 为粒度

物化编译/调度以 node 为粒度（简单明确，批量优化留后续）：

1. 结构编译得到 DAG + deterministic order
2. ready queue：deps 满足的 nodes 进入就绪队列
3. 物化编译：对 ready node 渲染 `$ctx` → 得到 `init_vars` → 编译 demand → 执行
4. node 完成后发布 ctx summary，并触发下游 nodes 的就绪推进

### 5) 失败传播与取消语义

- 若 prerequisite 失败，下游 nodes MUST NOT 执行，且 MUST 标记为 cancelled（reason=dependency_failed 等）
- `failure_policy=all_fail` 时，系统 MUST 取消所有未开始 nodes，reason MUST 为 `policy_all_fail`
- 取消/失败需要与 `workflow-observability-bridge` 的 workflow-level 事件契约对齐（`workflow_node_cancelled`）

### 6) 与 cache pool 的协作

cache pool（workflow-cache-pool）在 compile-on-ready 下必须满足：

- signature 以“已渲染 params”为 SSOT（渲染发生在物化编译阶段）
- 冲突检测增量发生（不能再强依赖启动前全量预检）

## Risks / Trade-offs

- [ctx 失控变成隐式共享状态] → 强制 deps 可见性 + JSON-like/大小护栏 + fail-fast
- [编译时机变化影响错误诊断] → 将“为何此时才报错”的原因写入错误摘要（例如 ctx 未就绪/依赖失败）
- [并发 + ctx 读写竞态] → ctx store 线程安全 + 只允许从已完成 deps 读取

## Migration Plan

- 不配置 `depends_on` / 不使用 `$ctx` 时：行为应与现有 workflow 语义等价（只是内部调度器实现可替换）
- 增量引入：先支持最小 DAG + ctx 注入，再扩展到 write nodes/resources（workflow-shared-output-containers）

## Final Decisions (no open questions)

- ctx 护栏配置入口固定为 `workflow.options.ctx`:
  - 默认值：`max_value_bytes=65536`、`max_bytes=1048576`
  - 超限行为：fail-fast（错误必须包含 key/path 与当前/上限摘要）
- 默认 ctx keys 不做版本化:
  - v0 SSOT 仅包含 `output_path` / `total_rows` / `duration_secs`
  - 后续若新增 keys,视为向后兼容扩展,且不得改变既有 keys 的语义
- `$ctx` 不支持 `node: self`（避免引入“读未完成值”的歧义）；如需复用本节点参数,应使用 `{$init_var: ...}` 或在 demand 内部表达

## Docs / Generated Boundaries

- SSOT:
  - workflow schema DSL: `src/scalim/dsl/by_yaml/schema_dsl/**`
  - workflow runtime: `src/scalim/dsl/by_yaml/runtime/**`
- Generated（禁止手改）：
  - `src/scalim/dsl/by_yaml/schema/workflow.gen.json`（通过 `just gen-yaml-dsl-schema` 生成）
  - docs 中的 `.gen.` 与 injected blocks（通过 `just gen-docs` 生成）
- Drift / gates：
  - `just qa`
  - `just openspec-check`
