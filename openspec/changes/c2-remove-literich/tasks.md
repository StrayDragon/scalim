## 1. 约束固化（console 输出契约）

- [ ] 1.1 在 `src/scalim/ob/` 内引入最小的 internal helper（例如 `ob/_internal/console_report.py`），封装 prefix/kind/`k=v` 逐行输出拼接（internal 模块显式封堵导出面，遵循 public-surface 治理）。
- [ ] 1.2 为 `relations/performance` 的 console 输出定义并实现最小稳定 kind 与 key 集合（见本 change specs），并在测试中仅断言“关键信息存在”（不锁定对齐/边框）。

## 2. 移除 `scalim.vendor.literich`（BREAKING，一次性升级）

- [ ] 2.1 删除 `src/scalim/vendor/literich/` 并移除所有运行时引用点（`src/scalim/ob/**`）。
- [ ] 2.2 更新 `src/scalim/vendor/README.md`：移除 `literich` 小节或标记为已移除（该文件为 SSOT，可直接修改）。
- [ ] 2.3 删除 `tests/test_literich.py`，新增覆盖新的 console 输出格式的最小回归测试（pytest + capsys）。

## 3. 逐模块替换 console 输出（不改指标口径）

- [ ] 3.1 `src/scalim/ob/presets/relations.py`：将 `console` 报告改为 `summary` + 多行 `per_source` + 有界 samples 的逐行 `k=v` 输出。
- [ ] 3.2 `src/scalim/ob/presets/performance_presentation.py`：将 `console` 报告改为 `summary` +（可选）`stage`/`loader` 逐行输出；`json/csv/none` 行为保持不变。
- [ ] 3.3 `src/scalim/ob/presets/logs.py`（PrettyLoggingObserver）：将 panel/table 输出改为 prefix + 逐行文本（并保持 `pytest capsys` 可捕获 stdout）。
- [ ] 3.4 `src/scalim/ob/presets/execution_trace.py`：将 `print_summary()` 输出改为逐行文本（summary + 可选 last batch details），不使用表格渲染器。
- [ ] 3.5 `src/scalim/ob/presets/memory.py`：将内存优化统计输出改为逐行 `k=v`，并保持字段列表输出有界/可读。
- [ ] 3.6 `src/scalim/ob/metrics.py`：将 `MetricsCollector.print_summary()` 表格输出改为逐行 `k=v`，保持信息等价。

## 4. 治理与验收

- [ ] 4.1 更新 `scripts/check-user-material-import-boundaries.py`：增加对 `scalim.vendor.literich` 的硬禁止 token（仅该模块，不泛化到整个 `scalim.vendor.*`）。
- [ ] 4.2 自查 docs/skills/notebooks 不再引用 `scalim.vendor.literich`；如需改动生成物/注入块，修改 SSOT 并运行 `just gen-docs`（禁止直接编辑 `.gen.` 或 `AUTOGEN` 区块内部）。
- [ ] 4.3 运行 `just qa` 与 `just openspec-check` 验收（lint/tests + drift checks + OpenSpec sanitize/validate）。
