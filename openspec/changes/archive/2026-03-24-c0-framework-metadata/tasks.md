## 1. Python 运行时版本号入口

- [x] 1.1 在 `src/scalim/__init__.py` 暴露 `__version__`（与 `src/scalim/_project_constants.py` 的 `VERSION` 一致），保持包根不做公共重导出聚合

## 2. 测试与验收

- [x] 2.1 新增运行时测试：`import scalim` 后 `scalim.__version__` 可读且与 `_project_constants.VERSION` 一致
- [x] 2.2 验收命令：`just quick-check-only-py`、`just openspec-check`
