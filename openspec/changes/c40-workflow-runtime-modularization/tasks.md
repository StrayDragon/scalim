## 1. Baseline Guardrails（先固化入口与关键不变量）

- [ ] 1.1 新增稳定入口 smoke test：`run_workflow` 仍可从既有 import path 导入并执行最小 workflow（对应 `workflow-runtime-module-organization`）
- [ ] 1.2 新增单测：writes 顺序确定性（按 runs 顺序 + writes 顺序），避免重构引入非确定性
- [ ] 1.3 新增单测：failure_policy 的关键语义（all_fail / primary_only）在最小 case 下不变

## 2. `run_workflow` phase 拆分（先在同文件拆小）

- [ ] 2.1 在 `workflow_entrypoints.py` 内先把 `run_workflow` 拆成 4 个 phase 函数（load/compile/execute/finalize），并确保行为不变
- [ ] 2.2 将复杂度豁免逐步收敛到 glue 层（尽量让 phase 无需豁免）

## 3. 内部模块化迁移（保持稳定入口不变）

- [ ] 3.1 新增内部模块骨架：`workflow_load.py` / `workflow_compile.py` / `workflow_execute.py` / `workflow_report.py`
- [ ] 3.2 逐步把 phase 实现从 `workflow_entrypoints.py` 迁移到上述模块，并保持 `workflow_entrypoints.py` 作为 thin wrapper
- [ ] 3.3 增加/更新测试覆盖迁移后的模块边界（至少覆盖 load/compile/execute 的最小 fixture）

## 4. workflow resources 拆分

- [ ] 4.1 将 `workflow_resources.py` 拆为 base + resource-type 子模块（sheetbook/workbook/csv），并保持对外导入不变（必要时在旧文件 re-export）
- [ ] 4.2 增加资源生命周期相关单测（create/write/commit/discard 的关键事件/顺序不变量）

## 5. workflow config / paths 拆分 + CLI glue 收敛

- [ ] 5.1 将 `workflow.py` 拆分为 config/paths/types（保持原有对外函数可用：必要时在旧文件 re-export）
- [ ] 5.2 更新 `src/scalim/cli/yaml_dsl.py` 使用新的 config/paths API（减少 CLI 与 runtime 的耦合）

## 6. Final Gates

- [ ] 6.1 运行 `just openspec-check` 确保 OpenSpec 工件通过校验
- [ ] 6.2 运行 `just qa`（或最小子集）确保无 lint/test 回归
