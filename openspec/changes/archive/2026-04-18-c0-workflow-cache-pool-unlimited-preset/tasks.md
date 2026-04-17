## 1. Public API（runtime presets）

- [x] 1.1 新增 `WorkflowCachePoolPreloadForeverUnlimited()` preset（代码: `src/scalim/dsl/yaml_dsl/workflow_types.py`）
- [x] 1.2 调整 `WorkflowCachePoolPreloadForeverShared`：`max_entries` 改为必填（移除默认 `16`），保留 `pin`（BREAKING；同步更新 `__all__` export）
- [x] 1.3 仓库内调用点迁移：将 `WorkflowCachePoolPreloadForeverShared()` 无参用法升级为显式 `max_entries=...` 或改用 unlimited preset（覆盖 tests / notebooks / docs）

## 2. Compile / IR / Runtime 语义

- [x] 2.1 扩展 `workflow_compile._build_workflow_cache_pool_ir_from_runtime`：支持 unlimited preset；并收紧 bounded preset 的校验（`max_entries` 必填且为正整数）
- [x] 2.2 调整 workflow cache pool IR/配置结构以表达 “budget disabled”（避免通过“大数”模拟无限；必要时更新 `src/scalim/spec/ir/_workflow.py`）
- [x] 2.3 更新 `src/scalim/execution/workflow_cache_pool.py`：当 budget disabled 时跳过 entries 数量预算检查；并确保 unlimited preset 语义等价 `release_policy=workflow_end`

## 3. 测试

- [x] 3.1 更新 `tests/yaml_dsl/test_yaml_workflow_compile_runtime_options_validation_coverage.py`：覆盖 unlimited preset；覆盖 bounded preset 的参数校验（含 breaking 行为）
- [x] 3.2 增加/更新 `tests/workflow/test_workflow_cache_pool.py`：验证 unlimited preset 不触发 over-budget，且 workflow_end 生命周期下不发生 refcount 释放
- [x] 3.3 更新 integration/demo 覆盖中对 cache_pool preset 的使用（如 `tests/integration/**`、`notebooks/marimo/**`）以消除隐式 `16`

## 4. 文档与规范

- [x] 4.1 更新用户文档示例（SSOT: `docs/doc/yaml-dsl/workflow.md`）：用 unlimited preset 替代 “大数=无限”；bounded 示例显式 `max_entries=...`
- [x] 4.2 规范同步验收：实现完成后运行 `just openspec-check`；在归档前将 delta spec 合并回主规范（`openspec/specs/workflow-cache-pool/spec.md`）

## 5. 质量门禁

- [x] 5.1 运行 `just check-only-py`（ruff/basedpyright/py36 兼容等）
- [x] 5.2 运行 `just test-gate`（含覆盖率门禁）
- [x] 5.3 运行 `just openspec-check`
