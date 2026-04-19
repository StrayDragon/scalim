# public-api-governance Specification

**状态: ✅ 已实现**

## Purpose
定义 public API 边界治理规则：稳定入口编目、`__all__` 治理、用户材料导入边界、agent skill 生成器，确保在不引入"符号级硬 manifest SSOT"的前提下维护清晰的公共契约。
定义 public API 边界治理规则：稳定入口编目、`__all__` 治理、用户材料导入边界、agent skill 生成器，确保在不引入"符号级硬 manifest SSOT"的前提下维护清晰的公共契约。

## Related Code (as implemented)
- `scripts/check-*.py` (public API 治理门禁)
- `scripts/gen-public-api-*.py` (public API 生成器)
- `agentdev/skills/scalim-public-api/` (agent skill + generated references)
- `docs/doc/getting-started/public-api.gen.md` (自动生成的 public API 文档)

## Requirements


### Requirement: stable public entrypoints MUST be explicitly cataloged
系统 MUST 为用户侧可依赖的公共入口维护一份显式、可审计的稳定目录，而不是让"当前能 import 的路径"自然演化成公共契约。

该目录在本轮至少 MUST 覆盖：

- `scalim.dsl.yaml_dsl` 及其官方 facade 符号（包括 `run`、`compile`、`run_workflow` 与运行期契约类型）
- `scalim.dsl.yaml_dsl.workflow`
- `scalim.dsl.yaml_dsl.workflow_types`
- `scalim.dsl.yaml_dsl.workflow_paths`
- `scalim.dsl.yaml_dsl.tools`
- `scalim.spec.ir`
- `scalim.workflow.loaders`（workflow YAML 中可通过字符串引用的内置 loader 入口）
- `scalim.events`（事件 envelope、事件类型常量与事件目录查询入口；typed payload 不作为公共导入契约）
- `scalim.sinks`（sink 契约与常用 sinks；内部 helper 不作为公共导入契约）
- `scalim.shortcuts.resources`（资源类 shortcut 稳定入口 package）
- `scalim.shortcuts.resources.outputs`（输出发现/最新产物定位 facade；隐藏底层 D-2 落盘协议细节）

系统 MUST 将未列入目录的路径视为非公共契约；其中至少包括：

- `scalim.dsl.yaml_dsl.runtime.*`
- `scalim.dsl.yaml_dsl._internal.*`
- `scalim.dsl.yaml_dsl.schema_dsl.*`
- `scalim.dsl.by_yaml.*`（旧路径：本轮收敛后不得再作为用户侧稳定契约）
- `scalim.events._*`
- `scalim.sinks._internal.*`
- `scalim.execution.versioned_outputs`（底层落盘协议工具；不作为推荐 public facade）

#### Scenario: curated public entrypoints are import-smoke covered
- **WHEN** 维护者执行 public-surface import smoke gate
- **THEN** 目录中的稳定公开入口 MUST 全部可导入
- **AND** gate MUST 以显式白名单为准,而不是扫描整个包树自动放大公共表面

### Requirement: public entrypoints MUST be explicit via `__all__` + docs
系统 MUST 仍以模块 `__all__` 作为 public export 的符号级契约来源,并通过文档提供用户侧推荐导入的可读投影.

与此前"手工维护推荐导入页"不同,本要求修改为:
- public API 文档页 MUST 由 public API catalog 自动生成,而不是手工维护
- 文档内容 MUST 与 `__all__` 导出面保持一致（通过生成与 drift-check 约束）

#### Scenario: docs stay consistent with `__all__`
- **WHEN** public API 文档生成器从 `__all__` 导出面生成 `.gen.md`
- **THEN** 文档中的模块/导出清单 MUST 与扫描得到的 catalog 一致

### Requirement: public API catalog MUST be generated from `__all__` exports
系统 MUST 提供一个可重复运行的生成入口,用于扫描 `src/scalim/**` 下所有声明了 `__all__` 的模块,并汇总其导出符号集合,形成可审计的 public API catalog.

