> Status (2026-03-11): 已实现(v1 IR/Python-only).本文档保留为设计与约束说明;实现完成后用于回溯默认策略与边界。

## Context
需要在一次运行内产出“详情 + 分析/汇总”多份结果,并支持写入同一报表容器(多 sheet)或拆分为独立输出.同时要求保留现有单输出行为与性能特性,且 v1 仅通过 IR/Python 进行配置.

## Downstream Patterns (Survey → Framework Concepts)

需求侧（以 ET 迁移为主）多 sheet 的现实形态可以抽象为 7 类 sheet（覆盖绝大多数报表）：

1) **DetailSheet（明细流）**
- 每行一条业务事实（订单/用户/交易）；列多、行可能非常大；通常必须支持流式写入。

2) **FilteredDetailSheet（过滤子明细）**
- 与 Detail 同源，但按规则过滤（产品类型/状态/快付与否等），输出子集明细；仍倾向流式写入。

3) **SummarySheet（维度汇总）**
- 从明细流聚合 `group_by` 产出每组一行（行数不大）；常见指标可增量计算（count/sum/min/max/count_true）。

4) **RankedSummarySheet（带排名的汇总）**
- SummarySheet + 全局排序/排名/积分；通常需要“先聚合再排名”两阶段（或 finalize 后处理）。

5) **AuditSheet（审计/异常清单）**
- 用于对拍与解释口径：缺失映射、排除用户、异常订单等；常是 ID 清单或带 reason 的明细；倾向流式写入。

6) **MetaSheet（运行参数/运行信息）**
- 记录统计区间、过滤条件摘要、版本/配置 hash、各 sheet 行数/耗时等，保证可解释可复现；对双跑对拍非常关键。

7) **MultiRootSheets（多根数据源的 sheet 集合）**
- 每张 sheet 来自独立数据源/独立 demand；workbook 作为容器，不强行把所有根源塞进一个 main_source。

这 7 类并不要求在 v1 作为 DSL 的强类型出现，但有助于约束“最小能力边界”与测试矩阵。

### Legacy Anti-Patterns To Avoid (Explicit Guardrails)

需求侧现有实现里反复出现的一些问题，建议在框架层用默认行为“钉死”：

- **内存模型**：先攒全量 rows 再写 Excel（多 sheet 叠加后更容易 OOM）。
- **命名冲突**：重复 sheet 名不 fail-fast，导致静默覆盖、难以对拍。
- **header/rows 污染**：header list 与 rows 混在同一结构里，或被 `extend` 复用污染，导致后续 sheet header/数据错位。
- **顺序不稳定**：输出顺序依赖 dict/迭代顺序，导致 compare 误报与不确定性。

## Goals / Non-Goals
- Goals:
  - 单次运行支持多输出目标(详情/汇总)
  - 支持增量聚合,避免加载全部详情数据
  - 支持同一容器多逻辑输出与独立输出
  - 不中断既有单输出行为与事件顺序
- Non-Goals:
  - v1 不新增 YAML DSL 配置(仅评估影响)
  - v1 不强制引入外部依赖或分布式组件

## Options Considered
1) **输出组合器 + 增量聚合器(推荐方向)**
   - 运行期维护多个输出目标,详情输出照常写入;派生输出通过增量聚合器在 batch/row/column 粒度累计并在结束时输出.
   - 优点: 单次运行完成;可控内存;与现有运行模式贴合.
   - 缺点: 需要定义聚合接口与失败策略;并行模式一致性需要约束.

2) **两阶段执行(详情 → 汇总)**
   - 第一阶段生成详情;第二阶段读取详情进行汇总,可在同一运行序列中自动触发.
   - 优点: 聚合逻辑简单;与既有 sink 解耦.
   - 缺点: 需要中间落盘或完整内存;端到端耗时增加.

3) **纯后处理工具(离线聚合)**
   - 运行结束后用独立工具/脚本聚合.
   - 优点: 最低侵入.
   - 缺点: 无法满足“单次运行交付”与多输出一致性.

## Decisions
- Decision: 采用“输出组合器 + 增量聚合器”为主方案,并保留“二阶段执行”作为兜底模式(适用于列式/超大数据场景).
- Decision: v1 仅提供 IR/Python 配置入口,不改动 YAML DSL;文档说明潜在映射.
- Decision: 同一容器内输出名称冲突时直接拒绝,避免隐式改名掩盖问题.
- Decision: failure policy 默认 `all_fail`(任一输出失败即 run 失败);同时支持 `primary_only`(仅主输出失败才失败,派生输出失败会被标记并写入 meta/audit).
- Decision: `adaptive` 下允许内置派生聚合(交换律/结合律指标,且 finalize 在单线程执行);自定义聚合器默认要求 `parallel_mode=\"seq\"`(否则 fail-fast),避免非确定统计.

## Implementation Priorities (When Resumed)

本 change 重新开启时，建议按“先容器与健壮性，再派生能力”的顺序推进，避免把 DSL 设计绑死在早期实现细节上：

1) **Workbook 容器 + 多 sheet 流式写入**
- 支持单 workbook 多 sheet 的输出组合；每个 sheet 可独立 header/rows；默认 sheet 名冲突 fail-fast。
- 输出顺序稳定可控（便于 compare）。

2) **同源明细流多路分发（router/tee）**
- 明细只跑一次；多张 Detail/FilteredDetail/Audit 同时消费同一 row stream。
- 为 summary/audit/meta 采集必要的计数与诊断信息。

