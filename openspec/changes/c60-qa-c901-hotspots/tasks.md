## 1. `resources_workbook` 拆分（纯规则函数 + 原子落盘薄层）

- [ ] 1.1 在 `src/scalim/workflow/resources_workbook.py` 将 `_commit_workbook` 拆分为可命名边界：提取 workbook 构建/追加规则函数与 atomic save 薄层（保持调用顺序与行为不变）
- [ ] 1.2 为提取出的规则函数新增单测覆盖（不依赖全链路 workflow），至少覆盖：header/公式转义/字段映射等分支

## 2. `resources_sheetbook` 拆分（规则函数化）

- [ ] 2.1 在 `src/scalim/workflow/resources_sheetbook.py` 将 `_sheetbook_append_prepare` 与 `iter_sheetbook_sheet_rows` 的核心规则拆成函数：对齐策略（align_by）、不匹配策略（on_mismatch）、budget/顺序校验、visible/cutoff 过滤等
- [ ] 2.2 为规则决策函数增加测试矩阵：覆盖 `error|warn|skip` 组合与可见性过滤边界

## 3. `execute.py` 热点先抽纯数据整形（为 c90 铺路）

- [ ] 3.1 在 `src/scalim/workflow/execute.py` 对 capture/replay 中的“事件分类/分桶/归并”逻辑提取纯函数（输入 events，输出分类结构），并补单测覆盖
- [ ] 3.2 对 outcome 构造/异常分类等规则提取可测试函数（不改变调度/资源生命周期语义；更大规模 controller 重构由 c90 承接）

## 4. C901/noqa 治理与验收

- [ ] 4.1 尽量移除或缩小 `# noqa: C901` 放行范围；若短期仍需保留，确保每个放行点在 tasks 中可追踪且有拆分边界
- [ ] 4.2 为 `# noqa: C901` 建立轻量门禁：新增 `scripts/check-noqa-c901.py`（或等价）扫描 `# noqa: C901`，要求存在 `# pragma: allow-c901 ...` 且包含可追踪的拆分计划引用（例如 `plan: c60`）；在 `just qa` 中启用 `--check` fail-fast
- [ ] 4.3 跑 `just quick-qa-only-py`（含 module-size gate / workflow layering gate / tests suites gate）验证无回归

## 5. 规范同步与门禁

- [ ] 5.1 将本 change 的 delta 规范同步到 SSOT：更新 `openspec/specs/module-organization/spec.md` 增加 “C901 hotspots MUST be decomposed into testable boundaries” 的治理要求
- [ ] 5.2 运行 `just openspec-check` 校验 OpenSpec 工件
