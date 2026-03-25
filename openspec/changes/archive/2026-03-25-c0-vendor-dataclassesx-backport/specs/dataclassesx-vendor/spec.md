# dataclassesx-vendor Specification

## ADDED Requirements

### Requirement: 提供 `scalim.vendor.dataclassesx` 入口

系统 MUST 提供 `scalim.vendor.dataclassesx` 作为 dataclasses 能力的唯一入口,并覆盖 `scalim` 运行时使用到的核心符号(至少包括 `dataclass`、`field`、`replace`、`asdict`)。

#### Scenario: 运行时可导入核心符号
- **WHEN** 调用方执行 `from scalim.vendor.dataclassesx import dataclass, field, replace, asdict`
- **THEN** 导入 MUST 成功

### Requirement: Python 3.6 环境不依赖外部 `dataclasses` backport

系统 MUST 在 Python 3.6 环境下使 `scalim.vendor.dataclassesx` 可用,且不得依赖外部安装的 `dataclasses` backport 包。

#### Scenario: 干净 Python 3.6 环境 import smoke
- **WHEN** 在干净的 Python 3.6 环境中仅通过 `PYTHONPATH=<repo>/src` 运行 `python -c "from scalim.vendor.dataclassesx import dataclass"`
- **THEN** 命令 MUST 返回 0
- **AND** 不应要求额外安装 `dataclasses` backport

### Requirement: `src/scalim/` 内部不得直接导入 `dataclasses`

系统 MUST 确保 `src/scalim/` 内部模块不再出现 `from dataclasses import ...` 或 `import dataclasses` 的直接导入。

#### Scenario: 源码扫描无 dataclasses 直接导入
- **WHEN** 扫描 `src/scalim/` 下的 import 语句
- **THEN** 不应出现 `from dataclasses import` 或 `import dataclasses`

### Requirement: `src/scalim/` 内部使用相对导入引用 `dataclassesx`

系统 MUST 要求 `src/scalim/` 内部模块在引用 `dataclassesx` 时使用相对导入,避免在包内出现 `from scalim.vendor.dataclassesx ...` 的绝对导入,以防 vendors 化/多份包共存时引入错误的 `scalim` 实现。

#### Scenario: 源码扫描无包内绝对导入
- **WHEN** 扫描 `src/scalim/` 下的 import 语句
- **THEN** 不应出现 `from scalim.vendor.dataclassesx` 的导入形式

### Requirement: 发行物不再声明 `dataclasses` 运行时依赖

系统 MUST 在 `pyproject.toml` 的 `[project].dependencies` 中移除 `dataclasses;python_version<'3.7'` 依赖项,以避免将 backport 作为运行时外部依赖暴露给调用方。

#### Scenario: `pyproject.toml` 不含 dataclasses 依赖
- **WHEN** 审阅 `pyproject.toml` 的 `[project].dependencies`
- **THEN** 不应存在 `dataclasses` 依赖条目

### Requirement: vendored provenance 可审计

系统 MUST 记录 vendored `dataclassesx` 的来源与许可证信息,并在 `src/scalim/vendor/README.md` 中维护其用途与更新策略入口。

#### Scenario: vendor README 记录 dataclassesx
- **WHEN** 审阅 `src/scalim/vendor/README.md`
- **THEN** MUST 存在 `dataclassesx` 的来源/许可证与 usage 说明
