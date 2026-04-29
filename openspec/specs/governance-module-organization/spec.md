# module-organization Specification

**状态: ✅ 已实现**
## Purpose
定义运行时模块的边界、入口最小化与依赖约束,避免将内部实现路径误用为公共 API,并保持模块层级单向依赖与 Python 3.6 运行时兼容性.

## Related Concepts
- 模块边界控制 (公共入口 vs 内部实现)
- Facade 模块与显式导出白名单
- 子包化组织 (yaml_dsl、execution、planning)
- 层级依赖约束 (planning → execution → workflow → dsl)
- 热点模块治理与职责拆分
- Python 3.6 typing 兼容层
## Requirements
### Requirement: internal implementation paths MUST remain non-contract

系统 MUST 将"可导入"与"可承诺"分为两个层级：稳定公开入口由显式白名单定义,其余实现路径即使可导入也 MUST 视为内部实现细节.

#### Scenario: implementation paths are not promoted to public contract
- **WHEN** 某个内部实现模块可以被 import
- **THEN** 系统 MUST NOT 因此自动将其视为稳定公开入口
- **AND** 面向用户的回归门禁 MUST 仍以显式公共白名单为准

### Requirement: facade modules MUST use explicit export whitelists

稳定公开入口的 facade 模块 MUST 使用显式 `__all__` 或等价白名单控制导出面,避免内部符号随重构被无意带出.

#### Scenario: facade export growth is deliberate
- **WHEN** 维护者调整某个稳定 facade 模块中的导出符号
- **THEN** 变更 MUST 通过显式白名单体现
- **AND** 公共表面 gate MUST 能对新增或删除导出做出确定性回归提示

### Requirement: yaml_dsl MUST maintain subpackage structure

yaml_dsl 的解析与 runtime MUST 保持显式子包结构：`_internal.config_parsing` 采用 package 形式,保留 `loader.py`/`validator.py` 作为稳定入口；`runtime` 采用子模块组织并通过稳定入口提供访问.

#### Scenario: yaml_dsl 入口可稳定导入
- **WHEN** 导入 yaml_dsl 的 loader、validator、runtime 入口
- **THEN** 导入 MUST 成功且行为与现有实现一致

### Requirement: execution/planning MUST minimize __init__.py surface

复杂实现 MUST 放入显式子模块,`__init__.py` 仅允许最小 glue.对于内部实现子包,`__init__.py` MUST NOT 通过 re-export 暴露实现符号；对于领域 facade 包根,MAY 提供少量稳定符号 re-export 但 MUST 使用显式 `__all__` 且避免层级反转.

#### Scenario: 子包入口不承载核心实现
- **WHEN** 审阅 execution/planning 的子包 `__init__.py`
- **THEN** 文件中 MUST NOT 包含核心执行/规划算法实现
- **AND** 内部实现子包 MUST NOT 通过 re-export 暴露实现符号

### Requirement: cross-cutting helpers MUST have single SSOT implementation

当"基础设施级"逻辑被多个领域模块复用时,系统 MUST 避免重复实现：MUST 将该逻辑抽取到单一 SSOT 内部 util 模块,该 util 模块 MUST 保持低耦合避免层级反转,测试口径 MUST 覆盖该 SSOT util.

#### Scenario: exception clone helper is centralized
- **GIVEN** workflow 与 execution 都需要"跨线程传播异常"的 clone 逻辑
- **WHEN** 维护者实现该能力
- **THEN** 仓库 MUST 只有一份权威的 clone_exception_for_reraise 实现
- **AND** workflow/execution 调用点 MUST 导入该 SSOT util

### Requirement: C901 hotspots MUST be decomposed into testable boundaries

当核心热点函数因复杂度被 `# noqa: C901` 放行时,系统 MUST 将其视为治理对象：MUST 优先通过规则函数提取降低复杂度,被提取的规则函数 MUST 具备明确输入输出并可通过单元测试覆盖,新增或保留 `# noqa: C901` 时 MUST 同时标注可追踪的拆分计划引用.

#### Scenario: rules extracted from a C901 function are unit-testable
- **GIVEN** 某个热点函数包含多个规则分支
- **WHEN** 维护者治理该热点
- **THEN** 规则决策 MUST 被提取到可单测的函数
- **AND** 单元测试 MUST 覆盖主要分支组合

### Requirement: core hotspot modules MUST be split by responsibility

系统 MUST 对核心热点实现采用职责分层的子模块组织,至少以下热点路径 MUST 被视为持续治理对象：schema_dsl models、execution adaptive、observability presets、hooks.

