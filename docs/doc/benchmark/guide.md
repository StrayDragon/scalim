# Benchmark 报告阅读指南

??? note "适用读者"
    - 需要阅读 pytest-benchmark/memray 报告的开发者/贡献者
    - 需要做性能分析与回归定位的同学

本文档介绍如何阅读和理解 `just bench` 和 `just bench-memray` 生成的性能报告.

---

## 1. 报告结构概览

运行 benchmark 后会生成两类报告:

1. **pytest-benchmark 时间报告** - 测量执行时间
2. **memray 内存报告** - 测量内存分配(仅 `just bench-memray`)

---

## 2. pytest-benchmark 时间报告

### 2.1 报告分组

测试按 `group` 标记分组显示,例如:

| 分组名 | 含义 |
|--------|------|
| `baseline` | 核心基准测试(纯 scalim 库) |
| `planning` | 计划构建阶段 |
| `pipeline` | 完整管道执行 |
| `hooks` | 带钩子/观察者的管道 |
| `dsl` | YAML DSL 解析执行 |
| `diagnostics` | 诊断/工具类操作 |

### 2.2 时间指标详解

```
Name (time in us)              Min          Max      Mean    StdDev    Median     IQR   Outliers  OPS (Kops/s)  Rounds  Iterations
---------------------------------------------------------------------------------------------------------------------------------
test_bench_plan_build     224.2870  13,547.7110  248.8369  288.6447  234.1455  8.8570     1;338        4.0187    2138           1
```

| 指标 | 含义 | 如何解读 |
|------|------|----------|
| **time in** | 时间单位 | `ns`=纳秒, `us`=微秒, `ms`=毫秒, `s`=秒 |
| **Min** | 最小执行时间 | 理想情况下的最佳性能 |
| **Max** | 最大执行时间 | 包含 GC、系统抖动等干扰 |
| **Mean** | 平均执行时间 | **主要参考指标**,用于比较 |
| **StdDev** | 标准差 | 越小越稳定,大则说明性能波动 |
| **Median** | 中位数 | 排除极端值的典型性能 |
| **IQR** | 四分位距 | 中间 50% 数据的分布范围 |
| **Outliers** | 异常值 | 格式 `a;b`,a=1σ外,b=1.5IQR外 |
| **OPS** | 每秒操作数 | = 1/Mean,越大越好 |
| **Rounds** | 运行轮数 | 自动校准,确保统计显著性 |
| **Iterations** | 每轮迭代数 | 通常为 1,极快操作会合并 |

### 2.3 括号中的相对比值

**每个指标列的括号数字表示相对于该组中该指标最小值的倍数**:

```
--------------------------- benchmark 'baseline': 2 tests ---------------------------
Name (time in us)                          Min                   Max              Mean
-------------------------------------------------------------------------------------
test_bench_scalim_only_plan_build      18.0240 (1.0)        656.4990 (1.0)     22.4283 (1.0)
test_bench_scalim_only_pipeline       667.5900 (37.04)    1,250.2490 (1.90)   690.8135 (30.80)
```

解读方式:

| 指标 | plan_build | pipeline | 含义 |
|------|------------|----------|------|
| Min | 18.02 (1.0) | 667.59 (37.04) | pipeline 的 Min 是 plan_build 的 37 倍 |
| Max | 656.50 (1.0) | 1250.25 (1.90) | pipeline 的 Max 是 plan_build 的 1.9 倍 |
| Mean | 22.43 (1.0) | 690.81 (30.80) | pipeline 的 Mean 是 plan_build 的 31 倍 |

**关键点**:
- `(1.0)` = 该列的基准值(该组中最小的)
- `(N)` = 是基准值的 N 倍
- 每列独立计算,所以同一行不同列的括号值可能差异很大
- 这让你能快速看出哪个测试在哪个指标上表现最好/最差

### 2.4 关键阅读技巧

1. **关注 Mean 和 Median**:Mean 用于比较,Median 反映典型情况
2. **检查 StdDev**:StdDev > Mean 的 50% 说明性能不稳定
3. **观察 Outliers**:大量异常值可能表示 GC 或系统干扰
4. **对比 OPS**:直观了解吞吐能力

---

## 3. memray 内存报告

### 3.1 报告结构

