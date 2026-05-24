# 如何阅读本项目

??? note "适用读者"
    - 项目贡献者/二次开发者(需要读代码与定位入口)
    - 需要排查执行链路的使用方开发者

这页带你从“一个入口文件”一路跟到“执行结果”,把每一层该看的目录/符号标出来,减少靠猜的时间.

## 0. 目录索引(快速定位)

- 运行时代码: `src/scalim/`
  - YAML DSL: `src/scalim/dsl/yaml_dsl/` (`compiler_frontend/`, `_internal/`, `schema_dsl/`, `runtime/`)
  - IR/types: `src/scalim/spec/`
  - 规划层: `src/scalim/planning/`
  - 执行层: `src/scalim/execution/`
  - 输出 sinks: `src/scalim/sinks/`
  - 可观测性: `src/scalim/ob/`, `src/scalim/events/`, `src/scalim/hooks/`
- 开发脚本: `scripts/` (生成/校验/漂移门禁)
- 测试: `tests/` (pytest) + `tests/bench/` (benchmark-only)
- 示例与数据: `notebooks/` (marimo) + `packages/scalim-misc/src/scalim_misc/`
- 文档站点: `docs/doc/` (manual + `*.gen.*`) + `docs/zensical.toml`
- 规范与变更: `llmanspec/specs/` + `llmanspec/changes/`

## 1. 先读哪些文档(避免迷路)

