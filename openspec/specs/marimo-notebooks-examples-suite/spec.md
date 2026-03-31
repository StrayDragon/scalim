# marimo-notebooks-examples-suite Specification

**状态: ✅ 已实现**

## Purpose
定义仓库内 `notebooks/marimo/` 的示例/教学套件治理边界:Marimo notebooks 作为唯一交互载体,headless runner/pytest 作为确定性回归入口,并要求执行真相来源位于 notebooks(同源复用).

## Context
示例体系需要同时满足“可学”(交互讲解)与“可测”(确定性回归).若 UI 与 headless 执行路径分叉,将形成第二套真相并导致 drift/门禁碎片化.

## Related Code (as implemented)
- `justfile` (`just examples` gate 入口; runner 内联实现)
- `notebooks/marimo/` (示例 suites: `demo_*`/`example_*` + `chapters*/registry.py` 契约)
- `scripts/gen-marimo-coverage.py` + `notebooks/marimo/marimo_coverage.gen.toon` (覆盖报告生成与 drift-check)
- `packages/scalim-misc/src/scalim_misc/notebook_support/*` (notebook 复用 helper; 不依赖 marimo)
## Requirements
### Requirement: 示例 notebooks 以 Marimo 为唯一交互载体
系统 MUST 将 `notebooks/marimo/` 作为示例/教程的交互载体目录;其中用于教学展示的示例 notebooks MUST 为 Marimo notebook(即包含 `marimo.App`).

系统 MAY 在 `notebooks/marimo/` 下保留非 Marimo 的 headless runner 实现,但该实现 MUST 明确定位为 runner/工具实现,不得承担交互教学入口职责.

#### Scenario: 示例 notebooks 可被识别为 Marimo
- **WHEN** 维护者枚举 `notebooks/marimo/**.py` 中用于教学展示的 notebooks
- **THEN** 这些 notebooks 文件内容 MUST 包含 `marimo.App`

### Requirement: 每个示例套件必须同时具备“教学入口”和“回归入口”
系统 MUST 将示例套件拆分为两层并保持同源:

1) **教学入口**: Marimo notebooks,用于逐章讲解与交互查看结果
2) **回归入口**: headless runner/pytest,用于确定性对拍与 CI 集成

#### Scenario: 套件具备双入口
- **WHEN** 维护者为某个示例套件新增一个可运行章节
- **THEN** 该章节 MUST 同时具备一个 Marimo notebook 入口
- **AND** MUST 同时具备一个可被 headless runner 执行的 SSOT 用例入口

### Requirement: 示例 SSOT 必须位于 notebooks 且可被 headless 复用
系统 MUST 将 `notebooks/marimo/` 下纳入 examples gate 的示例/章节执行真相来源定义为“可被导入调用的 Python 入口函数”，且该入口 MUST 位于 notebooks 侧（例如同一 notebook 模块内的 `run_*()`，或 notebooks 侧的纯 Python 支撑模块）。

该 SSOT 入口 MUST 满足：

- MUST 可被 `just examples` 所执行的 headless runner 与 pytest 直接导入并执行（允许导入 `marimo` 与 notebook 模块，但不得要求启动 marimo UI server）。
- MUST 产生可定位的结果摘要（至少包含 `passed` 与 `summary`；可选 `details` 供 notebook UI 展示与排障）。
- MUST 与对应的 Marimo notebook 交互入口同源：notebook 侧展示的核心执行路径 MUST 复用同一 SSOT 入口（避免 “UI 一套逻辑 / headless 一套逻辑” 的漂移）。

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

### Requirement: canonical YAML SSOT 路径保持不变
系统 MUST 保持 canonical YAML SSOT 文件路径不变,至少包括:
- `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml`
- `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report_fragments.yaml`

#### Scenario: canonical YAML 路径稳定
- **WHEN** 维护者检查上述 canonical YAML 文件路径
- **THEN** 文件 MUST 存在且路径未被移动或重命名

### Requirement: marimo_coverage.gen.toon 明确映射“notebooks → SSOT → gate”
系统 MUST 维护 `notebooks/marimo/marimo_coverage.gen.toon` 作为可检查的 SSOT 报告,用于将示例套件的回归点映射到:

- 对应的 Marimo notebook(教学入口)
- 对应的 notebooks 侧 SSOT 入口/实现文件(执行真相来源)
- 对应的 headless gate(`just examples`)与 pytest 复用点(如存在)

该文件 MUST 由脚本 `scripts/gen-marimo-coverage.py` 生成,不得手工维护.

#### Scenario: 新增示例时 coverage 报告同步
- **WHEN** 维护者新增或调整一个示例/章节回归点
- **THEN** 运行 `just gen-marimo-coverage` MUST 更新 `notebooks/marimo/marimo_coverage.gen.toon`
- **AND** `just marimo-coverage-drift-check` MUST 在 CI 中可用且能检测到 drift
