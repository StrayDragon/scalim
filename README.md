<p align="center">
  <img src="docs/assets/logo.svg" alt="logo" width="100%">
</p>

| - | - |
| --- | --- |
| 库分发 | [![PyPI version](https://img.shields.io/pypi/v/scalim?logo=pypi&logoColor=white&style=flat-square)](https://pypi.org/project/scalim/) [![Python versions](https://img.shields.io/pypi/pyversions/scalim?logo=python&logoColor=white&style=flat-square)](https://pypi.org/project/scalim/) |
| 文档生成器 | [![Zensical](https://img.shields.io/badge/docs-Zensical-526CFE?style=flat-square)](https://zensical.org/docs/) |
| 项目工具 | [![uv](https://img.shields.io/badge/uv-managed-6A2C70?logo=uv&logoColor=white&style=flat-square)](https://github.com/astral-sh/uv) [![ruff](https://img.shields.io/badge/ruff-linted-D7FF64?logo=ruff&logoColor=111111&style=flat-square)](https://github.com/astral-sh/ruff) [![basedpyright](https://img.shields.io/badge/basedpyright-checked-3B82F6?style=flat-square)](https://github.com/DetachHead/basedpyright) [![pnpm](https://img.shields.io/badge/pnpm-workspace-F69220?logo=pnpm&logoColor=white&style=flat-square)](https://pnpm.io/) |
| 配套前端 | [![Svelte](https://img.shields.io/badge/Svelte-frontend-FF3E00?logo=svelte&logoColor=white&style=flat-square)](https://svelte.dev/) [![Vite](https://img.shields.io/badge/Vite-built-646CFF?logo=vite&logoColor=white&style=flat-square)](https://vite.dev/) |

# 简介

**Scalim** 是一个基于字段依赖和数据源加载关系的数据编排框架, 通过统一的方式控制内存占用和资源调度方案, 简化性能优化门槛和开发难度.

- 可以用 Python 编写需求

```python
DemandIr(
  source=SourceIr(name=”orders”, loader=load_orders),
  fields=[
    FieldIr(name=”order_id”, source_field=”order_id”),
    FieldIr(name=”total_amount”, source_field=”amount”,
      derive=lambda x: sum(x)),
  ],
  relations=[
    RelationIr(
      name=”payment”,
      source_key=”pay_id”,
      target=SourceIr(name=”payments”, loader=load_payments),
      target_key=”id”,
      bindings=[
        BindingIr(field=”method”, target_field=”payment_method”)
      ]
    )
  ]
)
```

- 也可以用 YAML DSL 配置需求

```yaml
name: orders_report

main_source:
  source_id: orders
  loader: load_orders
  fields:
    order_id:
      name: 订单ID

    # 主源字段，用于派生计算
    amount:
      name: 金额

    # 关联键字段
    pay_id:
      name: 支付ID

sources:
  payments:
    loader: load_payments
    key: id
    bind: {use_keys: {param: ids}}
    fields:
      method:
        name: 支付方式
        field: payment_method
        relation: *orders_to_payments

relations:
  orders_to_payments: &orders_to_payments
    steps:
      - from: orders.pay_id
        to: payments.id

fields:
  total_amount:
    name: 总金额
    compute: "sum(amount)"

output:
  format: csv
  path: ./output/orders_report.csv```
```

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
# 交互式教程
just notebook
```

## 主要特性

- **自适应并发执行**:  大部分情况无需手动优化 — 运行时自动为你找到最优执行路径
  - 自动识别并发机会:基于依赖图的拓扑分析
  - Fan-out/Fan-in 编排:独立任务并行执行,依赖任务串行化
  - 资源感知调度:根据任务数量、数据量、CPU 资源动态调整
  - 快速失败回退:并发失败自动降级到串行模式
- **生产级可观测性**: 16+ 种事件类型 + 4 种预设 Observer
  - PerformanceObserver:吞吐量、延迟统计
  - MemoryOptimizationObserver:内存释放追踪
  - RelationObserver:关系查找命中率
  - ExecutionTraceObserver:完整执行链路追踪
- **运行时防护机制**: 内置 Guardrails 系统,提供策略模式错误处理(quiet / fast_fail),可自定义 Loader 级别的错误策略,实现细粒度容错控制
- **低内存模式**: 内置字段剪枝、字段释放和行级释放,尽量只保留当前批次真正还要用的数据,减少上下文占用(内存占用)
- **多种编写方式**: 支持直接用 `Python` 描述计算逻辑,也支持用 `YAML DSL` 写配置, 配套可视化编辑器, `json schema` 校验和 `CLI` 工具, 写配置时更容易补全、检查和落地
- **多种写入支持**: 支持批量执行、流式输出和行式/列式 sink,方便在吞吐、内存和输出形式之间做取舍
- **方便集成AI开发环境**: 支持 [agent skill](./artifacts/skills/) 集成
- **可视化在线工具**: 有可视化在线工具做回放和排查,执行计划、事件流和 trace 都能接起来看

更多见 [参考文档](docs/doc/index.md)

## 质量保证

- 100% 核心测试覆盖率 (低于 100% 强制 CI 失败)
- 基于 pyright 的类型检查
- Ruff 全量规则通过

## 设计哲学

1. Core First:核心运行时与方言/CLI 解耦
2. Type Safety:完整的类型注解,支持静态分析
3. Observable:默认可观测,而非事后补丁
4. Extensible:通过 Hook/Observer/Policy 三大扩展点支持自定义
