## 1. API 收敛（workflow 入口改为 options-object，breaking）

- [x] 1.1 将 `src/scalim/dsl/by_yaml/workflow_entrypoints.py:run_workflow` 收敛为 `run_workflow(..., options: RunOptions, ...)`（移除重复 kwargs）
- [x] 1.2 在 `src/scalim/dsl/by_yaml/__init__.py` 更新 facade 的 `run_workflow` 类型签名（保持动态 import 机制不变）
- [x] 1.3 为 `RunOptions` 增加/抽取公开归一化 SSOT（例如 `src/scalim/dsl/by_yaml/runtime/normalize.py`），并在 demand/workflow 两个入口复用
- [x] 1.4 workflow 入口对 `options.sink is not None` 做 fail-fast（给出明确迁移提示；本变更不引入 sink_factory）

## 2. 仓库内调用点与用户材料升级（不做兼容层）

- [x] 2.1 扫描并升级仓库内所有 `run_workflow(..., batch_size=..., template_vars=..., ...)` 调用点为 `RunOptions(...)`（tests/scripts/docs/notebooks/skills）
- [x] 2.2 同步更新 OpenSpec 能力规范中对 `run_workflow` 签名的示例（本 change 的 delta specs 已覆盖）

## 3. 文档治理与生成物（如涉及）

- [x] 3.1 若 docs/skills 中存在被注入区块或生成页引用旧签名：修改 SSOT 并运行 `just gen-docs`（禁止手工编辑 `*.gen.*` 与 AUTOGEN 区块）
- [x] 3.2 运行并通过漂移门禁（例如 `just qa` 的 doc drift / spec drift checks）

## 4. 测试与验收

- [x] 4.1 增加/更新 smoke 覆盖：`run_workflow(..., options=RunOptions(...))` 成功路径（最小 workflow fixture）
- [x] 4.2 增加回归覆盖：per-run patch 仍可覆盖 base `RunOptions.batch_size` 等 knobs（`run_patches_by_id` 优先级）
- [x] 4.3 运行质量门禁：
  - [x] 4.3.1 `just openspec-check`
  - [x] 4.3.2 `just qa`
