## 1. snapshot 原子写入（temp+replace）

- [x] 1.1 在 `src/scalim/ob/presets/_internal/viz_output.py` 的 `_write_snapshot_if_needed()` 将 `open(\"w\") + json.dump` 改为 “写入临时文件 + `Path.replace` 原子替换” 语义（允许最后写入者覆盖，但不产生损坏 JSON）
- [x] 1.2 在 `src/scalim/workflow/execute.py` 的 `_report_workflow_viz_finished()` 将 workflow 结束时的 snapshot 重写同样改为 temp+replace（避免半写/截断）
- [x] 1.3 复用仓库现有临时文件 helper（例如 `create_temp_path(...)`）并保持 Python 3.6 兼容；不在 Phase 0 引入写锁或改变 `run_id` 目录结构

## 2. 回归测试（并发写不损坏 JSON）

- [x] 2.1 在 `tests/ob/test_viz_hook.py` 增加并发回归：并发触发 `_write_snapshot_if_needed()` 多次写同一路径，断言最终 `viz_snapshot.json` 始终可被 `json.loads` 解析
- [x] 2.2 为 workflow 级重写路径补充最小覆盖：执行一次 workflow viz bundle 流程后读取 `.../workflow/viz_snapshot.json` 并断言可解析且包含关键字段（避免回归到半写）

## 3. 规范同步与验收门禁

- [x] 3.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/flow-visualization/spec.md` 增加 “viz_snapshot.json MUST be written atomically (temp+replace)” 的要求
- [x] 3.2 运行 `just openspec-check` 校验 OpenSpec 工件
- [x] 3.3 运行 `just quick-qa-only-py`（或 `just qa`）作为最终验收
