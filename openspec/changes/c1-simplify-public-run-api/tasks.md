## 1. Specs & Public Contract Inventory

- [ ] 1.1 将本 change 的 spec（`specs/dsl-runtime-structure/spec.md`）补齐到最终 API：`DemandRunOptions`/`WorkflowRunOptions`、options-only `run_workflow`、capture 语义、patch policy（验收：spec 与 `design.md` 的 C1~C9 不冲突，且包含至少 1 个 fail-fast 场景/条目）。
- [ ] 1.2 列出将被新增/更新/移除的 public exports 清单，并与 `public-api-exports.md` 的 baseline 对齐（验收：design 的 “API Deltas” 与 exports 清单一致）。

## 2. Demand Public Contracts (C1, C4, C5)

- [ ] 2.1 引入 `DemandRunOptions`（正交分组 + `__post_init__` fail-fast），并替换所有 demand 入口使用旧 `RunOptions` 的路径（验收：`scalim.dsl.yaml_dsl.compile/run` 只接受 `DemandRunOptions`）。
- [ ] 2.2 引入 capture 策略（`CaptureNone`/`CaptureRows`）并定义与文件输出组合时的显式 tee 语义（验收：不通过“额外参数”隐式推导 tee；capture 默认关闭）。
- [ ] 2.3 引入 `DemandRunResult`：移除 `sink` 暴露，改为直接返回捕获结果（验收：`to_dataframe()` 在未开启 capture 时 fail-fast 指引开启 capture）。

## 3. Demand Runtime Wiring (C4, C5)

- [ ] 3.1 重构 `runtime.entrypoints.compile/run`：移除 public `sink` 输入路径，改为从 capture 策略装配 internal sink（验收：`run()` 在“无 outputs”时仍可 `CaptureRows` 得到 rows；在“有 outputs”时 capture 与写文件可同时成立且语义可预测）。
- [ ] 3.2 重构 `runtime.compiler.build_request`：不再依赖 options.sink，并保证输出组合（output_composition）与 capture 规则边界一致（验收：相关单测覆盖通过）。
- [ ] 3.3 为 capture/tee 关键路径补充/更新单测（验收：新增测试能区分 “file-only” vs “file+capture” vs “capture-only”，且没有隐式 tee 行为）。

## 4. Workflow Public Contracts (C2, C3, C6)

- [ ] 4.1 引入 `WorkflowRunOptions`：显式包含 `demand: DemandRunOptions`、`patches_by_run_id`、`runtime`、`path_aliases`、`workflow_components`（验收：workflow 入口不再需要额外 kwargs 来承载这些 knobs）。
- [ ] 4.2 引入 per-run patch 新类型（例如 `WorkflowNodePatch`）：只允许 patch 节点的 demand options 子集，并对禁止项（尤其是安全边界）fail-fast（验收：非法 patch 在合并阶段报错，错误信息包含 run_id + 字段路径）。
- [ ] 4.3 拆分 components 语义：workflow-level vs demand-level（验收：workflow instrumentation 仍可工作，且 demand 级 observers/hooks 仍能收到每个节点执行事件）。

## 5. Workflow Entrypoints Refactor (C2, C7)

- [ ] 5.1 将 public `scalim.dsl.yaml_dsl.run_workflow` 改为 options-only：`run_workflow(path, *, options: WorkflowRunOptions)`（验收：旧 kwargs 不再存在；调用方必须迁移）。
- [ ] 5.2 从 public surface 移除注入/测试 knobs（`run_ir_fn/compile_demand_yaml_fn`），并提供 internal/test-only 注入入口（验收：`scalim.dsl.yaml_dsl.run_workflow` 与 `scalim.dsl.yaml_dsl.workflow_entrypoints.run_workflow` 都不接受这些参数；tests 使用 `scalim.dsl.yaml_dsl._internal.workflow_injected_entrypoints.run_workflow_injected` 完成注入需求）。
- [ ] 5.3 workflow 节点运行链路改用 `DemandRunOptions`（含 capture）作为 SSOT（验收：workflow 节点的捕获/写文件语义与独立 demand 一致）。

## 6. Public API Exports & Governance (C8)

- [ ] 6.1 更新 `scalim.dsl.yaml_dsl` 的 public re-export（`__all__`）：新增 `DemandRunOptions/WorkflowRunOptions/...`，移除旧 `RunOptions`/注入 knobs/`sink` 暴露（验收：`public-api-exports.md` 的差异与 design 的变更点一致）。
- [ ] 6.2 重新生成 public API exports 审计快照（验收：运行 `python openspec/changes/c0-simplify-public-run-api/gen-public-api-exports.py` 后 `public-api-exports.md` 与源码 `__all__` 一致）。
  - SSOT：源码各模块 `__all__`
  - 生成入口：`python openspec/changes/c0-simplify-public-run-api/gen-public-api-exports.py`

## 7. Tests / Notebooks / Docs Migration (C8)

- [ ] 7.1 更新 `tests/yaml_dsl/**`：替换 `RunOptions`/旧 patch 类型/旧入口签名，补足 capture 语义与 fail-fast 的覆盖（验收：相关测试全绿）。
- [ ] 7.2 更新 `tests/workflow/**`：替换 options-only `run_workflow` 与新 patch 结构；覆盖 “禁止注入 knobs” 的断言（验收：相关测试全绿）。
- [ ] 7.3 更新 `notebooks/marimo/example_public_api_suite/**`：对齐新 public API（验收：示例套件运行通过，且导入路径仅使用 curated entrypoints）。
- [ ] 7.4 若 docs 站点存在示例/导入路径/签名描述，更新 SSOT 文档并用生成器刷新（验收：不手改 `.gen.` 文件；运行 `just gen-docs` 后无 drift）。
  - SSOT：`docs/doc/**` 非 `.gen.` 源文件与非注入区块内容
  - 生成入口：`just gen-docs`

## 8. Downstream Integration: `INTEGRATION_APP` (C9)

- [ ] 8.1 迁移下游 `INTEGRATION_APP`（目录 `INTEGRATION_DIR`）的 workflow 调用点到 `WorkflowRunOptions`（验收：原逻辑 `allowed_modules/init_vars/template_vars/batch_size/components` 可等价表达；默认值语义无意外漂移）。
- [ ] 8.2 迁移下游 `INTEGRATION_APP` 的 per-run diagnostics patch（验收：`DemandDiagnosticsOverride(validate_unique_field_names=False)` 仍可对指定 run 生效）。

## 9. QA / Drift Gates

- [ ] 9.1 OpenSpec 校验（验收：`just openspec-check` 通过；包含 sanitize + validate）。
- [ ] 9.2 Repo 质量门禁（验收：`just qa` 通过，包含 lint/tests + drift checks）。
- [ ] 9.3 最终核对：`public-api-exports.md` 已由生成器更新且与 `__all__` 一致（验收：无未生成的快照差异）。
