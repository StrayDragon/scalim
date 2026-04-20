# public-api-governance Specification

**状态: ✅ 已实现**

## Purpose
定义 public API 边界治理规则：稳定入口编目、`__all__` 治理、用户材料导入边界、agent skill 生成器，确保在不引入"符号级硬 manifest SSOT"的前提下维护清晰的公共契约。

## Related Concepts
- Public API 治理门禁脚本 (scripts/check-*.py)
- Public API 生成器 (scripts/gen-public-api-*.py)
- scalim-public-api skill (agentdev/skills/scalim-public-api/)
- 自动生成的 public API 文档

## Requirements


### Requirement: stable public entrypoints MUST be explicitly cataloged
系统 MUST 为用户侧可依赖的公共入口维护一份显式、可审计的稳定目录，而不是让"当前能 import 的路径"自然演化成公共契约。

该目录 MUST 覆盖核心公共模块（如 YAML DSL 入口、IR 类型、事件系统、sink 契约、资源 shortcuts 等），并将未列入目录的路径（如 internal 模块、运行期细节、旧路径、底层协议工具）视为非公共契约。

#### Scenario: curated public entrypoints are import-smoke covered
- **WHEN** 维护者执行 public-surface import smoke gate
- **THEN** 目录中的稳定公开入口 MUST 全部可导入
- **AND** gate MUST 以显式白名单为准，而不是扫描整个包树自动放大公共表面

### Requirement: public entrypoints MUST be explicit via `__all__` + docs
系统 MUST 仍以模块 `__all__` 作为 public export 的符号级契约来源,并通过文档提供用户侧推荐导入的可读投影.

与此前"手工维护推荐导入页"不同,本要求修改为:
- public API 文档页 MUST 由 public API catalog 自动生成,而不是手工维护
- 文档内容 MUST 与 `__all__` 导出面保持一致（通过生成与 drift-check 约束）

#### Scenario: docs stay consistent with `__all__`
- **WHEN** public API 文档生成器从 `__all__` 导出面生成 `.gen.md`
- **THEN** 文档中的模块/导出清单 MUST 与扫描得到的 catalog 一致

### Requirement: public API catalog MUST be generated from `__all__` exports
系统 MUST 提供一个可重复运行的生成入口，用于扫描源码树下声明了 `__all__` 的模块并汇总其导出符号集合，形成可审计的 public API catalog。

该 catalog MUST 满足：
- 扫描源码根目录（排除 vendor 等显式排除项）
- 对于 internal 模块，其 `__all__` 按治理规则应为空，因此不会扩大 catalog
- 输出 MUST 为确定性产物，并具备可用于 drift-check 的稳定格式

#### Scenario: catalog generation is deterministic and reviewable
- **WHEN** 维护者运行 public API catalog 的生成入口
- **THEN** 系统 MUST 输出一个可审阅的 catalog（包含模块与导出符号清单）
- **AND** 在无代码变更时重复运行 MUST 产生相同结果

### Requirement: hard manifest SSOT MUST NOT be required
系统 MUST NOT 要求维护者手工维护"符号级 manifest"才能通过 public API 治理门禁(维护成本高,且容易把简单约定复杂化).

#### Scenario: public API gates do not rely on a symbol-level manifest
- **WHEN** 贡献者为 public facade 模块调整 `__all__`(新增/删除/重命名符号)
- **THEN** 治理门禁 MUST 仅依赖 `__all__` 治理脚本 + 示例回归通过
- **AND** 不应要求同步更新某个符号级 manifest 文件才能通过 CI


### Requirement: user-facing materials MUST use only cataloged entrypoints
系统 MUST 要求文档、skills、examples 与 public API 回归用例仅使用已编目的稳定公开入口表达官方用法，并禁止其导入内部实现路径。

#### Scenario: docs and examples avoid internal implementation imports
- **WHEN** 维护者审阅或检查用户可见文档、skills 与 examples
- **THEN** 其中的官方导入示例 MUST 仅引用已编目的稳定公开入口
- **AND** 不得把内部实现模块（如 runtime/_internal/schema_dsl）写成推荐用户路径
- **AND** 不得把旧的已弃用路径写成推荐用户路径

