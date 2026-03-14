## 1. 目录结构与入口

- [x] 1.1 新增 `notebooks/marimo/example_public_api/` 目录与主线 notebook(`index.py`),说明运行方式/失败定位/覆盖矩阵
- [x] 1.2 为 5 个稳定入口模块新增对应 notebook 文件(占位亦可),用于承接最小可运行示例与边界说明
- [x] 1.3 新增 `notebooks/marimo/run_examples.py` 作为 `just examples` 的单一入口,统一执行 `demo_big_data_report` + `example_public_api`
- [x] 1.4 更新 `justfile:examples` 入口指向 `notebooks/marimo/run_examples.py`(一步到位升级;不保留旧入口)

## 2. `packages/scalim-misc` 复用层(章节 + oracle)

- [x] 2.1 新增 `packages/scalim-misc/src/scalim_misc/examples/` 模块(专门承接 `notebooks/marimo/example_*` 的底层实现),并提供 registry/harness(可枚举/可运行/可汇总 PASS/FAIL)
- [x] 2.2 新增 `packages/scalim-misc/src/scalim_misc/examples/public_api/`(`example_public_api` 的章节实现 SSOT),并提供可调用 `run_*()` 入口给 runner/pytest 复用
- [x] 2.3 抽取通用 oracle helper(排序/结构化对拍/错误摘要),供 pytest 与 runner 复用
- [x] 2.4 为少量“大但固定”的 expected 建立 fixtures 落点: `packages/scalim-misc/src/scalim_misc/examples/**/fixtures/**`(并在章节/测试中声明来源与更新策略)
- [x] 2.5 为“仅展示 API 用法”的章节定义 smoke 约定(无产物也能回归),并在结果汇总中区分 smoke/oracle/fixture

## 3. 覆盖 `scalim.dsl.by_yaml`

- [x] 3.1 覆盖 `scalim.dsl.by_yaml.__all__` 的最小示例章节(至少: `compile`/`run`/`run_workflow` + 关键 config/options/overrides 类型)
- [x] 3.2 为 `run/compile` 增加一个小规模 deterministic demand YAML(可在 tmp_path 生成或使用轻量 fixture),并提供 oracle 对拍
- [x] 3.3 在 `example_public_api` 中提供一条最小 workflow 学习链路(调用 `run_workflow`),并覆盖 `share_preload_cache=true` 的可观察断言点(轻量)

## 4. 覆盖 `scalim.spec.ir`

- [x] 4.1 覆盖 `scalim.spec.ir.__all__` 的最小示例章节(IR 构造/读取/关键字段展示)
- [x] 4.2 为 IR→执行链路补一个 smoke 回归(不依赖业务 loader)

## 5. 覆盖 `scalim.planning`

- [x] 5.1 覆盖 `scalim.planning.__all__` 的最小示例章节(PlanBuilder/plan 结构/关键边界)
- [x] 5.2 增加一个可对拍的 planning 章节: 给定确定性 IR,断言 plan 的关键可观察输出稳定

## 6. 覆盖 `scalim.execution`

- [x] 6.1 覆盖 `scalim.execution.__all__` 的最小示例章节(ScalimEngine 创建/运行/最小 sinks)
- [x] 6.2 若章节产生数据/文件产物,必须提供 deterministic oracle(优先结构化对拍)

## 7. 覆盖 `scalim.ob`

- [x] 7.1 覆盖 `scalim.ob.__all__` 的最小示例章节(Observability 事件/输出/最小观测)
- [x] 7.2 增加一个可断言的观测回归点(例如事件数量/事件顺序/关键统计字段存在),避免只靠日志观察

## 8. 覆盖矩阵(cov)与回归接入

- [x] 8.1 新增或更新 `notebooks/marimo/coverage_matrix.md`,将 5 个入口模块的 `__all__` 覆盖映射到 notebook/章节与 pytest/`just examples` 回归点
- [x] 8.2 在覆盖矩阵中补齐 YAML DSL demand/workflow 能力清单的映射,并显式标注近期归档变更(今日 changes/archive)对应的组合覆盖点,至少包含:
  - `yaml-dsl-outputs`(多 sheet + where + aggregate + meta/audit/fingerprint)
  - `yaml-dsl-workflow`(`max_concurrency` 顺序确定 + `share_preload_cache` + 冲突预检查)
  - `yaml-source-normalize-shapes`(`take_first/map_values/project_fields/call_by` + int-key extract)
  - `derived-outputs-set-aggregations`(`count_distinct/max_distinct`、`dedup_by`、`two_stage_group_by`)
  - `yaml-dsl-micro-tunes`(runtime vars 指令节点等破坏性收敛点)
- [x] 8.3 增加至少一个非 bench pytest 用例复用 `example_public_api` 的章节/对拍逻辑,确保 `just qa` 默认可回归

## 9. `demo_big_data_report` 深覆盖补齐(合并原 demo coverage 主线)

- [x] 9.1 为 `demo_big_data_report` 增加一个 deterministic workflow YAML fixture(含 `share_preload_cache=true`),并配套最小 demand YAML(避免依赖外部业务 loader)
- [x] 9.2 新增章节执行该 workflow fixture 并提供可对拍断言(至少覆盖 outcomes/顺序确定性/共享 preload cache 行为可观察)
- [x] 9.3 补齐派生聚合 set 口径示例与对拍(至少覆盖 `dedup_by`/`two_stage_group_by`/`count_distinct.max_distinct` 的关键边界之一),并纳入 `just examples`
- [x] 9.4 在 `yaml-dsl-output-fields-alias` 落地后,为 canonical YAML 或 targeted fixture 增加 `outputs[*].fields: - *alias` 示例并补齐回归(可作为 follow-up 子任务)

## 10. QA

- [x] 10.1 通过: `just qa`
- [x] 10.2 通过: `just openspec-check`
