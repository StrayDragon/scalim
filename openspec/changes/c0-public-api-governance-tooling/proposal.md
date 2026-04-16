## Why

当前 public API 的真实契约来源是 `__all__` + Tier1 curated entrypoints 标记（`# pragma: scalim-public-api tier1:...`），但：

- 缺少一个“可重复生成、可审阅”的审计视图，让维护者快速看清 **框架主动 re-export 的稳定入口与符号集合**。
- 缺少一个低摩擦的“编辑器跳转辅助”产物，导致理解 public surface 需要手工追踪多个 `__init__.py` 与 `__all__`。

我们已经有了 SSOT（标记 + `__all__`），现在需要把“可视化/审计/门禁闭环”补齐，避免 public surface 漂移变成隐性 breaking。

## What Changes

- 引入/固化 public API 工具链（生成物均落在 `.tmp/`，不提交）：
  - 生成 “Tier1 curated entrypoints 的 jump-imports 辅助文件”（供 IDE/LSP 快速跳转）。
  - 生成 “Tier1 curated entrypoints 的导出清单审计视图”（供 review/排错/对齐文档与门禁）。
- 增加 `justfile` 入口（例如 `just gen-public-api-jump-imports`）统一生成命令，避免贡献者记忆脚本路径。
- 增加一个 check 入口（可被 `just qa` 或独立 gate 调用）：
  - Tier1 marker 语法合法、无重复 module
  - marker 指向模块必须存在且必须声明字面量 `__all__`
  - 生成物可重复运行且确定性（无变更时输出一致）

> 说明：本 change 只做治理与工具链，不改运行时行为。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `public-api-manifest`: 增补对 “jump-imports 与审计视图生成入口” 的要求，并明确其产物为 `.tmp/` 非提交物。
- `public-api-surface-governance`: 增补对 Tier1 curated entrypoints 的一致性校验/门禁要求（marker 与 `__all__` 对齐）。

## Impact

- 受影响代码：
  - `scripts/`：新增或升级 public API 扫描/生成脚本
  - `justfile`：新增生成/检查命令入口
- 受影响门禁：
  - `just qa`（若接入）：新增 public surface 一致性检查（fail-fast，输出可定位错误）
- 受影响用户材料：
  - (可选) docs/skills 的 public surface 页面若依赖 catalog，将需要按 doc governance 刷新生成物（`just gen-docs`）
