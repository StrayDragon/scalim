# numeric-type-loss — xlsx_file 数字类型丢失 MVP 复现

## 问题

`xlsx_file` book 路径在 workflow 中经过 CSV 中间层（`InMemoryCsvSink._normalize_csv_value()` → `str(value)`），
所有 Python 数字类型（`int`/`float`/`Decimal`/`bool`）被字符串化，导致最终 Excel 中数字列表现为文本。

`xlsx_memory`（sheetbook）路径使用 `InMemoryRows` 保留原始类型，**不受影响**。

## 场景覆盖

本 MVP 设计为**脱敏的支付报表场景**，镜像 ET Pay Order 项目的多 sheet 模式：

| 场景 | 文件 | 说明 |
|---|---|---|
| **A: 多 sheet（主场景）** | `workflow.yaml` | 3 demands → 3 个 sheet 写入同一 xlsx_file book，对应 Pay Order 的"明细 + 渠道维度 + 整体指标" |
| **B: 单 sheet（最小复现）** | `workflow_detail_only.yaml` | 1 demand → 1 sheet，最简复现路径 |

**数据边界情况覆盖** (`loaders.py`)：

| 类型 | 示例 | 说明 |
|---|---|---|
| `float` | `1299.00`, `0.0` | 标准浮点数 + 零值 |
| `int` | `2`, `0`, `1` | 整型 + 零值 |
| `Decimal` | `Decimal('158.00')` | 精确十进制 |
| `bool` | `True`, `False` | 布尔在 `to_numeric` 中被转为 `int`，但在 `xlsx_memory` 中保留为 `bool` |
| `None` | 折扣率、金额 | 可选字段缺失值，在数字列中合法 |
| 零值 | `0.0`, `0`, `False` | 零值不应被视为类型丢失 |

**Demand 字段处理** (`demand_a.yaml`)：

- 部分字段直接用 loader 返回的原始类型
- 部分字段通过 `call_by: loaders:to_numeric(value=...)` 处理
- 模仿真实业务的防御性编程，但**即使经过 `to_numeric`，xlsx_file 路径仍会 stringify**

## Workflow 依赖链

```
detail (root)  ──→  交易明细 sheet (float/int/Decimal/bool/None)
     │ depends_on
     ▼
channel        ──→  渠道维度 sheet (聚合 float/int)
     │ depends_on
     ▼
kpi            ──→  整体指标 sheet (float + bool)
```

每级 demand 同时写入 `report_workbook`（xlsx_file）和 `report_sheetbook`（xlsx_memory），
共 3 个 sheet × 2 本书 = 6 个 sheet 可供逐列对比。

## 文件结构

| 文件 | 说明 |
|---|---|
| `loaders.py` | 脱敏 loader 函数 + `to_numeric()` 工具 |
| `demand_a.yaml` | Demand A：交易明细 |
| `demand_b.yaml` | Demand B：渠道维度聚合 |
| `demand_c.yaml` | Demand C：整体指标 |
| `workflow.yaml` | 场景 A workflow：3 runs + xlsx_file / xlsx_memory 双 book |
| `workflow_detail_only.yaml` | 场景 B workflow：单 run + 双 book |
| `run.py` | 运行 + 逐列检查 + 汇总评分 |
| `repro-numeric-type-loss.py` | 底层 API 级复现（不依赖 YAML DSL，保留原样） |
| `README.md` | 本文档 |

## 用法

```bash
# 从仓库根目录
uv run python3 llmanspec/changes/c5-xlsx-file-numeric-type-loss/examples/numeric-type-loss/run.py
```

## 预期输出

```
场景 A:
  xlsx_file / 交易明细
    B2: '1299.0' (type=str)    <<< 数字类型丢失!
    C2: '0.85' (type=str)      <<< 数字类型丢失!
    ...
  xlsx_memory / 交易明细
    B2: 1299 (type=float)
    C2: 0.85 (type=float)
    ...

场景 B:
  (同场景 A 的明细 sheet, 最简路径)

汇总评分:
  场景A: 总数字列: 24 | 类型丢失: 24 | 类型保留: 0  (xlsx_file)
        总数字列: 24 | 类型丢失: 0  | 类型保留: 24 (xlsx_memory)
  场景B: 总数字列: 8  | 类型丢失: 8  | 类型保留: 0  (xlsx_file)
        总数字列: 8  | 类型丢失: 0  | 类型保留: 8  (xlsx_memory)

✅ 确认: xlsx_file 路径存在数字类型丢失, xlsx_memory 路径保留类型
```
