## ADDED Requirements

### Requirement: 示例 SSOT 必须位于 notebooks 且可被 headless 复用
系统 MUST 将 `notebooks/marimo/` 下纳入 examples gate 的示例/章节执行真相来源定义为“可被导入调用的 Python 入口函数”，且该入口 MUST 位于 notebooks 侧（例如同一 notebook 模块内的 `run_*()`，或 notebooks 侧的纯 Python 支撑模块）。

该 SSOT 入口 MUST 满足：

- MUST 可被 `notebooks/marimo/run_examples.py` 与 pytest 直接导入并执行（允许导入 `marimo` 与 notebook 模块，但不得要求启动 marimo UI server）。
- MUST 产生可定位的结果摘要（至少包含 `passed` 与 `summary`；可选 `details` 供 notebook UI 展示与排障）。
- MUST 与对应的 Marimo notebook 交互入口同源：notebook 侧展示的核心执行路径 MUST 复用同一 SSOT 入口（避免 “UI 一套逻辑 / headless 一套逻辑” 的漂移）。

#### Scenario: 新增章节时 SSOT 入口可被 runner/pytest 复用
- **WHEN** 维护者为示例体系新增一个纳入 gate 的章节 notebook
- **THEN** 该章节 MUST 提供一个 notebooks 侧 SSOT 入口函数供 `notebooks/marimo/run_examples.py` 与 pytest 复用
- **AND** 该 notebook 的交互执行路径 MUST 调用同一入口函数得到结果并展示

## MODIFIED Requirements

### Requirement: Marimo notebooks 必须是薄封装,不得形成第二套真相
每个 Marimo notebook MUST 通过调用对应的 SSOT `run_*()`/example case 来执行核心逻辑并展示结果.

Marimo notebook MUST NOT 在 notebook 内部复制实现一套独立的示例执行主路径(例如以 cell 代码绕开 SSOT 入口、仅在 UI 模式下生效的分支逻辑),以避免与 headless runner/pytest 执行路径漂移.

#### Scenario: notebook 调用 SSOT 入口
- **WHEN** 读者在 marimo 中运行任一示例章节 notebook
- **THEN** notebook 的核心执行入口 MUST 来自 notebooks 侧的 SSOT `run_*()`/example case
- **AND** headless runner/pytest MUST 复用同一 SSOT 入口执行对拍回归

### Requirement: `just examples` 继续通过 headless runner 执行示例对拍
系统 MUST 提供一个 headless runner 作为 `just examples` 的单一入口,并保证 runner 不依赖 marimo UI.

runner MUST 输出可定位的 PASS/FAIL 与章节级 summary,并以非零退出码表示存在失败.

#### Scenario: examples gate 可在 CI 中稳定运行
- **WHEN** 开发者运行 `just examples`(或等价入口)
- **THEN** headless runner MUST 执行示例套件并输出章节级 PASS/FAIL 与 summary
- **AND** 当存在失败时,进程退出码 MUST 非零

### Requirement: marimo_coverage.gen.md 明确映射“notebooks → SSOT → gate”
系统 MUST 维护 `notebooks/marimo/marimo_coverage.gen.md` 作为可检查的 SSOT 报告,用于将示例套件的回归点映射到:

- 对应的 Marimo notebook(教学入口)
- 对应的 notebooks 侧 SSOT 入口/实现文件(执行真相来源)
- 对应的 headless gate(`notebooks/marimo/run_examples.py`)与 pytest 复用点(如存在)

该文件 MUST 由脚本 `scripts/gen-marimo-coverage.py` 生成,不得手工维护.

#### Scenario: 新增示例时 coverage 报告同步
- **WHEN** 维护者新增或调整一个示例/章节回归点
- **THEN** 运行 `just gen-marimo-coverage` MUST 更新 `notebooks/marimo/marimo_coverage.gen.md`
- **AND** `just marimo-coverage-drift-check` MUST 在 CI 中可用且能检测到 drift

## REMOVED Requirements

### Requirement: SSOT 执行与对拍逻辑必须下沉到 `packages/scalim-misc`
**Reason**: 本变更将 notebooks 重新定义为“用户第一”的教学与执行真相来源；教学主流程代码需要在 notebook 中可见且可照抄改写，`scalim-misc` 仅保留 fixtures/oracle/工具函数。

**Migration**: 将 `packages/scalim-misc` 中承载教学主流程的 `run_*()`/example case 迁移到 notebooks 侧 SSOT 入口（同 notebook 或 notebooks 侧支撑模块），并更新 `notebooks/marimo/run_examples.py`、pytest 与 `scripts/gen-marimo-coverage.py` 以复用 notebooks 侧入口。

