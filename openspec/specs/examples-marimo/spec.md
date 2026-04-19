# marimo-examples Specification

**状态: ✅ 已实现**

## Purpose
定义仓库内 `notebooks/marimo/` 的示例/教学套件治理边界：Marimo notebooks 作为唯一交互载体，headless runner/pytest 作为确定性回归入口，要求执行真相来源位于 notebooks（同源复用）。

## Related Code (as implemented)
- `justfile` (`just examples` gate 入口; runner 内联实现)
- `notebooks/marimo/demo_big_data_report/` (主线示例套件)
- `notebooks/marimo/example_public_api_suite/` (public API 覆盖套件)
- `scripts/gen-marimo-coverage.py` + `notebooks/marimo/marimo_coverage.gen.toon` (覆盖报告生成与 drift-check)
- `packages/scalim-misc/src/scalim_misc/notebook_support/*` (notebook 复用 helper; 不依赖 marimo)

## Requirements


### Requirement: 示例 notebooks 以 Marimo 为唯一交互载体
系统 MUST 将 `notebooks/marimo/` 作为示例/教程的交互载体目录;其中用于教学展示的示例 notebooks MUST 为 Marimo notebook(即包含 `marimo.App`)。

系统 MAY 在 `notebooks/marimo/` 下保留非 Marimo 的 headless runner 实现,但该实现 MUST 明确定位为 runner/工具实现,不得承担交互教学入口职责。

#### Scenario: 示例 notebooks 可被识别为 Marimo
- **WHEN** 维护者枚举 `notebooks/marimo/**.py` 中用于教学展示的 notebooks
- **THEN** 这些 notebooks 文件内容 MUST 包含 `marimo.App`

### Requirement: 每个示例套件必须同时具备"教学入口"和"回归入口"
系统 MUST 将示例套件拆分为两层并保持同源:

1) **教学入口**: Marimo notebooks,用于逐章讲解与交互查看结果
2) **回归入口**: headless runner/pytest,用于确定性对拍与 CI 集成

#### Scenario: 套件具备双入口
- **WHEN** 维护者为某个示例套件新增一个可运行章节
- **THEN** 该章节 MUST 同时具备一个 Marimo notebook 入口
- **AND** MUST 同时具备一个可被 headless runner 执行的 SSOT 用例入口

### Requirement: 示例 SSOT 必须位于 notebooks 且可被 headless 复用
系统 MUST 将 `notebooks/marimo/` 下纳入 examples gate 的示例/章节执行真相来源定义为"可被导入调用的 Python 入口函数"，且该入口 MUST 位于 notebooks 侧（例如同一 notebook 模块内的 `run_*()`，或 notebooks 侧的纯 Python 支撑模块）。

该 SSOT 入口 MUST 满足：

- MUST 可被 `just examples` 所执行的 headless runner 与 pytest 直接导入并执行（允许导入 `marimo` 与 notebook 模块，但不得要求启动 marimo UI server）。
- MUST 产生可定位的结果摘要（至少包含 `passed` 与 `summary`；可选 `details` 供 notebook UI 展示与排障）。
- MUST 与对应的 Marimo notebook 交互入口同源：notebook 侧展示的核心执行路径 MUST 复用同一 SSOT 入口（避免 "UI 一套逻辑 / headless 一套逻辑" 的漂移）。

#### Scenario: 新增章节时 SSOT 入口可被 runner/pytest 复用
- **WHEN** 维护者为示例体系新增一个纳入 gate 的章节 notebook
- **THEN** 该章节 MUST 提供一个 notebooks 侧 SSOT 入口函数供 `just examples` 的 headless runner 与 pytest 复用
- **AND** 该 notebook 的交互执行路径 MUST 调用同一入口函数得到结果并展示

### Requirement: Marimo notebooks 必须是薄封装,不得形成第二套真相
每个 Marimo notebook MUST 通过调用对应的 SSOT `run_*()`/example case 来执行核心逻辑并展示结果.

Marimo notebook MUST NOT 在 notebook 内部复制实现一套独立的示例执行主路径(例如自行构建与执行整套 demo 引擎链路作为章节唯一真相),以避免与 SSOT 漂移.

#### Scenario: notebook 调用 SSOT 入口
- **WHEN** 读者在 marimo 中运行任一示例章节 notebook
- **THEN** notebook 的核心执行入口 MUST 来自 notebooks 侧的 SSOT `run_*()`/example case

### Requirement: `just examples` 继续通过 headless runner 执行示例对拍
系统 MUST 提供一个 headless runner 作为 `just examples` 的单一入口,并保证 runner 不依赖 marimo UI.

runner MUST 输出可定位的 PASS/FAIL 与章节级 summary,并以非零退出码表示存在失败.

