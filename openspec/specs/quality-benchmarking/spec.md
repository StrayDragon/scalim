# benchmarking Specification

## Purpose
定义基准测试入口与依赖约束，覆盖 pytest-benchmark 执行、JSON 导出、baseline 对比、benchlib 复用与可选 memray 剖析。

## Related Concepts
- pytest-benchmark 套件 (tests/bench/)
- 资源采样 (packages/benchlib/src/benchlib/resources.py)
- justfile 任务 (bench* recipes, memray integration)
- dev extras 依赖 (pytest-benchmark, memray)

## Requirements
### Requirement: pytest-benchmark 基准入口
- 基准 MUST 基于 pytest-benchmark 执行.
- 基准 MUST 支持导出 JSON 结果,并可通过 baseline 进行对比.

#### Scenario: 生成 JSON 结果
Given 运行基准命令并指定 `--benchmark-json`
When 执行 pytest-benchmark
Then 生成包含测试条目与统计的 JSON 文件

#### Scenario: baseline 对比
Given 已保存 baseline 结果
When 使用 `--benchmark-compare` 进行对比
Then 输出对比结果并标注差异

### Requirement: examples 复用与全链路覆盖
- 基准用例 MUST 复用 examples 的共享模块,避免重复实现.
- 基准 MUST 覆盖核心链路(源加载、关联、派生、sink、hooks、质量/诊断等).

#### Scenario: 复用共享模块
Given examples 提供 `_shared.py` / `_loaders.py`
When 基准执行需要构建 IR 与加载数据
Then 复用共享模块完成构建与执行

#### Scenario: DB 示例缺失依赖
Given 未配置 `DW_DB_URL`
When 运行 DB 示例基准
Then 基准标记为 skip 而非失败

### Requirement: 资源指标采样
- 基准 MUST 采集 CPU 与 RSS 指标(psutil 可选).
- 未安装 psutil 时 MUST 不导致基准失败.
- 资源指标 MUST 写入 pytest-benchmark 的 `extra_info` 并随 JSON 输出.

#### Scenario: psutil 缺失
Given 环境中未安装 psutil
When 执行基准采样
Then 资源指标为空但基准通过

#### Scenario: 资源指标写入 JSON
Given 基准运行并启用 JSON 输出
When 采集 CPU/RSS 指标
Then 指标应记录在 `extra_info` 中并写入 JSON 结果

### Requirement: benchlib workspace
- benchlib MUST 作为 workspace member 提供统一采样/封装能力.

#### Scenario: workspace 依赖解析
Given workspace 成员包含 `packages/benchlib`
When 在 tests/bench 引用 benchlib
Then 依赖由 workspace 提供并可直接导入

### Requirement: 基准范围隔离
- 默认基准 MUST 仅覆盖 PROJECT_NAME 核心执行路径.
- 默认基准 MUST NOT 导入或执行 notebook 的 `_verification.py` 对拍逻辑.
- 若需要对拍性能基准,MUST 使用独立 marker 或基准组并从默认基线中排除.

#### Scenario: 默认基准不包含对拍套件
- **WHEN** 执行 `pytest tests/bench -m bench`
- **THEN** 不应导入 `_verification.py` 且仅测量 PROJECT_NAME 核心路径

### Requirement: 基准对比元数据
- 基准结果 MUST 在 `extra_info` 中记录用于对比的 `scenario`、`scale`、`scope` 元数据.

#### Scenario: JSON 结果包含对比字段
- **WHEN** 运行基准并生成 `--benchmark-json`
- **THEN** JSON 的 `extra_info` 包含 `scenario`、`scale`、`scope`

### Requirement: 可选 memray 内存剖析 (dev-only)
- 内存剖析 MUST 通过 pytest-memray 独立入口启用,且仅作为 dev 依赖存在.
- 默认 bench MUST NOT 依赖 memray;未安装 memray 时基准仍可运行.
- memray 的使用 MUST 不引入 `src/IMPL_ROOT/` 运行时依赖,以保持 3.6+ 兼容性.

#### Scenario: 默认基准不依赖 memray
- **WHEN** 执行 `pytest tests/bench -m bench`
- **THEN** 未安装 memray 也能正常运行且不触发导入错误

#### Scenario: memray 基准输出可用
- **WHEN** 执行 memray 基准入口
- **THEN** 生成可用于分析的内存剖析输出

### Requirement: 可选 py-spy CPU profiling (dev-only)
- 系统 MUST 提供 dev-only 的 CPU profiling 入口（例如 `py-spy` flamegraph），用于定位执行热路径的 CPU sampling hotspot。
- 默认 bench/CI MUST NOT 依赖 `py-spy`；未安装时不得影响 `pytest tests/bench -m bench` 的运行。
- profiling 产物 MUST 输出到稳定目录（例如 `.tmp/artifacts/perf/`），且不应被提交。
- profiling 入口 MUST 使用仓库自带的自生成用例作为默认场景（例如 `demo_big_data_report`，默认 `BindingIr.mode=keys` 代表主路径）。

#### Scenario: py-spy flamegraph 写入稳定目录
- **WHEN** 开发者运行 CPU profiling 入口（例如 `just profile-cpu`）
- **THEN** 系统生成 flamegraph 产物并写入 `.tmp/artifacts/perf/`（或等价受控目录）

#### Scenario: 默认基准不依赖 py-spy
- **WHEN** 环境未安装 `py-spy` 且开发者运行默认基准入口（例如 `just bench`）
- **THEN** 基准 MUST 正常运行（不得因为缺少 `py-spy` 而失败）
