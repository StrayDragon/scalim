# demo_big_data_report

电商订单报表示例,作为 Scalim 框架的**集成测试**和**教程文档**.

## 核心特性

**所有执行 Scalim 的 demo 都内置对拍验证**,使用纯 Python 实现的对照组验证每一行每一个值的正确性.

## 业务场景

电商平台订单报表,覆盖多种关联类型:

| 关联类型 | 示例 | 说明 |
|----------|------|------|
| 单级关联 | orders → customers | 直接外键关联 |
| 单级关联 | orders → promotions | 可能为空(20%订单无促销) |
| 多级关联 | orders → products → categories | 2级链式关联 |
| 多级关联 | orders → warehouses → regions | 2级链式关联 |
| 复合键关联 | orders → region_pricing | (region_id, product_category_id) |
| 派生字段 | order_amount | quantity × unit_price × discount_rate |

## 快速开始

```bash
# region SCALIM-SKILL:example-full:run
# 运行主演示
marimo run demo_a0_main.py

# 运行教程
marimo run demo_a0_tutor.py
# endregion
```

## 文件结构

```
demo_big_data_report/
├── _loaders.py          # 电商数据加载器
├── _verification.py     # 对照组验证库
├── _shared.py           # IR 模型构建
├── demo_a0_main.py      # 主入口
├── demo_a0_tutor.py     # 全链路教程
├── demo_a1_plan_visualization.py  # 执行计划可视化
├── demo_b*.py           # Sink 演示
├── demo_c*.py           # 数据处理
├── demo_d*.py           # Hook/可观测
├── demo_d3_parallel_mode_compare.py  # seq vs adaptive + 纯Py基准三方对拍
├── demo_e*.py           # 调试工具
├── by_yaml_dsl/
│   └── ecommerce_report.yaml
└── README.md
```

## 对拍验证

每个 demo 内置验证,使用方法:

```python
from _verification import verify_scalim_output

# 执行 Scalim 后验证
vr = verify_scalim_output(results, target_fields)
print(vr)  # ✅ PASSED - 100/100 rows, 0 mismatches
assert vr.passed, vr.summary
```

验证库 (`_verification.py`) 完全不依赖 Scalim 框架,使用纯 Python 实现 Join 和计算逻辑作为对照组.

## 演示分组

| 字母 | 分组 | 说明 | 验证 |
|------|------|------|------|
| **a** | 基础入门 | 主入口、全链路教程、执行计划 | ✅ |
| **b** | Sink | 各种输出类型演示 | ✅ |
| **c** | 数据处理 | 外键转换、内存优化、字段转换 | ✅ |
| **d** | Hook | 性能监控、可观测性 | ✅ |
| **e** | 调试 | 关联诊断(仅分析配置) | - |

## 目标字段集

```python
from _shared import (
    TARGET_FIELDS_FULL,       # 全部 29 个字段
    TARGET_FIELDS_BASIC,      # 基础 5 个字段
    TARGET_FIELDS_RELATIONS,  # 关联 20 个字段
    TARGET_FIELDS_DERIVED,    # 派生 4 个字段
)
```
