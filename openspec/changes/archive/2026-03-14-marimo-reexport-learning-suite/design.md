## Context

当前 `notebooks/marimo/` 基本以 `demo_big_data_report/` 为唯一主线,能够覆盖一部分 YAML DSL 与输出/对拍能力,但它并不擅长同时承担:

1) **框架用户学习场**: 以稳定公共入口(主动 re-export)为索引,明确 “从哪导入/怎么用/关键边界是什么”。
2) **集成回归场**: 在 `just qa` 链路内,对公开 re-export 内容 + YAML DSL(demand/workflow) 语法与关键组合场景做 deterministic 回归,并能定位失败原因。

同时近期 YAML DSL 与执行层迭代较多(例如 `outputs` authoring surface、workflow、多种 normalize 形状、派生聚合 set 口径等),需要一个更易维护的“可学 + 可测”结构来承接后续演进,避免示例/门禁碎片化。

约束与治理边界:

- **Doc governance**: `.gen.*` 文件与 `BEGIN/END AUTOGEN:*` 注入区块不可手改;涉及 docs 生成物必须走 `just gen-docs`/drift gate。
- **QA gate**: `just qa` 会运行 `examples` 与 pytest;示例回归必须快速稳定,不得依赖 marimo UI。
- **Public surface 口径**: “公开面”暂时只认 5 个入口模块的 `__all__`(不扩大到其它 `__all__` 文件):
  - `scalim.dsl.by_yaml`
  - `scalim.spec.ir`
  - `scalim.planning`
  - `scalim.execution`
  - `scalim.ob`

## Goals / Non-Goals

**Goals:**

- 将 `notebooks/marimo/` 补齐为“主线串联 + demo + examples”的结构,目录集中在 `notebooks/marimo/` 根下分目录(不继续把所有内容堆在 `demo_big_data_report/` 内)。
- 为上述 5 个稳定入口模块提供可运行、可复用的最小示例,并能在 `just qa` 中作为集成回归执行。
- 把可复用执行逻辑/对拍逻辑下沉到 `packages/scalim-misc/`(notebook 只负责交互与讲解;CI/runner 不依赖 marimo)。
- 对“有结果输出(数据/文件产物)”的示例提供 deterministic oracle:
  - 优先运行时计算 expected(小数据确定性)并对拍
  - 少量“大但固定”的 expected 允许固化为 fixtures,但需明确来源与更新策略
- 固化“用户功能组合覆盖(cov)”口径,以 `notebooks/marimo/coverage_matrix.md` 作为可检查的映射(能力 → notebook/章节 → pytest/`just examples`)。
- 继续强化 `demo_big_data_report/` 的深覆盖(尤其 workflow + set aggregations 等近期变动),并确保这些关键组合被 `just examples` 与 pytest 稳定回归。

**Non-Goals:**

- 不在本 change 中改动 YAML DSL/执行层语义本身(示例只表达已实现能力;能力缺口由对应功能 change 负责)。
- 不在本 change 中解决 `scalim-viz` 的对拍/回归(可后续单独开 change 做表达/示例更新,优先级较低)。
- 不推进前端 editor 适配实现(已有 `frontend-yaml-dsl-editor-adaptations` change,且当前标记为 DELAYED)。

## Decisions

### Decision 0: notebooks/marimo 命名约定(避免泛化名)

为避免 “learning_suite/xxx” 这类抽象命名,本次约定 `notebooks/marimo/` 的顶层目录以用途前缀命名:

- `demo_*`: 大而全的主线 demo(可承载较多组合 cov,但需保持对拍确定性)
- `tutor_*`: 长篇教程/讲解型 notebook(更强调阅读体验;如需纳入回归,必须保持小数据与确定性)
- `example_*`: 面向“可运行 + 可回归”的能力示例/公共入口示例(小数据、快回归;本 change 的 `example_public_api` 属于此类)

### Decision 1: notebook 结构集中在 `notebooks/marimo/example_public_api/`

新增一个独立目录作为“公共入口示例套件”,并保留现有 `demo_big_data_report/`:

