## Why

当前仓库中存在大量“可导入但不应成为公共契约”的实现路径被 tests/packages/notebooks 直接引用的现状，同时 `src/scalim/` 下仍有较多模块缺少 `__all__`、以及少数模块在 `__all__` 中误纳入 `_...` 内部符号，导致后续重构的爆炸半径不可控、也容易把内部实现路径沉淀为事实公共 API。

我们已经具备 `just qa` 的质量门禁与既有的 public surface governance 规范/回归，但缺少一份以 OpenSpec 为唯一来源的“现状审计 → 决策收敛 → 分阶段任务”的完整提案，来支撑接下来的重构与 API 强化限制固定。

## What Changes

- 将 API 表面审计、关键冲突点与分阶段实施任务沉淀为本 OpenSpec change（作为唯一 SSOT），并移除仓库内零散的 `_NEXT/` 与 `.tmp/api-surface-audit-report.md`。
- 为 public surface governance 增量补充“模块导出面封堵（`__all__`）”与“内部符号泄漏”相关的规范要求与可回归门禁。
- 以分批（每批 ≤10 文件）策略逐步补齐/封堵 `__all__`、修复 `__all__` 中的 `_...` 误导出，并在每批后执行 `just qa`。
- **BREAKING**（仅针对非稳定入口/内部实现路径）：允许对内部模块进行移动/重命名（例如 `_internal/` 与 `_` 前缀封装），并一次性同步迁移仓内所有引用；不提供兼容别名或 shim。
- 明确 types 聚合入口与 barrel 策略的取舍：避免 `types.py` 等 stdlib 同名冲突；遵循 `__init__.py` 的最小化与可选依赖导入副作用约束。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `public-api-surface-governance`: 增量补充对 `__all__` 导出面封堵、内部符号泄漏与审计回归的规范性要求（不扩大默认稳定公开入口目录；仅强化治理与回归门禁）。

## Impact

- 代码：影响 `src/scalim/` 多个热点区域（by_yaml/config_parsing、schema_dsl、execution/executor、hooks/ob、spec/ir 等）的模块导出面与潜在的内部结构封装；若执行内部模块移动/重命名，将产生仓内大范围 import 路径迁移。
- 测试与示例：tests/packages/notebooks 的导入路径将按治理策略收敛（必要时一次性迁移），并通过 `just qa` 守护。
- 文档治理：本 change 的工件（proposal/design/specs/tasks + references）为 SSOT；涉及 docs-site 的生成/注入内容需遵循生成物规则，入口为 `just gen-docs`（不手改 `.gen.` 与 `BEGIN/END AUTOGEN` 区块内部）。

