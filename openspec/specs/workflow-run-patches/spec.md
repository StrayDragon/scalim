# workflow-run-patches Specification

## Purpose
允许 run_workflow 接受按 workflow run id 注入的 per-run runtime patches，支持覆盖 batch_size、parallel_mode、max_workers、demand_diagnostics、components 等参数，并确保安全边界参数不可覆盖。

## Related Concepts
- run_workflow
- run_options_patches_by_run_id
- WorkflowRunOptionsPatch（typed）
- per-run diagnostics overrides
- components patch（replace/extend）
- workflow resources overlay
- 三态语义（inherit/disable/override）
- 安全边界参数（allowed_modules/allowed_functions/resolver_trusted_mode）
## Requirements
### Requirement: run_workflow MUST accept per-run patches keyed by workflow run id

`run_workflow(...)` MUST 接受一个可选参数 `run_options_patches_by_run_id`,用于按 `workflow.runs[*].id` 注入 per-run runtime patches（其语义为对 base `RunOptions` 的字段级 patch）。

语义:

- `run_options_patches_by_run_id` 的 key MUST 等于 `workflow.runs[*].id`
- patch 仅作用于对应的 demand run,不作用于 workflow 内部派生节点(例如 write/append 等)
- per-run patch 的优先级 MUST 高于 `run_workflow(..., options=RunOptions(...))` 的全局 runtime knobs

#### Scenario: per-run batch_size overrides the global batch_size

- **WHEN** workflow 定义两个 runs: `A` 与 `B`
- **AND** 调用 `run_workflow(..., options=RunOptions(..., batch_size=2000), run_options_patches_by_run_id={"A": WorkflowRunOptionsPatch(batch_size=5000)})`
- **THEN** run `A` 的 effective `batch_size` MUST 为 `5000`
- **AND** run `B` 的 effective `batch_size` MUST 为 `2000`

### Requirement: per-run patches MUST support parallel_mode and max_workers overrides
`run_workflow(..., run_options_patches_by_run_id=...)` 的 per-run patch MUST 支持覆盖并发相关 runtime knobs，使同一 workflow 内不同 run 可采用差异化策略：

- `parallel_mode` MUST 支持 `seq|adaptive`（其余值 MUST fail-fast）
- `max_workers` MUST 支持非负整数（`0=auto`）；负数或非整数 MUST fail-fast
- 当 per-run patch 未显式提供上述字段时 MUST 继承全局 `RunOptions` 的对应值
- per-run patch 的该类覆盖 MUST 仍遵循既有安全边界：不得覆盖 `allowed_modules/allowed_functions/resolver_trusted_mode`

#### Scenario: per-run parallel_mode overrides global parallel_mode
- **GIVEN** 全局 `RunOptions.parallel_mode="seq"`
- **WHEN** 调用 `run_workflow(..., run_options_patches_by_run_id={"A": WorkflowRunOptionsPatch(parallel_mode="adaptive")})`
- **THEN** run `A` 的 effective `parallel_mode` MUST 为 `"adaptive"`

#### Scenario: per-run max_workers overrides global max_workers
- **GIVEN** 全局 `RunOptions.max_workers=0`（auto）
- **WHEN** 调用 `run_workflow(..., run_options_patches_by_run_id={"A": WorkflowRunOptionsPatch(max_workers=4)})`
- **THEN** run `A` 的 effective `max_workers` MUST 为 `4`

#### Scenario: invalid per-run parallelism knobs are rejected
- **WHEN** 用户提供 `WorkflowRunOptionsPatch(parallel_mode="thread")` 或 `WorkflowRunOptionsPatch(max_workers=-1)`
- **THEN** `run_workflow` MUST fail-fast
- **AND** 错误信息 MUST 指出合法值范围（`parallel_mode=seq|adaptive`, `max_workers>=0`）

### Requirement: per-run demand diagnostics overrides MUST survive workflow compile preloading

当 `run_workflow(...)` 提供 `run_options_patches_by_run_id[*].demand_diagnostics` 时，系统 MUST 保证这些 per-run diagnostics override 不会被 workflow compile 阶段的 demand 预加载抢跑绕过。

#### Scenario: per-run duplicate-name suppression applies after workflow compile
- **GIVEN** workflow 中 run `A` 引用的 demand YAML 含有 duplicate effective field display names
- **AND** 调用方传入 `run_options_patches_by_run_id={"A": WorkflowRunOptionsPatch(demand_diagnostics=DemandDiagnosticsOverride(validate_unique_field_names=False))}`
- **WHEN** 系统执行 `run_workflow(...)`
- **THEN** workflow compile 阶段 MUST 成功完成 demand 预加载
- **AND** run `A` 的后续 demand compile MUST 使用该 per-run override
- **AND** 系统 MUST NOT 因阶段 1 的默认 duplicate-name 校验提前失败

### Requirement: per-run patches MUST NOT override security boundary parameters

per-run patches MUST 仅覆盖 runtime/perf/control-plane knobs,并 MUST NOT 允许覆盖以下安全边界参数:

