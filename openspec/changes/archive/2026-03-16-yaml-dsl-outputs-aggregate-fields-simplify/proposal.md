## Why

我们在迁移一类“多事实流 + 多维度 + 多 sheet + 汇总排名/积分”的统计报表时,当前 YAML DSL 在 `outputs[*]`/`aggregate` 的表达存在两类高频痛点:

1) **语法不直观,学习成本高**  
`aggregate.metrics` + `{op: ..., field: ...}` 这套写法偏“实现细节配置”,与 YAML DSL 其它部分“围绕字段(field_id)做声明”的直觉不一致。

2) **能力缺口导致大量 Python 大循环 / workflow 中间文件**  
常见需求(按分区排名、dense rank、聚合后算分/二次排序)在 DSL 内缺少原生能力,业务侧只能在 Python 中维护大量 dict/set/state 或用 workflow+中间 CSV 串两次 demand。

我们希望在不引入复杂新概念(CTE/数据集图等)的前提下,重做 `outputs[*]`/`aggregate` 的最小语法,让“最终追求的字段”成为主体,同时补齐 dense/partition rank 与聚合后派生字段的下沉能力。

## What Changes

- **Non-breaking**: 保持 `outputs[*].where` 字段名不变,但在 schema/hover 中明确其为 **行级过滤谓词**  
  - 语义不变: 满足条件的行才进入该 output(明细输出或聚合输出)  
  - hover 将明确: 执行阶段/变量来源/限制(聚合前),并说明这不是“是否启用整个 sheet”的开关;如需该能力后续另引入 `enabled_if`(不在本变更范围)

- **BREAKING**: `outputs[*].aggregate.metrics` 重命名为 `outputs[*].aggregate.fields`

- **BREAKING**: `outputs[*].aggregate.fields.<field_id>` 使用“函数当 key”的字段自描述形态,替代 `{op: ...}` 映射  
  - 目标: schema/LSP 能对函数 key 提供强补全与参数说明,降低试错成本  
  - 例:
    - 旧: `order_cnt: {op: count}`
    - 新: `order_cnt: {count: {}}`

- **New**: 在同一 `outputs[*].aggregate.fields` 中支持“排名字段”与“聚合后派生字段”  
  - 排名字段: `row_number`/`rank`/`dense_rank` + `partition_by` + `order_by` + `top_k_mode`  
  - 聚合后派生字段:
    - 优先提供内置字段函数(如 `score_by_rank`)以获得补全
    - 同时保留 `call_by` 作为 hotfix 口子(补全弱但可快速落地,后续再固化为内置函数)

## Capabilities

### New Capabilities
- `yaml-dsl-output-targets-v2`: 定义 v2 的 `outputs[*]` 语法与语义(含 `where`/`aggregate.fields`/rank/score 的约束与迁移规则)

### Modified Capabilities
- `yaml-dsl-schema`: JSON Schema/hover 需要反映 `outputs[*].where` 的行级语义与 `aggregate.fields` 新结构,并提供函数 key 的补全与示例
- `derived-outputs`: 派生聚合 finalize 排名能力扩展(dense/partition/top_k_mode)与聚合后派生字段执行顺序/确定性边界

## Impact

- YAML DSL:
  - `outputs[*]`/`aggregate` 相关配置需要一次性升级(不保留旧字段别名与双写法)
  - 文档与示例需要同步升级,并提供迁移指引(建议提供 `PROJECT_CLI_NAME yaml-dsl upgrade` 或脚本化升级入口)
- Runtime:
  - `RankedGroupByAggregator` 需要支持 dense/partition/top_k_mode/order_by
  - 输出过滤谓词(`where`)语义说明补全(实现语义不变)
  - 聚合后派生字段需要在 finalize 阶段执行,并保持结果确定性与可对拍
- Tooling:
  - schema 生成与 editor 补全将是主要收益点(函数 key → 固定参数结构)
  - 测试需要覆盖: 语义回归(旧行为) + 新增 dense/partition/top_k_mode + hotfix call_by 的最小契约
