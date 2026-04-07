## 1. 命名决策收敛（review gate）

- [x] 1.1 冻结 canonical public module：`scalim.dsl.yaml_dsl`（确认 `by_yaml` 是否完全移除还是 internal-only alias）
- [x] 1.2 冻结 workflow patch surface 命名：`WorkflowRunOptionsPatch` + `run_options_patches_by_run_id`（确认是否允许更短别名）
- [x] 1.3 冻结可选别名策略：是否提供 `run_demand/compile_demand` 作为非阻塞 alias（仅 facade 内赋值，不引入第二套入口文档）
- [x] 1.4 评审 “Components*” 是否也需要改名为 `ComponentsPatch*`（或保持现状）

## 2. 引入新的 facade 包（不要求先搬内部实现）

- [x] 2.1 新增 `src/scalim/dsl/yaml_dsl/__init__.py`（对齐 `src/scalim/dsl/by_yaml/__init__.py` 的受控 re-export 策略，必要时使用延迟 import 规避循环导入）
- [x] 2.2 新增 curated modules：
  - [x] 2.2.1 `src/scalim/dsl/yaml_dsl/workflow.py`
  - [x] 2.2.2 `src/scalim/dsl/yaml_dsl/workflow_types.py`
  - [x] 2.2.3 `src/scalim/dsl/yaml_dsl/workflow_paths.py`
  - [x] 2.2.4 `src/scalim/dsl/yaml_dsl/tools.py`
- [x] 2.3 更新 public API manifest 与导入 smoke gate（确保新模块纳入 curated 白名单）

## 3. 全仓库导入路径迁移（AST/IDE 重构优先）

- [x] 3.1 全局迁移 `scalim.dsl.by_yaml` → `scalim.dsl.yaml_dsl`（src/tests/docs/notebooks/artifacts/skills/openspec）
- [x] 3.2 更新 OpenSpec 主规范中写死的导入路径（本 change 的 delta specs 为 SSOT；同步到 `openspec/specs/**` 需在 apply 时执行）
- [x] 3.3 更新用户材料导入边界门禁：
  - [x] 3.3.1 `scripts/check-user-material-import-boundaries.py --check` 期望的 canonical 路径
  - [x] 3.3.2 `scripts/check-api-surface-governance.py --check` 与 public API suite 断言
- [x] 3.4 若涉及 docs 注入区块或生成页：修改 SSOT 并运行 `just gen-docs`（禁止手工编辑 `*.gen.*` 与 AUTOGEN 区块）

## 4. workflow per-run patch 命名与参数名收敛

- [x] 4.1 将 `WorkflowRunPatch` 重命名为 `WorkflowRunOptionsPatch`（稳定导入路径：`scalim.dsl.yaml_dsl.workflow_types`）
- [x] 4.2 将 `run_workflow(..., run_patches_by_id=...)` 参数收敛为 `run_workflow(..., run_options_patches_by_run_id=...)`
- [x] 4.3 更新所有示例/测试/文档中对 patch 的使用（确保读起来能直接映射到 `RunOptions` patch 语义）

## 5. 验收与门禁

- [x] 5.1 `just openspec-check`
- [x] 5.2 `just qa`（包含 py36 import smoke、examples gate、public surface governance gate）
