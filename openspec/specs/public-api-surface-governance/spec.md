# public-api-surface-governance Specification

**状态: ✅ 已实现**

## Purpose
定义稳定公开入口的编目规则与回归门禁,避免内部实现路径在文档/skills/examples/tests 中被误固化为事实公共 API.
## Requirements
### Requirement: stable public entrypoints MUST be explicitly cataloged

系统 MUST 为用户侧可依赖的公共入口维护一份显式、可审计的稳定目录，而不是让“当前能 import 的路径”自然演化成公共契约。

该目录在本轮至少 MUST 覆盖：

- `scalim.dsl.by_yaml` 及其官方 facade 符号（包括 `run`、`compile`、`run_workflow` 与运行期契约类型）
- `scalim.dsl.by_yaml.workflow`
- `scalim.dsl.by_yaml.workflow_types`
- `scalim.dsl.by_yaml.workflow_paths`
- `scalim.spec.ir`
- `scalim.workflow.loaders`（workflow YAML 中可通过字符串引用的内置 loader 入口）
- `scalim.events`（事件 envelope、事件类型常量与事件目录查询入口；typed payload 不作为公共导入契约）
- `scalim.sinks`（sink 契约与常用 sinks；内部 helper 不作为公共导入契约）

系统 MUST 将未列入目录的路径视为非公共契约；其中至少包括：

- `scalim.dsl.by_yaml.runtime.*`（例如 `scalim.dsl.by_yaml.runtime.workflow_loaders`）
- `scalim.dsl.by_yaml.config_parsing.*`
- `scalim.dsl.by_yaml.schema_dsl.*`
- `scalim.events._*`
- `scalim.sinks._internal.*`

#### Scenario: curated public entrypoints are import-smoke covered
- **WHEN** 维护者执行 public-surface import smoke gate
- **THEN** 目录中的稳定公开入口 MUST 全部可导入
- **AND** gate MUST 以显式白名单为准,而不是扫描整个包树自动放大公共表面

### Requirement: public-facing materials MUST use only cataloged entrypoints

系统 MUST 要求文档、skills、examples 与 public API 回归用例仅使用已编目的稳定公开入口表达官方用法。

系统 MUST NOT 在这些面向用户的材料中把内部实现路径当作推荐导入路径、教程示例或长期契约。

#### Scenario: docs and examples avoid internal implementation imports
- **WHEN** 维护者审阅或检查用户可见文档、skills 与 examples
- **THEN** 其中的官方导入示例 MUST 仅引用已编目的稳定公开入口
- **AND** 不得把 `scalim.dsl.by_yaml.runtime.*`、`scalim.dsl.by_yaml.config_parsing.*` 或 `scalim.dsl.by_yaml.schema_dsl.*` 写成推荐用户路径
- **AND** 不得把 `scalim.events._*` 或 `scalim.sinks._internal.*` 写成推荐用户路径

### Requirement: public facades MUST NOT re-export internal implementation modules

系统 MUST 将 internal 实现细节与稳定公开入口物理隔离.

至少对以下类型的 internal 路径,public facades MUST NOT re-export,且用户材料 MUST NOT 引用：
- `*_internal*` 或 `._internal.*`
- `events._*`
- `dsl.by_yaml.runtime.*`
- 其它在 public API manifest 中未编目的模块路径

#### Scenario: internal re-exports are detected and rejected
- **WHEN** 维护者在 public facade 中新增对 internal 模块的 re-export
- **THEN** public surface gate MUST fail-fast 指出具体模块路径与建议的 facade 迁移方式

### Requirement: stable public surface changes MUST be explicit and auditable

系统 MUST 将 public surface 的新增/删除/重命名视为需要显式决策的变更：
- 任何变更 MUST 同步更新 public API manifest
- 任何变更 MUST 同步更新 public API suite（或等价回归）以覆盖新的公开面

#### Scenario: changing exports requires manifest and suite updates
- **WHEN** 维护者调整任一稳定公开入口模块的 `__all__`
- **THEN** 对应 gate MUST 要求同时更新 manifest 与 suite,否则 fail-fast

