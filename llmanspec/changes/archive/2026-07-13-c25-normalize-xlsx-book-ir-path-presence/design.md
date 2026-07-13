## Context

YAML 侧已统一为 `xlsx`（path 可选）。内部仍用 `kind=xlsx_file|xlsx_memory` 字符串驱动后端选择。

## Goals / Non-Goals

**Goals**

- IR SSOT：有 path = 版本化落盘后端；无 path = 内存总线后端
- 迁移 shim：过渡期可保留内部映射函数，但公共/调试面不把假 kind 当作身份

**Non-Goals**

- 合并 `resources_workbook.py` / `resources_sheetbook.py` 文件
- BREAKING 删除 YAML `xlsx_file` / `xlsx_memory` keys（另案）
- 改写策略 / budget 语义

## Decisions

1. **身份维度**：`path is not None`（规范化后）决定后端；不再新增第三种 identity。
2. **兼容**：若仍接受 deprecated YAML kind，parse 后立即归一到 path 形状，不把 `xlsx_file`/`xlsx_memory` 字符串长期存为业务字段（或仅作 deprecated wire 兼容字段并标注）。
3. **后端绑定**：materialize 按 path 有无选择现有 workbook/sheetbook 实现；不改磁盘布局与总线可见性规则。

## Risks / Trade-offs

- 大面积 `kind ==` 分支需一次性梳理；漏改会导致静默走错后端 → 靠测试矩阵（有/无 path × 旧/新 YAML）。

## Migration Plan

1. 引入归一辅助（path-presence）并替换分派点。
2. 更新测试断言：从断言 kind 字符串改为断言 path / backend 行为。
3. skills/升级笔记：说明 IR 已与 YAML 对齐为 path 语义。

## Open Questions

- 无（后端文件合并是否另开 change：默认另开）
