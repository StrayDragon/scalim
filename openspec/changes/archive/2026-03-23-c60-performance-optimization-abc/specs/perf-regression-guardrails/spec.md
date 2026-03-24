# perf-regression-guardrails Specification

## ADDED Requirements

### Requirement: Deterministic hotpath regression guardrails
系统 MUST 为执行热路径提供确定性的回归护栏（单元测试级别），用于防止“wants-gated 退化”与无订阅时的额外循环/分配被重新引入。

该护栏 MUST 满足：
- 不依赖机器性能阈值（避免 CI 抖动）。
- 以“调用次数/分支路径/是否构造中间结构”为断言信号。

#### Scenario: relation diagnostics is skipped when not wanted
- **WHEN** 未订阅 `relation_lookup` 事件且执行一次包含 `LoadRef` 的批次
- **THEN** 系统 MUST 不执行逐行的 lookup 命中/缺失诊断循环（等价于不产生与 `row_count` 成正比的诊断开销）

### Requirement: Benchmark suites exist for trend measurement
系统 MUST 提供可重复执行的 benchmark suites 用于趋势测量，并支持导出结构化结果用于对比。

#### Scenario: benchmark run produces structured output
- **WHEN** 运行基准入口并启用 JSON 导出
- **THEN** 输出 MUST 包含每个场景的统计数据与 `extra_info`（至少包含 `scenario`/`scale`/`scope`）

### Requirement: Memory profiling entrypoints exist (dev-only)
系统 MUST 提供 dev-only 的内存剖析入口（例如 memray），并将产物写入受控目录，便于定位“分配热点”与“峰值驻留”来源。

#### Scenario: memray output is written under a stable directory
- **WHEN** 运行内存剖析入口
- **THEN** 剖析产物 MUST 输出到稳定目录（例如 `.benchmarks/memray/`）且不影响默认 benchmark 执行

