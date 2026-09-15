<div align="center">
  <img src="docs/assets/logo.svg" alt="logo" width="60%">

  # Scalim
</div>

| - | - |
| --- | --- |
| 库分发 | `scalim` [![PyPI version](https://img.shields.io/pypi/v/scalim?logo=pypi&logoColor=white&style=flat-square)](https://pypi.org/project/scalim/) [![Python versions](https://img.shields.io/pypi/pyversions/scalim?logo=python&logoColor=white&style=flat-square)](https://pypi.org/project/scalim/)<br>`scalim-cli` [![PyPI version](https://img.shields.io/pypi/v/scalim-cli?logo=pypi&logoColor=white&style=flat-square)](https://pypi.org/project/scalim-cli/) [![Python versions](https://img.shields.io/pypi/pyversions/scalim-cli?logo=python&logoColor=white&style=flat-square)](https://pypi.org/project/scalim-cli/)<br>`scalim-yaml-dsl-lsp` [![PyPI version](https://img.shields.io/pypi/v/scalim-yaml-dsl-lsp?logo=pypi&logoColor=white&style=flat-square)](https://pypi.org/project/scalim-yaml-dsl-lsp/) [![Python versions](https://img.shields.io/pypi/pyversions/scalim-yaml-dsl-lsp?logo=python&logoColor=white&style=flat-square)](https://pypi.org/project/scalim-yaml-dsl-lsp/) |
| 文档生成器 | [![Zensical](https://img.shields.io/badge/docs-Zensical-526CFE?style=flat-square)](https://zensical.org/docs/) |
| 项目工具 | [![uv](https://img.shields.io/badge/uv-managed-6A2C70?logo=uv&logoColor=white&style=flat-square)](https://github.com/astral-sh/uv) [![ruff](https://img.shields.io/badge/ruff-linted-D7FF64?logo=ruff&logoColor=111111&style=flat-square)](https://github.com/astral-sh/ruff) [![basedpyright](https://img.shields.io/badge/basedpyright-checked-3B82F6?style=flat-square)](https://github.com/DetachHead/basedpyright) [![pnpm](https://img.shields.io/badge/pnpm-workspace-F69220?logo=pnpm&logoColor=white&style=flat-square)](https://pnpm.io/) |
| 配套前端 | [![Svelte](https://img.shields.io/badge/Svelte-frontend-FF3E00?logo=svelte&logoColor=white&style=flat-square)](https://svelte.dev/) [![Vite](https://img.shields.io/badge/Vite-built-646CFF?logo=vite&logoColor=white&style=flat-square)](https://vite.dev/) |


# 简介

**Scalim** 是一个基于数据源加载和字段依赖关系的数据编排框架，通过统一的方式控制内存占用和资源调度，简化性能优化和开发。

对于复杂大宽表的业务报表：从多个数据源取数，按关系组合，计算派生字段，再写成 CSV 或 XLSX。源表很宽、内存又容易吃紧时，它通常更有用。

如果只是临时改一份小 CSV，pandas 往往更直接。Scalim 是在规则开始变多、报表要反复跑时才值得引入的。报表可以写成 YAML，也可以直接在 Python 里定义。

下面三个「第一口」与 `just notebook` 打开后的主线教程 `demo_big_data_report` 是**同一条链路**（代码/YAML 都从主线章节投影，不是第二套例子）：

| 第一口 | 主线章节 |
| --- | --- |
| Python 写需求 | `chapters_of_ir/ch010_basics.py` |
| YAML DSL 写需求 | `chapters_of_yaml_dsl/ch005_yaml_dsl_min.py` |
| 为什么省内存 | `chapters_of_ir/ch020_memory_compare.py` |

**可以用 Python 编写需求**

<!-- BEGIN AUTOGEN:readme-min-python -->
以下代码逐 cell 投影自主线章节（同一份真相，打开 notebook 即可就地重跑）：

```python
import marimo as mo

from scalim_misc.notebook_support.pathing import ensure_repo_root_on_sys_path

repo_root = ensure_repo_root_on_sys_path(__file__)
_ = repo_root

from scalim.execution.engine import ScalimEngine
from scalim.execution.runtime_bindings import RuntimeBindings
from scalim.planning import PlanBuilder
from scalim.sinks.memory import InMemoryRowDataSink
from scalim.spec.ir import (
    CallBySpecIr,
    CallByValueIr,
    DemandIr,
    DerivedFieldIr,
    FieldIr,
    MainSourceIr,
    RuntimeHandleIdIr,
)
from scalim_misc.notebook_support.chapter_result import make_chapter_result, render_checks

def load_orders():
    return [
        {"order_id": 1, "amount": 10.0},
        {"order_id": 2, "amount": 20.5},
        {"order_id": 3, "amount": 7.0},
    ]

def calc_amount_x2(amount):
    return float(amount) * 2

orders = MainSourceIr(source_id="orders", loader_ref=RuntimeHandleIdIr(handle_id="orders.loader"))
demand = DemandIr.from_irs(
    sources=[],
    main_source=orders,
    fields=(
        FieldIr(field_id="order_id", name="订单ID", source_id=orders.source_id),
        FieldIr(field_id="amount", name="金额", source_id=orders.source_id),
        DerivedFieldIr(
            field_id="amount_x2",
            name="金额*2",
            dependencies=("amount",),
            call_by=CallBySpecIr(
                reference=RuntimeHandleIdIr(handle_id="amount_x2.calculator"),
                kwargs=(("amount", CallByValueIr(kind="field", value="amount")),),
                field_names=("amount",),
            ),
        ),
    ),
    name="demo_big_data_report_ch010",
)

plan = PlanBuilder(demand).build()
runtime_bindings = RuntimeBindings(
    main_source_loaders={"orders": load_orders},
    derived_calculators={"amount_x2": calc_amount_x2},
)

engine = ScalimEngine(
    demand=demand,
    plan=plan,
    runtime_bindings=runtime_bindings,
    batch_size=1000,
    parallel_mode="seq",
)
sink = InMemoryRowDataSink()
engine.run(sink=sink)
rows = list(sink.get_data())

expected_rows = [
    {"order_id": 1, "amount": 10.0, "amount_x2": 20.0},
    {"order_id": 2, "amount": 20.5, "amount_x2": 41.0},
    {"order_id": 3, "amount": 7.0, "amount_x2": 14.0},
]
keys = ("order_id", "amount", "amount_x2")
actual_rows = [{k: row.get(k) for k in keys} for row in rows]
mo.vstack(
    [
        mo.md("**期望 vs 实际**(派生字段 `amount_x2 = 金额 * 2`):"),
        mo.ui.table(
            [{"kind": "期望", **row} for row in expected_rows] + [{"kind": "实际", **row} for row in actual_rows],
            selection=None,
        ),
    ]
)

checks = {
    "运行 3 行假数据": len(rows) == 3,
    "期望行完全一致": actual_rows == expected_rows,
}
render_checks(checks)
passed = bool(all(checks.values()))
summary = "rows={} amount_x2[0]={}".format(len(rows), rows[0].get("amount_x2") if rows else None)

# 对拍期望(教学 payload;headless 可经 details 键定位)
expected = {"rows": 3, "amount_x2_first": 20.0}
print("expected:", expected)

chapter_result = make_chapter_result(
    passed=passed,
    summary=summary,
    details={
        "expected": expected,
        "rows": len(rows),
        "sample": rows[0] if rows else None,
        "expected_rows": expected_rows,
        "actual_rows": actual_rows,
        "checks": {k: bool(v) for k, v in checks.items()},
    },
)
```

- 代码：[`notebooks/marimo/demo_big_data_report/chapters_of_ir/ch010_basics.py`](./notebooks/marimo/demo_big_data_report/chapters_of_ir/ch010_basics.py)
- 主线第一章：loader → `DemandIr` → `Plan` → `Engine` → 对拍；在仓库中可用 `just examples` 运行，也可用 `just notebook` 打开
<!-- END AUTOGEN:readme-min-python -->

**也可以用 YAML DSL 配置需求**

<details>
<summary>查看 YAML 示例</summary>

<!-- BEGIN AUTOGEN:readme-min-yaml -->
```yaml
# yaml-language-server: $schema=../../../../../src/scalim/dsl/yaml_dsl/schema/demand.gen.json
# 最小可跑需求（README 第一口 · ecommerce 主线的两源切片）：
# 主源 orders + 维表 payments 单级关联 + 一个派生字段 + 一个 csv 输出。

name: min_report
description: |
  最小电商订单报表: 订单 -> 支付方式(单级关联) + 派生字段 总金额

main_source:
  source_id: orders
  loader: myapp.loaders:load_orders
  fields:
    order_id:
      name: 订单ID
    amount:
      name: 金额
    pay_id:
      name: 支付ID

sources:
  payments:
    loader: myapp.loaders:load_payments
    key: id
    params:
      ids: {$keys: {as: set}}
    fields:
      method:
        name: 支付方式
        extract: payment_method
        relation: orders_to_payments

relations:
  orders_to_payments:
    steps:
      - from: orders.pay_id
        to: payments.id

fields:
  total_amount:
    name: 总金额
    compute: "amount * 2"

outputs:
  - name: detail
    to: {file: detail_csv}
    write: {header_fields_output_by: name}
    fields: [order_id, method, total_amount]

resources:
  files:
    detail_csv:
      csv_file:
        path: ./output
```

> 把 `myapp.loaders` 换成你的加载函数所在模块。这份示例会在仓库里自动运行。

- 代码：[`notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch005_yaml_dsl_min.py`](./notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/ch005_yaml_dsl_min.py)
- 最小 YAML 章节：`compile()` 语义校验 + `run()` 取行对拍；在仓库中可用 `just examples` 运行，也可用 `just notebook` 打开

- 完整配置：[`min_report.yaml`](./notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/min_report.yaml)
<!-- END AUTOGEN:readme-min-yaml -->

</details>

## 快速上手

```bash
# 加入到你的项目
uv add scalim
```

```bash
# 加入到你的环境
uv pip install scalim
```

```bash
# 交互式教程（需要先 clone 仓库 并且需要安装好 https://github.com/casey/just）
just notebook
```

运行库支持 Python 3.10 及以上版本（支持窗口与演进见 [ROADMAP](./ROADMAP.md)）。仓库中的交互式教程和文档工具同样需要 Python 3.10+。

<p align="center">
  <img src="docs/assets/meme.webp" alt="meme" width="100%">
</p>

## 主要特性

- **多种编写方式**: 支持直接用 `Python` 描述计算逻辑,也支持用 `YAML DSL` 写配置,配套 JSON Schema 补全/校验 + `scalim-cli` 语义校验 + LSP/IDE 集成,写配置时更容易补全、检查和落地

- **多种写入支持**: 支持批量执行、流式输出和行式/列式 sink,方便在吞吐、内存和输出形式之间做取舍

- **方便集成AI开发环境**: 支持 [agent skill](./agentdev/skills/) 集成

- **可视化在线工具**: 有可视化在线工具做回放和排查,执行计划、事件流和 trace 都能接起来看

- **可配置自适应并发执行**:  大部分情况无需手动优化 — 运行时自动为你找到最优执行路径
  - 自动识别并发机会:基于依赖图的拓扑分析
  - Fan-out/Fan-in 编排:独立任务并行执行,依赖任务串行化
  - 资源感知调度:根据任务数量、数据量、CPU 资源动态调整
  - 快速失败回退:并发失败自动降级到串行模式

- **生产级可观测性**: 16+ 种事件类型 + 4 种预设 Observer
  - PerformanceObserver:吞吐量、延迟统计
  - MemoryOptimizationObserver:内存释放追踪
  - RelationObserver:关系查找命中率
  - ExecutionTraceObserver:完整执行链路追踪

- **延迟计算非必要字段**
  当某个派生字段仅用于最终输出，且未被其他字段或数据加载环节依赖时，Scalim 会将其推迟到写出前再计算。配置中无需额外开关；有下游依赖的字段则仍按正常顺序计算。

- **低内存模式**: 内置字段剪枝、字段释放和行级释放,尽量只保留当前批次真正还要用的数据,减少上下文占用(内存占用)

## 性能

与 pandas / polars 惯用法（DataFrame 全量物化 + 向量化派生 + 库内写出）的同任务端到端对比，覆盖七种典型表（报表宽表 / 大宽表 csv+xlsx / 大长表 / 超多列宽表 / 链式边界 / 多源关联）：

<!-- BEGIN AUTOGEN:readme-memory-chart -->
**① 行数扫参**（1k → 1M · 20 派生列 · csv，折线看趋势）：

| 内存 | 耗时 |
|------|------|
| ![峰值内存随行数变化：Scalim 保持约 30 MiB 平线](docs/assets/readme/external-baseline-sweep.svg?v=3) | ![总耗时随行数变化](docs/assets/readme/external-baseline-sweep-time.svg?v=3) |

复现：`just bench-external-probes --runs 3` · 脚本 [run_probes.py](./docs/doc/releases/repro/external-baseline/run_probes.py) · 数据 [external-baseline-0.10.probes.json](./docs/doc/assets/data/external-baseline-0.10.probes.json)

**② 七种典型表**（倍数 = 相对 pandas 的比值，1.0× 虚线为持平，条尾含绝对值）：

| 内存 | 耗时 |
|------|------|
| ![七种典型表的峰值内存对比](docs/assets/readme/external-baseline-matrix.svg?v=3) | ![七种典型表的总耗时对比](docs/assets/readme/external-baseline-matrix-time.svg?v=3) |

复现：`just bench-external --runs 3` · 脚本 [run_ab.py](./docs/doc/releases/repro/external-baseline/run_ab.py) · 数据 [external-baseline-0.10.json](./docs/doc/assets/data/external-baseline-0.10.json) · 完整表格与交互图表：[外部基线对比](./docs/doc/benchmark/external-baseline.md)
<!-- END AUTOGEN:readme-memory-chart -->

- **内存（scalim 主定位）**：全部形状峰值 RSS 保持 **30–56 MiB 平台**，与表面积无关；对照 pandas 为 1/4–1/35，对照 polars 为 1/7–1/37。polars 内存并不总是更低——csv 大导出与关联场景其峰值反高于 pandas。
- **时间（分场景取舍）**：xlsx 报表场景优于 pandas（0.61–0.65×）、约为 polars 的 1.6×；csv 大导出时间让给 pandas/polars（2–96×），换峰值内存 1/9–1/37；关联查询（本机 SQLite 真实 IO）时间 7.2×、内存 1/4。
- **adaptive ≈ seq**：单数据流报表 demand 无并行机会，自适应并发不劣化也无收益；其收益场景是多任务编排。

以上数字的条件与边界（务必同读）：scalim **0.10.3** vs pandas **2.3.3** vs polars **1.42.1**、Python 3.10.18、单机合成数据（关联 shape 为本机 SQLite 真实 IO）、每场景 **3/5 次**取 median、读回 golden 校验（108/108 通过）、薄算术派生函数；**不构成通用加速、真实业务基准或跨机器 SLA**。完整表格、形状明细、复现命令与数据 JSON 见 [外部基线对比](./docs/doc/benchmark/external-baseline.md)；扫参曲线、派生函数复杂度、慢源分片并行与 0.10 历史 Python 3.6 兼容边界（0.20 起 floor 为 3.10）的交互图表也在该页。

<details>
<summary>naive vs Scalim 内存代理图（小规模相对增量口径）的代码、数据与重跑方法</summary>

- 测量口径：**相对 RSS 增量代理**（naive = 1.0）——同一台机器上一次运行前后进程 RSS 的变化，不是运行中的最高内存；不能跨机器比较绝对值，也不构成 SLA 承诺。代理图资产：[`memory-compare.svg`](./docs/assets/readme/memory-compare.svg) · [`memory-compare-scenarios.svg`](./docs/assets/readme/memory-compare-scenarios.svg)。
- 默认旋钮在 [`ch020_memory_compare.py`](./notebooks/marimo/demo_big_data_report/chapters_of_ir/ch020_memory_compare.py) 的「旋钮」cell：1,500 行、48 个字段，每批 150 行（CI 固定小 scale 保证秒级；本地改常量即可放大重跑）。
- 图表内容来自 [`memory-compare.json`](./docs/doc/assets/data/memory-compare.json)。仓库会确认示例能运行，但不会要求某个固定的内存比例。
- 重跑：`SCALIM_EXAMPLES_SUITES=demo_big_data_report just examples`，然后 `just gen-readme-examples` 更新图表。

<!-- BEGIN AUTOGEN:readme-naive-baseline -->
- 代码：[`notebooks/marimo/demo_big_data_report/chapters_of_ir/ch020_memory_compare.py`](./notebooks/marimo/demo_big_data_report/chapters_of_ir/ch020_memory_compare.py)
- 对比章节（naive 基线管线在 cells 内）；在仓库中可用 `just examples` 运行，也可用 `just notebook` 打开
<!-- END AUTOGEN:readme-naive-baseline -->

<!-- BEGIN AUTOGEN:readme-scalim-path -->
- 代码：[`notebooks/marimo/demo_big_data_report/chapters_of_ir/ch020_memory_compare.py`](./notebooks/marimo/demo_big_data_report/chapters_of_ir/ch020_memory_compare.py)
- 对比章节（scalim 窄字段管线在 cells 内）；在仓库中可用 `just examples` 运行，也可用 `just notebook` 打开
<!-- END AUTOGEN:readme-scalim-path -->

</details>

更多见 [参考文档](./docs/doc/index.md)。

## 质量保证

- 100% 核心逻辑测试覆盖率 (CI全覆盖), 将用户演示[`notebooks`](./notebooks/marimo/)作为集成测试辅助对拍验证主要场景
- 100% 核心逻辑类型注解, 使用 `basedpyright` 进行较为严格的类型检查
- 严格的 Ruff 检查和统一代码格式化
- 最低支持版本 `Python 3.10` 在 CI matrix 中完整回归（3.10–3.14；`typing-extensions>=4.4`）.
