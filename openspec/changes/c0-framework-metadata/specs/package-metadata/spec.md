# package-metadata Specification

**状态: ✅ 已实现**

## Purpose
为 `scalim` 提供一套轻量、稳定、Python 3.6 兼容的运行时版本号入口（`__version__`），用于排查与集成，并与 `pyproject.toml` 的 `project.version` 保持一致。

## Related Code (as implemented)
- `pyproject.toml`（SSOT）
- `scripts/gen-project-constants.py`（从 SSOT 生成常量）
- `src/IMPL_ROOT/_project_constants.py`（生成物，禁止手改）
- `src/IMPL_ROOT/__init__.py`（最小元信息暴露）

## ADDED Requirements

### Requirement: 提供 `IMPL_ROOT.__version__` 元信息
系统 MUST 在包根提供 `IMPL_ROOT.__version__`，其值 MUST 为非空字符串并与 `IMPL_ROOT._project_constants.VERSION` 一致。

#### Scenario: 运行时读取版本号
- **WHEN** 调用方执行 `import IMPL_ROOT` 并读取 `IMPL_ROOT.__version__`
- **THEN** 读取到的值 MUST 为非空字符串
- **AND** 该值 MUST 等于 `IMPL_ROOT._project_constants.VERSION`