在上述热点重构过程中,系统 MUST 保持既有稳定入口可用,不得因内部拆分破坏调用方基本导入能力.

#### Scenario: 热点模块拆分后稳定入口仍可用
- **WHEN** 维护者将热点模块按职责拆分为多个子模块
- **THEN** 调用方通过既有稳定入口的导入 MUST 成功
- **AND** 系统 MUST 不要求调用方立即迁移到内部私有路径

#### Scenario: 新增实现遵循职责分层
- **WHEN** 在热点路径新增实现逻辑
- **THEN** 新逻辑 MUST 放入对应职责子模块
- **AND** `__init__.py` MUST NOT 成为核心算法实现聚合点

### Requirement: operator package MUST use consistent entry convention

系统 MUST 对 package 形态的 operator 统一使用 `<op>/executor.py` 作为入口模块,`__init__.py` 不通过 re-export 暴露 executor 类.

#### Scenario: operator 入口显式导入可用
- **WHEN** 导入 operator 的 executor 模块
- **THEN** 导入 MUST 成功
- **AND** 从对应 package 的 `__init__.py` 不应获得 executor 类 re-export

### Requirement: layer dependencies MUST remain unidirectional

系统 MUST 保持核心层级依赖方向可审计且单向：planning MUST NOT 依赖 execution 实现,dsl runtime MUST NOT 直接依赖 execution 内部实现,hooks/observability MUST 通过事件契约交互不得反向依赖 DSL 专有配置,workflow runtime MUST NOT 反向依赖 DSL 层.

#### Scenario: 层级依赖扫描不出现反向依赖
- **WHEN** 执行模块依赖方向检查
- **THEN** 结果 MUST 不出现 `planning -> execution` 或 `workflow -> dsl` 的反向依赖
- **AND** MUST 不出现 `hooks/observability -> dsl 专有配置` 的直接依赖

### Requirement: runtime core MUST NOT import dev tooling packages

runtime core MUST NOT 导入 dev tooling packages (例如 scalim-misc),dev tooling packages MAY 导入 runtime core 并消费其 SSOT/公共入口.该约束禁止通过 optional hook 或动态导入绕开.

#### Scenario: importing runtime core does not require dev tooling
- **GIVEN** 环境中未安装 dev tooling packages
- **WHEN** 用户仅导入并使用 runtime core
- **THEN** 导入与运行 MUST 成功

### Requirement: no new top-level public facades

系统 MUST NOT 新增顶层公共 facade (如 `api.py` 或在顶层 `__init__.py` 做公共 re-export 聚合),公共入口继续采用显式模块路径.

#### Scenario: 公共入口保持显式路径
- **WHEN** 调用方查找运行入口
- **THEN** 仍通过既有显式模块导入,不依赖新的顶层 facade

### Requirement: Python 3.6 typing compatibility MUST be centralized

系统 MUST 保持 Python 3.6 兼容；运行时内扩展 typing 能力 (如 `Self`/`override`) 仅允许通过 `vendor/compact/typing_extensionsx.py` 引入,MUST 通过 lint 禁止直接导入 `typing_extensions`.

#### Scenario: typing 扩展导入路径受控
- **WHEN** 在运行时内新增扩展类型引用
- **THEN** MUST 通过 typing_extensionsx.py 引入且 lint 可阻止直接 typing_extensions 导入

### Requirement: vendor modules MUST be auditable

系统 MUST 在 vendor README 维护每个 vendor 子模块的最小 provenance (来源与许可证) 以及 usage/保留理由.未被主路径使用的 vendor 子模块 MUST 记录明确保留理由与预计接入点,否则应移除.

#### Scenario: vendor 可审计
- **WHEN** 审阅 vendor README
- **THEN** 每个 vendor 子模块 MUST 有来源/许可证与 usage/保留理由说明

### Requirement: stdlib naming conflicts MUST be avoided

系统 MUST NOT 在运行时引入与 Python 标准库同名且语义含混的模块文件 (如 `types.py`、`inspect.py`、`trace.py`),以避免导入语义混淆与潜在 shadowing 风险.系统 MUST 提供自动化检查以阻止该类命名回归.

#### Scenario: 历史冲突模块不回归
- **WHEN** 审阅模块命名
- **THEN** 不应存在与 stdlib 高冲突且语义含混的模块命名

#### Scenario: stdlib 同名检查可用
- **WHEN** 运行 stdlib 同名模块检查脚本
- **THEN** 若存在冲突模块,检查 MUST 失败并输出冲突路径列表

### Requirement: batch hotspot refactoring MAY cover multiple modules in one change

