# marimo-notebooks-examples-suite Specification

**状态: ✅ 已实现**

## Purpose
定义仓库内 `notebooks/marimo/` 的示例/教学套件治理边界:Marimo notebooks 作为唯一交互载体,headless runner/pytest 作为确定性回归入口,并要求执行真相下沉到 `packages/scalim-misc`.

## Context
示例体系需要同时满足“可学”(交互讲解)与“可测”(确定性回归).如果 notebook 内复制实现,将形成第二套真相并导致 drift/门禁碎片化.

## Related Code (as implemented)
- `notebooks/marimo/index.py` (示例 hub/导航与约定说明)
- `notebooks/marimo/run_examples.py` (`just examples` headless runner)
- `scripts/gen-marimo-coverage.py` + `notebooks/marimo/marimo_coverage.gen.md` (覆盖报告生成与 drift-check)
- `packages/scalim-misc/src/scalim_misc/notebook_support/*` (notebook 复用 helper; 不依赖 marimo)

## Requirements
### Requirement: 示例 notebooks 以 Marimo 为唯一交互载体
系统 MUST 将 `notebooks/marimo/` 作为示例/教程的交互载体目录;其中用于教学展示的示例 notebooks MUST 为 Marimo notebook(即包含 `marimo.App`).

系统 MAY 在 `notebooks/marimo/` 下保留非 Marimo 的 headless 脚本,但该脚本 MUST 明确定位为 runner/工具脚本,不得承担交互教学入口职责(例如 `notebooks/marimo/run_examples.py`).

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

### Requirement: SSOT 执行与对拍逻辑必须下沉到 `packages/scalim-misc`
系统 MUST 将示例/章节的可运行执行逻辑与 deterministic oracle 逻辑下沉到 `packages/scalim-misc/src/scalim_misc/**`,并提供稳定的 `run_*()`/example case 入口供 runner 与 notebooks 复用.

该 SSOT 层 MUST NOT 依赖 marimo.

#### Scenario: SSOT 逻辑可被 headless 复用
- **WHEN** 在不导入 marimo 的 Python 进程中导入并执行示例 SSOT `run_*()`/example case
- **THEN** 执行 MUST 成功或给出可定位的失败摘要
- **AND** 不应触发 marimo 依赖加载

### Requirement: Marimo notebooks 必须是薄封装,不得形成第二套真相
每个 Marimo notebook MUST 通过调用对应的 SSOT `run_*()`/example case 来执行核心逻辑并展示结果.

Marimo notebook MUST NOT 在 notebook 内部复制实现一套独立的示例执行主路径(例如自行构建与执行整套 demo 引擎链路作为章节唯一真相),以避免与 SSOT 漂移.

#### Scenario: notebook 调用 SSOT 入口
- **WHEN** 读者在 marimo 中运行任一示例章节 notebook
- **THEN** notebook 的核心执行入口 MUST 来自 `packages/scalim-misc/src/scalim_misc/**` 中的 SSOT `run_*()`/example case

### Requirement: `just examples` 继续通过 headless runner 执行示例对拍
系统 MUST 提供一个 headless runner 作为 `just examples` 的单一入口,并保证 runner 不依赖 marimo UI.

runner MUST 输出可定位的 PASS/FAIL 与章节级 summary,并以非零退出码表示存在失败.

#### Scenario: examples gate 可在 CI 中稳定运行
- **WHEN** 开发者运行 `just examples`(或等价入口)
- **THEN** headless runner MUST 执行示例套件并输出章节级 PASS/FAIL 与 summary
- **AND** 当存在失败时,进程退出码 MUST 非零

### Requirement: canonical YAML SSOT 路径保持不变
系统 MUST 保持 canonical YAML SSOT 文件路径不变,至少包括:
- `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml`
- `notebooks/marimo/demo_big_data_report/by_yaml_dsl/ecommerce_report_fragments.yaml`

#### Scenario: canonical YAML 路径稳定
- **WHEN** 维护者检查上述 canonical YAML 文件路径
- **THEN** 文件 MUST 存在且路径未被移动或重命名

### Requirement: marimo_coverage.gen.md 明确映射“notebooks → SSOT → gate”
系统 MUST 维护 `notebooks/marimo/marimo_coverage.gen.md` 作为可检查的 SSOT 报告,用于将示例套件的回归点映射到:

- 对应的 Marimo notebook(教学入口)
- 对应的 `packages/scalim-misc` SSOT 实现文件(真相来源)
- 对应的 headless gate(`notebooks/marimo/run_examples.py`)与 pytest 复用点(如存在)

该文件 MUST 由脚本 `scripts/gen-marimo-coverage.py` 生成,不得手工维护.

#### Scenario: 新增示例时 coverage 报告同步
- **WHEN** 维护者新增或调整一个示例/章节回归点
- **THEN** 运行 `just gen-marimo-coverage` MUST 更新 `notebooks/marimo/marimo_coverage.gen.md`
- **AND** `just marimo-coverage-drift-check` MUST 在 CI 中可用且能检测到 drift

