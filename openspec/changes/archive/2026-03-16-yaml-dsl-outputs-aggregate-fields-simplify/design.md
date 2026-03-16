## Context

当前 YAML DSL 的 `outputs[*]` 与 `outputs[*].aggregate` 在实践中承载了“同一明细行流的多路分发 + 汇总/排名/积分”的绝大多数报表需求,但存在两个结构性问题:

1) **表达主体不一致**  
YAML DSL 的核心心智模型通常是“围绕字段(field_id)声明”,但 `aggregate.metrics` + `{op, field}` 的写法更像“算子配置”,不利于学习与 schema 补全。

2) **缺少高频 finalize 能力导致 Python 大循环**  
dense rank/partition rank/聚合后算分等高频需求缺口,迫使业务侧写多轮 dict/set 聚合或用 workflow+中间 CSV 串联两次 demand。

本设计聚焦于: **重做 outputs/aggregate 的最小语法,让字段成为主体,并补齐 finalize 排名/派生字段能力**,同时严格控制新增概念数量,避免演化成“半个 SQL 引擎”。

约束:
- 运行时必须兼容 Python 3.6
- schema/文档治理: `.gen.` 文件禁止手改,需通过 `just gen-docs` 刷新
- 本变更为破坏性升级: 不保留旧字段别名与双写法(一次性升级仓库内写法)

## Goals / Non-Goals

**Goals:**
- 保持 `outputs[*].where` 字段名不变,但在 schema/hover 中明确其为行级过滤谓词(避免被误解为“是否启用 sheet”)
- 将 `outputs[*].aggregate.metrics` 改名为 `outputs[*].aggregate.fields`
- 将聚合指标的 `{op: ...}` 改为“函数当 key”的字段自描述形态,以获得强 schema 补全
- 在同一 aggregate 中支持:
  - `row_number`/`rank`/`dense_rank`
  - `partition_by`
  - `order_by` 多 key
  - `top_k_mode`(默认含并列扩张)
  - 聚合后派生字段(优先内置函数,同时留 `call_by` hotfix 口子)

**Non-Goals:**
- 不引入“数据集图/CTE/subquery”语义,不支持 derived output 结果回流为 sources/relations 的输入
- 不引入“整张 sheet 是否启用”的配置级开关(如 `enabled_if`),仅保留行级过滤(未来可增)
- 不扩展 workflow 作为 run 间内存数据管道
- 不在本变更中重构顶层 `fields`(派生字段)的入口位置与语义

## Decisions

### D1. `outputs[*].where` 明确为“行级过滤”

- 保持字段名不变: `where`
- 语义保持不变: 编译为 `predicate(row)->bool`,每行决定是否进入该 output
- 文档/hover 必须显式写明:
  - `where` 是行级过滤谓词(按行路由/过滤),等价 SQL `WHERE`
  - 执行阶段:
    - 对明细输出: 在写出前对每行执行,命中才写入该 output
    - 对聚合输出: 在 `group_by` 之前对每行执行(只有命中的行参与聚合)
  - 表达式的变量来自当前行的字段值: 可引用 demand 中的 `fields.<field_id>`(包含 relation/derive 后的字段)
    - 系统会在编译期静态提取表达式依赖字段,只保证这些字段会被准备(其它未引用字段可能为 `None`)
    - `where` 不能引用聚合后的输出字段(例如 `aggregate.fields.*` 产生的指标/排名/派生字段)
  - 若需要“是否启用整个 sheet”的能力,未来新增 `enabled_if`(与 `where` 语义互补,而非替代)

### D2. `aggregate.metrics` → `aggregate.fields`,并将“指标如何得到”表达为 key

将:
```yaml
metrics:
  order_cnt: {op: count}
```
改为:
```yaml
fields:
  order_cnt:
    count: {}
```

核心规则:
- `aggregate.fields.<out_field_id>` MUST 是 object 且只允许出现 **一个 producer key**
- producer key 分为三类:
  1) **Agg function keys(强 schema 补全)**: `count/sum/min/max/count_true/count_true_gte/count_distinct`
  2) **Rank function keys(强 schema 补全)**: `row_number/rank/dense_rank`
  3) **Hotfix key(弱补全但保留口子)**: `call_by`