3) **派生汇总：增量聚合 + finalize 后处理**
- 先落“可增量”指标集合（count/sum/min/max/count_true），保证常见 SummarySheet 可 streaming。
- RankedSummary 允许 finalize 后排序/排名（或二阶段兜底），明确哪些指标必须 finalize/保留 state。

4) **Meta/Audit 标准化**
- 统一的 meta sheet（运行参数、行数、耗时、版本/配置 hash 等）与基础 audit（例如重复 sheet 名/写入失败/聚合冲突）的事件对齐。

5) **MultiRootSheets**
- workbook 允许多个 root demand，并把输出路由到不同 sheet；避免“一个 main_source 绑所有 SQL”。

## Risks / Trade-offs
- 内存压力: 聚合器状态可能增长 → 需要批次级累计、稀疏化/分桶、或可选落盘策略.
- 并行一致性: 并行模式可能导致聚合顺序与统计非确定 → 需要清晰限制或隔离.
- 输出顺序: 多输出写入顺序需固定,避免同一容器内不一致.

## Migration Plan
- 评估对单输出路径的兼容性影响;如需迁移,提供清晰的迁移说明.
- 逐步引入新的输出组合与派生输出配置;不影响旧用法.

## Open Questions
- 派生输出的最小聚合接口(聚合函数签名、生命周期)如何定义才足够通用?
- 同一容器多输出的命名/冲突策略如何约束?
- 并行模式下派生输出是否必须强制隔离或禁用?
- 失败策略是否需要默认值? 若需要,在调研后确定.
- 不可增量指标的精确与近似策略如何形成默认推荐?

## Reference Examples

> 注意：以下 YAML 片段仅用于表达“概念形态”，不代表本 change 会立即扩展 YAML DSL。

### MVP-A: 单明细流，分发多 sheet（Detail/FilteredDetail/Summary/Audit/Meta）
```yaml
container:
  type: workbook
  path: report.xlsx

datasets:
  detail:
    demand: detail_wide_table.demand.yaml  # 一次跑出 canonical rows

sheets:
  - name: 明细
    from: detail
    kind: detail
    select: [order_id, user_id, pay_datetime, product_type]
    write_mode: stream

  - name: 快付-应走
    from: detail
    kind: filtered_detail
    where:
      call_by: "myapp.filters:should_quick"  # 概念: 复用 allowlist/安全引用机制,避免引入任意表达式语言
    select: [order_id, custom_service_name]
    write_mode: stream

  - name: 客服汇总
    from: detail
    kind: summary
    aggregate:
      group_by: [custom_service_id, custom_service_name, group_name]
      metrics:
        paid_order_cnt: {op: count, field: order_id}
        should_quick_cnt: {op: count_true, field: should_quick}
        quick_cnt: {op: count_true, field: quick}
    post:
      rank_by: [paid_order_cnt desc]
    write_mode: finalize

  - name: 标签排除用户
    from: detail
    kind: audit
    where:
      call_by: "myapp.filters:excluded_by_tag"  # 概念
    select: [user_key, exclude_reason]
    write_mode: stream

  - name: 运行参数
    kind: meta
    rows:
      - [start_datetime, "..."]
      - [end_datetime, "..."]
      - [detail_total_rows, 123456]
```

### MVP-B: 多根数据源 sheet（MultiRootSheets）
```yaml
container:
  type: workbook
  path: report.xlsx

sheets:
  - name: 总体
    demand: total_view.demand.yaml

  - name: 渠道
    demand: channel_view.demand.yaml

  - name: 客服
    demand: service_view.demand.yaml
```

### Example: “详情 + 汇总”派生输出(概念 API, v1 IR/Python-only)
```python
# 目标:
# - 详情: 每行订单明细写入 detail.csv
# - 汇总: 按 supplier_id 聚合 sum(profit)/sum(amount) 写入 summary.csv

from collections import defaultdict

from IMPL_ROOT.sinks.sink_base import IRowSink, ISink


class SupplierProfitRateAgg(IRowSink):
    def __init__(self, out_sink: ISink) -> None:
        self._out_sink = out_sink
        self._sum_profit = defaultdict(float)
        self._sum_amount = defaultdict(float)

    def write_row(self, row):  # RowData: Dict[str, Any]
        sid = row.get("supplier_id")
        if sid is None:
            return
        self._sum_profit[sid] += float(row.get("profit") or 0.0)
        self._sum_amount[sid] += float(row.get("amount") or 0.0)

    def close(self) -> None:
        summary_rows = []
        for sid, amount in self._sum_amount.items():
            profit = self._sum_profit.get(sid, 0.0)
            rate = (profit / amount) if amount else None
            summary_rows.append({"supplier_id": sid, "profit_rate": rate})
        self._out_sink.write_batch(summary_rows)
        self._out_sink.close()


# 运行期通过“输出组合器”把明细 sink 与聚合器同时挂到同一次 run.
# sink = TeeRowSink(detail_sink, SupplierProfitRateAgg(summary_sink))
```

### Example: 二阶段兜底(同一次 run 的序列,但非增量)
```text
stage 1: 跑 demand -> 产出 detail(落盘)
stage 2: 读取 detail -> 计算 summary -> 写出 summary

优点: 聚合实现简单,与 sink 解耦
缺点: 需要中间落盘或全量内存,端到端耗时更高
```

### Example: 同一容器多逻辑输出的命名冲突(应拒绝)
```text
workbook.xlsx:
  - sheet "detail"
  - sheet "detail"   # 冲突 -> fail-fast,返回明确错误
```
