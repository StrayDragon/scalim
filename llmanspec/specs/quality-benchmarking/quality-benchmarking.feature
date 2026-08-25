# language: zh-CN
# capability: quality-benchmarking
# purpose: 定义基准测试入口与依赖约束，覆盖 pytest-benchmark 执行、JSON 导出、baseline 对比、benchlib 复用与可选 memray 剖析。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: quality-benchmarking

  @req:r70 @human
  场景: pytest-benchmark 基准入口
    - 基准 MUST 基于 pytest-benchmark 执行，MUST 支持导出 JSON 结果，并可通过 baseline 进行对比。

  @req:r314 @human
  场景: examples 复用与全链路覆盖
    - 基准用例 MUST 复用 examples 的共享模块，避免重复实现。基准 MUST 覆盖核心链路(源加载、关联、派生、sink、hooks、质量/诊断等)。

  @req:r437 @human
  场景: 资源指标采样
    - 基准 MUST 采集 CPU 与 RSS 指标(psutil 可选)。未安装 psutil 时 MUST 不导致基准失败。资源指标 MUST 写入 pytest-benchmark 的 extra_info 并随 JSON 输出。

  @req:r529 @human
  场景: benchlib workspace
    - benchlib MUST 作为 workspace member 提供统一采样/封装能力。

  @req:r603 @human
  场景: 基准范围隔离
    - 默认基准 MUST 仅覆盖核心执行路径。默认基准 MUST NOT 导入或执行 notebook 的 _verification.py 对拍逻辑。

  @req:r657 @human
  场景: 基准对比元数据
    - 基准结果 MUST 在 extra_info 中记录用于对比的 scenario、scale、scope 元数据。

  @req:r699 @human
  场景: 可选 memray 内存剖析 (dev-only)
    - 内存剖析 MUST 通过 pytest-memray 独立入口启用，且仅作为 dev 依赖存在。默认 bench MUST NOT 依赖 memray。

  @req:r736 @human
  场景: 可选 py-spy CPU profiling (dev-only)
    - 系统 MUST 提供 dev-only 的 CPU profiling 入口，用于定位执行热路径的 CPU sampling hotspot。默认 bench MUST NOT 依赖 py-spy。

  @req:r71 @human
  场景: Deterministic hotpath regression guardrails
    - 系统 MUST 为执行热路径提供确定性的回归护栏（单元测试级别），用于防止“wants-gated 退化”与无订阅时的额外循环/分配被重新引入。 该护栏 MUST 满足： - 不依赖机器性能阈值（避免 CI 抖动）。 - 以“调用次数/分支路径/是否构造中间结构”为断言信号。

  @req:r315 @human
  场景: Benchmark suites exist for trend measurement
    - 系统 MUST 提供可重复执行的 benchmark suites 用于趋势测量，并支持导出结构化结果用于对比。

  @req:r438 @human
  场景: Memory profiling entrypoints exist (dev-only)
    - 系统 MUST 提供 dev-only 的内存剖析入口（例如 memray），并将产物写入受控目录，便于定位“分配热点”与“峰值驻留”来源。

  @req:r70 @human
  场景: json-export
    - 必须成立：假如 运行基准命令并指定 --benchmark-json；当 执行 pytest-benchmark；那么 生成包含测试条目与统计的 JSON 文件
    假如 运行基准命令并指定 --benchmark-json
    当 执行 pytest-benchmark
    那么 生成包含测试条目与统计的 JSON 文件

  @req:r70 @human
  场景: baseline-compare
    - 必须成立：假如 已保存 baseline 结果；当 使用 --benchmark-compare 进行对比；那么 输出对比结果并标注差异
    假如 已保存 baseline 结果
    当 使用 --benchmark-compare 进行对比
    那么 输出对比结果并标注差异

  @req:r314 @human
  场景: reuse-shared
    - 必须成立：假如 examples 提供 _shared.py / _loaders.py；当 基准执行需要构建 IR 与加载数据；那么 复用共享模块完成构建与执行
    假如 examples 提供 _shared.py / _loaders.py
    当 基准执行需要构建 IR 与加载数据
    那么 复用共享模块完成构建与执行

  @req:r314 @human
  场景: db-skip
    - 必须成立：假如 未配置 DW_DB_URL；当 运行 DB 示例基准；那么 基准标记为 skip 而非失败
    假如 未配置 DW_DB_URL
    当 运行 DB 示例基准
    那么 基准标记为 skip 而非失败

  @req:r437 @human
  场景: psutil-missing
    - 必须成立：假如 环境中未安装 psutil；当 执行基准采样；那么 资源指标为空但基准通过
    假如 环境中未安装 psutil
    当 执行基准采样
    那么 资源指标为空但基准通过

  @req:r437 @human
  场景: metrics-json
    - 必须成立：假如 基准运行并启用 JSON 输出；当 采集 CPU/RSS 指标；那么 指标应记录在 extra_info 中并写入 JSON 结果
    假如 基准运行并启用 JSON 输出
    当 采集 CPU/RSS 指标
    那么 指标应记录在 extra_info 中并写入 JSON 结果

  @req:r529 @human
  场景: workspace-dep
    - 必须成立：假如 workspace 成员包含 packages/benchlib；当 在 tests/bench 引用 benchlib；那么 依赖由 workspace 提供并可直接导入
    假如 workspace 成员包含 packages/benchlib
    当 在 tests/bench 引用 benchlib
    那么 依赖由 workspace 提供并可直接导入

  @req:r603 @human
  场景: no-verification
    - 必须成立：当 执行 pytest tests/bench -m bench；那么 不应导入 _verification.py 且仅测量核心路径
    当 执行 pytest tests/bench -m bench
    那么 不应导入 _verification.py 且仅测量核心路径

  @req:r657 @human
  场景: compare-fields
    - 必须成立：当 运行基准并生成 --benchmark-json；那么 JSON 的 extra_info 包含 scenario、scale、scope
    当 运行基准并生成 --benchmark-json
    那么 JSON 的 extra_info 包含 scenario、scale、scope

  @req:r699 @human
  场景: no-memray-dep
    - 必须成立：当 执行 pytest tests/bench -m bench；那么 未安装 memray 也能正常运行且不触发导入错误
    当 执行 pytest tests/bench -m bench
    那么 未安装 memray 也能正常运行且不触发导入错误

  @req:r699 @human
  场景: memray-output
    - 必须成立：当 执行 memray 基准入口；那么 生成可用于分析的内存剖析输出
    当 执行 memray 基准入口
    那么 生成可用于分析的内存剖析输出

  @req:r736 @human
  场景: no-pyspy-dep
    - 必须成立：假如 环境未安装 py-spy；当 开发者运行默认基准入口；那么 基准 MUST 正常运行
    假如 环境未安装 py-spy
    当 开发者运行默认基准入口
    那么 基准 MUST 正常运行
  @req:r71 @human
  场景: relation-diagnostics-is-skipped-when-not-wanted
    - 必须成立：当 未订阅 `relation_lookup` 事件且执行一次包含 `LoadRef` 的批次；那么 系统 MUST 不执行逐行的 lookup 命中/缺失诊断循环（等价于不产生与 `row_count` 成正比的诊断开销）
    当 未订阅 `relation_lookup` 事件且执行一次包含 `LoadRef` 的批次
    那么 系统 MUST 不执行逐行的 lookup 命中/缺失诊断循环（等价于不产生与 `row_count` 成正比的诊断开销）
  @req:r315 @human
  场景: benchmark-run-produces-structured-output
    - 必须成立：当 运行基准入口并启用 JSON 导出；那么 输出 MUST 包含每个场景的统计数据与 `extra_info`（至少包含 `scenario`/`scale`/`scope`）
    当 运行基准入口并启用 JSON 导出
    那么 输出 MUST 包含每个场景的统计数据与 `extra_info`（至少包含 `scenario`/`scale`/`scope`）
  @req:r438 @human
  场景: memray-output-is-written-under-a-stable-directory
    - 必须成立：当 运行内存剖析入口；那么 剖析产物 MUST 输出到稳定目录（例如 `.benchmarks/memray/`）且不影响默认 benchmark 执行
    当 运行内存剖析入口
    那么 剖析产物 MUST 输出到稳定目录（例如 `.benchmarks/memray/`）且不影响默认 benchmark 执行
