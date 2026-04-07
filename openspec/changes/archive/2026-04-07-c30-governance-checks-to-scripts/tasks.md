## 1. 新增静态门禁脚本（scripts/check-*.py）

- [x] 1.1 新增 `scripts/check-import-graph.py`：检查 `src/scalim/**`（排除 `vendor`）导入图无环 + 禁止函数内导入，`--check` 失败输出包含最小导入环/定位信息
- [x] 1.2 新增 `scripts/check-workflow-layering.py`：检查 `src/scalim/workflow/**` 不得 import/dynamic import `scalim.dsl.*`；检查 `src/scalim/dsl/by_yaml/runtime/**` 下不得出现 `workflow_*.py`
- [x] 1.3 新增 `scripts/check-tests-domain-suites.py`：检查 `tests/` 领域目录存在、禁止根目录 `tests/test_*.py`、禁止 `test_*_additional.py`、以及 `tests.*` 字符串引用必须落在 `tests/fixtures/**`
- [x] 1.4 新增 `scripts/check-monkeypatch-policy.py`：扫描 `tests/**.py`，禁止 `monkeypatch.setattr(..., \”_private\”, ...)` 与 patch `builtins.__import__`/`importlib.import_module`
- [x] 1.5 统一脚本 CLI 约定：至少 `--root`（默认 `.`）与 `--check`；违规输出包含文件路径与行号；返回码遵循 0=通过,1=失败

## 2. 将门禁接入 `just qa` fail-fast 阶段

- [x] 2.1 在 `justfile` 增加 recipe：`check-import-graph`、`check-workflow-layering`、`check-tests-domain-suites`、`check-monkeypatch-policy`（使用 `uv run python scripts/check-*.py --check`）
- [x] 2.2 将上述 recipe 加入 `quick-check-only-py` 且排序在 `test` 之前（保证 pytest 之前 fail-fast）

## 3. 迁移/替换 `tests/governance/` 中的静态 pytest 门禁

- [x] 3.1 删除（或改造为”脚本单测”）`tests/governance/test_import_graph_no_cycles_and_no_local_imports.py`，新增 `tests/governance/test_check_import_graph.py` 覆盖脚本行为（tmp repo、退出码、输出可定位）
- [x] 3.2 删除（或改造为”脚本单测”）`tests/governance/test_workflow_layering_gates.py`，新增 `tests/governance/test_check_workflow_layering.py`
- [x] 3.3 删除（或改造为”脚本单测”）`tests/governance/test_tests_domain_suites_gates.py`，新增 `tests/governance/test_check_tests_domain_suites.py`
- [x] 3.4 删除（或改造为”脚本单测”）`tests/governance/test_monkeypatch_policy.py`，新增 `tests/governance/test_check_monkeypatch_policy.py`
- [x] 3.5 保持 `tests/governance/` 仅包含：运行时契约测试 + check 脚本单元测试；不在 pytest 测试文件里内嵌完整静态门禁逻辑

## 4. 验收与漂移检查

- [x] 4.1 运行 `just openspec-check`，确保本 change 的 delta specs 与 artifacts 结构可被严格校验
- [x] 4.2 运行 `just qa`，确保新的脚本门禁在 pytest 前执行且全链路通过
- [x] 4.3 运行 `uv run python scripts/check-tests-domain-suites.py --check` / `...check-import-graph.py --check` 等，确认门禁可独立运行（不依赖 pytest/coverage）