```
Allocation results for tests/bench/test_bench_examples.py::test_bench_yaml_dsl at the high watermark

         📦 Total memory allocated: 1.7MiB
         📏 Total allocations: 188
         📊 Histogram of allocation sizes: | █   |
         🥇 Biggest allocating functions:
                - construct_object:...yaml/constructor.py:100 -> 1.0MiB
                - _write_header:...sink_csv.py:123 -> 128.6KiB
```

### 3.2 内存指标详解

| 指标 | 含义 | 如何解读 |
|------|------|----------|
| **Total memory allocated** | 高水位内存总量 | 测试期间的峰值内存占用 |
| **Total allocations** | 分配次数 | 次数多可能影响性能(GC 压力) |
| **Histogram** | 分配大小分布 | 直观显示大/小分配比例 |
| **Biggest allocating functions** | 内存热点函数 | **优化重点**,按分配量排序 |

### 3.3 高水位 (High Watermark)

memray 报告的是 **high watermark**(高水位),即程序运行期间内存占用的峰值时刻.这不是累计分配量,而是某一时刻的最大活跃内存.

### 3.4 内存热点分析

```
🥇 Biggest allocating functions:
    - construct_object:.../yaml/constructor.py:100 -> 1.0MiB
    - _write_header:.../sink_csv.py:123 -> 128.6KiB
```

- 格式:`函数名:文件路径:行号 -> 分配量`
- 优化时优先关注排名靠前的函数
- 区分**库代码**(如 yaml)和**项目代码**(如 sink_csv)

### 3.5 二进制 dump 文件

```
Created 13 binary dumps at .benchmarks/memray with prefix 4ccff39a...
```

可用 memray 命令进一步分析:

```bash
# 生成火焰图
memray flamegraph .benchmarks/memray/<prefix>-test_bench_xxx.bin

# 生成表格报告
memray table .benchmarks/memray/<prefix>-test_bench_xxx.bin

# 生成树状报告
memray tree .benchmarks/memray/<prefix>-test_bench_xxx.bin
```

---

## 4. 常用工作流

### 4.1 基准保存与比较

基准产物落在本地 `.benchmarks/`（已 gitignore）。**不要提交**：跨机器 / CI / 不同负载下的数字没有可比性，只适合本机前后对比。

```bash
# 保存当前基准（仅本机）
just bench-baseline-save

# 与本机基准比较(显示差异)
just bench-compare

# 回归检测(超过阈值则失败)
just bench-compare-fail          # 默认 mean:10%
just bench-compare-fail "mean:5%"  # 自定义阈值
```

### 4.2 性能回归检测

比较报告会显示:

```
test_xxx    100.00us    110.00us    +10.00%
```

- 正数表示变慢(回归)
- 负数表示变快(优化)

### 4.3 内存分析流程

1. 运行 `just bench-memray`
2. 查看报告中的内存热点
3. 对可疑函数生成火焰图深入分析
4. 优化后重新运行对比

---

## 5. 指标参考值

> **定位注记**：本节是 scalim **框架自身微基准**（plan 构建/管道框架开销）的回归检测参考，
> 只用于贡献者判断「这次改动有没有让框架变慢」，**不是库级性能承诺，更不是选型参考**。
> 评估「scalim 是否值得引入」请看 [外部基线对比](external-baseline.md)。

以下是 scalim 项目的典型性能范围(供参考):

| 测试类型 | 典型 Mean | 典型内存 |
|----------|-----------|----------|
| plan_build | 20-40 us | < 1 MiB |
| pipeline_basic | 600-1000 us | < 500 KiB |
| pipeline_full | 3-6 ms | 1-2 MiB |
| yaml_dsl | 35-55 ms | 1-2 MiB |
| diagnostics | < 2 us | < 10 MiB |

---

## 6. 实际报告解读示例

以下基于一次实际运行结果进行解读:

### 6.1 baseline 组分析

```
------------------------- benchmark 'baseline': 2 tests -------------------------
Name (time in us)                          Min         Max        Mean      StdDev      Median       IQR
----------------------------------------------------------------------------------------------------------
test_bench_scalim_only_plan_build      18.0240    656.4990    22.4283    13.8743    20.1580    1.0920
test_bench_scalim_only_pipeline       667.5900  1,250.2490   690.8135    30.7982   682.6135   18.9960
```