系统 MUST 允许将多个已确认热点模块的结构重构放在单个 change 中统一规划与实施,前提是各热点仍通过显式 phase 与任务分组保持边界清晰.

#### Scenario: 单个 change 聚合多个热点模块
- **WHEN** 维护者决定一次性重构多个核心热点模块
- **THEN** 系统 MUST 允许单个 change 同时覆盖这些热点
- **AND** tasks MUST 通过显式 phase 或任务分组区分不同热点主线

### Requirement: hotspot governance MAY be split into independent phases

系统 MUST 允许将热点模块治理拆分为多个 phase 独立推进；当维护者先处理 hooks/observability managers 时,不得强制与其它热点模块在同一 change 中一起重构.

#### Scenario: hooks / observability managers 可以单独作为一轮重构
- **WHEN** 维护者选择先重构 HookManager / ObserverManager 相关热点模块
- **THEN** 系统 MUST 允许该 change 仅覆盖 hooks/observability managers
- **AND** 不应要求同一 change 同时包含其它热点模块的拆分

### Requirement: hotspot modules MUST be guarded against unbounded growth

系统 MUST 对热点模块提供可维护性护栏：当单个模块超过约定阈值 (例如 >1000 行) 时,维护者 MUST 拆分为多个职责单一的模块,拆分 MUST 保持行为等价并由自动化回归覆盖.

#### Scenario: module size guardrail fails fast
- **WHEN** 热点模块超过阈值且继续增长
- **THEN** guardrail gate MUST fail-fast 并提示拆分策略

### Requirement: import graph MUST be acyclic and ban function-local imports

系统 MUST 保持主包 (排除 vendor) 的模块导入图无环.同时,主包模块 MUST NOT 在函数体内出现 import 语句,以避免通过局部导入绕开依赖方向约束并隐藏导入副作用.该约束 MUST 由可独立运行的静态门禁守护.

#### Scenario: import graph gate reports cycles
- **WHEN** 开发者运行导入图门禁脚本
- **THEN** 若导入图存在环,门禁 MUST 失败并输出至少一个可定位的最小导入环

#### Scenario: import graph gate reports function-local imports
- **WHEN** 开发者运行导入图门禁脚本
- **THEN** 若主包存在函数内导入,门禁 MUST 失败并输出文件路径与行号

### Requirement: yaml_dsl runtime MUST NOT contain workflow runtime modules

系统 MUST 保持 yaml_dsl runtime 子包不包含 workflow runtime 语义模块 (例如 `workflow_*.py`),以避免把 workflow 层实现符号误放入 DSL runtime.该约束 MUST 由可独立运行的静态门禁守护.

#### Scenario: workflow_* modules are rejected under yaml_dsl runtime
- **WHEN** 维护者运行 workflow layering 的静态门禁
- **THEN** 若 yaml_dsl runtime 下出现 `workflow_*.py`,门禁 MUST 失败并输出违规路径列表

### Requirement: workflow_compile hotspot MUST be decomposed into responsibility-focused submodules

系统 MUST 将 `workflow_compile.py` 这类多职责热点模块拆分为职责单一的子模块,以降低复杂度并提升可测试性。

拆分后系统 MUST 满足:
- 对外稳定入口(例如 `compile_workflow_ir`)保持可用且行为不变
- 纯规则/校验逻辑 MUST 位于可单测的子模块中(无 IO、输入输出明确)
- IO 相关逻辑(例如 demand YAML 预加载) MUST 与纯规则逻辑分离

#### Scenario: workflow compile remains stable after internal split
- **WHEN** 维护者按职责拆分 `workflow_compile.py` 为多个 `_internal` 子模块
- **THEN** 对外入口 `compile_workflow_ir` 的导入与运行 MUST 保持不变
- **AND** `just qa` MUST 通过

### Requirement: output_composition hotspot MUST be decomposed into spec/router/builder submodules

系统 MUST 将 `execution/output_composition.py` 这类混合 spec+runtime+builder 的热点模块拆分为职责单一的子模块,至少分离:
- spec/数据类层
- router/runtime 实现层
- builder/工厂层

拆分后系统 MUST 保持:
- `scalim.execution.output_composition` 的稳定导入路径继续可用
- 对外行为不变(纯重构)

#### Scenario: stable import path remains after refactor
- **WHEN** 维护者将 output composition 代码迁移到子模块/子包
- **THEN** 调用方仍可通过 `scalim.execution.output_composition` 导入公共类型与 `build_output_composition`
- **AND** `just qa` MUST 通过

