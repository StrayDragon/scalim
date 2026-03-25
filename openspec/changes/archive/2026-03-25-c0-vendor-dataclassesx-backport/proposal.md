## Why

我们需要把 `src/scalim/` 同步到下游旧工程的 `vendors/libs/scalim/` 导入链路,但当前 `scalim` 在 Python 3.6 下依赖 `dataclasses` backport 包,导致同步到下游时还需要额外同步/安装 `dataclasses` 才能运行,过程容易被人工改动并产生漂移与“幽灵 bug”.

为了让 vendors 同步产物尽可能自包含、可审计且不依赖下游环境的第三方安装状态,我们需要把 `dataclasses` backport 作为内部 vendored 代码纳入 `src/scalim/` 并统一由自身引用。

## What Changes

- 在 `src/scalim/vendor/dataclassesx/` 引入 Python 3.6 `dataclasses` backport 的 vendored 实现,作为 `scalim` 运行时内部使用的 dataclasses 能力来源。
- 统一将 `src/scalim/` 内部对 `dataclasses` 的引用迁移为对 `vendor/dataclassesx` 的**相对导入**（例如 `from ..vendor.dataclassesx import dataclass, field` 等）,避免在包内出现 `from scalim...` 的绝对导入,以保证 vendors 化场景不会意外混入另一份 `scalim`。
- （可选,依实现取舍）从 `pyproject.toml` 移除 `dataclasses;python_version<'3.7'` 的运行时依赖,避免让调用方把该 backport 当作间接依赖来源。
- vendors 同步链路(镜像 `src/scalim/`)将自然携带 `dataclassesx`,从而下游仅通过同步即可运行核心逻辑。

## Capabilities

### New Capabilities
- `dataclassesx-vendor`: 在运行时提供 `scalim.vendor.dataclassesx` 作为 Python 3.6 兼容的 dataclasses 能力,并要求 `src/scalim/` 内部仅依赖该实现,以便 vendors 同步产物自包含。

### Modified Capabilities
<!-- 本变更不修改 legacy-vendors-sync 的 REQUIREMENTS,仅增强其下游可运行性(同步产物更自包含). -->

## Impact

- 受影响代码范围: `src/scalim/` 内大量 `from dataclasses import ...` 的模块将迁移为对 `vendor/dataclassesx` 的相对导入（例如 `from ..vendor.dataclassesx import ...`）。
- 受影响交付/集成: 下游 `vendors/libs/` 同步后不再需要额外同步/安装 `dataclasses` backport 即可运行 `scalim`（以本仓库提供的 vendored 版本为准）。
- 风险与约束:
  - vendoring 需要明确来源版本与许可证处理策略,并在后续升级/同步时保持可审计。
  - dataclasses backport 与 stdlib dataclasses 在极端边界行为上可能存在差异,需要以 `scalim` 现有使用范围为准进行回归验证。
