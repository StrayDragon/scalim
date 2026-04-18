# testing-quality Specification

## ADDED Requirements

### Requirement: public API coverage drift gate MUST run before pytest in `just qa`
系统 MUST 将 “public API coverage 漂移检测” 实现为独立的静态脚本门禁（`scripts/check-*.py --check`），并把它纳入 `just qa` 的 pytest 之前阶段执行，以实现 fail-fast：

- 不依赖 pytest 收集/执行模型
- 失败时输出可定位差异与修复入口

#### Scenario: drift gate fails fast before pytest
- **GIVEN** Tier1 curated entrypoints 或示例/pytest 覆盖集合发生漂移
- **WHEN** 开发者运行 `just qa`
- **THEN** gate MUST 在 pytest 之前失败退出
- **AND** 输出 MUST 指出缺失/新增模块集合与推荐修复命令

