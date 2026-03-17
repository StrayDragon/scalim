## Context

当前 workflow YAML 已有稳定的 authoring surface 与 `run_workflow()` 入口，但实现上仍是“直接执行器”：

- 以 `workflow.runs[*]` 为单位解析 demand 路径、编译 demand，并用线程池并发执行
- 缺少一个统一的、可扩展的中间表示（IR）来承载 DAG、ctx 传递、资源管理、写出节点、取消语义与确定性规则

随着需求扩展到 DAG/compile-on-ready、cache pool、共享输出容器、条件/选择器等节点类型，如果继续在 YAML 与 runner 上“叠字段/叠分支”，会迅速失控（语义分散、难以验证确定性/并发/内存边界、难以做静态校验）。

约束：

- workflow YAML 应逐步退化为“编译到 IR 的语法前端”，而不是驱动执行器分支
- 运行时必须保持 Python 3.6 兼容
- demand 侧 DSL 尽量不引入新的概念（尽可能复用 loader/params/init_vars）

## Goals / Non-Goals

**Goals:**

- 定义 `WorkflowIr` 图作为 workflow 的统一底座（nodes/deps/resources/options/artifacts）
- 明确 workflow 的“两阶段编译”边界：
  - 结构编译：workflow YAML → Workflow IR 图（静态校验 + 确定性顺序）
  - 物化编译：node 就绪时再编译/执行（compile-on-ready），为后续 ctx/$ctx 预留
- 定义确定性的 DAG 调度器与节点状态机（pending/ready/running/done/failed/cancelled）
- 定义 artifacts 可见性与生命周期契约（显式 deps + 显式 artifacts；禁止隐式全局共享）
- 为后续 node 类型扩展提供稳定接口（write_sheet/append_sheet/condition/selector 等）

**Non-Goals:**

- 不在本 change 内落地 ctx store 与 `$ctx`（由 `workflow-dag-context-passing` 负责）
- 不在本 change 内落地 cache pool（由 `workflow-cache-pool` 负责）
- 不在本 change 内落地共享资源与写出节点（由 `workflow-shared-output-containers` 负责）
- 不在本 change 内锁死 dataset/rows 工件复用的完整方案（仅保留扩展点）

## Decisions

### 1) 术语与稳定 id

- YAML 的 `runs[*]` 在编译后统一视为 **workflow nodes**（MVP 节点类型为 demand）
- `workflow_node_id` 来自 Workflow IR 的 node id；对 demand 节点等于 YAML `runs[*].id`

### 2) Workflow IR v0 形态

`WorkflowIr` 需要覆盖最小闭环：

- `nodes`: `WorkflowNodeIr` 列表/映射（id、type、decl_order、payload）
- `deps`: 显式边（`from_node_id -> to_node_id`）
- `resources`: workflow-scope 资源声明（由 `workflow-shared-output-containers` 填充细节）
- `options`: 并发上限、失败策略、确定性/调度策略、cache/resource 策略挂载点
- `artifacts`: workflow-scope 工件目录（由节点产生并通过 deps 显式可见）

### 3) 两阶段编译边界（SSOT）

- **结构编译**阶段只做：
  - 解析 YAML（或其它 frontend）为 `WorkflowIr`
  - 静态校验（id 唯一、deps 合法、无环、资源声明合法、artifact 引用不越界）
  - 生成确定性顺序（用于 ready tie-break 与结果对齐）
- **物化编译**阶段才做：
  - 渲染 node 输入（例如 init_vars/params template，可能依赖上游 ctx）
  - demand node：编译 demand YAML → Demand IR 并执行
  - write node：消费上游 artifacts 并写入资源（由 `workflow-shared-output-containers` 定义）

### 4) 调度器与确定性

- 调度采用拓扑就绪队列（Kahn 风格）：deps 满足 → ready
- 并发下 ready 节点的启动顺序 tie-break 必须稳定（优先按声明顺序/编译生成的 deterministic order）
- `outcomes` 对齐规则必须稳定（不得依赖并发完成顺序）

### 5) 状态机与失败/取消语义

节点状态机建议最小集合：pending/ready/running/done/failed/cancelled。

- 失败策略（例如 all_fail/primary_only）仍由 workflow options 控制
- DAG 场景下下游取消/失败传播的精确定义由 `workflow-dag-context-passing` 补齐，但本 change 需要预留 “cancelled reason” 的结构与确定性约束

### 6) Artifacts vs ctx vs resources 的边界

- `ctx`：仅承载 JSON-like 小对象（路径/计数/摘要），用于依赖边上传递与 init_vars 注入（`workflow-dag-context-passing`）
- `artifacts`：承载可引用的大对象/结构化产物（例如 output target、dataset/index），必须通过 deps 显式可见
- `resources`：承载 workflow-level 共享资源（workbook/csv），由资源管理器统一生命周期（`workflow-shared-output-containers`）

## Risks / Trade-offs

- [迁移成本] 旧 `run_workflow()` 与新 IR 调度器需要一段并存期 → 以“编译 YAML → IR → 执行”逐步替换内部实现，保证入口不变
- [确定性回归] 并发下 tie-break 容易被实现细节污染 → 在 IR 层固定 deterministic order，并增加对拍测试
- [接口膨胀] 过早把所有未来能力塞进 IR → v0 只保留必要字段 + 预留扩展点，细节由后续 changes 填充

## Migration Plan

1. 先引入 `WorkflowIr` 与编译器：workflow YAML 作为 frontend 编译到 IR（不改外部入口）
2. 引入调度器：用 IR 执行 demand nodes，保证行为与旧 `run_workflow()` 等价（尤其是 outcomes 顺序与 failure_policy）
3. 后续在 IR 上叠加：
   - DAG/ctx/compile-on-ready（workflow-dag-context-passing）
   - cache pool（workflow-cache-pool）
   - resources/write nodes（workflow-shared-output-containers）

## Follow-ups (explicitly out of scope)

- dataset/rows 工件复用与“内置 loader”入口不在本 change 内落地（由独立变更承载,例如 `workflow-artifact-datasets`）
- “用户显式取消整个 workflow”的外部接口不在本 change 内落地（本 change 仅提供调度器可支持 cancelled 状态的内部语义骨架）

## Docs / Generated Boundaries

- SSOT:
  - 规范：`openspec/specs/yaml-dsl-workflow/spec.md` 与 `openspec/specs/ir-structure/spec.md`（实现阶段通过 sync 将本 change 的 delta specs 合入）
  - 运行时实现：`src/scalim/**`（必须保持 Python 3.6 兼容）
- Generated（禁止手改）：
  - docs 中的 `.gen.` 与 injected blocks（通过 `just gen-docs` 生成）
- Drift / gates：
  - `just qa`
  - `just openspec-check`
