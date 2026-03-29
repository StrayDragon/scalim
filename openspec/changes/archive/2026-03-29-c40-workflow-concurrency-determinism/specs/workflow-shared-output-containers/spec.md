## ADDED Requirements

### Requirement: commit order MUST NOT depend on thread scheduling

当 workflow 在并发模式执行时,系统 MUST 禁止将共享资源（csv/workbook/sheetbook）的最终写入顺序绑定到线程调度或节点完成时序.

系统 MUST 为每条写入意图记录稳定的 `decl_order`（声明顺序序号）,并在 commit 阶段按 `decl_order` 稳定排序后写出.

#### Scenario: concurrent appends preserve declaration order
- **GIVEN** 两个并发 runs 对同一共享 csv 资源 append 写入
- **WHEN** workflow 在并发模式下重复执行多次
- **THEN** 最终落盘 csv 的段顺序 MUST 始终与 YAML 声明顺序一致

### Requirement: workbook/sheetbook sheet order MUST be stable

系统 MUST 定义 workbook/sheetbook 的 sheet 顺序策略,且不得依赖“并发首次创建时 append”导致的漂移.

#### Scenario: sheet order is stable across concurrent runs
- **WHEN** 并发执行多个写入不同 sheets 的 write intents
- **THEN** 导出的 workbook/sheetbook 内 sheet 顺序 MUST 可复现

