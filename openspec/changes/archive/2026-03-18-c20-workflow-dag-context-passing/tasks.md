## 1. DAG 语法与静态校验

- [x] 1.1 扩展 workflow YAML：支持 `runs[*].depends_on`
- [x] 1.2 实现静态校验：引用合法、无环（cycle detection）、错误摘要可读
- [x] 1.3 结果确定性：ready tie-break 与 outcomes 对齐规则稳定（对拍）

## 2. Ctx store（workflow-level）

- [x] 2.1 实现 ctx store：按 `workflow_node_id` 命名空间隔离、线程安全
- [x] 2.2 约束 ctx 值：JSON-like + 大小护栏；越界 fail-fast
- [x] 2.3 发布默认 ctx keys：`output_path` / `total_rows` / `duration_secs`

## 3. `$ctx` 指令与 init_vars 注入

- [x] 3.1 定义 `$ctx` 对象节点语法：`{$ctx: {node: <id>, key: <k>}}`
- [x] 3.2 在物化编译阶段渲染 `$ctx`，注入 demand 编译期 `init_vars`
- [x] 3.3 依赖可见性校验：禁止读取非依赖闭包的 ctx

## 4. compile-on-ready 调度与失败传播

- [x] 4.1 实现以 node 为粒度的 compile-on-ready：ready node 才物化编译并执行
- [x] 4.2 失败传播：依赖失败导致下游 cancelled（reason 可诊断）
- [x] 4.3 `failure_policy=all_fail` 时取消未开始 nodes（reason=policy_all_fail）

## 5. 与 cache/observability 的协作

- [x] 5.1 适配 cache pool：signature 在渲染后计算、冲突检测增量发生、refcount 随 DAG 推进递减
- [x] 5.2 适配 observability bridge：下游 cancelled 发出 `workflow_node_cancelled` 事件并复用归因字段

## 6. 测试与门禁

- [x] 6.1 测试：DAG 调度正确性、ctx 传递、cycle detection、取消传播
- [x] 6.2 更新 workflow schema SSOT（`src/scalim/dsl/by_yaml/schema_dsl/**`）并运行 `just gen-yaml-dsl-schema`（禁止手改 `src/scalim/dsl/by_yaml/schema/workflow.gen.json`）
- [x] 6.3 如涉及 docs/注入块,更新 SSOT 并运行 `just gen-docs`（禁止手改 `.gen.` 与 injected blocks）
- [x] 6.4 运行 `just qa`
- [x] 6.5 运行 `just openspec-check`
