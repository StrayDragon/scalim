## 1. 抽取唯一 SSOT util（方案 B）

- [ ] 1.1 新增内部 util 模块 `src/scalim/_internal/utils/exceptions.py`，实现 `clone_exception_for_reraise(exc)`（best-effort：`copy.copy` → `exc.__class__(*exc.args)` → fallback），并尽量 `with_traceback(None)` 清理 traceback
- [ ] 1.2 将 `src/scalim/workflow/resources_base.py` 与 `src/scalim/execution/preload_cache.py` 的重复实现替换为导入 util，并删除本地副本（避免漂移）
- [ ] 1.3 确认 util 模块不引入 workflow/execution 依赖，避免层级反转与循环导入

## 2. 测试口径收敛（单点覆盖 + 调用点回归）

- [ ] 2.1 迁移 `tests/workflow/test_workflow_resources_coverage.py` 中对 workflow 版本的测试，使其直接测试 util 的权威实现（并保留/补充 fallback 覆盖点）
- [ ] 2.2 为 preload_cache 路径补一条最小回归覆盖（确保其使用 util 且行为一致）

## 3. 规范同步与验收门禁

- [ ] 3.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/module-organization/spec.md` 增加 “cross-cutting helper MUST be single SSOT util” 的要求
- [ ] 3.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [ ] 3.3 运行 `just quick-qa-only-py`（或 `just qa`）作为最终验收
