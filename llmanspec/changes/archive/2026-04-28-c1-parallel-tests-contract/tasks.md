## 1. Test Isolation Utilities

- [x] 1.1 在 `tests/` 下新增一个集中化工具(模块或 fixture),用于安全地 patch/restore `scalim_misc.demo_big_data_report.loaders` 的全局 config(包含全局锁)
- [x] 1.2 为 `scalim_misc.example_report_ir` 提供一个 fixture: 使用 monkeypatch 替换 `data_loader` 为 `PandasDataLoader(random_delay=0.0)` (避免原地修改 `random_delay`)

## 2. Migrate Existing Tests

- [x] 2.1 迁移 `tests/conftest.py` 中的 `example_report_ir_module`/`ecommerce_config_small` 等 fixture 到新的隔离工具,移除手写 try/finally 全局 patch
- [x] 2.2 迁移 `tests/integration/test_demo_big_data_report_workflow_demo.py` 与 `tests/cases/notebook_ecommerce.py` 中对 `set_config/get_config` 的手写 patch

## 3. Verification

- [x] 3.1 新增一个最小回归测试: 验证隔离工具在异常路径也能恢复全局状态
- [x] 3.2 运行 `just qa` 确认 `pytest -n auto` 下稳定通过
- [x] 3.3 运行 `just openspec-check` 确认 OpenSpec 工件合法
