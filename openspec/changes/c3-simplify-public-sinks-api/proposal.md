## Why

`scalim.sinks` 是用户最容易直接接触到的执行层扩展点之一，但当前 public surface 存在几个问题：

- 导出面过宽：contracts、file sinks、内存 sinks、以及带可选依赖的 sinks 混在同一层级，用户难以判断“稳定/推荐/可选”边界。
- 内存数据形态不统一：既有 “RowData 列表” 的 in-memory sink，也有 workflow 中间态使用的 `InMemoryRows`（typed rows）。当调用方需要“捕获结果以二次处理”时容易选错，导致不可预期的类型/顺序语义。

本 change 目标是收敛 sinks public surface，显式区分稳定契约、常用 sinks 与可选能力，并统一推荐的“捕获 rows 工件”形态。

## What Changes

- **BREAKING**：调整 `scalim.sinks` 的对外导出与模块分组：
  - `scalim.sinks` 只承诺 contracts + 常用 sinks 的稳定入口（通过 `__all__` 明确）。
  - 可选依赖相关 sinks（例如 pandas）迁移到显式子模块（例如 `scalim.sinks.pandas`）或其它明确边界，避免被误认为默认 runtime 依赖。
- **BREAKING**：统一对外推荐的“捕获 rows 工件”形态为 `scalim.sinks.rows.InMemoryRows`：
  - 明确其字段顺序、值域与转换/适配入口。
  - 降低 “拿到一个 sink 然后猜它有没有 get_data/to_dataframe” 的不稳定用法。
- 同步治理：public API catalog/docs、import-boundary gate、tests/notebooks 示例需要一次性升级。

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `sinks-contracts`: 明确可选依赖 sinks 的导入边界与错误提示要求，并对稳定导出面/推荐分组做补充约束。
- `public-api-surface-governance`: sinks 作为 Tier1 curated entrypoint，需要对 `__all__` 漂移进行显式 gate（新增/移除/迁移必须可审计）。
- `public-api-manifest`: public API catalog/docs 需要反映新的 sinks 分组与稳定导出面。

## Impact

- 受影响代码：
  - `src/scalim/sinks/__init__.py`、`src/scalim/sinks/api.py`、以及相关实现模块（exports 组织与分组）
  - tests/notebooks 中对 sinks 的直接导入
- 受影响链路：
  - YAML DSL 的 public run API 未来若进一步收敛 “capture” 语义，将更倾向返回 `InMemoryRows` 而不是暴露 sink
- 风险：
  - public surface 变更，需一次性升级调用点（不做兼容层）