- `notebooks/marimo/example_public_api/`
  - `index.py`: 主线串联(如何运行/覆盖矩阵/失败定位/与 `just examples` 的关系)
  - `dsl_by_yaml.py`: 覆盖 `scalim.dsl.by_yaml.__all__` 的最小示例
  - `spec_ir.py`: 覆盖 `scalim.spec.ir.__all__` 的最小示例
  - `planning.py`: 覆盖 `scalim.planning.__all__` 的最小示例
  - `execution.py`: 覆盖 `scalim.execution.__all__` 的最小示例
  - `ob.py`: 覆盖 `scalim.ob.__all__` 的最小示例

说明:
- 每本 notebook 只做“入口/用法/边界”讲解,避免沉淀复杂业务 demo;复杂覆盖仍由 `demo_big_data_report` 承接。
- 不在 notebook 内堆共享实现,共享实现统一下沉到 `packages/scalim-misc/`。

### Decision 2: “章节实现 + runner”作为单一真相来源

沿用 `demo_big_data_report` 的模式:

- `packages/scalim-misc/src/scalim_misc/examples/public_api/**`: `example_public_api` 的章节/用例/对拍逻辑 SSOT
- `packages/scalim-misc/src/scalim_misc/examples/**/fixtures/**`: 少量“大但固定”的 expected fixtures 的默认落点(由 runner/测试引用)
- `notebooks/marimo/example_public_api/*.py`: marimo UI + 讲解,调用 `scalim_misc.examples.public_api.*` 的可运行函数
- `notebooks/marimo/run_examples.py`: `just examples` gate 的单一入口,统一执行:
  - `demo_big_data_report` 的章节/对拍
  - `example_public_api` 的章节/对拍
  runner 只运行章节与 oracle,不依赖 marimo UI
- pytest: 至少一个非 bench 测试复用同一套章节/对拍逻辑,避免“两套真相”

### Decision 3: oracle 策略与对拍边界

- 任何会产生“数据结果/文件产物”的章节:
  - MUST 提供 oracle(纯 Python expected vs actual)
  - expected 优先运行时计算(小数据)
  - 对“文件产物”(如 workbook)优先对拍其**结构化结果**(表格数据/统计信息/指纹)而非二进制文件字节,减少 flaky 与平台差异
- 只做 API 入门/结构展示的章节可以是 smoke(无产物),但必须在 coverage_matrix 中标注其“回归类型”(smoke/oracle/fixture)。

### Decision 4: coverage_matrix.md 为 SSOT,以“公开入口 + YAML DSL 能力清单”验收

- `notebooks/marimo/coverage_matrix.md` 作为可检查 SSOT:
  - 5 个 re-export 入口模块及其 `__all__` 导出符号覆盖映射
  - YAML DSL demand/workflow 能力清单覆盖映射(含近期归档 change 的关键能力点)
  - 每一项明确对应到: notebook/章节 + pytest/`just examples` 回归点
- “95% 覆盖”以矩阵为准: 允许少量例外,但必须在矩阵中显式列出并给出原因与后续计划。

## Risks / Trade-offs

- [风险] 新增 notebooks 数量增加维护成本 → 缓解: 共享逻辑下沉到 `scalim-misc`,notebook 只做薄封装;以 coverage_matrix 约束范围与漂移。
- [风险] `just examples` 运行时间增长 → 缓解: `example_public_api` 章节必须小数据且 fast;重负载场景继续放在单独入口(如 `examples-big-data`)。
- [风险] 输出/对拍存在顺序不稳定导致 flaky → 缓解: oracle 强制排序/稳定化(显式排序键),并对拍结构化数据而非文件字节。

## Migration Plan

1) 先新增 `example_public_api/` 与其 runner/pytest 回归,与 `demo_big_data_report` 并存。
2) 将 coverage_matrix 扩展到同时覆盖 `demo_big_data_report` 与 `example_public_api`。
3) 将 `just examples` 收敛为单一入口 `notebooks/marimo/run_examples.py`(统一打印 PASS/FAIL 与上下文),并保持 `just qa` 稳定。

## Open Questions

- `example_public_api/` 内每个模块 notebook 的粒度: “每模块 1 本”是否足够,还是需要按主题再拆分(例如 `dsl_by_yaml` 拆为 demand/workflow 两本)?