#### Scenario: examples gate 可在 CI 中稳定运行
- **WHEN** 开发者运行 `just examples`(或等价入口)
- **THEN** headless runner MUST 执行示例套件并输出章节级 PASS/FAIL 与 summary
- **AND** 当存在失败时,进程退出码 MUST 非零

### Requirement: marimo_coverage.gen.toon 明确映射"notebooks → SSOT → gate"
系统 MUST 维护 `notebooks/marimo/marimo_coverage.gen.toon` 作为可检查的 SSOT 报告,用于将示例套件的回归点映射到:

- 对应的 Marimo notebook(教学入口)
- 对应的 notebooks 侧 SSOT 入口/实现文件(执行真相来源)
- 对应的 headless gate(`just examples`)与 pytest 复用点(如存在)

该文件 MUST 由脚本 `scripts/gen-marimo-coverage.py` 生成,不得手工维护.

#### Scenario: 新增示例时 coverage 报告同步
- **WHEN** 维护者新增或调整一个示例/章节回归点
- **THEN** 运行 `just gen-marimo-coverage` MUST 更新 `notebooks/marimo/marimo_coverage.gen.toon`
- **AND** `just marimo-coverage-drift-check` MUST 在 CI 中可用且能检测到 drift

### Requirement: notebook-support helpers 必须 headless 且不依赖 marimo
当引入 notebook 复用 helper(例如路径解析、结果结构化展示、YAML 片段摘录等)时,这些 helper MUST 为纯 Python 且 MUST NOT 依赖 marimo UI server.

这些 helper MAY 位于：
- `packages/scalim-misc/src/scalim_misc/notebook_support/`（仅工具函数/不承载教学主流程）
- 或 `notebooks/marimo/` 下的受控纯 Python 支撑模块（用于多个 notebooks 复用）

#### Scenario: helper 可被 headless runner 导入
- **WHEN** 在不导入 marimo 的 Python 进程中导入这些 helper 模块
- **THEN** 导入成功且不触发 marimo 依赖


### Requirement: `demo_big_data_report` 提供章节化 Marimo notebooks
系统 MUST 在 `notebooks/marimo/demo_big_data_report/` 下提供 `chapters_of_yaml_dsl/` 目录,并为主线 demo 的每个 SSOT 章节提供一份对应的 Marimo notebook.

主线章节 MUST 以 **YAML DSL 场景化**为主（面向工程使用方），并避免以 IR/Plan 等底层视角作为主线教学内容。

系统 MAY 额外提供 `chapters_of_ir/` 目录用于承载 IR 视角的回归章节,但这些章节不得作为主线教学内容。

初始章节集合 MUST 至少覆盖以下 `chapter_id`:
- `yaml_dsl_ecommerce`
- `yaml_dsl_ads`
- `yaml_dsl_support`
- `workflow_yaml`
- `workflow_demo_big_data_report`
- `yaml_dsl_debugging`

public API 覆盖章节（`__all__` 覆盖断言 + hooks/ob 扩展点）不再属于该主线章节集合，迁移为独立 suite 并仍纳入 examples gate（见对应规范）。

章节 notebook 文件名 MUST 以 `<chapter_id>.py` 结尾,且 MAY 额外包含有序前缀(例如 `01_`),用于稳定排序与导航.

#### Scenario: 章节 notebooks 存在
- **WHEN** 维护者检查 `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/` 的文件集合
- **THEN** 上述每个 `chapter_id` 都存在至少一份以 `<chapter_id>.py` 结尾的 notebook 文件

### Requirement: `demo_big_data_report` 章节 notebooks 作为 SSOT 并可对拍回归
系统 MUST 将 `demo_big_data_report` 的每个纳入 examples gate 的章节 notebook 同时视为教学入口与 SSOT 执行入口：

- 每个章节 notebook MUST 提供一个可被导入调用的 SSOT 入口函数（例如 `run_<chapter_id>()` 或 `run()`），用于执行 deterministic 对拍回归。
- `just examples` 的 headless runner（`justfile` 内联实现）与 pytest MUST 复用该入口执行该章节的对拍回归（不得再通过 `packages/scalim-misc` 的章节实现作为唯一真相来源）。

#### Scenario: chapter SSOT 入口可被 headless runner 调用
- **WHEN** 开发者运行 `just examples` 执行 `demo_big_data_report` 的某个章节
- **THEN** runner MUST 通过导入该章节 notebook 的 SSOT 入口函数来执行
- **AND** runner MUST 输出可定位的 PASS/FAIL 与章节级 summary

### Requirement: `demo_main.py` 保持为 hub/index 入口并可一键跑完章节
系统 MUST 保持 `notebooks/marimo/demo_big_data_report/demo_main.py` 为 `demo_big_data_report` 的 Marimo hub/index 入口.

