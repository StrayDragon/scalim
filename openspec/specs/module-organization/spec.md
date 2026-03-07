# module-organization Specification

**状态: ✅ 已实现**
## Purpose
定义 `src/IMPL_ROOT/` 的模块边界、入口最小化与兼容约束,避免将内部实现路径误用为公共 API,并保持 Python 3.6 运行时可用性.

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/`
- `src/IMPL_ROOT/dsl/by_yaml/runtime/`
- `src/IMPL_ROOT/execution/`
- `src/IMPL_ROOT/planning/`
- `src/IMPL_ROOT/vendor/README.md`
- `src/IMPL_ROOT/vendor/compact/typing_extensionsx.py`

## Requirements
### Requirement: by_yaml 解析与 runtime 模块保持子包化
系统 MUST 保持 by_yaml 的解析与 runtime 为显式子包结构:
- `config_parsing` 采用 package 形态,并保留 `loader.py`/`validator.py` 作为稳定入口;
- 解析与校验实现应放在 `parsers/` 与 `validators/` 子包;
- `runtime` 采用子模块组织(如 `entrypoints.py`、`contracts.py`、`introspection.py`),并通过 `IMPL_ROOT.dsl.by_yaml.runtime` 提供稳定入口.

#### Scenario: by_yaml 入口可稳定导入
- **WHEN** 导入 `IMPL_ROOT.dsl.by_yaml.config_parsing.loader`、`IMPL_ROOT.dsl.by_yaml.config_parsing.validator`、`IMPL_ROOT.dsl.by_yaml.runtime`
- **THEN** 导入 MUST 成功且行为与现有实现一致

### Requirement: execution/planning 实现按子模块拆分且入口最小化
系统 MUST 将复杂实现放入显式子模块,`__init__.py` 仅允许最小 glue,不得承载大型实现.

系统 MUST 限制 `__init__.py` 的 re-export 行为:

- 对于 **内部实现子包**(至少包括 `execution/pipeline`、`execution/executor` 及其子包,以及 `planning` 的内部子包),`__init__.py` MUST NOT 通过 re-export 暴露实现符号;若定义 `__all__` 则 MUST 为空.
- 对于 **领域 facade 包根**(`IMPL_ROOT.execution` 与 `IMPL_ROOT.planning`),系统 MAY 提供少量且明确的稳定符号 re-export,用于形成可维护的官方入口.该 re-export MUST 满足:
  - MUST 使用显式 `__all__` 白名单(禁止 `import *`).
  - MUST 仅导出小集合稳定符号(避免把包根变成杂货铺).
  - MUST NOT 引入可选依赖要求或明显的导入副作用.
  - MUST NOT 造成层级反转或循环依赖(例如 `planning -> execution`).

#### Scenario: 子包入口不承载核心实现
- **WHEN** 审阅 `src/IMPL_ROOT/execution/**/__init__.py` 与 `src/IMPL_ROOT/planning/**/__init__.py`
- **THEN** 文件中 MUST NOT 包含核心执行/规划算法实现

#### Scenario: 内部实现子包不通过 __init__ 暴露实现符号
- **WHEN** 审阅 `src/IMPL_ROOT/execution/pipeline/**/__init__.py` 与 `src/IMPL_ROOT/execution/executor/**/__init__.py`
- **THEN** 这些 `__init__.py` MUST NOT 通过 re-export 暴露实现符号
- **AND** 若存在 `__all__` 定义,其 MUST 为空

### Requirement: 核心热点模块必须按职责拆分并保持稳定入口
系统 MUST 对核心热点实现采用职责分层的子模块组织,避免单文件持续聚合多种职责.至少以下热点路径 MUST 被视为持续治理对象:
- `src/IMPL_ROOT/dsl/by_yaml/schema_dsl/models`
- `src/IMPL_ROOT/execution/adaptive`
- `src/IMPL_ROOT/ob/presets`
- `src/IMPL_ROOT/hooks`

在上述热点重构过程中,系统 MUST 保持既有稳定入口可用(直接导入路径或兼容导出路径),不得因内部拆分破坏调用方基本导入能力.

#### Scenario: 热点模块拆分后稳定入口仍可用
- **WHEN** 维护者将热点模块按职责拆分为多个子模块
- **THEN** 调用方通过既有稳定入口的导入 MUST 成功
- **AND** 系统 MUST 不要求调用方立即迁移到内部私有路径

#### Scenario: 新增实现遵循职责分层
- **WHEN** 在热点路径新增实现逻辑
- **THEN** 新逻辑 MUST 放入对应职责子模块
- **AND** `__init__.py` MUST NOT 成为核心算法实现聚合点

### Requirement: operator package 入口模块约定一致
系统 MUST 对 package 形态的 operator 统一使用 `<op>/executor.py` 作为入口模块,`__init__.py` 不通过 re-export 暴露 `<Name>OperatorExecutor`.

#### Scenario: operator 入口显式导入可用
- **WHEN** 导入 `IMPL_ROOT.execution.executor.operators.compute.executor` 或 `...load_ref.executor`
- **THEN** 导入 MUST 成功
- **AND** 从对应 package 的 `__init__.py` 不应获得 executor 类 re-export

### Requirement: planning 与 execution 保持层次解耦
系统 MUST 保持 `src/IMPL_ROOT/planning/**` 不依赖 `src/IMPL_ROOT/execution/**` 实现符号,避免层次反转与循环依赖.

#### Scenario: planning 独立导入
- **WHEN** 导入 `IMPL_ROOT.planning.builder` 与 `IMPL_ROOT.planning.plan`
- **THEN** 导入 MUST 成功且不触发 execution 循环依赖错误

### Requirement: 核心层级依赖方向必须保持单向
系统 MUST 保持核心层级依赖方向可审计且单向,至少满足:
- `planning` MUST NOT 依赖 `execution` 实现.
- `dsl runtime` MUST NOT 直接依赖 `execution` 的内部私有实现路径.
- `hooks/ob` MUST 通过事件契约与组件装配交互,不得反向依赖 DSL 专有配置模型.

#### Scenario: 层级依赖扫描不出现反向依赖
- **WHEN** 执行模块依赖方向检查
- **THEN** 结果 MUST 不出现 `planning -> execution` 的反向依赖
- **AND** MUST 不出现 `hooks/ob -> dsl 专有配置` 的直接依赖

### Requirement: 不新增顶层公共 facade
系统 MUST NOT 新增 `src/IMPL_ROOT/api.py` 或在顶层 `src/IMPL_ROOT/__init__.py` 做公共 re-export 聚合;公共入口继续采用显式模块路径.

#### Scenario: 公共入口保持显式路径
- **WHEN** 调用方查找运行入口
- **THEN** 仍通过既有显式模块导入,不依赖新的顶层 facade

### Requirement: Python 3.6 typing 兼容入口唯一
系统 MUST 保持 Python 3.6 兼容;`src/IMPL_ROOT/` 内扩展 typing 能力(如 `Self`/`override`)仅允许通过 `src/IMPL_ROOT/vendor/compact/typing_extensionsx.py` 引入.
系统 MUST 通过 lint 禁止在 `src/IMPL_ROOT/` 内直接导入 `typing_extensions`.

#### Scenario: typing 扩展导入路径受控
- **WHEN** 在 `src/IMPL_ROOT/` 内新增扩展类型引用
- **THEN** MUST 通过 `typing_extensionsx.py` 引入且 lint 可阻止直接 `typing_extensions` 导入

### Requirement: vendor 模块必须可审计且有用途
系统 MUST 在 `src/IMPL_ROOT/vendor/README.md` 维护每个 vendor 子模块的最小 provenance(来源与许可证)以及 usage/保留理由.
版本/commit pin、本地修改点、更新策略在已知时 SHOULD 记录;历史条目允许临时缺省并在后续补齐.
未被主路径使用的 vendor 子模块 MUST 记录明确保留理由与预计接入点,否则应移除.

#### Scenario: vendor 可审计
- **WHEN** 审阅 `src/IMPL_ROOT/vendor/README.md`
- **THEN** 每个 vendor 子模块 MUST 有来源/许可证与 usage/保留理由说明

### Requirement: 避免 stdlib 同名冲突模块
系统 MUST NOT 在 `src/IMPL_ROOT/` 引入与 Python 标准库同名且语义含混的模块文件(如 `types.py`、`inspect.py`、`trace.py`),以避免导入语义混淆与潜在 shadowing 风险.
系统 MUST 提供自动化检查(脚本或 CI 任务)以阻止该类命名回归.

#### Scenario: 历史冲突模块不回归
- **WHEN** 审阅 by_yaml runtime 与 observability presets 的模块命名
- **THEN** 不应存在与 stdlib 高冲突且语义含混的模块命名

#### Scenario: stdlib 同名检查可用
- **WHEN** 运行 stdlib 同名模块检查脚本
- **THEN** 若存在冲突模块,检查 MUST 失败并输出冲突路径列表
- **AND** 若不存在冲突模块,检查 MUST 成功

### Requirement: 一次性热点重构可以在单个 change 中覆盖多个核心热点模块
系统 MUST 允许将多个已确认热点模块的结构重构放在单个 change 中统一规划与实施,前提是各热点仍通过显式 phase 与任务分组保持边界清晰.

#### Scenario: 单个 change 聚合多个热点模块
- **WHEN** 维护者决定一次性重构多个核心热点模块
- **THEN** 系统 MUST 允许单个 change 同时覆盖这些热点
- **AND** tasks MUST 通过显式 phase 或任务分组区分不同热点主线

### Requirement: 已确认热点模块必须按职责拆分并保持稳定入口
系统 MUST 将以下路径视为本轮一次性重构的确认热点,并要求其内部实现按职责拆分:
- `src/IMPL_ROOT/dsl/by_yaml/config_parsing/validators/fields.py`
- `src/IMPL_ROOT/dsl/by_yaml/runtime/conversion.py`
- `src/IMPL_ROOT/hooks/base.py`
- `src/IMPL_ROOT/ob/manager.py`
- `src/IMPL_ROOT/ob/presets/viz.py`
- `src/IMPL_ROOT/execution/adaptive/loadref_scheduler.py`

拆分后,系统 MUST 保持这些热点相关的官方稳定入口继续可用,不得要求调用方迁移到新的内部私有路径.

#### Scenario: 热点拆分后稳定入口仍可用
- **WHEN** 上述任一热点模块被拆入新的内部子模块或 package
- **THEN** 通过当前官方稳定入口的导入 MUST 继续成功
- **AND** 调用方 MUST NOT 被要求直接导入新的内部私有模块

### Requirement: 热点模块 phase 1 重构可以从 hooks 与 observability managers 独立推进
系统 MUST 允许将热点模块治理拆分为多个 phase 独立推进;当维护者先处理 `hooks` / `ob` managers 时,不得强制与其它热点模块在同一 change 中一起重构.

#### Scenario: hooks / ob managers 可以单独作为一轮重构
- **WHEN** 维护者选择先重构 `HookManager` / `ObserverManager` 相关热点模块
- **THEN** 系统 MUST 允许该 change 仅覆盖 hooks / observability managers
- **AND** 不应要求同一 change 同时包含 YAML runtime、adaptive scheduler 或其它热点模块的拆分

### Requirement: 热点模块内部拆分后必须保持官方稳定入口不变
系统 MUST 在热点模块内部拆分后继续保持官方稳定入口可用;对于 `HookManager` / `ObserverManager` 这类已被测试和调用路径依赖的核心类型,实现拆分不得改变推荐导入路径.

#### Scenario: 内部重构不改变推荐导入路径
- **WHEN** `HookManager` / `ObserverManager` 的实现被拆入新的内部模块或 package
- **THEN** 调用方通过当前推荐导入路径 MUST 继续可用
- **AND** 模块布局测试 SHOULD 覆盖该稳定入口承诺
