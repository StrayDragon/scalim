## Why

`scalim.vendor.literich` 是一个仅用于 CLI/调试输出的轻量表格/面板渲染器，目前只在 observability presets 与 metrics summary 中被引用。继续维护该模块会带来：

- 增加 `src/scalim/vendor/` 的维护面（需要兼容 Python 3.6、测试与边界处理）。
- 由于其可直接 import（`scalim.vendor.literich`），容易被下游当作事实公共 API 使用，未来难以演进/删除。
- 与现有日志规范（稳定前缀 + `k=v` 诊断字段）方向不一致：表格/面板渲染会让用户可见输出形态更碎片化，且难以保证长期稳定。

因此希望移除该包，统一观测/摘要输出为 dependency-free 的纯文本 logger 输出，减少运行时表面与 vendor 负担。

## What Changes

- **BREAKING** 移除模块 `scalim.vendor.literich`（`Table`/`Panel`/`Column` 不再可导入）。
- 将以下内部输出从 Table/Panel 渲染调整为纯文本（保持相同指标语义、通过 logger 输出、无新增运行时依赖）：
  - `MetricsCollector.print_summary`
  - `PrettyLoggingObserver`（pipeline start/end 与 loader 统计部分）
  - `ExecutionTraceObserver.print_summary`
  - `MemoryOptimizationObserver.print_summary`
  - `RelationObserver.print_summary`
  - `PerformancePresentationLayer.render_summary`（`console` 报告）
- 移除/替换仅用于 `literich` 的单测，并为新的文本输出添加最小回归（以“包含关键信息/字段”为准，而非精确对齐）。
- 更新 vendor 文档与 public API 治理材料，确保不再把 `scalim.vendor.literich` 当作稳定入口。

## Capabilities

### New Capabilities

- `dependency-free-console-reports`: 可观测性/性能报告在 `console` 模式下提供无额外依赖的稳定文本输出（不依赖 rich/表格渲染器）。

### Modified Capabilities

- `performance-observability`: `console` 报告与 pretty logging 的展示形式调整为纯文本，但指标口径与报告格式（console/json/csv/none）保持不变。
- `public-api-surface-governance`: 从治理与回归角度显式移除 `scalim.vendor.literich`，避免 vendor 工具被固化为公共契约。

## Impact

- **User-visible output**: 控制台输出从“框线表格/面板”变为“纯文本分组 + k=v/列表”形式（信息等价但视觉不同）。
- **Public API**: 任何下游若直接 `import scalim.vendor.literich` 将在升级后失败；本变更不提供兼容层/弃用期。
- **Code areas**: `src/scalim/ob/**`、`src/scalim/vendor/**`、相关测试与治理脚本/文档。
- **Docs / SSOT / generated**:
  - `src/scalim/vendor/README.md` 为 SSOT，可直接修改。
  - 若需要调整对外推荐导入路径，以 `docs/doc/getting-started/public-api.md` 为 SSOT；若触发站点生成或注入块变更，按治理规则运行 `just gen-docs`，避免直接编辑 `.gen.` 或 `AUTOGEN` 区块。
