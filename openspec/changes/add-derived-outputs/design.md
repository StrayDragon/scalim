## Context
需要在一次运行内产出“详情 + 分析/汇总”多份结果,并支持写入同一报表容器(多 sheet)或拆分为独立输出.同时要求保留现有单输出行为与性能特性,且 v1 仅通过 IR/Python 进行配置.

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