#### Scenario: internal-path imports are rejected in user-facing materials
- **WHEN** docs/skills/examples 中出现 `_internal` 或其它未编目的内部实现导入路径
- **THEN** 治理门禁 MUST 立即报错并提示替代的稳定导入路径

### Requirement: removed internal modules MUST be blocked from user-facing materials
系统 MUST 将已移除的内部实现模块列入黑名单，并通过用户材料门禁阻止其再次出现在用户可见材料中。

#### Scenario: removed modules are rejected in user materials
- **GIVEN** 任一用户材料文件包含已移除模块的导入或引用
- **WHEN** 维护者运行用户材料门禁检查
- **THEN** gate MUST fail-fast 并提示移除该导入/引用

### Requirement: runtime code MUST NOT depend on non-cataloged console renderers
系统 MUST 禁止将仅用于展示输出的渲染器当作运行时依赖或事实公共契约扩散；当某模块仅用于 console 展示且不在 public API curated 入口中时，系统应将其实现放在 internal 边界内并允许被移除。

#### Scenario: removing a console renderer is treated as breaking
- **WHEN** 维护者移除一个非 cataloged 的展示渲染器
- **THEN** 该变更 MUST 被视为 BREAKING（不提供兼容层/弃用期）
- **AND** 代码库中的引用 MUST 被一次性升级到新的 dependency-free 输出方案


### Requirement: internal modules MUST explicitly seal exports and avoid symbol leakage
系统 MUST 要求内部实现模块显式声明其导出面以避免符号泄漏，并禁止任何模块 `__all__` 包含非 dunder 的内部符号。

最小治理要求：
- 位于 `_internal/` 目录或以 `_` 前缀命名的模块 MUST 定义空的 `__all__`
- 任一模块的 `__all__` MUST NOT 包含以 `_` 开头且非 dunder 的名称

#### Scenario: underscore symbols are rejected from __all__
- **WHEN** 回归门禁扫描源码中的 `__all__`
- **THEN** 任一 `__all__` MUST NOT 包含以 `_` 开头且非 dunder 的名称
- **AND** 若发现该类条目，门禁 MUST fail-fast 并输出可定位的模块路径与符号名集合

#### Scenario: internal modules declare empty __all__
- **WHEN** 回归门禁扫描内部模块目录与文件
- **THEN** 每个模块 MUST 定义 `__all__`
- **AND** 其 `__all__` MUST 为空（`[]` 或 `()`）

### Requirement: public facades MUST NOT re-export internal implementation modules
系统 MUST 将 internal 实现细节与稳定公开入口物理隔离；public facades MUST NOT re-export 内部路径（如 `*_internal*`、`._internal.*`、`events._*`、未编目的模块路径）。

#### Scenario: internal re-exports are detected and rejected
- **WHEN** 维护者在 public facade 中新增对内部模块的 re-export
- **THEN** public surface gate MUST fail-fast 指出具体模块路径与建议的 facade 迁移方式

### Requirement: events/sinks public facades MUST be pinned by explicit __all__ gates
系统 MUST 将 `scalim.events` 与 `scalim.sinks` 视为稳定公开入口的一部分，并通过显式 `__all__` 白名单回归门禁固定其公共导出面。

#### Scenario: changing facade exports fails fast in curated gate
- **WHEN** 维护者在 `scalim.events` 或 `scalim.sinks` 调整对外导出符号集合
- **THEN** curated public surface gate MUST fail-fast 指出缺失或新增的导出符号


### Requirement: stable public surface changes MUST be explicit and auditable
系统 MUST 将 public surface 的新增/删除/重命名视为需要显式决策的变更：
- 任何变更 MUST 同步更新 public API manifest
- 任何变更 MUST 同步更新 public API suite（或等价回归）以覆盖新的公开面

