# language: zh-CN
# capability: examples-marimo
# purpose: 定义仓库内 Marimo 示例/教学套件治理边界：Marimo notebooks 作为唯一交互载体，headless runner/pytest 作为确定性回归入口，要求执行真相来源位于 notebooks（同源复用）。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: examples-marimo

  @req:r31 @human
  场景: Marimo notebooks 作为唯一交互载体
    - 系统 MUST 将 Marimo notebooks 作为示例/教程的交互载体。用于教学展示的示例 notebooks MUST 包含 `marimo.App`。 系统 MAY 保留非 Marimo 的 headless runner 实现，但该实现 MUST 明确定位为 runner/工具实现，不得承担交互教学入口职责。

  @req:r275 @human
  场景: 示例套件必须同时具备"教学入口"和"回归入口"
    - 系统 MUST 将示例套件拆分为两层并保持同源： 1) **教学入口**：Marimo notebooks，用于逐章讲解与交互查看结果 2) **回归入口**：headless runner/pytest，用于确定性对拍与 CI 集成

  @req:r401 @human
  场景: SSOT 入口必须位于 notebooks 且可被 headless 复用
    - 系统 MUST 将纳入 examples gate 的示例/章节执行真相来源定义为"可被导入调用的 Python 入口函数"，且该入口 MUST 位于 notebooks 侧。 该 SSOT 入口 MUST 满足： - MUST 可被 headless runner 与 pytest 直接导入并执行（不得要求启动 marimo UI server） - MUST 产生可定位的结果摘要（至少包含 `passed` 与 `summary`） - MUST 与对应的 Marimo notebook 交互入口同源（避免"UI 一套逻辑 / headless 一套逻辑"的漂移）

  @req:r497 @human
  场景: Marimo notebooks 必须是薄封装
    - 每个 Marimo notebook MUST 通过调用对应的 SSOT 入口函数来执行核心逻辑并展示结果。 Marimo notebook MUST NOT 在 notebook 内部复制实现一套独立的示例执行主路径，以避免与 SSOT 漂移。

  @req:r576 @human
  场景: headless runner 作为示例对拍入口
    - 系统 MUST 提供一个 headless runner 作为示例 gate 的单一入口，并保证 runner 不依赖 marimo UI。 runner MUST 输出可定位的 PASS/FAIL 与章节级 summary，并以非零退出码表示存在失败。

  @req:r636 @human
  场景: coverage 报告必须映射"notebooks → SSOT → gate"
    - 系统 MUST 维护 coverage 报告作为可检查的 SSOT 报告，用于将示例套件的回归点映射到： - 对应的 Marimo notebook（教学入口） - 对应的 notebooks 侧 SSOT 入口/实现文件（执行真相来源） - 对应的 headless gate 与 pytest 复用点 该文件 MUST 由脚本生成，不得手工维护。

  @req:r682 @human
  场景: notebook helpers 必须 headless 且不依赖 marimo
    - 当引入 notebook 复用 helper（例如路径解析、结果结构化展示、YAML 片段摘录等）时，这些 helper MUST 为纯 Python 且 MUST NOT 依赖 marimo UI server。 这些 helper MAY 位于 notebook_support 模块或 notebooks 下的受控纯 Python 支撑模块。

  @req:r722 @human
  场景: 主线示例套件提供场景化教学章节
    - 系统 MUST 在主线示例套件下提供 YAML DSL 场景化章节目录，并为主线 demo 的每个 SSOT 章节提供一份对应的 Marimo notebook。 主线章节 MUST 以 **YAML DSL 场景化**为主（面向工程使用方），并避免以 IR/Plan 等底层视角作为主线教学内容。 系统 MAY 额外提供 IR 视角的回归章节，但这些章节不得作为主线教学内容。 章节 MUST 覆盖常见场景（如电商报表、广告报表、技术支持、workflow 工作流、大数据报告演示、调试等）。 章节 notebook 文件名 MUST 以章节标识结尾，且 MAY 额外包含有序前缀，用于稳定排序与导航。

  @req:r754 @human
  场景: 主线示例套件章节作为 SSOT 并可对拍回归
    - 系统 MUST 将主线示例套件的每个纳入 examples gate 的章节 notebook 同时视为教学入口与 SSOT 执行入口： - 每个章节 notebook MUST 提供一个可被导入调用的 SSOT 入口函数，用于执行 deterministic 对拍回归 - headless runner 与 pytest MUST 复用该入口执行该章节的对拍回归

  @req:r136 @human
  场景: hub/index 入口提供一键执行与导航
    - 系统 MUST 保持主线示例套件的 hub/index 入口。 该入口 MUST 提供： - 一键执行全部章节（通过章节 registry） - 对章节结果的汇总展示（至少包含每章章节标识/passed/summary） - 指向各章节 notebook 的导航信息

  @req:r159 @human
  场景: canonical YAML SSOT 路径保持稳定
    - 系统 MUST 保持 canonical YAML SSOT 文件路径不变（如示例报表相关的 YAML 文件）。

  @req:r180 @human
  场景: public API 套件必须独立并纳入 examples gate
    - 系统 MUST 将稳定公开入口模块的覆盖回归从主线教学套件中解耦，迁移为独立示例套件，并保持确定性回归门禁不降级。 该 suite MUST： - 位于独立目录 - 为每个稳定公开入口模块提供至少一个纳入 gate 的章节入口（章节对公开入口做覆盖断言） - 至少包含一个章节演示扩展点（hook/observer/events/components 注入）

  @req:r198 @human
  场景: headless runner 必须覆盖所有套件
    - 系统 MUST 将 headless runner 覆盖默认执行主线示例套件、public API suite，以及 README validated examples suite（`example_readme_suite` 或文档声明的等价目录名）。

  @req:r216 @human
  场景: public API 套件覆盖 curated facade 导入
    - 系统 MUST 扩展 public API suite，使其覆盖 curated public surface，而不只是零散的公开入口冒烟。 该 suite 至少 MUST 覆盖： - YAML DSL 的 facade imports - workflow 辅助公开模块 - IR 模块 - shortcuts.resources（资源类 shortcut 稳定入口 package） - shortcuts.resources.outputs（输出发现/最新产物定位 facade）

  @req:r229 @human
  场景: 防止内部路径漂移回教学示例
    - 系统 MUST 通过 suite、辅助检查或等价 gate 防止内部实现路径重新出现在教学示例与公开入口覆盖中。

  @req:r241 @human
  场景: public API suite 与 manifest 保持一致
    - 系统 MUST 将 public API suite 与 public API manifest 视为同一份"稳定公开面 SSOT"的两个投影： - manifest 表达"允许的公开入口与导出面" - suite 通过可运行示例与覆盖断言表达"可用且可回归" 两者 MUST 保持一致： - suite 覆盖的稳定公开入口集合 MUST 与 manifest 对齐 - suite 中的导入示例 MUST 仅使用 manifest 的 curated entrypoints

  @req:r17 @human
  场景: public API suite 与 pytest 套件形成双重覆盖
    - 系统 MUST 将 public API catalog 的回归覆盖分为两条互补链路，并要求二者同时存在： - example_public_api_suite：教学/叙事型示例套件（由 examples gate 执行） - tests/public_api/：用户侧最小闭环 pytest 套件（由默认 pytest 非 bench gate 执行） 两者 MUST 覆盖同一份 public API catalog，并提供可自动化的漂移检测；当覆盖集合不一致时，门禁 MUST fail-fast 并输出差异。

  @req:r18 @human
  场景: public API suite 演示 events 和 sinks
    - public API suite MUST 以用户侧稳定入口演示 `events` 与 `sinks` 的最小可用用法，并将其纳入 examples gate 的确定性回归范围： - 事件常量/目录查询入口（例如 events 的稳定导入与基本使用） - 常用 sinks（例如 sinks 的稳定导入与最小写入闭环）

  @req:r19 @human
  场景: runtime-policy 边界回归必须有用户入口 smoke coverage
    - 当某个 runtime-only policy 的错误可能通过 run_workflow、public API example 或 notebook 示例暴露给用户时，系统 MUST 在用户侧入口保留至少一条 smoke coverage，用于验证真实入口没有绕过底层边界修复。

  @req:r20 @human
  场景: 用户入口 smoke 补充而非替代底层测试
    - notebook / public API smoke coverage MUST 作为补充层存在，不能替代 compile / runtime / workflow 层的定向测试。

  @req:r21 @human
  场景: Tier1 curated entrypoints 与 suite/pytest 覆盖必须同步
    - 系统 MUST 提供一个静态治理 gate，用于检测并拒绝以下漂移： - Tier1 curated entrypoints 集合发生变化，但 example_public_api_suite 未同步补齐覆盖 - pytest public_api suite 覆盖集合与 examples 覆盖集合不一致（至少在 Tier1 范围内） 该 gate MUST 输出缺失/新增模块列表，并提供可操作的修复建议。

  @req:r989 @human
  场景: README validated suite is a marimo examples suite
    - 根 README 的 validated examples suite（公开页假数据最小例与内存对比；合约交叉引用 `governance-readme-examples` 的注入/图资产面）MUST 以独立 marimo 套件形式落在 `notebooks/marimo/example_readme_suite/`（或文档声明的等价路径），提供可导入章节 SSOT 与 hub/`demo_main`，并 MUST 纳入本 capability 的 examples gate 默认覆盖。该套件 MUST NOT 替代主线 `demo_big_data_report` 教学地位；公开页注入/漂移细节以 `governance-readme-examples` 为准。
  @req:r31 @human
  场景: 示例-notebooks-可被识别为-marimo
    - 必须成立：当 维护者枚举用于教学展示的 notebooks；那么 这些 notebooks 文件内容 MUST 包含 `marimo.App`
    当 维护者枚举用于教学展示的 notebooks
    那么 这些 notebooks 文件内容 MUST 包含 `marimo.App`
  @req:r275 @human
  场景: 套件具备双入口
    - 必须成立：当 维护者为某个示例套件新增一个可运行章节；那么 该章节 MUST 同时具备一个 Marimo notebook 入口
    当 维护者为某个示例套件新增一个可运行章节
    那么 该章节 MUST 同时具备一个 Marimo notebook 入口
  @req:r401 @human
  场景: 新增章节时-ssot-入口可被-runner-pytest-复用
    - 必须成立：当 维护者为示例体系新增一个纳入 gate 的章节 notebook；那么 该章节 MUST 提供一个 notebooks 侧 SSOT 入口函数供 headless runner 与 pytest 复用
    当 维护者为示例体系新增一个纳入 gate 的章节 notebook
    那么 该章节 MUST 提供一个 notebooks 侧 SSOT 入口函数供 headless runner 与 pytest 复用
  @req:r497 @human
  场景: notebook-调用-ssot-入口
    - 必须成立：当 读者在 marimo 中运行任一示例章节 notebook；那么 notebook 的核心执行入口 MUST 来自 notebooks 侧的 SSOT 入口函数
    当 读者在 marimo 中运行任一示例章节 notebook
    那么 notebook 的核心执行入口 MUST 来自 notebooks 侧的 SSOT 入口函数
  @req:r576 @human
  场景: examples-gate-可在-ci-中稳定运行
    - 必须成立：当 开发者运行 examples gate（或等价入口）；那么 headless runner MUST 执行示例套件并输出章节级 PASS/FAIL 与 summary
    当 开发者运行 examples gate（或等价入口）
    那么 headless runner MUST 执行示例套件并输出章节级 PASS/FAIL 与 summary
  @req:r636 @human
  场景: 新增示例时-coverage-报告同步
    - 必须成立：当 维护者新增或调整一个示例/章节回归点；那么 运行 coverage 生成命令 MUST 更新 coverage 报告
    当 维护者新增或调整一个示例/章节回归点
    那么 运行 coverage 生成命令 MUST 更新 coverage 报告
  @req:r682 @human
  场景: helper-可被-headless-runner-导入
    - 必须成立：当 在不导入 marimo 的 Python 进程中导入这些 helper 模块；那么 导入成功且不触发 marimo 依赖
    当 在不导入 marimo 的 Python 进程中导入这些 helper 模块
    那么 导入成功且不触发 marimo 依赖
  @req:r722 @human
  场景: 场景化章节-notebooks-存在
    - 必须成立：当 维护者检查主线示例套件的章节目录；那么 每个主要场景都存在至少一份以对应章节标识结尾的 notebook 文件
    当 维护者检查主线示例套件的章节目录
    那么 每个主要场景都存在至少一份以对应章节标识结尾的 notebook 文件
  @req:r754 @human
  场景: chapter-ssot-入口可被-headless-runner-调用
    - 必须成立：当 开发者运行 examples gate 执行主线示例套件的某个章节；那么 runner MUST 通过导入该章节 notebook 的 SSOT 入口函数来执行
    当 开发者运行 examples gate 执行主线示例套件的某个章节
    那么 runner MUST 通过导入该章节 notebook 的 SSOT 入口函数来执行
  @req:r136 @human
  场景: hub-可发现并可汇总
    - 必须成立：当 读者打开主线示例套件的 hub 入口；那么 能看到章节列表/导航
    当 读者打开主线示例套件的 hub 入口
    那么 能看到章节列表/导航
  @req:r159 @human
  场景: canonical-yaml-路径稳定
    - 必须成立：当 维护者检查 canonical YAML 文件路径；那么 文件存在且路径未被移动或重命名
    当 维护者检查 canonical YAML 文件路径
    那么 文件存在且路径未被移动或重命名
  @req:r180 @human
  场景: public-api-suite-与主线解耦
    - 必须成立：当 维护者检查 notebooks 目录；那么 MUST 能找到一个独立于主线示例套件的 public API suite 目录
    当 维护者检查 notebooks 目录
    那么 MUST 能找到一个独立于主线示例套件的 public API suite 目录
  @req:r198 @human
  场景: examples-gate-覆盖所有套件
    - 必须成立：当 开发者运行 examples gate；那么 runner MUST 执行主线示例套件、public API suite 与 README validated suite 的章节
    当 开发者运行 examples gate
    那么 runner MUST 执行主线示例套件、public API suite 与 README validated suite 的章节
  @req:r216 @human
  场景: public-api-suite-exercises-curated-public-imports
    - 必须成立：当 开发者运行 public API suite；那么 suite MUST 对 curated public surface 做稳定导入断言
    当 开发者运行 public API suite
    那么 suite MUST 对 curated public surface 做稳定导入断言
  @req:r229 @human
  场景: suite-detects-drift-back-to-internal-imports
    - 必须成立：当 面向用户的示例或 suite 章节重新引用内部实现路径作为官方用法；那么 对应 gate MUST 失败或给出明确回归提示
    当 面向用户的示例或 suite 章节重新引用内部实现路径作为官方用法
    那么 对应 gate MUST 失败或给出明确回归提示
  @req:r241 @human
  场景: manifest-suite-drift-is-rejected
    - 必须成立：当 suite 覆盖集合与 manifest 不一致（缺失/新增模块或导出）；那么 gate MUST fail-fast 并指出差异
    当 suite 覆盖集合与 manifest 不一致（缺失/新增模块或导出）
    那么 gate MUST fail-fast 并指出差异
  @req:r17 @human
  场景: suite-and-pytest-stay-aligned-on-the-public-api-catalog
    - 必须成立：当 维护者运行 examples gate 与默认 pytest 非 bench 套件；那么 public API suite 与 pytest public_api suite MUST 覆盖同一份 public API catalog
    当 维护者运行 examples gate 与默认 pytest 非 bench 套件
    那么 public API suite 与 pytest public_api suite MUST 覆盖同一份 public API catalog
  @req:r18 @human
  场景: events-and-sinks-are-exercised-in-the-suite
    - 必须成立：当 开发者运行 public API suite；那么 suite MUST 执行一个覆盖 events 与 sinks 的章节/用例
    当 开发者运行 public API suite
    那么 suite MUST 执行一个覆盖 events 与 sinks 的章节/用例
  @req:r19 @human
  场景: public-api-example-exercises-a-runtime-policy-boundary
    - 必须成立：当 某个 runtime-only policy 既影响底层 compile/runtime 行为，也影响用户可直接调用的 public API 入口；那么 review 文档 MUST 指出至少一个 notebook / public API smoke 入口
    当 某个 runtime-only policy 既影响底层 compile/runtime 行为，也影响用户可直接调用的 public API 入口
    那么 review 文档 MUST 指出至少一个 notebook / public API smoke 入口
  @req:r20 @human
  场景: review-distinguishes-smoke-from-branch-coverage
    - 必须成立：当 维护者为 runtime-policy boundary 问题补充用户侧 smoke；那么 review 文档 MUST 同时说明下层定向测试的职责
    当 维护者为 runtime-policy boundary 问题补充用户侧 smoke
    那么 review 文档 MUST 同时说明下层定向测试的职责
  @req:r21 @human
  场景: adding-a-tier1-entrypoint-without-examples-coverage-is-rejec
    - 必须成立：假如 贡献者新增/修改了 Tier1 marker；当 对应入口模块未被 example_public_api_suite 覆盖；那么 gate MUST fail-fast 并指出缺失模块
    假如 贡献者新增/修改了 Tier1 marker
    当 对应入口模块未被 example_public_api_suite 覆盖
    那么 gate MUST fail-fast 并指出缺失模块

  @req:r21 @human
  场景: pytest-and-examples-drift-is-rejected
    - 必须成立：假如 examples suite 覆盖了某个 Tier1 入口模块；当 pytest public_api suite 未覆盖该入口模块；那么 gate MUST fail-fast 并指出差异集合
    假如 examples suite 覆盖了某个 Tier1 入口模块
    当 pytest public_api suite 未覆盖该入口模块
    那么 gate MUST fail-fast 并指出差异集合

  @req:r989 @human
  场景: README-suite-registered-as-marimo-suite
    - 必须成立：当 维护者检查 notebooks/marimo 与 examples gate 默认覆盖；那么 MUST 能定位到 README validated suite 目录与 chapters registry，且 examples gate 默认执行其章节
    当 维护者检查 notebooks/marimo 与 examples gate 默认覆盖
    那么 MUST 能定位到 README validated suite 目录与 chapters registry，且 examples gate 默认执行其章节

  @req:r989 @human
  场景: README-suite-does-not-replace-mainline
    - 必须成立：当 维护者枚举主线 demo_big_data_report 与 README suite；那么 二者 MUST 可区分；README suite MUST NOT 被表述为主线教学唯一入口
    当 维护者枚举主线 demo_big_data_report 与 README suite
    那么 二者 MUST 可区分；README suite MUST NOT 被表述为主线教学唯一入口
