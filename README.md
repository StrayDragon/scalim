<p align="center">
  <img src="docs/assets/logo.svg" alt="logo" width="100%">
</p>

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

**可以用 Python 编写需求**

<!-- BEGIN AUTOGEN:readme-min-python -->
- 代码：[`notebooks/marimo/example_readme_suite/support/min_python.py`](./notebooks/marimo/example_readme_suite/support/min_python.py)
- 章节：`notebooks/marimo/example_readme_suite/chapters/ch010_min_python.py`；在仓库中可用 `just examples` 运行，也可用 `just notebook` 打开
<!-- END AUTOGEN:readme-min-python -->

**也可以用 YAML DSL 配置需求**

<details>
<summary>查看 YAML 示例</summary>

<!-- BEGIN AUTOGEN:readme-min-yaml -->
```yaml
name: readme_min_yaml_report

main_source:
  source_id: orders
  loader: "myapp.loaders:load_orders"
  fields:
    order_id:
      name: 订单ID
    amount:
      name: 金额
    pay_id:
      name: 支付ID

sources:
  payments:
    loader: "myapp.loaders:load_payments"
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

- 完整配置：[`support/min_yaml_example.yaml`](./notebooks/marimo/example_readme_suite/support/min_yaml_example.yaml)
- 示例数据和运行脚本：[`support/min_yaml_loaders.py`](./notebooks/marimo/example_readme_suite/support/min_yaml_loaders.py) · [`support/min_yaml.py`](./notebooks/marimo/example_readme_suite/support/min_yaml.py)
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

运行库支持 Python 3.6 及以上版本。仓库中的交互式教程和文档工具需要 Python 3.10 及以上版本。

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

图里的数字是同一台机器上一次运行前后进程 RSS 的变化，不是运行中的最高内存，也不能直接和别人的电脑比较。

<!-- BEGIN AUTOGEN:readme-memory-chart -->
![本地内存变化对比：naive 和 Scalim](docs/assets/readme/memory-compare.svg)

![不同数据大小下的本地内存变化](docs/assets/readme/memory-compare-scenarios.svg)
<!-- END AUTOGEN:readme-memory-chart -->

<details>
<summary>查看内存比较的代码、数据复现方法</summary>

- 默认测试数据在 [`support/knobs.py`](./notebooks/marimo/example_readme_suite/support/knobs.py)：1,500 行、48 个字段，每批 150 行。
- 图表内容来自 [`chart_snapshot.json`](./notebooks/marimo/example_readme_suite/support/chart_snapshot.json)。仓库会确认示例能运行，但不会要求某个固定的内存比例。
- 想自己重跑，可以在仓库中执行 `SCALIM_EXAMPLES_SUITES=example_readme_suite just examples`，然后执行 `just gen-readme-examples` 更新图表。

<!-- BEGIN AUTOGEN:readme-naive-baseline -->
- 代码：[`notebooks/marimo/example_readme_suite/support/naive_baseline.py`](./notebooks/marimo/example_readme_suite/support/naive_baseline.py)
- 对比章节：`notebooks/marimo/example_readme_suite/chapters/ch030_memory_compare.py`；在仓库中可用 `just examples` 运行，也可用 `just notebook` 打开
<!-- END AUTOGEN:readme-naive-baseline -->

<!-- BEGIN AUTOGEN:readme-scalim-path -->
- 代码：[`notebooks/marimo/example_readme_suite/support/scalim_path.py`](./notebooks/marimo/example_readme_suite/support/scalim_path.py)
- 对比章节：`notebooks/marimo/example_readme_suite/chapters/ch030_memory_compare.py`；在仓库中可用 `just examples` 运行，也可用 `just notebook` 打开
<!-- END AUTOGEN:readme-scalim-path -->

</details>

更多见 [参考文档](./docs/doc/index.md)。

## 质量保证

- 100% 核心逻辑测试覆盖率 (CI全覆盖), 将用户演示[`notebooks`](./notebooks/marimo/)作为集成测试辅助对拍验证主要场景
- 100% 核心逻辑类型注解, 使用 `basedpyright` 进行较为严格的类型检查
- 严格的 Ruff 检查和统一代码格式化
- 兼容并回归验证最低版本 `Python 3.6` 除了语法检查外，还会在 `typing-extensions==4.1.1` 的隔离环境中验证。