### Requirement: unsafe capabilities MUST NOT live on default public facades

系统 MUST 将“放宽安全边界”的能力与默认公共 facade 隔离。

若后续仍需保留不安全能力，系统 MUST 通过显式 `unsafe` 语义的专用入口、专用参数或等价强标识暴露；系统 MUST NOT 继续将其挂载在默认公共 facade 上，造成“官方推荐入口也可直接放宽边界”的印象。

#### Scenario: public API review rejects non-explicit unsafe escape hatches
- **WHEN** 维护者为默认公共 facade 新增一个会放宽安全边界的能力
- **THEN** 该能力 MUST 因缺少显式 `unsafe` 语义而被视为不符合公共表面治理约束

### Requirement: `__all__` MUST NOT export internal underscore symbols

系统 MUST 将任何模块 `__all__` 中包含非 dunder 的 `_...` 名称视为内部符号泄漏，并要求在治理变更中将其从 `__all__` 移除。

#### Scenario: underscore symbols are rejected from __all__
- **WHEN** 回归门禁扫描 `src/scalim/**.py` 中的 `__all__`
- **THEN** 任一 `__all__` MUST NOT 包含以 `_` 开头且非 dunder 的名称
- **AND** 若发现该类条目，门禁 MUST fail-fast 并输出可定位的模块路径与符号名集合

### Requirement: internal implementation modules MUST explicitly seal exports

系统 MUST 要求内部实现模块显式声明其导出面，以避免 `from <module> import *` 意外将内部符号扩散为事实公共 API。

最小治理要求：
- 位于任意 `_internal/` 目录下的模块 MUST 定义 `__all__`，且其 MUST 为空。
- 文件名以 `_` 前缀标识为内部实现的模块 MUST 定义 `__all__`，且其 MUST 为空。

#### Scenario: internal modules declare empty __all__
- **WHEN** 回归门禁扫描 `_internal/` 目录与 `_*.py` 模块
- **THEN** 每个模块 MUST 定义 `__all__`
- **AND** 其 `__all__` MUST 为空（`[]` 或 `()`）

### Requirement: events/sinks public facades MUST be pinned by explicit __all__ gates

系统 MUST 将 `scalim.events` 与 `scalim.sinks` 视为稳定公开入口的一部分，并通过显式 `__all__` 白名单回归门禁固定其公共导出面。

#### Scenario: changing facade exports fails fast in curated gate
- **WHEN** 维护者在 `scalim.events` 或 `scalim.sinks` 调整对外导出符号集合
- **THEN** curated public surface gate MUST fail-fast 指出缺失或新增的导出符号

### Requirement: removed internal modules MUST be blocked from reappearing in user-facing materials

系统 MUST 将 `scalim.vendor.literich` 视为已移除的内部实现模块，并通过用户材料门禁阻止其再次出现在用户可见材料中（docs / skills / notebooks）。

#### Scenario: user-material import boundary gate rejects scalim.vendor.literich
- **GIVEN** 任一用户材料文件（docs/skills/notebooks）包含文本 `scalim.vendor.literich`
- **WHEN** 维护者运行 `scripts/check-user-material-import-boundaries.py --check`
- **THEN** gate MUST fail-fast 并提示移除该导入/引用

### Requirement: runtime code MUST NOT depend on non-cataloged console renderers

系统 MUST 禁止将仅用于“漂亮输出”的渲染器当作运行时依赖或事实公共契约扩散。

具体而言：当某模块仅用于 console 展示且不在 public API curated 入口中，系统 SHOULD 将其实现放在 internal 边界内并允许被移除；本变更中 `scalim.vendor.literich` 即为该类模块并被移除。

#### Scenario: removing a console renderer is treated as breaking and does not require compatibility
- **WHEN** 维护者移除 `scalim.vendor.literich`
- **THEN** 该变更 MUST 被视为 BREAKING（不提供兼容层/弃用期）
- **AND** 代码库中的引用 MUST 被一次性升级到新的 dependency-free console 输出方案