该 catalog MUST 满足:
- 扫描范围默认为 `src/scalim/**`
- MUST 排除 `src/scalim/vendor/**`（以及其它显式排除项; CLI 已迁出 `src/scalim/`）
- 对于 internal 模块（例如 `_internal/` 或 `_*.py`）,其 `__all__` 按治理规则应为空,因此不会扩大 catalog
- 输出 MUST 为确定性产物,并具备可用于 drift-check 的稳定格式

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


### Requirement: public-facing materials MUST use only cataloged entrypoints
系统 MUST 要求文档、skills、examples 与 public API 回归用例仅使用已编目的稳定公开入口表达官方用法.

系统 MUST NOT 在这些面向用户的材料中把内部实现路径当作推荐导入路径、教程示例或长期契约.

#### Scenario: docs and examples avoid internal implementation imports
- **WHEN** 维护者审阅或检查用户可见文档、skills 与 examples
- **THEN** 其中的官方导入示例 MUST 仅引用已编目的稳定公开入口
- **AND** 不得把 `scalim.dsl.yaml_dsl.runtime.*`、`scalim.dsl.yaml_dsl._internal.*` 或 `scalim.dsl.yaml_dsl.schema_dsl.*` 写成推荐用户路径
- **AND** 不得把旧的 `scalim.dsl.by_yaml.*` 写成推荐用户路径
- **AND** 不得把 `scalim.events._*` 或 `scalim.sinks._internal.*` 写成推荐用户路径

### Requirement: user-facing materials MUST NOT import internal paths
系统 MUST 将 docs/skills/examples 视为"用户可见材料",并禁止其导入内部实现路径(约定: `._internal` 或 `._foo` 均视为内部实现).

#### Scenario: internal-path imports are rejected in user-facing materials
- **WHEN** docs/skills/examples 中出现 `_internal` 或其它未编目的内部实现导入路径
- **THEN** `scripts/check-user-material-import-boundaries.py --check` MUST 立即报错 并提示替代的稳定导入路径

### Requirement: removed internal modules MUST be blocked from reappearing in user-facing materials
系统 MUST 将 `scalim.vendor.literich` 视为已移除的内部实现模块，并通过用户材料门禁阻止其再次出现在用户可见材料中（docs / skills / notebooks）。

#### Scenario: user-material import boundary gate rejects scalim.vendor.literich
- **GIVEN** 任一用户材料文件（docs/skills/notebooks）包含文本 `scalim.vendor.literich`
- **WHEN** 维护者运行 `scripts/check-user-material-import-boundaries.py --check`
- **THEN** gate MUST fail-fast 并提示移除该导入/引用

### Requirement: runtime code MUST NOT depend on non-cataloged console renderers
系统 MUST 禁止将仅用于"漂亮输出"的渲染器当作运行时依赖或事实公共契约扩散。

具体而言：当某模块仅用于 console 展示且不在 public API curated 入口中，系统 SHOULD 将其实现放在 internal 边界内并允许被移除；本变更中 `scalim.vendor.literich` 即为该类模块并被移除。

#### Scenario: removing a console renderer is treated as breaking and does not require compatibility
- **WHEN** 维护者移除 `scalim.vendor.literich`
- **THEN** 该变更 MUST 被视为 BREAKING（不提供兼容层/弃用期）
- **AND** 代码库中的引用 MUST 被一次性升级到新的 dependency-free console 输出方案


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
系统 MUST 提供一个可重复运行的生成入口,用于基于 Tier1 curated entrypoints（`# pragma: scalim-public-api tier1:...`）与各模块字面量 `__all__` 生成一个"编辑器跳转辅助导入文件"，以便维护者快速了解框架主动 re-export 的稳定入口与符号集合。

该生成物 MUST 满足：

- 输出路径 MUST 为 `.tmp/public_api_jump_imports.py`（属于 dev artifact，禁止提交）。
- 生成逻辑 MUST 采用 `AST` 扫描（不 import 目标模块，避免副作用与可选依赖影响）。
- 输出 MUST 为确定性产物（无代码变更时重复运行输出一致）。

