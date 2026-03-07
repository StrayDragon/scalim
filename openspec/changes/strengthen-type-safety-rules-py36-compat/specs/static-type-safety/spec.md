## ADDED Requirements

### Requirement: 静态类型治理必须采用可渐进收紧的分层策略
系统 MUST 在 `basedpyright` 中为类型检查定义显式分层策略,至少区分“核心稳定区的更严格策略”与“动态/工具边界的受控放宽策略”,并保持 `pythonVersion = "3.6"` 作为统一前提.
对于 `src/IMPL_ROOT/` 中不属于已批准边界目录的新核心模块,系统 MUST 默认将其纳入更严格策略,而不是默认继承最宽松配置.

#### Scenario: 新增核心模块默认进入更严格策略
- **WHEN** 维护者在 `src/IMPL_ROOT/` 的核心稳定区新增模块
- **THEN** 该模块 MUST 默认接受更严格的类型检查策略
- **AND** 不应因为仓库存在动态边界而自动落入最宽松配置

### Requirement: 首批类型收紧必须优先覆盖缺失/未知类型类问题
系统 MUST 在保持现有核心规则的基础上,优先收紧能够抑制 `Any` / `Unknown` 无声扩散的规则束.
首批最小规则束 MUST 包含 `reportMissingParameterType`、`reportUnknownParameterType`、`reportUnknownArgumentType`、`reportUnknownVariableType` 与 `reportMissingTypeArgument`;现有已开启的 `reportArgumentType`、`reportReturnType`、`reportUnknownMemberType` MUST 继续保持启用.

#### Scenario: 核心稳定区至少启用首批规则束
- **WHEN** 审阅核心稳定区的 `basedpyright` 配置
- **THEN** 可见首批最小规则束已对该区域启用
- **AND** 现有核心规则不会因本轮治理而被重新放宽

### Requirement: 类型强化不得破坏 Python 3.6 兼容前提
系统 MUST 在加强静态类型时继续保持 Python 3.6 运行时兼容.
因此,`src/IMPL_ROOT/` 内的类型增强 MUST NOT 依赖仅适用于较新 Python 的运行时语法,并 MUST 继续通过 `typing` 旧语法与兼容 shim 组织类型表达.

#### Scenario: 类型增强后 Python 3.6 兼容检查仍通过
- **WHEN** 在核心库中新增或收紧类型标注后运行 `just qa`
- **THEN** `py36-compat-check` 与 `py36-typingext-check` MUST 继续通过
- **AND** 类型增强不应要求运行时升级到 Python 3.7+

### Requirement: suppression 必须局部化且可审计
系统 MUST 将 `src/IMPL_ROOT/` 内的类型例外控制为“局部、显式、可审计”的形式.
对于新增的类型 suppression,系统 MUST 优先使用带具体规则代码的 `# type: ignore[...]`、局部 helper seam 或显式类型别名/Protocol/TypedDict/compat shim,而不是继续扩大 executionEnvironment 级别的全局放宽.

#### Scenario: 新增类型例外不会扩大为目录级宽免
- **WHEN** 维护者为某个核心模块处理动态边界导致的类型噪声
- **THEN** 例外 MUST 优先落在该模块的局部代码或窄 helper 中
- **AND** 不应仅为了单点噪声而新增更大范围的目录级 `reportX = false`