- `allowed_modules`
- `allowed_functions`
- `resolver_trusted_mode`

#### Scenario: forbidden security overrides are rejected

- **WHEN** 用户尝试通过 `run_options_patches_by_run_id` 提供任何等价于覆盖上述安全边界的输入
- **THEN** 系统 MUST fail-fast 并指出 forbidden 字段名

### Requirement: per-run patches MUST provide explicit inherit/disable/override semantics

per-run patch 模型 MUST 支持明确的三态语义:

- `inherit`(继承): 使用 `run_workflow(..., options=RunOptions(...))` 的全局值
- `disable`(禁用): 当该字段支持禁用语义时,显式关闭该能力
- `override`(覆盖): 显式指定新值

#### Scenario: batch_size supports inherit / disable / override

- **WHEN** 全局 `batch_size=2000`
- **AND** run `A` patch 省略 `batch_size` 字段(继承)
- **THEN** run `A` 的 effective `batch_size` MUST 为 `2000`
- **WHEN** run `B` patch 指定 `batch_size=None`(禁用分批)
- **THEN** run `B` 的 effective `batch_size` MUST 为 `null`(禁用分批)
- **WHEN** run `C` patch 指定 `batch_size=5000`(覆盖)
- **THEN** run `C` 的 effective `batch_size` MUST 为 `5000`

### Requirement: components patch MUST support replace and extend semantics

per-run patch MUST 提供对 `components` 的显式策略选择,至少包含:

- `replace`: 以 per-run 列表替换全局 components
- `extend`: 在全局 components 基础上追加 per-run 列表

#### Scenario: components can be extended on a single run

- **GIVEN** 全局 `components=[C0]`
- **WHEN** run `A` patch 指定 `components=ComponentsExtend([C1])`
- **THEN** run `A` 的 effective `components` MUST 等价于 `[C0, C1]`

**Note:** `extend` MUST 保持顺序: 全局 components 在前,per-run components 追加在后;系统不应隐式去重。

#### Scenario: components can be disabled on a single run

- **GIVEN** 全局 `components=[C0]`
- **WHEN** run `A` patch 指定 `components=ComponentsReplace([])`
- **THEN** run `A` 的 effective `components` MUST 为空列表

### Requirement: per-run overrides MUST compose with workflow resources overlay

当 workflow YAML 声明 `workflow.resources` 时,系统 MUST 将其视为低优先级 overlay,并与全局/per-run `RunOverrides.resources` 进行组合:

- workflow resources overlay MUST 生效
- 当 per-run overrides 对同一资源字段提供覆盖时,per-run overrides MUST 具有更高优先级

#### Scenario: per-run resources override wins over workflow resources overlay

- **GIVEN** workflow YAML 声明 `workflow.resources.files.detail_csv.path = P0`
- **AND** run `A` patch 提供 `RunOverrides.resources.files.detail_csv.path = P1`
- **WHEN** 执行 `run_workflow(...)`
- **THEN** run `A` 的 effective 资源配置 MUST 使用 `P1`

**Note:** 当 per-run patch 选择“禁用 overrides”(例如 `overrides=None`)时,workflow `resources` overlay 仍 MUST 生效;这不会被视为“恢复到无资源”的信号。

**Note:** `run_options_patches_by_run_id` 仅作用于 demand runs,不作用于 workflow 内部派生节点(例如 `__wf__write.*`). 因此,per-run patch 不是“为每个 demand 单独改 workflow-managed book export 路径”的入口;此类共享资源配置应通过 workflow YAML `workflow.resources` 与全局 `run_workflow(..., overrides=RunOverrides(resources=...))` 管理。

### Requirement: run_options_patches_by_run_id values MUST be typed patches (dict patches are not supported)

`run_options_patches_by_run_id` 的 values MUST 为系统提供的 typed patch 对象(例如 `WorkflowRunOptionsPatch`),并且 MUST NOT 接受 YAML-shaped 的 `dict` 作为 patch payload。

#### Scenario: dict patch value is rejected

- **WHEN** 用户调用 `run_workflow(..., run_options_patches_by_run_id={"A": {"batch_size": 5000}})`
- **THEN** `run_workflow` MUST fail-fast
- **AND** 错误信息 MUST 提示迁移到 typed patch 对象

### Requirement: unknown run ids in run_options_patches_by_run_id MUST fail fast with diagnostics

当 `run_options_patches_by_run_id` 包含未知 run id 时,系统 MUST fail-fast:

- 错误信息 MUST 指出未知 id
- 错误信息 MUST 列出合法的 `workflow.runs[*].id` 集合(或其子集)

#### Scenario: unknown run id is rejected

- **WHEN** workflow 仅声明 run ids: `A`
- **AND** 调用 `run_workflow(..., run_options_patches_by_run_id={"B": WorkflowRunOptionsPatch()})`
- **THEN** `run_workflow` MUST 抛出配置错误
- **AND** 错误信息 MUST 同时包含 `"B"` 与 `"A"`
