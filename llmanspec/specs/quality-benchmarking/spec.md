---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate quality-benchmarking --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "quality-benchmarking"
purpose: "定义基准测试入口与依赖约束，覆盖 pytest-benchmark 执行、JSON 导出、baseline 对比、benchlib 复用与可选 memray 剖析。"
requirements[8]{req_id,title,statement}:
  r1,"pytest-benchmark 基准入口","基准 MUST 基于 pytest-benchmark 执行，MUST 支持导出 JSON 结果，并可通过 baseline 进行对比。"
  r2,"examples 复用与全链路覆盖","基准用例 MUST 复用 examples 的共享模块，避免重复实现。基准 MUST 覆盖核心链路(源加载、关联、派生、sink、hooks、质量/诊断等)。"
  r3,"资源指标采样","基准 MUST 采集 CPU 与 RSS 指标(psutil 可选)。未安装 psutil 时 MUST 不导致基准失败。资源指标 MUST 写入 pytest-benchmark 的 extra_info 并随 JSON 输出。"
  r4,"benchlib workspace","benchlib MUST 作为 workspace member 提供统一采样/封装能力。"
  r5,"基准范围隔离","默认基准 MUST 仅覆盖核心执行路径。默认基准 MUST NOT 导入或执行 notebook 的 _verification.py 对拍逻辑。"
  r6,"基准对比元数据","基准结果 MUST 在 extra_info 中记录用于对比的 scenario、scale、scope 元数据。"
  r7,"可选 memray 内存剖析 (dev-only)","内存剖析 MUST 通过 pytest-memray 独立入口启用，且仅作为 dev 依赖存在。默认 bench MUST NOT 依赖 memray。"
  r8,"可选 py-spy CPU profiling (dev-only)","系统 MUST 提供 dev-only 的 CPU profiling 入口，用于定位执行热路径的 CPU sampling hotspot。默认 bench MUST NOT 依赖 py-spy。"
scenarios[12]{req_id,id,given,when,then}:
  r1,json-export,"运行基准命令并指定 --benchmark-json",执行 pytest-benchmark,生成包含测试条目与统计的 JSON 文件
  r1,baseline-compare,"已保存 baseline 结果","使用 --benchmark-compare 进行对比",输出对比结果并标注差异
  r2,reuse-shared,"examples 提供 _shared.py / _loaders.py",基准执行需要构建 IR 与加载数据,复用共享模块完成构建与执行
  r2,db-skip,"未配置 DW_DB_URL",运行 DB 示例基准,基准标记为 skip 而非失败
  r3,psutil-missing,"环境中未安装 psutil",执行基准采样,资源指标为空但基准通过
  r3,metrics-json,"基准运行并启用 JSON 输出",采集 CPU/RSS 指标,指标应记录在 extra_info 中并写入 JSON 结果
  r4,workspace-dep,"workspace 成员包含 packages/benchlib",在 tests/bench 引用 benchlib,依赖由 workspace 提供并可直接导入
  r5,no-verification,"",执行 pytest tests/bench -m bench,不应导入 _verification.py 且仅测量核心路径
  r6,compare-fields,"",运行基准并生成 --benchmark-json,"JSON 的 extra_info 包含 scenario、scale、scope"
  r7,no-memray-dep,"",执行 pytest tests/bench -m bench,未安装 memray 也能正常运行且不触发导入错误
  r7,memray-output,"",执行 memray 基准入口,生成可用于分析的内存剖析输出
  r8,no-pyspy-dep,"环境未安装 py-spy",开发者运行默认基准入口,基准 MUST 正常运行
```
