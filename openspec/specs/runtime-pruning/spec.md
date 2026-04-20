# runtime-pruning Specification

## Purpose
PlanBuilder 基于目标字段构建依赖图并裁剪 required_fields,生成仅包含必需字段的 ExecutionPlan;运行时在 BatchContext 中仅保留 required_fields,并在列式/流式写入与显式释放时触发 FieldSlimEvent 以降低内存占用.

## Context
**FR021: 依赖字段剪枝**

支持自动剪枝结果集不需要的字段和计算逻辑.

**FR022: 字段瘦身**

运行时关联过程需要支持智能剪枝不需要的部分,以减少内存占用.

## Related Concepts
- 计划构建器 (builder.py)
- 批次上下文 (BatchContext)
- Pipeline (pipeline.py)
- 写入/释放算子 (write/release operators)
- Load 算子 (load operators)
- YAML 转换器 (conversion.py)

## Requirements

### Requirement: 依赖剪枝与计划元数据
系统 SHALL 基于目标字段收集依赖并构建仅包含必需字段的执行计划,并使用依赖图进行拓扑排序以保证计算顺序正确.
系统 SHALL 在未显式指定 targets 时默认包含所有字段;可通过 output.fields 配置指定输出字段顺序.
系统 SHALL 在执行计划元数据中记录 pruned_fields(总字段数减去 required_fields 数量).

#### Scenario: 未配置输出字段
- **WHEN** YAML 未设置 output.fields
- **THEN** 计划应包含全部字段

#### Scenario: 剪枝非目标字段
- **WHEN** 目标字段仅包含订单 ID 与名称
- **THEN** 未被依赖的字段不应被加载或计算

### Requirement: YAML 转换阶段按 output.fields 剪枝字段定义
系统 SHALL 在 YAML DSL `DemandConfig → DemandIr` 转换阶段基于 `output.fields` 计算 required-fields 闭包(包含派生字段依赖与 `main_source.order_by` 引用字段),并跳过未被 required-fields 覆盖的字段定义转换,以降低无效字段带来的 IR/计划噪声.
当 `output.fields` 缺省时,转换阶段 MUST 保留全部字段定义.

#### Scenario: 未引用字段不进入 IR
- **WHEN** 字段未在 `output.fields` 中出现且不被派生依赖引用
- **THEN** 该字段不应被转换到 IR

### Requirement: 运行时字段保留与释放策略
系统 SHALL 在 BatchContext 中仅存储 required_fields 内的字段值.
系统 SHALL 在列式写入/行式流式缓存/显式释放算子触发时释放无后续依赖且非 key_fields 的字段并触发 FieldSlimEvent(基于 reverse_deps 结果判定).

#### Scenario: 非必需字段被忽略
- **WHEN** 计算过程中写入一个非 required_fields 字段
- **THEN** BatchContext 不应保存该字段

#### Scenario: 列写入后释放
- **WHEN** 目标字段列写入完成且无后续依赖
- **THEN** 该字段应从 BatchContext 删除并触发 FieldSlimEvent

## Notes
- RowReleaseEvent 仅在行式流式写入路径中触发(详见 `streaming-output`).
- LoaderSlimEvent 在 Load 路径提取字段并发生"瘦身"(loader 返回 row_data=dict 且包含多余 keys)时触发,且为 wants-gated.
