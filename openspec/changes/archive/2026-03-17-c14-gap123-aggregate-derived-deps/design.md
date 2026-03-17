## Context

下游典型 KPI 报表链路需要把“按比率排名 → 积分 → 综合分 → 综合二次排名”尽量下沉到 YAML DSL 的 `outputs.*.aggregate` 中,以减少 Python 侧大内存与自定义逻辑,并复用 Scalim 的流式输出/缓存能力。

`.tmp/downstream_report/gaps/01~03_*.md` 给出了 0.2.7 的三个关键缺口:

- `rank.by` 只能引用 `group_by + 聚合指标字段`,不能引用聚合后派生字段(例如 ratio / all_integral)
- `aggregate.fields.*.call_by` 不能依赖其它 post 字段(例如 score_by_rank 的结果),无法表达综合分
- 无法实现 rank-after-post(综合分后的二次排名)

代码层面对应两类约束:

1) **编译期语义限制**: `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` 对 rank/call_by 引用范围做了硬限制。
2) **运行时固定顺序**: `src/scalim/execution/derived_outputs.py:RankedGroupByAggregator.finalize_rows` 固定为 metrics → rank → top_k/sort → post。

本变更将把 aggregate 场景下的“排名/派生字段”统一升级为依赖驱动的 DAG,并引入 `compute` 以更稳定、更符合 DSL 心智的方式表达简单派生。

约束:

- **运行时兼容 Python 3.6**(`src/scalim/`)
- **结果确定性**: 输出顺序与排名结果应稳定可预测(同输入与同配置)
- **安全边界**: `compute` 必须复用现有安全表达式引擎; `call_by` 继续受 allowlist(allowed_modules/allowed_functions) 约束

## Goals / Non-Goals

**Goals:**

- 将 `outputs.*.aggregate.fields` 中的 rank/post 字段统一视为“聚合后派生字段 DAG”,允许它们相互引用并以拓扑序执行
- 支持 `rank.by` / `rank.order_by` 引用聚合后派生字段,覆盖 rank-by-ratio 与 rank-after-post
- 放开 post 字段对 post 字段的依赖,覆盖 “all_integral = s1 + s2 + ...”
- 在 aggregate 中引入 `compute: <expression>` (安全表达式),用于 ratio/加权/求和等简单派生,并允许被 rank/post 引用
- 保持 `top_k` 行为可预测,并尽量保持旧行为的默认语义(非必要不引入破坏性变化)
- 提供清晰、可操作的编译期诊断(未知引用、循环依赖链路)

**Non-Goals:**

- 不引入显式的 `aggregate.stages`/多阶段 DSL(本变更以 DAG 统一解决顺序问题)
- 不放开 `partition_by` 限制: 仍要求为 `group_by` 子集
- 不允许聚合后派生字段直接引用“明细行字段”(聚合前状态不可用,仍以聚合输出行字段为引用边界)
- 不改变 c13 已解决的“derived output 输出编排(select + order)”语义(该能力已独立落地)

## Decisions

### 1) 依赖模型: finalize 计算按 DAG 驱动

将 `aggregate.fields.<out_field_id>` 中的下列字段统一纳入 DAG:

- 排名字段: `row_number` / `rank` / `dense_rank`
- 派生字段: `score_by_rank` / `call_by` / `compute`

依赖提取规则(编译期):

- rank: 依赖 `by` + `order_by`(若未提供 `order_by`,等价依赖 `by`)
- score_by_rank: 依赖 `rank_field`
- call_by: 依赖 `parse_call_by(...).field_names`
- compute: 依赖 `extract_compute_dependencies(expression)`

所有依赖必须引用 `aggregate.group_by` 或 `aggregate.fields` 中声明的字段 ID。未声明引用在编译期报错。

### 2) 循环依赖检测与稳定拓扑序

编译期构建有向图并检测环,在存在环时给出“依赖链路”提示(便于定位哪几个字段互相引用导致不可计算)。

对无环图,采用**稳定拓扑序**:

- 在可选节点集合中,按 `out_field_id` 排序选择下一个节点(保证确定性)
- 这使得“无依赖关系的字段”也能稳定输出与稳定执行(减少心智负担)

### 3) `top_k` 与输出顺序的行为保持策略

现有实现会在所有 rank 字段计算完成后:

1) 选择一个 “primary rank”(优先选带 top_k 的 rank;否则按 id 稳定选一个)
2) 按该 rank 的 `order/order_by` 对行做稳定排序并应用 `top_k`(若配置)
3) 再逐行执行 post 字段

为尽量保持旧语义并避免额外的“top_k 之外”失败扩散,本变更采用分段执行:

- **阶段 A(全量行)**: 计算 rank 字段所需的上游依赖字段(例如 ratio / all_integral),并计算所有 rank 字段
- **阶段 B(全量行)**: 选择 primary rank 并应用 top_k/sort(保持现有行为)
- **阶段 C(过滤后行)**: 计算其余派生字段

该策略的关键 trade-off:

- 当某个派生字段被 rank/order_by 依赖时,必须在 top_k 之前对全量行计算(这是 gap01/03 的必要行为变化)。

### 4) `compute` 的安全边界与推荐用法

`aggregate.fields.*.compute` 复用 `SecureComputeEngine`:

- 仅允许安全表达式(算术/比较/安全内建函数等)
- 变量名为聚合输出行字段 ID(例如 `sum_a`, `ratio_rank`)
- 不提供任意 Python 执行能力(与 `call_by` 的逃生阀定位互补)

文档与 hover 中将明确:

- 简单派生优先 `compute`
- 复杂逻辑或需要复用既有函数时使用 `call_by`(继续受 allowlist 约束)

### 5) 文档/生成边界与 drift gate

SSOT 与生成边界:

- YAML schema/hover SSOT: `src/scalim/dsl/by_yaml/schema_dsl/models/*.py`(禁止手改任何 `.gen.` 文件与 injected blocks)
- 如需刷新 docs-site 的 schema reference 或注入区块,统一运行 `just gen-docs`

验收与 drift gate:

- 变更实现后应通过 `just qa`(包含 schema drift/py36/示例/前端构建等门禁)
- OpenSpec 工件应通过 `just openspec-check`

## Risks / Trade-offs

- [行为变化] 过去不允许的引用在编译期放开后可能暴露“隐藏的循环依赖/缺失字段” → 提供循环链路诊断与缺失依赖报错
- [性能] DAG 可能迫使部分派生字段在 top_k 前对全量行计算 → 分段执行(A/B/C)减少不必要的 post 计算
- [确定性] DAG 若无稳定 tie-break 可能导致执行顺序漂移 → 采用按 `out_field_id` 的稳定拓扑序
- [安全] compute 若实现不当可能扩大表达式能力边界 → 复用既有 `SecureComputeEngine` 与依赖提取/校验逻辑

## Migration Plan

- 默认无需迁移: 旧的 aggregate 写法继续生效
- 推荐迁移: 将可表达为表达式的 `call_by` 逐步升级为 `compute`(更少 allowlist/更少外部函数依赖)
- 代码/文档更新后运行 `just gen-docs` 与 `just qa` 确保无 drift 与行为回退

## Open Questions

- `aggregate.compute` 是否需要允许自定义安全函数映射(类似顶层 compute 可配置 allowed_function_map)？本变更默认仅允许内建安全函数,如需要再以单独变更引入。