**解读**:
- `plan_build` 平均耗时 22μs,是纯计划构建的基础开销
- `pipeline` 平均耗时 691μs,是 plan_build 的 **31 倍**(690.81/22.43)
- `pipeline` 的 StdDev (30.8) 相对 Mean (690.8) 很小(约 4.5%),说明性能**非常稳定**
- `plan_build` 的 Max (656μs) 远大于 Mean (22μs),存在偶发的高延迟(可能是 GC)

### 6.2 pipeline 组分析

```
--------------------------- benchmark 'pipeline': 4 tests ---------------------------
Name (time in us)                          Min         Max        Mean      StdDev      Median
----------------------------------------------------------------------------------------------
test_bench_pipeline_basic_row         585.6440  1,873.7450   640.1008    88.1714   635.5390
test_bench_pipeline_derived         1,514.7110  2,180.4890 1,588.6050    54.3904 1,607.9790
test_bench_pipeline_relations       2,549.0390  6,029.1300 2,798.6216   362.2128 2,789.6770
test_bench_pipeline_full_column     3,349.9920  7,665.6120 3,820.4782   877.4782 3,625.7570
```

**解读**:
- `basic_row` 最快(640μs),是最简单的行模式管道
- `derived` 约 1.6ms,派生字段计算增加了 2.5 倍开销
- `relations` 约 2.8ms,关系查找是主要耗时点
- `full_column` 最慢(3.8ms),列模式 + 完整功能

**性能瓶颈识别**:`full_column` 的 StdDev (877) 占 Mean (3820) 的 23%,波动较大,可能存在优化空间.

### 6.3 hooks 组分析

```
------------------------------ benchmark 'hooks': 4 tests ------------------------------
Name (time in us)                         Min          Max        Mean      StdDev      Median
---------------------------------------------------------------------------------------------
test_bench_pipeline_trace            506.6740    803.1780   546.1507    34.7992   561.2080
test_bench_pipeline_row_gap          790.2330 14,414.3840   860.0522   404.1877   865.5260
test_bench_pipeline_memory_opt       874.4640  2,393.7240   960.7150   168.0308   952.1415
test_bench_pipeline_perf_hooks     3,969.7930 18,810.4060 4,134.1147 1,051.9741 4,017.4330
```

**解读**:
- `trace` 最轻量(546μs),追踪钩子开销很小
- `row_gap` 的 Max (14.4ms) 异常高,但 Median (865μs) 正常,说明有**偶发的极端延迟**
- `perf_hooks` 最重(4.1ms),性能监控钩子本身有显著开销

**注意**:`perf_hooks` 的 StdDev (1052) 占 Mean (4134) 的 25%,不稳定,可能与系统资源采集(psutil)有关.

### 6.4 memray 内存报告分析

```
Allocation results for tests/bench/test_bench_examples.py::test_bench_yaml_dsl

         📦 Total memory allocated: 1.7MiB
         📏 Total allocations: 188
         🥇 Biggest allocating functions:
                - construct_object:.../yaml/constructor.py:100 -> 1.0MiB
                - _write_header:.../sink_csv.py:123 -> 128.6KiB
                - _cache_target_field:.../pipeline/base/__init__.py:427 -> 113.1KiB
```

**解读**:
- 总内存峰值 1.7MiB,对于 YAML DSL 解析来说合理
- **60% 内存 (1.0MiB)** 来自 YAML 解析库(`construct_object`),这是外部依赖,难以优化
- `_write_header` 和 `_cache_target_field` 是项目代码,如需优化可从这里入手
- 188 次分配相对较少,GC 压力不大

### 6.5 memray 开销对比

对比同一测试在有/无 memray 时的性能:

| 测试 | 无 memray Mean | 有 memray Mean | 开销 |
|------|----------------|----------------|------|
| plan_build | 22.4 μs | 33.8 μs | +51% |
| pipeline | 690.8 μs | 1077.5 μs | +56% |
| yaml_dsl | 35.8 ms | 55.4 ms | +55% |

**结论**:memray 带来约 50-60% 的性能开销,**时间基准应以无 memray 运行为准**.

---

## 7. 注意事项

1. **memray 开销**:启用 memray 会增加约 50-100% 的执行时间,时间指标应以无 memray 的运行为准
2. **环境一致性**:比较性能时确保相同机器、相同负载
3. **统计显著性**:单次运行可能有波动,关注多次运行的趋势
4. **GC 影响**:Python GC 可能导致偶发的高延迟,关注 Median 而非 Max
