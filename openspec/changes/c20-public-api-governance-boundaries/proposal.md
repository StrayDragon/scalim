## Why

目前框架的“可 import 即公开”边界仍偏模糊：部分包通过 re-export 把 `_internal` 实现细节暴露成事实公共契约；同时 docs/skills/examples 很容易引用到内部路径，导致后续重构成本上升（每次移动/拆分都可能破坏用户导入路径）。我们已经用 marimo public-api suite 对部分模块做了 `__all__` 覆盖回归，但仍需要把“公开面治理”升级为可审计、可 gate、可演进的 SSOT。

## What Changes

- 建立并固化“稳定公开入口”的 **单一事实来源（SSOT）**：以 `__all__` + marimo public-api suite 为基准，形成一份可机器读取的 public surface manifest。
- 收敛公开导入路径：默认 public facade 不再 re-export `_internal`；将内部实现与稳定入口物理隔离（必要时新增 `*.api` facade 模块）。
- 增加治理门禁：
  - docs/skills/examples 只能使用 cataloged entrypoints（禁止内部实现路径、禁止 `_internal`）。
  - 当 public surface 发生变化时，必须通过显式更新 manifest + 对应示例/文档/规范，避免“静默扩大公开面”。

## Capabilities

### New Capabilities

- `public-api-manifest`: 引入“公开面 manifest”作为可审计 SSOT（用于 gate、文档引用与回归）。

### Modified Capabilities

- `public-api-surface-governance`: 将“显式编目 + 禁止内部路径出现在用户材料中”的要求落地到可执行 gate，并覆盖更多包/模块。
- `marimo-example-public-api-suite`: 强化其作为公共 API 回归的地位（manifest 与示例保持一致；新增/删除导出必须同步更新）。

## Impact

- 受影响代码（SSOT）：`src/scalim/**/__init__.py` 的 `__all__` 与 re-export；潜在新增 `src/scalim/**/api.py` 或等价 facade；以及用于 gate 的脚本/just 目标。
- 受影响示例（SSOT）：`notebooks/marimo/example_public_api_suite/**`（公开面回归与示例一致性）。
- 受影响文档/技能：
  - docs SSOT 在 `docs/doc/**`（`.gen.*` 与 `BEGIN/END AUTOGEN` 为生成物/注入区块；入口 `just gen-docs`）。
  - skills SSOT 在 `artifacts/skills/**`（示例导入路径必须与 manifest 一致）。

