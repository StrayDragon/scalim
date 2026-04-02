## Why

`run_workflow()` 作为 workflow orchestration 入口,目前只能用一组全局运行期参数驱动整张 DAG:

- `batch_size` 只能全局一份,无法表达“不同 demand 节点不同批大小”的真实生产需求
- `components` / `RunOverrides` / `guardrails` 等运行期能力同样缺少 per-run 的差异化入口

与此同时,按既有 runtime-policy boundary 的方向,这些 knobs 已从 demand YAML 主线迁出,使得“在 YAML 内为不同 demand 配不同 batch_size/ob/guardrail”不再是可持续方案。我们需要一个可扩展、可维护的 per-run runtime patch 入口,同时不破坏现有安全边界(allowlist 等)与 authoring 分层。

## What Changes

- 为 `scalim.dsl.by_yaml.run_workflow(...)` 增加一个新的可选参数: `run_patches_by_id`
  - 映射: `<workflow.runs[*].id>` -> `<per-run runtime patch>`
  - 仅作用于 demand runs(即 `workflow.runs[*]`),不作用于派生 write/append 等内部节点
- 引入一个 typed 的 per-run patch 模型(用于表达“继承/禁用/覆盖/追加”等语义),并在 workflow 执行时对每个 run 计算 effective options
- fail-fast 语义:
  - patch 里出现未知 run id MUST 报错并列出合法 ids
  - patch MUST 仅允许覆盖 runtime/perf/control-plane knobs,禁止覆盖 allowlist 等安全边界参数
- 文档与示例更新: 说明 per-run patch 的优先级/合并规则,以及与全局 `run_workflow(...)` 参数的关系

## Capabilities

### New Capabilities

- `workflow-run-patches`: `run_workflow()` MUST 支持按 `workflow.runs[*].id` 注入 per-run runtime patch,以表达 `batch_size`/`components`/`RunOverrides`/`guardrails` 等差异化运行策略,并保持安全边界不可被 per-run patch 覆盖。

### Modified Capabilities

<!-- none -->

## Impact

- 入口 API: `src/scalim/dsl/by_yaml/workflow_entrypoints.py` 的 `run_workflow(...)` 签名与语义扩展
- 运行期编译/执行: per-run effective options 的构造与 merge,涉及 workflow 执行与 demand 编译回调
- 类型与 DX: 需要提供稳定的 typed patch 数据结构与错误信息(unknown ids / forbidden fields)
- 测试: 增加覆盖用例(不同 run id 不同 batch_size; components replace/extend; forbidden security overrides fail-fast)

