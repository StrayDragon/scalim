---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate workflow-run-patches --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "workflow-run-patches"
purpose: "允许 run_workflow 接受按 workflow run id 注入的 per-run runtime patches，支持覆盖 batch_size、parallel_mode、max_workers、demand_diagnostics、components 等参数，并确保安全边界参数不可覆盖。"
requirements[9]{req_id,title,statement}:
  r1,"run_workflow MUST accept per-run patches keyed by workflow run id","`run_workflow(...)` MUST 接受一个可选参数 `run_options_patches_by_run_id`,用于按 `workflow.runs[*].id` 注入 per-run runtime patches（其语义为对 base `RunOptions` 的字段级 patch）。 语义: - `run_options_patches_by_run_id` 的 key MUST 等于 `workflow.runs[*].id` - patch 仅作用于对应的 demand run,不作用于 workflow 内部派生节点(例如 write/append 等) - per-run patch 的优先级 MUST 高于 `run_workflow(..., options=RunOptions(...))` 的全局 runtime knobs"
  r2,"per-run patches MUST support parallel_mode and max_workers overrides","`run_workflow(..., run_options_patches_by_run_id=...)` 的 per-run patch MUST 支持覆盖并发相关 runtime knobs，使同一 workflow 内不同 run 可采用差异化策略： - `parallel_mode` MUST 支持 `seq|adaptive`（其余值 MUST fail-fast） - `max_workers` MUST 支持非负整数（`0=auto`）；负数或非整数 MUST fail-fast - 当 per-run patch 未显式提供上述字段时 MUST 继承全局 `RunOptions` 的对应值 - per-run patch 的该类覆盖 MUST 仍遵循既有安全边界：不得覆盖 `allowed_modules/allowed_functions/resolver_trusted_mode`"
  r3,"per-run demand diagnostics overrides MUST survive workflow compile preloading","当 `run_workflow(...)` 提供 `run_options_patches_by_run_id[*].demand_diagnostics` 时，系统 MUST 保证这些 per-run diagnostics override 不会被 workflow compile 阶段的 demand 预加载抢跑绕过。"
  r4,"per-run patches MUST NOT override security boundary parameters","per-run patches MUST 仅覆盖 runtime/perf/control-plane knobs,并 MUST NOT 允许覆盖以下安全边界参数: - `allowed_modules` - `allowed_functions` - `resolver_trusted_mode`"
  r5,"per-run patches MUST provide explicit inherit/disable/override semantics","per-run patch 模型 MUST 支持明确的三态语义: - `inherit`(继承): 使用 `run_workflow(..., options=RunOptions(...))` 的全局值 - `disable`(禁用): 当该字段支持禁用语义时,显式关闭该能力 - `override`(覆盖): 显式指定新值"
  r6,components patch MUST support replace and extend semantics,"per-run patch MUST 提供对 `components` 的显式策略选择,至少包含: - `replace`: 以 per-run 列表替换全局 components - `extend`: 在全局 components 基础上追加 per-run 列表"
  r7,"per-run overrides MUST compose with workflow resources overlay","当 workflow YAML 声明 `workflow.resources` 时,系统 MUST 将其视为低优先级 overlay,并与全局/per-run `RunOverrides.resources` 进行组合: - workflow resources overlay MUST 生效 - 当 per-run overrides 对同一资源字段提供覆盖时,per-run overrides MUST 具有更高优先级"
  r8,run_options_patches_by_run_id values MUST be typed patches (dict patches are not,"`run_options_patches_by_run_id` 的 values MUST 为系统提供的 typed patch 对象(例如 `WorkflowRunOptionsPatch`),并且 MUST NOT 接受 YAML-shaped 的 `dict` 作为 patch payload。"
  r9,unknown run ids in run_options_patches_by_run_id MUST fail fast with diagnostics,"当 `run_options_patches_by_run_id` 包含未知 run id 时,系统 MUST fail-fast: - 错误信息 MUST 指出未知 id - 错误信息 MUST 列出合法的 `workflow.runs[*].id` 集合(或其子集)"
scenarios[21]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,"per-run-batch-size-overrides-the-global-batch-size","","workflow 定义两个 runs: `A` 与 `B`",run `A` 的 effective `batch_size` MUST 为 `5000`
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,"per-run-parallel-mode-overrides-global-parallel-mode","全局 `RunOptions.parallel_mode=\"seq\"`","调用 `run_workflow(..., run_options_patches_by_run_id={\"A\": WorkflowRunOptionsPatch(parallel_mode=\"adaptive\")})`","run `A` 的 effective `parallel_mode` MUST 为 `\"adaptive\"`"
  r2,"per-run-max-workers-overrides-global-max-workers",全局 `RunOptions.max_workers=0`（auto）,"调用 `run_workflow(..., run_options_patches_by_run_id={\"A\": WorkflowRunOptionsPatch(max_workers=4)})`",run `A` 的 effective `max_workers` MUST 为 `4`
  r2,"invalid-per-run-parallelism-knobs-are-rejected","","用户提供 `WorkflowRunOptionsPatch(parallel_mode=\"thread\")` 或 `WorkflowRunOptionsPatch(max_workers=-1)`","`run_workflow` MUST fail-fast"
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"per-run-duplicate-name-suppression-applies-after-workflow-co",workflow 中 run `A` 引用的 demand YAML 含有 duplicate effective field display names,系统执行 `run_workflow(...)`,workflow compile 阶段 MUST 成功完成 demand 预加载
  r4,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r4,"forbidden-security-overrides-are-rejected","",用户尝试通过 `run_options_patches_by_run_id` 提供任何等价于覆盖上述安全边界的输入,"系统 MUST fail-fast 并指出 forbidden 字段名"
  r5,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r5,"batch-size-supports-inherit-disable-override","",全局 `batch_size=2000`,run `A` 的 effective `batch_size` MUST 为 `2000`
  r6,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r6,"components-can-be-extended-on-a-single-run","全局 `components=[C0]`","run `A` patch 指定 `components=ComponentsExtend([C1])`","run `A` 的 effective `components` MUST 等价于 `[C0, C1]` **Note:** `extend` MUST 保持顺序: 全局 components 在前,per-run components 追加在后;系统不应隐式去重。"
  r6,"components-can-be-disabled-on-a-single-run","全局 `components=[C0]`","run `A` patch 指定 `components=ComponentsReplace([])`",run `A` 的 effective `components` MUST 为空列表
  r7,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r7,"per-run-resources-override-wins-over-workflow-resources-over",workflow YAML 声明 `workflow.resources.files.detail_csv.path = P0`,执行 `run_workflow(...)`,"run `A` 的 effective 资源配置 MUST 使用 `P1` **Note:** 当 per-run patch 选择“禁用 overrides”(例如 `overrides=None`)时,workflow `resources` overlay 仍 MUST 生效;这不会被视为“恢复到无资源”的信号。 **Note:** `run_options_patches_by_run_id` 仅作用于 demand runs,不作用于 workflow 内部派生节点(例如 `__wf__write.*`). 因此,per-run patch 不是“为每个 demand 单独改 workflow-managed book export 路径”的入口;此类共享资源配置应通过 workflow YAML `workflow.resources` 与全局 `run_workflow(..., overrides=RunOverrides(resources=...))` 管理。"
  r8,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r8,"dict-patch-value-is-rejected","","用户调用 `run_workflow(..., run_options_patches_by_run_id={\"A\": {\"batch_size\": 5000}})`","`run_workflow` MUST fail-fast"
  r9,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r9,"unknown-run-id-is-rejected","","workflow 仅声明 run ids: `A`",`run_workflow` MUST 抛出配置错误
```