#### Scenario: changing exports requires manifest and suite updates
- **WHEN** 维护者调整任一稳定公开入口模块的 `__all__`
- **THEN** 对应 gate MUST 要求同时更新 manifest 与 suite,否则 fail-fast

### Requirement: unsafe capabilities MUST NOT live on default public facades
系统 MUST 将"放宽安全边界"的能力与默认公共 facade 隔离。

若后续仍需保留不安全能力，系统 MUST 通过显式 `unsafe` 语义的专用入口、专用参数或等价强标识暴露；系统 MUST NOT 继续将其挂载在默认公共 facade 上，造成"官方推荐入口也可直接放宽边界"的印象。

#### Scenario: public API review rejects non-explicit unsafe escape hatches
- **WHEN** 维护者为默认公共 facade 新增一个会放宽安全边界的能力
- **THEN** 该能力 MUST 因缺少显式 `unsafe` 语义而被视为不符合公共表面治理约束


### Requirement: public API jump-imports MUST be generated from Tier1 curated entrypoints
系统 MUST 提供一个可重复运行的生成入口，用于基于 Tier1 curated entrypoints 与各模块字面量 `__all__` 生成一个"编辑器跳转辅助导入文件"。

该生成物 MUST 满足：
- 输出为 dev artifact（禁止提交）
- 生成逻辑 MUST 采用 AST 扫描（不 import 目标模块）
- 输出 MUST 为确定性产物（无代码变更时重复运行输出一致）

#### Scenario: maintainer generates jump-imports for Tier1 entrypoints
- **WHEN** 维护者运行生成入口
- **THEN** 系统 MUST 写入跳转辅助导入文件
- **AND** 该文件 MUST 覆盖 Tier1 curated entrypoints 列表中的每个模块，并包含该模块 `__all__` 中的符号导入

### Requirement: public API docs MUST be generated as `.gen.md` from the catalog
系统 MUST 将 public API 导入指南与导出清单改为由 public API catalog 自动生成，并纳入文档治理与漂移门禁。

该生成物 MUST：
- 文件名包含 `.gen.` 标记
- 文件头部包含"自动生成 + 生成入口"提示
- 由受控入口（如 `just gen-docs`）刷新

#### Scenario: generated public API docs are drift-gated
- **WHEN** 维护者修改源码中的 `__all__` 导出面但未刷新生成文档
- **THEN** drift-check MUST 失败并提示运行生成入口


### Requirement: scalim-public-api skill MUST exist and be generated from SSOT
系统 MUST 提供一个 skill（`scalim-public-api`），采用"手工 SKILL.md + 受控 generated references"的治理模型，并基于 Tier1 markers 和 `__all__` 通过静态扫描生成确定性 references。

生成器约束：
- MUST 以 Tier1 curated entrypoints markers 与各模块 `__all__` 字面量为 SSOT 输入
- MUST 采用 AST/text 静态扫描（不 import 目标模块）
- MUST 仅写入受控输出（禁止覆盖手工 SKILL.md）
- 每个 Tier1 入口模块 MUST 至少对应一个可运行示例覆盖（examples/pytest）

#### Scenario: skill generator produces only managed outputs
- **WHEN** 维护者运行 `just gen-public-api-skill`
- **THEN** 系统 MUST 仅更新 skill 的受控 generated references
- **AND** MUST NOT 覆盖或重排 SKILL.md 手工内容

#### Scenario: tier1 catalog output is deterministic
- **WHEN** 输入不变且重复运行生成入口
- **THEN** 受控 references 输出 MUST 保持逐字节一致

#### Scenario: validate mode detects drift
- **GIVEN** 维护者修改了输入 SSOT（Tier1 markers / `__all__` / 示例套件结构）
- **WHEN** 维护者运行 `just validate-public-api-skill`
- **THEN** 若未刷新受控产物，校验 MUST fail-fast 并提示运行生成入口

#### Scenario: missing tier1 coverage fails validation
- **GIVEN** Tier1 markers 新增了一个入口模块
- **WHEN** examples/pytest 覆盖未同步补齐
- **THEN** 校验 MUST fail-fast 并指出缺失模块
