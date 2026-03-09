## Why

当前运行只能产出单一输出(通常是详情表),无法在同一次运行内生成分析/汇总表,导致详情与分析需要二次离线处理,也无法在同一报表包中稳定交付“明细 + 结论”。对于多 sheet workbook 或“宽表先产出,再按维度汇总”的报表链路,这会长期把编排逻辑卡在 Python 外围。

现在需要把“多输出组合”和“派生输出”作为执行层的一等能力收口进来,先打通一次运行内的详情/汇总协同与同容器多逻辑输出。

## What Changes

- 引入“多输出组合”能力: 单次运行可定义多个输出目标(详情+汇总),可写入同一容器(如同一 workbook 的多 sheet)或独立输出。
- 引入“派生输出”能力: 允许在同一次运行中对详情流做增量聚合并产出汇总表,支持批次累计、收尾输出与二阶段兜底模式。
- v1 明确限定为 IR/Python 配置入口,不在本 change 中扩展 YAML DSL authoring surface;文档需解释这一阶段边界与后续映射空间。
- 明确同容器命名冲突、输出失败策略、资源控制与并发一致性约束。

## Capabilities

### New Capabilities
- `output-composition`: 单次运行支持多个输出目标、同容器多逻辑输出与容器内命名冲突管理。
- `derived-outputs`: 单次运行支持基于详情流的派生输出、增量聚合与后置聚合兜底路径。

### Modified Capabilities
- None.

## Impact

- 影响执行流程、输出组合层、容器型 sink、派生聚合状态管理与可观测事件对齐。
- 主要风险是内存增长、输出顺序稳定性、以及 `adaptive` 并发下的聚合一致性约束。
- v1 不改 YAML DSL / schema / editor;如需 YAML authoring surface,应作为后续独立 change 处理。

## Compatibility Notes

- thread/process 批次级并行将被移除,执行并发语义收敛为 `seq|adaptive`;本 change 中关于“并行模式下可重复性”的讨论应以 `adaptive` 的批次内并发与提交点回放为主要并发形态。