`demo_main.py` MUST 提供:
- 一键执行全部章节(通过 `demo_big_data_report` 的章节 registry `run_all_chapters(...)`)
- 对章节结果的汇总展示(至少包含每章 `chapter_id/passed/summary`)
- 指向 `chapters_of_yaml_dsl/` 与 `chapters_of_ir/` 内各章节 notebook 的导航信息

#### Scenario: hub 可发现并可汇总
- **WHEN** 读者打开 `notebooks/marimo/demo_big_data_report/demo_main.py`
- **THEN** 能看到章节列表/导航
- **AND** 能运行全部章节并获得汇总结果

### Requirement: canonical YAML SSOT 路径不变
系统 MUST 保持 canonical YAML SSOT 文件路径不变,至少包括:
- `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`
- `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report_fragments.yaml`

#### Scenario: canonical YAML 路径稳定
- **WHEN** 维护者检查上述 canonical YAML 文件路径
- **THEN** 文件存在且路径未被移动或重命名


### Requirement: public API 覆盖必须迁移为独立 suite 并纳入 examples gate
系统 MUST 将稳定公开入口模块 `__all__` 的覆盖回归从 `demo_big_data_report` 主线教学套件中解耦，迁移为独立示例套件（suite），并保持确定性回归门禁不降级。

该 suite MUST：

- 位于 `notebooks/marimo/` 下的独立目录（例如 `notebooks/marimo/example_public_api_suite/`）
- 为每个稳定公开入口模块提供至少一个纳入 gate 的章节入口（章节对 `__all__` 做 fail-fast 覆盖断言）
- 至少包含一个章节演示扩展点（hook/observer/events/components 注入）

#### Scenario: public API suite 与主线解耦
- **WHEN** 维护者检查 `notebooks/marimo/`
- **THEN** MUST 能找到一个独立于 `demo_big_data_report/` 的 public API suite 目录

### Requirement: headless runner 必须覆盖 public API suite
系统 MUST 将 `just examples` 的 headless runner 覆盖默认执行：

- `demo_big_data_report`（YAML DSL 主线教学 + 场景化对拍）
- public API suite（`__all__` 覆盖 + 扩展点演示）

#### Scenario: `just examples` 覆盖 public API suite
- **WHEN** 开发者运行 `just examples`
- **THEN** runner MUST 执行 public API suite 的章节
- **AND** public API suite MUST 通过并输出可定位 summary

### Requirement: public API suite MUST cover curated facade imports
系统 MUST 扩展 public API suite，使其覆盖 curated public surface，而不只是零散的 `__all__` 冒烟。

该 suite 至少 MUST 覆盖：

- `scalim.dsl.yaml_dsl` 的 facade imports
- workflow 辅助公开模块（`workflow` / `workflow_types` / `workflow_paths`）
- `scalim.spec.ir`
- `scalim.shortcuts.resources`（资源类 shortcut 稳定入口 package）
- `scalim.shortcuts.resources.outputs`（输出发现/最新产物定位 facade）

#### Scenario: public API suite exercises curated public imports
- **WHEN** 开发者运行 public API suite
- **THEN** suite MUST 对 curated public surface 做稳定导入断言
- **AND** 这些断言 MUST 与公共表面白名单保持一致

### Requirement: public API suite MUST guard against internal-path drift
系统 MUST 通过 suite、辅助检查或等价 gate 防止内部实现路径重新出现在教学示例与公开入口覆盖中。

#### Scenario: suite detects drift back to internal imports
- **WHEN** 面向用户的示例或 suite 章节重新引用内部实现路径作为官方用法
- **THEN** 对应 gate MUST 失败或给出明确回归提示

### Requirement: public API suite MUST stay consistent with the public API manifest
系统 MUST 将 public API suite 与 public API manifest 视为同一份"稳定公开面 SSOT"的两个投影：
- manifest 表达"允许的公开入口与导出面"
- suite 通过可运行示例与 `__all__` 覆盖断言表达"可用且可回归"

两者 MUST 保持一致：
- suite 覆盖的稳定公开入口集合 MUST 与 manifest 对齐
- suite 中的导入示例 MUST 仅使用 manifest 的 curated entrypoints

#### Scenario: manifest/suite drift is rejected
- **WHEN** suite 覆盖集合与 manifest 不一致（缺失/新增模块或导出）
- **THEN** gate MUST fail-fast 并指出差异

### Requirement: public API suite MUST be paired with a pytest public_api suite
系统 MUST 将 public API catalog 的回归覆盖分为两条互补链路,并要求二者同时存在:
- `notebooks/marimo/example_public_api_suite/`：教学/叙事型示例套件（由 `just examples` gate 执行）
- `tests/public_api/`：用户侧最小闭环 pytest 套件（由默认 pytest 非 bench gate 执行）

