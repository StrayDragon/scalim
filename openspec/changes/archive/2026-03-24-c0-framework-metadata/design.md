## Context

当前仓库已经有一套基于 `pyproject.toml` 的项目常量生成链路:
- SSOT: `pyproject.toml` 的 `[project]` 与 `[tool.scalim.*]`
- 生成器: `scripts/gen-project-constants.py`
- 生成物: `src/scalim/_project_constants.py` + 前端 `frontend/**/project_constants.ts`
- 版本统一入口: `scripts/bump-versions.py` (通过正则更新白名单文件的 `version` 字段，且在根 `pyproject.toml` 变更时会调用 `gen-project-constants.py`)

但目前 Python 运行时缺少最常见的“库版本号”稳定入口：`scalim.__version__`。

约束:
- `src/scalim/` 运行时必须 Python 3.6 兼容（不能依赖 `importlib.metadata` 等 3.8+ 能力）。
- 任何 `.gen.*` 文件与 injected blocks 禁止手改；生成物应由生成脚本/`just` 目标产出，并通过漂移门禁兜底。

## Goals / Non-Goals

**Goals:**
- 提供稳定、轻量、无额外依赖的运行时版本号入口：`scalim.__version__`。
- 明确 SSOT/生成物边界，并保持现有漂移检查模式（`scripts/gen-project-constants.py --check`）覆盖版本号常量。

**Non-Goals:**
- 不引入“安装后动态读取包元数据”的机制（例如通过 `importlib.metadata`/`pkg_resources` 读取）。
- 不在本 change 中新增其它元信息字段（例如 bump 时间戳 / git SHA / 构建机器信息等）。
- 不改变现有对外 API 的导出策略（除最小版本号暴露外，不在 `scalim` 包根做公共重导出聚合）。

## Decisions

1) **版本号 SSOT 与生成物**
- 版本号 SSOT 为 `pyproject.toml` 的 `project.version`。
- 版本号常量来源为已存在的生成物 `src/scalim/_project_constants.py` 中的 `VERSION` 字段。

2) **运行时暴露面**
- 在 `src/scalim/__init__.py` 暴露 `__version__`，其值与 `._project_constants.VERSION` 保持一致。

3) **文档/生成边界与漂移门禁**
- `src/scalim/_project_constants.py` 与 `frontend/**/generated/project_constants.ts` 仍为生成物，禁止手改。
- 修改版本号应只改 `pyproject.toml`（SSOT），然后运行:
  - `just gen-project-constants`（写入）
  - `just gen-project-constants-check`（漂移检查）
- `just qa`/CI 会覆盖漂移门禁（已有），确保版本号常量不会引入隐式漂移。
