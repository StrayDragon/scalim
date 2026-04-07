## Why

`src/scalim/dsl/by_yaml/runtime/entrypoints.py:run/compile` 已经完成了 “kwargs → `RunOptions` 单对象契约” 的收敛；但 `workflow` 的稳定入口
`src/scalim/dsl/by_yaml/workflow_entrypoints.py:run_workflow` 仍然暴露了一组与 `RunOptions` 高度重叠的 kwargs，并在函数内部重新组装
`RunOptions`。

这带来三个持续摩擦：

1. **签名漂移风险**：新增/调整任何 runtime knob 都需要同时修改 `RunOptions` 与 `run_workflow` 的函数签名与组装逻辑，容易漏改导致行为不一致。
2. **重复的规范化逻辑**：`run`/`compile` 与 `run_workflow` 对 `template_sandbox`/`key_normalization`/`max_workers` 等输入的归一化路径不一致，会引入难定位的差异。
3. **演进成本高**：对外入口的 kwargs 膨胀会把内部实现细节变成长期兼容负担；而我们已经选择以 “对象契约” 承载 knobs（见 `RunOptions` 的定位）。

因此需要把 `run_workflow` 也一步到位收敛到 `RunOptions`，让 `RunOptions` 成为 demand/workflow 两个入口共享的唯一 runtime knobs 承载对象。

## What Changes

- **BREAKING**：将 `run_workflow` 的公开签名从 “长 kwargs 列表” 收敛为 “单对象 options”：
  - `run_workflow(workflow_yaml_path, *, options: RunOptions, ...)`
  - 移除所有与 `RunOptions` 字段重复的 kwargs（例如 `batch_size/guardrails/loader_retry/template_vars/...`）。
- `workflow` 仍保留少量 *workflow-scope* 参数作为独立 kwargs（不属于 demand runtime knobs）：
  - `run_patches_by_id` / `workflow_resources_wait` / `workflow_output_staging` / `path_aliases`
  - 依赖注入 seam：`run_ir_fn` / `compile_demand_yaml_fn`
- 复用同一套 `RunOptions` 公开规范化逻辑，确保 demand 与 workflow 的入口行为一致（避免 drift）。
- 同步升级仓库内所有示例、规范与文档中对 `run_workflow` 的调用方式（不做兼容层/双入口）。

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dsl-runtime-structure`: `run_workflow` 也必须接受 `RunOptions` 作为唯一 runtime knobs 承载对象。
- `workflow-run-patches`: “全局 knobs” 的表达方式改为 `RunOptions`，per-run patch 语义不变但示例/场景需更新。
- `yaml-template-vars-precompile`: workflow 示例改为通过 `RunOptions.template_vars` 注入（与 demand 入口一致）。
- `yaml-dsl-cli-runner`: 更新规范中对 workflow Python 入口的示例签名（CLI 不执行 YAML 的定位不变）。

## Impact

- 受影响代码：
  - `src/scalim/dsl/by_yaml/workflow_entrypoints.py`: `run_workflow` 签名与 `RunOptions` 归一化/校验逻辑
  - `src/scalim/dsl/by_yaml/__init__.py`: facade 的 `run_workflow` 类型签名与导出面
  - 仓库内所有调用 `run_workflow` 的位置（tests/docs/notebooks/skills）
- 受影响规范：
  - 本 change 提供 delta specs；归档/同步后会更新 `openspec/specs/*/spec.md`。
- 文档治理：
  - 任何 `*.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块禁止手改；如需要更新文档注入块，必须修改 SSOT 并运行 `just gen-docs`。