#### Scenario: maintainer generates jump-imports for Tier1 entrypoints
- **WHEN** 维护者运行 `just gen-public-api-jump-imports`
- **THEN** 系统 MUST 写入 `.tmp/public_api_jump_imports.py`
- **AND** 该文件 MUST 覆盖 Tier1 curated entrypoints 列表中的每个模块，并包含该模块 `__all__` 中的符号导入（忽略非法标识符条目）

### Requirement: public API docs MUST be generated as `.gen.md` from the catalog
系统 MUST 将 public API 导入指南与导出清单改为由 public API catalog 自动生成的 `*.gen.md`,并纳入文档治理与漂移门禁.

该生成物 MUST:
- 文件名包含 `.gen.`（例如 `docs/doc/getting-started/public-api.gen.md`）
- 文件头部包含"自动生成 + 生成入口(脚本或 `just` 目标)"提示
- 由 `just gen-docs`（或其覆盖的受控入口）刷新

#### Scenario: generated public API docs are drift-gated
- **WHEN** 维护者修改 `src/scalim/**` 中的 `__all__` 导出面但未刷新生成文档
- **THEN** drift-check MUST 失败并提示运行生成入口


### Requirement: `scalim-public-api` skill MUST exist and be governed with generated references
系统 MUST 提供一个新的 skill：`agentdev/skills/scalim-public-api/`，并采用"手工 SKILL.md + 受控 generated references"的治理模型：

- `agentdev/skills/scalim-public-api/SKILL.md` MUST 为手工维护（SSOT）。
- 生成器 MUST 仅写入以下受控输出（禁止覆盖手工文件）：
  - `agentdev/skills/scalim-public-api/references/**/*.gen.*`
  - `agentdev/skills/scalim-public-api/references/generated/**`
- 系统 MUST 提供可重复运行的入口用于生成与校验：
  - `just gen-public-api-skill`
  - `just validate-public-api-skill`

#### Scenario: skill generator produces only managed outputs
- **WHEN** 维护者运行 `just gen-public-api-skill`
- **THEN** 系统 MUST 仅更新 skill 的受控 generated references
- **AND** MUST NOT 覆盖或重排 `agentdev/skills/scalim-public-api/SKILL.md`

#### Scenario: validate mode detects drift
- **GIVEN** 维护者修改了输入 SSOT（Tier1 markers / `__all__` / 示例套件结构）
- **WHEN** 维护者运行 `just validate-public-api-skill`
- **THEN** 若未刷新受控产物，校验 MUST fail-fast 并提示运行生成入口

### Requirement: generated references MUST be derived from Tier1 markers and `__all__` via static scanning
生成器 MUST 以以下 SSOT 为输入，并通过静态扫描（AST/text）生成确定性 references：

- Tier1 curated entrypoints：`src/scalim/**/__init__.py` markers（`# pragma: scalim-public-api tier1:...`）
- 每个入口模块的导出符号集合：该模块的 `__all__` 字面量（tuple/list of string literals）

生成器 MUST NOT 通过 `import` 目标模块来发现 markers 或 `__all__`（避免副作用与可选依赖导致的不稳定）。

#### Scenario: tier1 catalog output is deterministic
- **WHEN** 输入不变且重复运行 `just gen-public-api-skill`
- **THEN** 受控 references 输出 MUST 保持逐字节一致

### Requirement: skill references MUST map Tier1 entrypoints to runnable example coverage
生成器 MUST 为 Tier1 curated entrypoints 生成一个可审阅的"覆盖映射"参考，用于把稳定入口模块映射到可运行示例与回归门禁：
- examples（`notebooks/marimo/example_public_api_suite/` 的章节 SSOT）
- pytest（`tests/public_api/` 的最小闭环回归）
- headless gate（`just examples`）

覆盖映射 MUST 满足：
- 每个 Tier1 入口模块 MUST 至少对应一个被 examples gate 覆盖的章节
- 每个 Tier1 入口模块 MUST 同时被 pytest public_api suite 覆盖（直接或通过执行章节间接覆盖）

#### Scenario: missing tier1 coverage fails validation
- **GIVEN** Tier1 markers 新增了一个入口模块
- **WHEN** examples/pytest 覆盖未同步补齐
- **THEN** `just validate-public-api-skill` MUST fail-fast 并指出缺失模块
