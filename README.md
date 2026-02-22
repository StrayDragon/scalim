# Scalim

用纯 Python 构建的声明式数据流水线运行时 — **DSL 不可知**，**自适应并发**，**生产级可观测性**

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)
![Type Safety](https://img.shields.io/badge/types-pyright%20strict-blueviolet.svg)

## 核心特性

**声明式 IR（中间表示）**

用 Python 对象描述复杂的数据需求，而非命令式代码：

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

支持多级关联链（`orders → payments → countries`）、复合键、派生字段与自动循环依赖检测。

---

**自适应并发执行**

ScalimEngine 的 `adaptive` 模式会自动分析数据依赖图，智能决策并发策略：

- 自动识别并发机会：基于依赖图的拓扑分析
- Fan-out/Fan-in 编排：独立任务并行执行，依赖任务串行化
- 资源感知调度：根据任务数量、数据量、CPU 资源动态调整
- 快速失败回退：并发失败自动降级到串行模式

无需手动优化 — 运行时自动为你找到最优执行路径。

---

**生产级可观测性**

16+ 种事件类型 + 4 种预设 Observer：

- PerformanceObserver：吞吐量、延迟统计
- MemoryOptimizationObserver：内存释放追踪
- RelationObserver：关系查找命中率
- ExecutionTraceObserver：完整执行链路追踪

```python
observer = PerformanceObserver(config=PerformanceConfig(
    enable_loader_timing=True,
    enable_field_compute_timing=True
))
engine = ScalimEngine(observers=[observer])
```

---

**运行时防护机制**

内置 Guardrails 系统，提供策略模式错误处理（quiet / fast_fail），可自定义 Loader 级别的错误策略，实现细粒度容错控制。

## 快速开始

```bash
pip install scalim
just notebook  # 交互式教程
```

## 质量保证

- 100% 测试覆盖率（668 个测试用例）
- 基于 pyright 的严格类型检查（0 errors, 0 warnings）
- Ruff 全量规则通过
- Python 3.10+ 全版本支持

## 设计哲学

1. Core First：核心运行时与方言/CLI 解耦
2. Type Safety：完整的类型注解，支持静态分析
3. Observable：默认可观测，而非事后补丁
4. Extensible：通过 Hook/Observer/Policy 三大扩展点支持自定义
