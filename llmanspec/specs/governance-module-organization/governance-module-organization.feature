# language: zh-CN
# capability: governance-module-organization
# purpose: 定义运行时模块的边界、入口最小化与依赖约束,避免将内部实现路径误用为公共 API,并保持模块层级单向依赖与 Python 3.6 运行时兼容性. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: governance-module-organization

  @req:r52 @human
  场景: internal implementation paths MUST remain non-contract
    - 系统 MUST 将"可导入"与"可承诺"分为两个层级：稳定公开入口由显式白名单定义,其余实现路径即使可导入也 MUST 视为内部实现细节.

  @req:r296 @human
  场景: facade modules MUST use explicit export whitelists
    - 稳定公开入口的 facade 模块 MUST 使用显式 `__all__` 或等价白名单控制导出面,避免内部符号随重构被无意带出.

  @req:r420 @human
  场景: yaml_dsl MUST maintain subpackage structure
    - yaml_dsl 的解析与 runtime MUST 保持显式子包结构：`_internal.config_parsing` 采用 package 形式,保留 `loader.py`/`validator.py` 作为稳定入口；`runtime` 采用子模块组织并通过稳定入口提供访问.

  @req:r514 @human
  场景: execution/planning MUST minimize __init__.py surface
    - 复杂实现 MUST 放入显式子模块,`__init__.py` 仅允许最小 glue.对于内部实现子包,`__init__.py` MUST NOT 通过 re-export 暴露实现符号；对于领域 facade 包根,MAY 提供少量稳定符号 re-export 但 MUST 使用显式 `__all__` 且避免层级反转.

  @req:r590 @human
  场景: cross-cutting helpers MUST have single SSOT implementation
    - 当"基础设施级"逻辑被多个领域模块复用时,系统 MUST 避免重复实现：MUST 将该逻辑抽取到单一 SSOT 内部 util 模块,该 util 模块 MUST 保持低耦合避免层级反转,测试口径 MUST 覆盖该 SSOT util.

  @req:r645 @human
  场景: C901 hotspots MUST be decomposed into testable boundaries
    - 当核心热点函数因复杂度被 `# noqa: C901` 放行时,系统 MUST 将其视为治理对象：MUST 优先通过规则函数提取降低复杂度,被提取的规则函数 MUST 具备明确输入输出并可通过单元测试覆盖,新增或保留 `# noqa: C901` 时 MUST 同时标注可追踪的拆分计划引用.

  @req:r689 @human
  场景: core hotspot modules MUST be split by responsibility
    - 系统 MUST 对核心热点实现采用职责分层的子模块组织,至少以下热点路径 MUST 被视为持续治理对象：schema_dsl models、execution adaptive、observability presets、hooks. 在上述热点重构过程中,系统 MUST 保持既有稳定入口可用,不得因内部拆分破坏调用方基本导入能力.

  @req:r727 @human
  场景: operator package MUST use consistent entry convention
    - 系统 MUST 对 package 形态的 operator 统一使用 `<op>/executor.py` 作为入口模块,`__init__.py` 不通过 re-export 暴露 executor 类.

  @req:r759 @human
  场景: layer dependencies MUST remain unidirectional
    - 系统 MUST 保持核心层级依赖方向可审计且单向：planning MUST NOT 依赖 execution 实现,dsl runtime MUST NOT 直接依赖 execution 内部实现,hooks/observability MUST 通过事件契约交互不得反向依赖 DSL 专有配置,workflow runtime MUST NOT 反向依赖 DSL 层.

  @req:r140 @human
  场景: runtime core MUST NOT import dev tooling packages
    - runtime core MUST NOT 导入 dev tooling packages (例如 scalim-misc),dev tooling packages MAY 导入 runtime core 并消费其 SSOT/公共入口.该约束禁止通过 optional hook 或动态导入绕开.

  @req:r163 @human
  场景: no new top-level public facades
    - 系统 MUST NOT 新增顶层公共 facade (如 `api.py` 或在顶层 `__init__.py` 做公共 re-export 聚合),公共入口继续采用显式模块路径.

  @req:r183 @human
  场景: Python 3.6 typing compatibility MUST be centralized
    - 系统 MUST 保持 Python 3.6 兼容；运行时内扩展 typing 能力 (如 `Self`/`override`) 仅允许通过 `vendor/compact/typing_extensionsx.py` 引入,MUST 通过 lint 禁止直接导入 `typing_extensions`.

  @req:r201 @human
  场景: vendor modules MUST be auditable
    - 系统 MUST 在 vendor README 维护每个 vendor 子模块的最小 provenance (来源与许可证) 以及 usage/保留理由.未被主路径使用的 vendor 子模块 MUST 记录明确保留理由与预计接入点,否则应移除.

  @req:r219 @human
  场景: stdlib naming conflicts MUST be avoided
    - 系统 MUST NOT 在运行时引入与 Python 标准库同名且语义含混的模块文件 (如 `types.py`、`inspect.py`、`trace.py`),以避免导入语义混淆与潜在 shadowing 风险.系统 MUST 提供自动化检查以阻止该类命名回归.

  @req:r232 @human
  场景: batch hotspot refactoring MAY cover multiple modules in one change
    - 系统 MUST 允许将多个已确认热点模块的结构重构放在单个 change 中统一规划与实施,前提是各热点仍通过显式 phase 与任务分组保持边界清晰.

  @req:r244 @human
  场景: hotspot governance MAY be split into independent phases
    - 系统 MUST 允许将热点模块治理拆分为多个 phase 独立推进；当维护者先处理 hooks/observability managers 时,不得强制与其它热点模块在同一 change 中一起重构.

  @req:r253 @human
  场景: hotspot modules MUST be guarded by function complexity
    - 系统 MUST 对约定 ENTRY 热点路径提供函数级复杂度硬闸：当任意函数的 cognitive(Sonar) 或 cyclomatic(McCabe) 超过约定阈值 (MAX_COGNITIVE=80 / MAX_CYCLOMATIC=44; SSOT 为 scripts/check-complexity.py 常量) 时,门禁 MUST fail-fast; 维护者 MUST 优先降低函数复杂度或按职责拆分,拆分 MUST 保持行为等价并由自动化回归覆盖. 物理行数仅为 SHOULD 指导; 单入口路径 MAY 在极高硬味天花板 (LOC_HARD_TASTE=2500) 时仍失败以防无底膨胀. 与 r645 (C901 / allow-c901 plan) 互补,不以行数替代复杂度闸.

  @req:r260 @human
  场景: import graph MUST be acyclic and ban function-local imports
    - 系统 MUST 保持主包 (排除 vendor) 的模块导入图无环.同时,主包模块 MUST NOT 在函数体内出现 import 语句,以避免通过局部导入绕开依赖方向约束并隐藏导入副作用.该约束 MUST 由可独立运行的静态门禁守护.

  @req:r267 @human
  场景: yaml_dsl runtime MUST NOT contain workflow runtime modules
    - 系统 MUST 保持 yaml_dsl runtime 子包不包含 workflow runtime 语义模块 (例如 `workflow_*.py`),以避免把 workflow 层实现符号误放入 DSL runtime.该约束 MUST 由可独立运行的静态门禁守护.

  @req:r378 @human
  场景: workflow_compile hotspot MUST be decomposed into responsibility-focused submodul
    - 系统 MUST 将 `workflow_compile.py` 这类多职责热点模块拆分为职责单一的子模块,以降低复杂度并提升可测试性。 拆分后系统 MUST 满足: - 对外稳定入口(例如 `compile_workflow_ir`)保持可用且行为不变 - 纯规则/校验逻辑 MUST 位于可单测的子模块中(无 IO、输入输出明确) - IO 相关逻辑(例如 demand YAML 预加载) MUST 与纯规则逻辑分离

  @req:r384 @human
  场景: output_composition hotspot MUST be decomposed into spec/router/builder submodule
    - 系统 MUST 将 output composition 热点实现拆分为职责单一的子模块(例如 `execution/output_composition/{specs,router,build}.py`),至少分离: - spec/数据类层 - router/runtime 实现层 - builder/工厂层 拆分后系统 MUST 保持: - `scalim.execution.output_composition` 的稳定导入路径继续可用 - 对外行为不变(纯重构)

  @req:r22 @human
  场景: openpyxl write helpers MUST use shared SSOT util
    - 系统 MUST 将 openpyxl write_only 关闭与原子保存辅助逻辑集中到单一内部 util(`src/scalim/_internal/utils/openpyxl_helpers.py`): - `best_effort_close_write_only_worksheet` / `best_effort_close_write_only_workbook_worksheets` / `save_openpyxl_workbook_atomic` MUST 为 SSOT - `workflow` 的 workbook/sheetbook 资源与 `sinks` Excel 实现 MUST 复用该 SSOT,不得再维护平行副本 - util MUST NOT 反向依赖 `sinks`/`workflow` 领域模块 - `resources_workbook` 对外 re-export 的兼容符号 MUST 保持可导入

  @req:r23 @human
  场景: atomic temp path helpers MUST live under _internal.utils
    - 系统 MUST 将原子临时路径辅助(`create_temp_path`/`atomic_replace_temp_path`/`best_effort_remove_temp_path`/`best_effort_cleanup_temp_path_dir`)的 SSOT 放在 `src/scalim/_internal/utils/atomic_paths.py`; `sinks._internal.base` MAY re-export 以保持既有导入路径可用,但 MUST NOT 再持有平行实现副本
  @req:r52 @human
  场景: implementation-paths-are-not-promoted-to-public-contract
    - 必须成立：当 某个内部实现模块可以被 import；那么 系统 MUST NOT 因此自动将其视为稳定公开入口
    当 某个内部实现模块可以被 import
    那么 系统 MUST NOT 因此自动将其视为稳定公开入口
  @req:r296 @human
  场景: facade-export-growth-is-deliberate
    - 必须成立：当 维护者调整某个稳定 facade 模块中的导出符号；那么 变更 MUST 通过显式白名单体现
    当 维护者调整某个稳定 facade 模块中的导出符号
    那么 变更 MUST 通过显式白名单体现
  @req:r420 @human
  场景: yaml-dsl-入口可稳定导入
    - 必须成立：当 导入 yaml_dsl 的 loader、validator、runtime 入口；那么 导入 MUST 成功且行为与现有实现一致
    当 导入 yaml_dsl 的 loader、validator、runtime 入口
    那么 导入 MUST 成功且行为与现有实现一致
  @req:r514 @human
  场景: 子包入口不承载核心实现
    - 必须成立：当 审阅 execution/planning 的子包 `__init__.py`；那么 文件中 MUST NOT 包含核心执行/规划算法实现
    当 审阅 execution/planning 的子包 `__init__.py`
    那么 文件中 MUST NOT 包含核心执行/规划算法实现
  @req:r590 @human
  场景: exception-clone-helper-is-centralized
    - 必须成立：假如 workflow 与 execution 都需要"跨线程传播异常"的 clone 逻辑；当 维护者实现该能力；那么 仓库 MUST 只有一份权威的 clone_exception_for_reraise 实现
    假如 workflow 与 execution 都需要"跨线程传播异常"的 clone 逻辑
    当 维护者实现该能力
    那么 仓库 MUST 只有一份权威的 clone_exception_for_reraise 实现
  @req:r645 @human
  场景: rules-extracted-from-a-c901-function-are-unit-testable
    - 必须成立：假如 某个热点函数包含多个规则分支；当 维护者治理该热点；那么 规则决策 MUST 被提取到可单测的函数
    假如 某个热点函数包含多个规则分支
    当 维护者治理该热点
    那么 规则决策 MUST 被提取到可单测的函数
  @req:r689 @human
  场景: 热点模块拆分后稳定入口仍可用
    - 必须成立：当 维护者将热点模块按职责拆分为多个子模块；那么 调用方通过既有稳定入口的导入 MUST 成功
    当 维护者将热点模块按职责拆分为多个子模块
    那么 调用方通过既有稳定入口的导入 MUST 成功

  @req:r689 @human
  场景: 新增实现遵循职责分层
    - 必须成立：当 在热点路径新增实现逻辑；那么 新逻辑 MUST 放入对应职责子模块
    当 在热点路径新增实现逻辑
    那么 新逻辑 MUST 放入对应职责子模块
  @req:r727 @human
  场景: operator-入口显式导入可用
    - 必须成立：当 导入 operator 的 executor 模块；那么 导入 MUST 成功
    当 导入 operator 的 executor 模块
    那么 导入 MUST 成功
  @req:r759 @human
  场景: 层级依赖扫描不出现反向依赖
    - 必须成立：当 执行模块依赖方向检查；那么 结果 MUST 不出现 `planning -> execution` 或 `workflow -> dsl` 的反向依赖
    当 执行模块依赖方向检查
    那么 结果 MUST 不出现 `planning -> execution` 或 `workflow -> dsl` 的反向依赖
  @req:r140 @human
  场景: importing-runtime-core-does-not-require-dev-tooling
    - 必须成立：假如 环境中未安装 dev tooling packages；当 用户仅导入并使用 runtime core；那么 导入与运行 MUST 成功
    假如 环境中未安装 dev tooling packages
    当 用户仅导入并使用 runtime core
    那么 导入与运行 MUST 成功
  @req:r163 @human
  场景: 公共入口保持显式路径
    - 必须成立：当 调用方查找运行入口；那么 仍通过既有显式模块导入,不依赖新的顶层 facade
    当 调用方查找运行入口
    那么 仍通过既有显式模块导入,不依赖新的顶层 facade
  @req:r183 @human
  场景: typing-扩展导入路径受控
    - 必须成立：当 在运行时内新增扩展类型引用；那么 MUST 通过 typing_extensionsx.py 引入且 lint 可阻止直接 typing_extensions 导入
    当 在运行时内新增扩展类型引用
    那么 MUST 通过 typing_extensionsx.py 引入且 lint 可阻止直接 typing_extensions 导入
  @req:r201 @human
  场景: vendor-可审计
    - 必须成立：当 审阅 vendor README；那么 每个 vendor 子模块 MUST 有来源/许可证与 usage/保留理由说明
    当 审阅 vendor README
    那么 每个 vendor 子模块 MUST 有来源/许可证与 usage/保留理由说明
  @req:r219 @human
  场景: 历史冲突模块不回归
    - 必须成立：当 审阅模块命名；那么 不应存在与 stdlib 高冲突且语义含混的模块命名
    当 审阅模块命名
    那么 不应存在与 stdlib 高冲突且语义含混的模块命名

  @req:r219 @human
  场景: stdlib-同名检查可用
    - 必须成立：当 运行 stdlib 同名模块检查脚本；那么 若存在冲突模块,检查 MUST 失败并输出冲突路径列表
    当 运行 stdlib 同名模块检查脚本
    那么 若存在冲突模块,检查 MUST 失败并输出冲突路径列表
  @req:r232 @human
  场景: 单个-change-聚合多个热点模块
    - 必须成立：当 维护者决定一次性重构多个核心热点模块；那么 系统 MUST 允许单个 change 同时覆盖这些热点
    当 维护者决定一次性重构多个核心热点模块
    那么 系统 MUST 允许单个 change 同时覆盖这些热点
  @req:r244 @human
  场景: hooks-observability-managers-可以单独作为一轮重构
    - 必须成立：当 维护者选择先重构 HookManager / ObserverManager 相关热点模块；那么 系统 MUST 允许该 change 仅覆盖 hooks/observability managers
    当 维护者选择先重构 HookManager / ObserverManager 相关热点模块
    那么 系统 MUST 允许该 change 仅覆盖 hooks/observability managers
  @req:r253 @human
  场景: complexity-guardrail-fails-fast
    - 必须成立：当 ENTRY 热点路径中任意函数 cognitive 或 cyclomatic 超过约定阈值；那么 complexity gate MUST fail-fast 并提示降复杂度或按职责拆分
    当 ENTRY 热点路径中任意函数 cognitive 或 cyclomatic 超过约定阈值
    那么 complexity gate MUST fail-fast 并提示降复杂度或按职责拆分

  @req:r253 @human
  场景: module-loc-should-warn-hard-taste-ceiling
    - 必须成立：当 热点模块物理行数超过舒适区或硬味天花板；那么 系统 SHOULD 报告行数并提示拆分; 仅当超过 LOC_HARD_TASTE=2500 时 module-size --check MAY 非零失败
    当 热点模块物理行数超过舒适区或硬味天花板
    那么 系统 SHOULD 报告行数并提示拆分; 仅当超过 LOC_HARD_TASTE=2500 时 module-size --check MAY 非零失败
  @req:r260 @human
  场景: import-graph-gate-reports-cycles
    - 必须成立：当 开发者运行导入图门禁脚本；那么 若导入图存在环,门禁 MUST 失败并输出至少一个可定位的最小导入环
    当 开发者运行导入图门禁脚本
    那么 若导入图存在环,门禁 MUST 失败并输出至少一个可定位的最小导入环

  @req:r260 @human
  场景: import-graph-gate-reports-function-local-imports
    - 必须成立：当 开发者运行导入图门禁脚本；那么 若主包存在函数内导入,门禁 MUST 失败并输出文件路径与行号
    当 开发者运行导入图门禁脚本
    那么 若主包存在函数内导入,门禁 MUST 失败并输出文件路径与行号
  @req:r267 @human
  场景: workflow-modules-are-rejected-under-yaml-dsl-runtime
    - 必须成立：当 维护者运行 workflow layering 的静态门禁；那么 若 yaml_dsl runtime 下出现 `workflow_*.py`,门禁 MUST 失败并输出违规路径列表
    当 维护者运行 workflow layering 的静态门禁
    那么 若 yaml_dsl runtime 下出现 `workflow_*.py`,门禁 MUST 失败并输出违规路径列表
  @req:r378 @human
  场景: workflow-compile-remains-stable-after-internal-split
    - 必须成立：当 维护者按职责拆分 `workflow_compile.py` 为多个 `_internal` 子模块；那么 对外入口 `compile_workflow_ir` 的导入与运行 MUST 保持不变
    当 维护者按职责拆分 `workflow_compile.py` 为多个 `_internal` 子模块
    那么 对外入口 `compile_workflow_ir` 的导入与运行 MUST 保持不变
  @req:r384 @human
  场景: stable-import-path-remains-after-refactor
    - 必须成立：当 维护者将 output composition 代码迁移到子模块/子包；那么 调用方仍可通过 `scalim.execution.output_composition` 导入公共类型与 `build_output_composition`
    当 维护者将 output composition 代码迁移到子模块/子包
    那么 调用方仍可通过 `scalim.execution.output_composition` 导入公共类型与 `build_output_composition`

  @req:r22 @human
  场景: openpyxl-helpers-ssot-imported
    - 必须成立：假如 workflow workbook/sheetbook 与 Excel sinks 需要 write_only close 或原子保存；当 维护者审查实现；那么 仓库 MUST 仅有一份 openpyxl_helpers SSOT 且调用方从该模块导入
    假如 workflow workbook/sheetbook 与 Excel sinks 需要 write_only close 或原子保存
    当 维护者审查实现
    那么 仓库 MUST 仅有一份 openpyxl_helpers SSOT 且调用方从该模块导入

  @req:r22 @human
  场景: workbook-reexport-remains
    - 必须成立：假如 既有调用方从 resources_workbook 导入 best_effort_close_write_only_workbook_worksheets；当 执行导入；那么 导入 MUST 成功且行为与共享实现一致
    假如 既有调用方从 resources_workbook 导入 best_effort_close_write_only_workbook_worksheets
    当 执行导入
    那么 导入 MUST 成功且行为与共享实现一致

  @req:r23 @human
  场景: atomic-paths-ssot
    - 必须成立：假如 多模块需要原子临时路径写出；当 维护者审查实现；那么 路径辅助 MUST 以 atomic_paths 为 SSOT,base 仅允许 re-export
    假如 多模块需要原子临时路径写出
    当 维护者审查实现
    那么 路径辅助 MUST 以 atomic_paths 为 SSOT,base 仅允许 re-export

  @req:r23 @human
  场景: no-utils-to-sinks-inversion
    - 必须成立：假如 openpyxl_helpers 需要临时路径辅助；当 模块导入图检查；那么 `_internal.utils` MUST NOT 导入 `sinks` 或 `workflow`
    假如 openpyxl_helpers 需要临时路径辅助
    当 模块导入图检查
    那么 `_internal.utils` MUST NOT 导入 `sinks` 或 `workflow`