两者 MUST 覆盖同一份 public API catalog,并提供可自动化的漂移检测;当覆盖集合不一致时,门禁 MUST fail-fast 并输出差异.

#### Scenario: suite and pytest stay aligned on the public API catalog
- **WHEN** 维护者运行 `just examples` 与默认 pytest 非 bench 套件
- **THEN** public API suite 与 pytest public_api suite MUST 覆盖同一份 public API catalog
- **AND** 若存在差异,对应门禁 MUST 失败并输出差异列表

### Requirement: public API suite MUST demonstrate events and sinks via stable facades
public API suite MUST 以用户侧稳定入口演示 `events` 与 `sinks` 的最小可用用法,并将其纳入 `just examples` gate 的确定性回归范围:
- 事件常量/目录查询入口（例如 `scalim.events` 的稳定导入与基本使用）
- 常用 sinks（例如 `scalim.sinks` 的稳定导入与最小写入闭环）

#### Scenario: events and sinks are exercised in the suite
- **WHEN** 开发者运行 public API suite
- **THEN** suite MUST 执行一个覆盖 `scalim.events` 与 `scalim.sinks` 的章节/用例
- **AND** 该章节/用例 MUST 通过并输出可定位的 summary

### Requirement: user-entry smoke coverage MUST exist for runtime-policy boundary regressions
当某个 runtime-only policy 的错误可能通过 `run_workflow(...)`、public API example 或 notebook 示例暴露给用户时,系统 MUST 在用户侧入口保留至少一条 smoke coverage,用于验证真实入口没有绕过底层边界修复.

#### Scenario: public API example exercises a runtime-policy boundary
- **WHEN** 某个 runtime-only policy 既影响底层 compile/runtime 行为,也影响用户可直接调用的 public API 入口
- **THEN** review 文档 MUST 指出至少一个 notebook / public API smoke 入口
- **AND** 该 smoke 入口 MUST 被设计为最小 fixture + 明确 oracle,而不是依赖偶然覆盖

### Requirement: user-entry smoke MUST complement lower-layer tests rather than replace them
notebook / public API smoke coverage MUST 作为补充层存在,不能替代 compile / runtime / workflow 层的定向测试.

#### Scenario: review distinguishes smoke from branch coverage
- **WHEN** 维护者为 runtime-policy boundary 问题补充用户侧 smoke
- **THEN** review 文档 MUST 同时说明下层定向测试的职责
- **AND** MUST NOT 把 notebook / public API smoke 视为唯一回归保障

### Requirement: public API suite MUST cover `events.type_groups` and `sinks.pandas` via stable facades
public API suite MUST 补齐 Tier1 curated entrypoints 的缺口覆盖，并将其纳入 `just examples` 的确定性回归范围：

- `scalim.events.type_groups`（事件类型分组视图）
- `scalim.sinks.pandas`（可选依赖 pandas sinks 门面）

覆盖 MUST 以"稳定 facade 导入 + 最小可运行闭环 + oracle 断言"的章节形式存在。

#### Scenario: type_groups is exercised in the suite
- **WHEN** 开发者运行 `just examples`
- **THEN** suite MUST 执行一个覆盖 `scalim.events.type_groups` 的章节/用例
- **AND** 该章节/用例 MUST 通过并输出可定位 summary

#### Scenario: pandas sinks are exercised in the suite
- **WHEN** 开发者运行 `just examples`
- **THEN** suite MUST 执行一个覆盖 `scalim.sinks.pandas` 的章节/用例
- **AND** 该章节/用例 MUST 在缺失 pandas 依赖时 fail-fast 给出明确提示（或在 dev 依赖中确保 pandas 可用）

### Requirement: a static gate MUST reject drift between Tier1 curated entrypoints and suite/pytest coverage
系统 MUST 提供一个静态治理 gate（`scripts/check-*.py --check` 形式），用于检测并拒绝以下漂移：

- Tier1 curated entrypoints 集合发生变化，但 `example_public_api_suite` 未同步补齐覆盖
- pytest public_api suite 覆盖集合与 examples 覆盖集合不一致（至少在 Tier1 范围内）

该 gate MUST 输出缺失/新增模块列表，并提供可操作的修复建议（新增章节/更新 pytest 章节选择）。

#### Scenario: adding a tier1 entrypoint without examples coverage is rejected
- **GIVEN** 贡献者新增/修改了 Tier1 marker
- **WHEN** 对应入口模块未被 `example_public_api_suite` 覆盖
- **THEN** gate MUST fail-fast 并指出缺失模块

#### Scenario: pytest and examples drift is rejected
- **GIVEN** examples suite 覆盖了某个 Tier1 入口模块
- **WHEN** pytest public_api suite 未覆盖该入口模块（直接或通过执行章节间接覆盖）
- **THEN** gate MUST fail-fast 并指出差异集合