- [`AGENTS.md`](#code=AGENTS.md): 仓库协作约定与硬边界(唯一准则)
- [架构详解](../architecture/arch.md): 架构分层与主要流程图;实现细节与行为约束会指向 `llmanspec/`
- [llmanspec 规范](../specs/index.md): 更接近“规范/约束”的描述,适合在改行为前先对齐预期
- [SSOT / 生成物 / 门禁地图](../dev/ssot-map.md): 统一查表“改哪里/跑哪个生成入口/哪个门禁会拦”
- [主线教程: demo_big_data_report](demo-big-data-report.md): 从一个稳定 demo 入口跑起来/对拍/排错(面向 CI 与日常开发)

站点文档更偏“用法与入口”,适合把经常问的问题沉淀成可维护的索引页.

## 2. 两条最常走的执行路径

??? tip "打开源码路径(可选)"
    本页中的源码路径已做成可点击链接:

    - 点击后可直接复制路径
    - 配置一次 `repo_root` 后,可选择用 VS Code / Cursor / Zed / file:// 打开
    - 如果你也配置了 Git Web Base,还能跳到对应的仓库网页

### 2.1 从 YAML DSL 跑起来

建议从这个入口开始读:

- [`src/scalim/dsl/yaml_dsl/runtime/entrypoints.py::run`](#code=src/scalim/dsl/yaml_dsl/runtime/entrypoints.py::run)

顺着调用链往下看,基本是这几段:

1. **读取与校验**
   - schema/语义校验: [`src/scalim/dsl/yaml_dsl/_internal/config_parsing/`](#code=src/scalim/dsl/yaml_dsl/_internal/config_parsing/)
   - CLI 入口: [`packages/scalim-cli/src/scalim_cli/yaml_dsl.py`](#code=packages/scalim-cli/src/scalim_cli/yaml_dsl.py)
2. **配置 → IR**
   - 编译编排(run/compile): [`src/scalim/dsl/yaml_dsl/runtime/compiler.py`](#code=src/scalim/dsl/yaml_dsl/runtime/compiler.py)
   - 静态前端(不 import/适合 LSP): [`src/scalim/dsl/yaml_dsl/compiler_frontend/compiler.py`](#code=src/scalim/dsl/yaml_dsl/compiler_frontend/compiler.py)
   - 运行时链接(RuntimeBindings): [`src/scalim/dsl/yaml_dsl/runtime/runtime_linking.py`](#code=src/scalim/dsl/yaml_dsl/runtime/runtime_linking.py)
   - 结构模型(schema 生成用): [`src/scalim/dsl/yaml_dsl/schema_dsl/models/`](#code=src/scalim/dsl/yaml_dsl/schema_dsl/models/)
3. **IR → plan → 执行**
   - 执行编排: [`src/scalim/execution/run_ir.py::run_ir`](#code=src/scalim/execution/run_ir.py::run_ir)
   - 规划层: [`src/scalim/planning/`](#code=src/scalim/planning/)(`PlanBuilder`, `ExecutionPlan`)
   - 引擎与流水线: [`src/scalim/execution/engine.py`](#code=src/scalim/execution/engine.py), [`src/scalim/execution/pipeline/`](#code=src/scalim/execution/pipeline/)

如果你在找“某个 YAML 字段最终影响了哪里”,通常会先在 yaml_dsl 的 **静态编译** 阶段把配置翻译成 `DemandIr`/`SourceIr`/`FieldIr`(纯数据),
再在 **runtime_linking** 阶段解析引用/编译表达式得到 `RuntimeBindings`,最后进入规划与执行.

### 2.2 直接从 IR / Engine 跑起来

如果你已经有 `DemandIr` 或在写更底层的集成,从这里开始读更顺:

- [`src/scalim/execution/run_ir.py::run_ir`](#code=src/scalim/execution/run_ir.py::run_ir)
- [`src/scalim/execution/engine.py::ScalimEngine`](#code=src/scalim/execution/engine.py::ScalimEngine)

`run_ir` 负责:

- 用 `PlanBuilder` 构建 `ExecutionPlan`
- 组装 `ObserverManager` / `HookManager`
- 创建 `ScalimEngine` 并驱动 `engine.run(...)`

## 3. 执行层怎么读: 从 Pipeline 到 Operator

执行主干在:

- [`src/scalim/execution/pipeline/base/pipeline.py::SeqPipeline.run`](#code=src/scalim/execution/pipeline/base/pipeline.py::SeqPipeline.run)
- [`src/scalim/execution/executor/batch/executor.py::BatchExecutor.execute_operators`](#code=src/scalim/execution/executor/batch/executor.py::BatchExecutor.execute_operators)

你会看到一个稳定的结构:

- `Pipeline` 负责分批、sink 分类(行/列/文件)、GC 节奏、可观测性事件
- `BatchExecutor` 负责按 `ExecutionPlan.operators` 执行算子
- 每种算子有自己的 executor:
  - `Load`: [`src/scalim/execution/executor/operators/load/`](#code=src/scalim/execution/executor/operators/load/)
  - `LoadRef`: [`src/scalim/execution/executor/operators/load_ref/`](#code=src/scalim/execution/executor/operators/load_ref/)
  - `Compute`: [`src/scalim/execution/executor/operators/compute/`](#code=src/scalim/execution/executor/operators/compute/)

并行模式(`seq`/`adaptive`)只影响 `LoadRef` 段的执行方式,详见:

- [执行并行模式: `seq` 与 `adaptive`](../architecture/parallel-modes.md)

## 4. 例子与回归从哪里找

- YAML 示例(带 anchors): [`tests/fixtures/order_report.yaml`](#code=tests/fixtures/order_report.yaml)
- 运行示例与 demo: [`notebooks/`](#code=notebooks/)(marimo)与 [`packages/scalim-misc/src/scalim_misc/`](#code=packages/scalim-misc/src/scalim_misc/)
  - 本地启动 marimo server(推荐): `uv run marimo edit notebooks/marimo/`
  - headless 回归入口(与 CI 一致): `just examples`（入口实现位于 `justfile` 的 `examples:` recipe）
  - 覆盖报告(生成物): `notebooks/marimo/marimo_coverage.gen.toon`（生成/漂移门禁: `just gen-marimo-coverage` / `just marimo-coverage-drift-check`）
- 规划/执行相关 fixture: [`tests/fixtures/planning_fixtures.py`](#code=tests/fixtures/planning_fixtures.py), [`tests/fixtures/executor_operator_fixtures.py`](#code=tests/fixtures/executor_operator_fixtures.py)

要改 DSL 行为或 schema,尽量先补一个能覆盖你场景的 fixture/测试,不然很难防止“文档写对了,实现悄悄漂”.

## 下一步

- [YAML DSL 语法总览](../yaml-dsl/syntax.md)
- [YAML DSL 用户指南](../yaml-dsl/user-guide.md)
