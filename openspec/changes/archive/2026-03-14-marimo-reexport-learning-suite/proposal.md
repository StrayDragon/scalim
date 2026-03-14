## Why

当前 `notebooks/marimo/` 基本只剩 `demo_big_data_report` 一条主线,虽然能覆盖部分能力,但它并不擅长承担以下两类职责:

1) **框架用户学习场**: 以稳定的公共入口(主动 re-export)为导向,分模块讲清楚“应该从哪导入、怎么用、关键边界是什么”。
2) **集成回归场**: 在 `just qa` 链路内,对公开 re-export 内容 + YAML DSL(demand/workflow)语法与关键组合场景做 deterministic 回归,并可定位失败原因。

为了让 notebooks 既“可学”又“可测”,需要把 notebooks/marimo 重构为一个以 re-export 公共面为索引的 `example_public_api` 套件,并为有产物/数据输出的示例建立独立 oracle(纯 Python 对照组)用于对拍。

## What Changes

- 将 `notebooks/marimo/` 重构为“主线串联 + demo + 分模块 example”的目录结构(根下分目录):
  - 保留并继续强化 `demo_big_data_report/` 作为**大而全**的主线 demo(覆盖 YAML DSL 的关键组合与对拍能力)。
  - 新增 `example_public_api/`(明确含义且带 `example_` 前缀)作为“公共入口示例/回归套件”:
    - 一份主线 notebook: 串联全局入口、运行方式、覆盖矩阵与一键 smoke
    - 按 5 个公共 re-export 模块分别提供 notebook(每个模块覆盖其 `__all__` 导出符号的最小可运行示例与边界说明):
      - `scalim.dsl.by_yaml`
      - `scalim.spec.ir`
      - `scalim.planning`
      - `scalim.execution`
      - `scalim.ob`
- 把 notebooks 中可复用的示例逻辑下沉到 `packages/scalim-misc/`:
  - notebook 负责交互/讲解/展示
  - 真实执行与回归入口在 `scalim-misc` 提供可调用的 `run_*()` 函数(供 `just examples`/pytest 复用)
  - 在 `scalim-misc` 中新增 `scalim_misc.examples` 模块,专门承接 `notebooks/marimo/example_*` 的底层实现与 fixtures/oracle 复用
- 为“有结果输出(主要是数据/文件产物)”的示例建立 oracle:
  - oracle 用纯 Python 计算 expected(小规模确定性数据)并提供可对拍断言
  - 少量“大但固定”的预期结果允许固化为 fixtures(需明确来源与更新策略)
- 固化“用户功能组合覆盖(cov)”口径:
  - `notebooks/marimo/coverage_matrix.md` 作为可检查的覆盖矩阵(公共 re-export + YAML DSL demand/workflow 全量语法入口 + 关键组合场景)
  - 覆盖矩阵需显式关联近期变动(尤其今日 `openspec/changes/archive/` 中的能力点)到具体示例/回归点(这是“95% 覆盖”验收口径)
- `just qa`/pytest 侧提供最小且稳定的集成回归:
  - 不运行 marimo 本体(避免 UI 依赖),只运行其底层 `run_*()` 示例函数与 oracle 对拍
  - `just examples` 收敛为单一入口 `notebooks/marimo/run_examples.py`,统一跑 `demo_big_data_report` + `example_public_api` 两类示例并输出章节级 PASS/FAIL

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `testing-quality`: 增补 notebooks/marimo 的 `example_public_api` 目录结构、覆盖矩阵、oracle 对拍与 `just qa` 集成回归的最低要求。

## Impact

- 受影响模块(预期):
  - `notebooks/marimo/**`(新增/重构目录与入口 notebook)
  - `packages/scalim-misc/src/scalim_misc/**`(示例 runner + oracle 复用代码)
  - `tests/**`(新增/扩展集成回归用例,覆盖公开 re-export + YAML DSL 关键组合)
  - `justfile`(可能新增/调整 examples 入口,保持 `just qa` 稳定)
