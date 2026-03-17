## ADDED Requirements

### Requirement: workflow may declare shared output container resources
系统 MUST 支持在 workflow YAML 中声明“共享输出容器资源”,用于多 demand 合并输出到同一个最终文件(例如 workbook/csv):
- 共享容器资源 MUST 具有稳定的 resource id,供写出节点引用
- 共享容器资源的生命周期 MUST 由 workflow 统一管理(创建/关闭/保存/原子替换)

#### Scenario: shared workbook resource is addressable by id
- **GIVEN** workflow 声明一个 workbook 资源 `report`
- **WHEN** 写出节点引用 `workbook: report`
- **THEN** 系统 MUST 将其解析为同一个共享 workbook 实例,而不是为每个 run 单独创建文件

### Requirement: workflow may bind demand outputs into shared containers
系统 MUST 支持 workflow 声明“写出节点”,将一个 demand(run) 的某个 output_target 写入共享容器:
- 写出节点 MUST 能引用 `(run_id, output_name)` 或等价标识来定位一个 output_target
- 写出节点 MUST 支持写入 workbook sheet 或写入 csv
- 系统 MUST 对 sheet 命名冲突提供可配置的冲突策略(至少支持 fail-fast error)

#### Scenario: multi-demand outputs write into one workbook as multiple sheets
- **GIVEN** workflow 包含两个 runs: A 与 B
- **AND** workflow 声明共享 workbook `report`
- **WHEN** 配置两个写出节点分别将 A/B 的某个 output 写入 `report` 的不同 sheet
- **THEN** 最终只保存 1 个 workbook 文件且包含两个 sheet

### Requirement: writing/merging into the same container is deterministic under concurrency
系统 MUST 定义并实现跨 runs 的写出确定性规则:
- 写出顺序 MUST 由 workflow 声明顺序决定(不得依赖并发完成顺序)
- 对同一共享容器的写出 MUST 串行化或采用等价互斥策略(避免并发写导致不确定性/文件损坏)
- 若 workflow 失败,系统 SHOULD 避免产出“部分落盘”的最终文件(建议延迟落盘并保持原子替换)

#### Scenario: append order is stable regardless of run completion order
- **GIVEN** 两个 runs 并发执行且完成顺序不稳定
- **WHEN** 两个写出节点都追加到同一个 sheet/csv
- **THEN** 最终输出中的段落顺序 MUST 与 workflow 写出节点的声明顺序一致

### Requirement: workflow supports append-to-single-sheet merge semantics
系统 MUST 支持将多个上游 output_target 合并到同一个 sheet/csv 的 append 语义,并定义最小可用的对齐规则:
- 至少支持按 `field_id` 对齐(缺失字段填空;或提供严格模式 fail-fast)
- header 输出策略必须可定义(至少支持“只输出一次 header”)

#### Scenario: append merge aligns by field_id
- **GIVEN** 上游 output_target 具有相同的 field_id 集合
- **WHEN** 配置 append 合并写入同一个 sheet/csv 且对齐策略为 field_id
- **THEN** 系统 MUST 将两段数据按相同列顺序输出并追加

