## MODIFIED Requirements

### Requirement: 示例 notebooks 以 Marimo 为唯一交互载体
系统 MUST 将 `notebooks/marimo/` 作为示例/教程的交互载体目录;其中用于教学展示的示例 notebooks MUST 为 Marimo notebook(即包含 `marimo.App`).

系统 MAY 在 `notebooks/marimo/` 下保留非 Marimo 的 headless runner 实现,但该实现 MUST 明确定位为 runner/工具实现,不得承担交互教学入口职责.

#### Scenario: 示例 notebooks 可被识别为 Marimo
- **WHEN** 维护者枚举 `notebooks/marimo/**.py` 中用于教学展示的 notebooks
- **THEN** 这些 notebooks 文件内容 MUST 包含 `marimo.App`

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

### Requirement: marimo_coverage.gen.md 明确映射“notebooks → SSOT → gate”
系统 MUST 维护 `notebooks/marimo/marimo_coverage.gen.md` 作为可检查的 SSOT 报告,用于将示例套件的回归点映射到:

- 对应的 Marimo notebook(教学入口)
- 对应的 notebooks 侧 SSOT 入口/实现文件(执行真相来源)
- 对应的 headless gate(`just examples`)与 pytest 复用点(如存在)

该文件 MUST 由脚本 `scripts/gen-marimo-coverage.py` 生成,不得手工维护.

#### Scenario: 新增示例时 coverage 报告同步
- **WHEN** 维护者新增或调整一个示例/章节回归点
- **THEN** 运行 `just gen-marimo-coverage` MUST 更新 `notebooks/marimo/marimo_coverage.gen.md`
- **AND** `just marimo-coverage-drift-check` MUST 在 CI 中可用且能检测到 drift