约束与好处:
- 不引入 `kind` 枚举,避免把配置平铺到同一层
- schema 可以对每个 producer key 提供固定参数结构与 hover
- 迁移是可机械化的(字段名改动 + 结构改写)

schema/hover 约束:
- `outputs[*].aggregate.group_by` 的 hover 必须解释:
  - `group_by` 引用的是输入行字段(`field_id`),来自 `where` 过滤后的行流
  - 每个唯一的 group key 组合会产生 1 行聚合输出
  - `partition_by`(排名分区)必须是 `group_by` 子集的原因(确保可解释性)
- `outputs[*].aggregate.fields` 的 hover 必须解释:
  - map key 是输出字段 ID
  - value 是“该字段如何产生”的声明,必须且只能选择一个 producer key
  - 执行顺序: 先聚合指标 → 再排名字段 → 再聚合后派生字段(call_by/score_by_rank)
  - 聚合后派生字段可引用的输入字段范围(可用字段集合与限制)

### D3. 排名语义: “rank by 值”与“排序稳定性”解耦

需求侧期望:
- dense/rank 的“并列”按某个指标值判断(例如 `metric_value`),而不是被 tie-break 字段打散

因此 rank function 的输入拆分为:
- `by`: 用于计算 rank 值与并列判断的字段(必须引用 `group_by` 或 agg 字段)
- `order_by`(可选): 用于输出稳定排序与 `top_k_mode=rows` 的稳定 tie-break

规则:
- 若 `order_by` 缺省,系统 MUST 默认按 `by` 单键排序
- `top_k_mode=rows` 时,系统 MUST 要求提供 `order_by`(否则 fail-fast)

### D4. `top_k` 在 partition 场景默认“含并列扩张”

默认策略:
- `top_k_mode=rank`(默认): 每个 partition 保留 `rank_value <= K`(含并列扩张)

可选策略:
- `top_k_mode=rows`: 每个 partition 强行取前 K 行(允许截断并列),依赖 `order_by` 提供稳定 tie-break

### D5. 聚合后派生字段: 优先内置函数,保留 `call_by` hotfix

为保证补全与可维护性:
- 常见派生(如 `score_by_rank`)优先提供内置 producer key(强 schema)
- 同时允许:
```yaml
score:
  call_by: "pkg.mod:fn(base=100, step=3)"
```
作为 escape hatch,用于快速 hotfix;后续可沉淀为内置 producer key 并提供补全

## Risks / Trade-offs

- [破坏性升级] → 提供清晰迁移指引与 fail-fast 错误信息;必要时提供脚本化升级入口(不承诺保留注释/锚点)
- [函数 key 扩展导致语义膨胀] → 严格控制允许的 producer key 集合,新增必须走 OpenSpec 评审与补齐 schema/测试
- [rank/partition/top_k 的确定性] → 强制 finalize 单线程计算;明确 tie-break 与排序稳定规则;补充对拍用例
- [`call_by` 参数补全弱] → 将其定位为 hotfix 口子;常用场景尽快固化为内置 producer key

## Migration Plan

1) 一次性升级仓库内 YAML:
   - `outputs[*].aggregate.metrics` → `outputs[*].aggregate.fields`
   - 指标条目 `{op: ...}` → `{<op>: {...}}` 结构改写
2) 更新 schema 与文档:
   - 更新 `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/models/outputs.py` 元数据
   - 运行 `just gen-docs` 刷新 `.gen.` 文档与 injected blocks
3) Drift gate:
   - schema 生成 drift: `tests/test_yaml_schema_generation.py`
   - 语义回归与新增能力: `tests/test_derived_outputs.py` + YAML parser/runtime 测试

## Open Questions

- rank function keys 的参数命名: `partition_by/order_by/top_k_mode` 是否需要统一命名风格(例如都用 `_by` 后缀)?本设计优先保持与现有命名接近以减少迁移面。
