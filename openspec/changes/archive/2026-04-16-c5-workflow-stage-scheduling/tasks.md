## 1. 公开运行期配置面（类型化预设）

- [x] 1.1 在 `src/scalim/dsl/yaml_dsl/workflow_types.py` 新增 `StageBarrierSchedulerOptions` preset，并通过 `__all__` 导出
- [x] 1.2 更新 `src/scalim/dsl/yaml_dsl/workflow_compile.py` 的运行期边界校验，使其接受 `pipeline` + `stage_barrier` scheduler preset
- [x] 1.3 补充/调整测试：确保 scheduler preset 可从稳定导入路径导入（`scalim.dsl.yaml_dsl.workflow_types`）

## 2. IR / 执行链路打通

- [x] 2.1 确定 `schedule_mode` 如何传递到运行时（扩展 `src/scalim/spec/ir/_workflow.py` 的 `WorkflowOptionsIr`），并端到端打通
- [x] 2.2 确保 scheduler 可拿到确定性的 stage 推导结果（复用共享辅助函数，避免与 viz 的层级推导分叉）
- [x] 2.3 验收：运行最小相关测试（例如 `pytest -q tests/yaml_dsl/test_yaml_dsl_workflow.py`），并确保 pipeline 模式无非预期行为变化

## 3. 实现 stage_barrier 调度

- [x] 3.1 基于 DAG 拓扑计算 `stage_by_node_id`（demand: `stage(node)=max(stage(dep))+1`；write nodes 折叠到 `input_demand`），并为诊断提供“环检测安全回退”
- [x] 3.2 在 `src/scalim/workflow/execute_controller.py` 阻止提交 `stage > current_stage` 的 ready 节点
- [x] 3.3 仅当 `current_stage` 的所有节点均为终态（done/failed/cancelled）后才推进 `current_stage`
- [x] 3.4 保持同一 stage 内调度确定性（沿用既有 `decl_order` 作为稳定裁决规则）
- [x] 3.5 保持失败语义（`all_fail` 取消未开始节点；`primary_only` 在 deps 允许时继续），并确保 cancelled 计入 stage 完成的“终态”

## 4. 可观测性 / 可视化（可解释性）

- [x] 4.1 对外暴露每个节点的 `stage` 与整次运行的 `schedule_mode`（通过 workflow viz snapshot 和 workflow node events）
- [x] 4.2 增加回归测试：验证 stage_barrier 运行时捕获到的 workflow events / viz snapshot 包含上述字段

## 5. 阶段屏障 vs pipeline 的行为测试

- [x] 5.1 增加 pipeline 模式测试：当 `max_concurrency>=2` 时，节点 `b`（depends_on `a`）可以在无关节点 `x`（同属 stage 0）仍运行时启动
- [x] 5.2 增加 stage_barrier 模式测试：节点 `b` 不得在 `a` 与 `x` 都到达终态前启动（与 5.1 同一 DAG）
- [x] 5.3 运行 `just qa`（SSOT 质量门禁）作为代码 + 测试的最终验收

## 6. 规格 / 文档治理与漂移门禁

- [x] 6.1 SSOT specs：实现后将变更期 specs 从 `openspec/changes/c5-workflow-stage-scheduling/specs/**` 同步到 `openspec/specs/**`（不得手改任何生成物）
- [x] 6.2 更新受影响的主规格（大概率包括 `openspec/specs/dsl-runtime-structure/spec.md`、`openspec/specs/workflow-ir/spec.md`、`openspec/specs/yaml-dsl-workflow/spec.md`），确保 requirements 覆盖新的 scheduler preset 与可观测性字段
- [x] 6.3 运行 `just openspec-check` 校验/清洗 OpenSpec 工件
- [x] 6.4 若 docs-site 页面或注入区块需要更新：编辑 `docs/doc/**` 下的 SSOT 并运行 `just gen-docs`（不得手改 `*.gen.*` 或 `BEGIN/END AUTOGEN` 块内内容）；验收：`just qa` 无漂移

## 7. 性能印象评估（`notebook`）

- [x] 7.1 新增 `marimo` 示例：`notebooks/marimo/workflow_stage_scheduling_perf/demo_main.py`，用可控 `sleep` 的 `workflow` 对拍 `pipeline` vs `stage_barrier`
- [x] 7.2 在 `notebook` 中输出最小报告：端到端耗时（`wall_s`）、估算最大并行度（`max_running_est`）、阶段间隔（`stage0->stage1_gap_s`）与节点时间线表
