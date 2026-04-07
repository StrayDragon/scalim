## ADDED Requirements

### Requirement: workflow entrypoint MUST accept a single `RunOptions` object
系统 MUST 将 workflow 的 Python 运行入口 `run_workflow` 收敛为 options-object 形态，以确保 runtime knobs 的唯一承载对象为 `RunOptions`
（避免再次扩大 `run_workflow` 的公开函数签名）。

该入口 MUST 形如：

- `run_workflow(workflow_yaml_path, *, options: RunOptions, ...) -> WorkflowResult`

其中：

- 所有 demand 运行期 knobs MUST 通过 `RunOptions` 提供（例如 allowlist、模板、并行、重试、护栏、overrides、batch_size、diagnostics）。
- workflow-scope 的编排参数 MAY 继续以独立 kwargs 形式存在（例如 `run_patches_by_id` / `workflow_resources_wait` / `path_aliases`）。

#### Scenario: options-object drives workflow runs
- **GIVEN** 调用方构造 `RunOptions(allowed_modules=..., batch_size=..., template_vars=...)`
- **WHEN** 调用方执行 `run_workflow("path/to/workflow.yaml", options=options)`
- **THEN** 系统 MUST 使用该 `RunOptions` 作为每个 demand run 的 base options
- **AND** 后续 per-run patches(若提供) MUST 在该 base options 上应用
