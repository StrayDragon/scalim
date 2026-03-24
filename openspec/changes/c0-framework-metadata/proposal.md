## Why

目前框架缺少最常见的“库版本号”入口：`scalim.__version__`。
这会让线上排查/问题复现/工单沟通时难以确认运行的具体版本与打包来源。

## What Changes

- 新增最小运行时元信息能力：在 Python 运行时可稳定读取版本号 `scalim.__version__`。
- 版本号的 SSOT 仍为 `pyproject.toml` 的 `project.version`，并通过既有生成链路输出到:
  - `src/scalim/_project_constants.py` (生成物，禁止手改)
  - 前端 `project_constants.ts` 生成物(若需要消费该字段)
- 在 `scalim` 包顶层暴露 `__version__`（与 `_project_constants.VERSION` 一致），不引入额外公共 API 聚合。

## Capabilities

### New Capabilities
- `package-metadata`: 提供可稳定读取的 `scalim.__version__` 运行时元信息。

### Modified Capabilities
<!-- 无 -->

## Impact

- 受影响文件/入口(示例):
  - SSOT: `pyproject.toml`
  - 生成器: `scripts/gen-project-constants.py`
  - 生成物: `src/scalim/_project_constants.py`、`frontend/**/project_constants.ts`
  - Python 运行时入口: `src/scalim/__init__.py`
- 行为变更风险:
  - 仅新增版本号元信息导出；运行时需保持 Python 3.6 兼容(不依赖 `importlib.metadata`)。
