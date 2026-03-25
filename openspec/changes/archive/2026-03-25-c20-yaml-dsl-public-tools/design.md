## Context

当前仓库对外承诺的 `YAML DSL` 稳定入口以 curated public modules 为准(由 public-surface gate 断言 `__all__` 与导入 smoke)。

但下游在真实集成中,除了 `run/compile` 这类运行入口外,还需要少量“工具/自省”能力,典型包括:

- 从 YAML 解析输出字段配置,用于报表导出字段对齐/前置校验/字段映射(`load_output_config`)。
- 在“相对引用”场景下,由 `yaml_path + sys.path` 推导 `base_module_path`(`derive_base_module_path`),用于自定义 resolver 或 fallback 逻辑。

这些能力目前存在于 `scalim.dsl.by_yaml.runtime.*` 内,下游可 import 但无法确定其是否属于长期公共契约(且 user-visible materials gate 禁止推广内部实现路径)。

此外,下游在升级 loader/call_by 等“引用 Python 可调用对象”的能力时,希望能引用一批 Scalim 内置 callable(例如 workflow 内置 loader),但不希望在 YAML 中写内部模块路径,也不希望因此扩大 allowlist 的承诺面。

## Goals / Non-Goals

**Goals:**
- 提供一个稳定、可审计、可回归的公开工具面,让下游无需依赖 `runtime.*` 内部路径即可使用 `load_output_config` 与 `derive_base_module_path`。
- 固化 `load_output_config()` 的返回结构契约(对下游字段对齐非常关键),同时保持运行期返回仍为普通 `dict`。
- 为 loader/call_by/... 等 callable 引用点提供 `^<id>` 的内置 callable 快捷方式,让下游能稳定引用框架内置能力且不扩大 allowlist。
- 保持 `scalim.dsl.by_yaml` 顶层 facade 的最小化: 不把工具面混入默认运行入口,而是放入独立公共模块。
- 保持 Python 3.6 运行时兼容(类型工具使用 `vendor/compact/typing_extensionsx.py`)。

**Non-Goals:**
- 不修改 YAML DSL 的解析/校验/运行语义,仅提供公开稳定入口与契约化文档/类型。
- 本 change 不引入 YAML tag 语法(例如 `!scalim`)或其它需要自定义 YAML parser 的机制;统一采用 plain string 的 `^<id>`。
- 本 change 不改变“缺少 allowlist fail-fast”的安全语义: allowlist 仍为必需,仅对 `^<id>` 这类内置引用做 allowlist bypass(不要求在 allowlist 中声明 `scalim.*`)。
- 不把 `runtime.*` 现有模块移除或标记为公共;内部实现仍可重构,公共承诺仅通过 curated surface 生效。

## Decisions

### Decision: 新增 `scalim.dsl.by_yaml.tools` 作为稳定工具 facade

- 新增模块 `scalim.dsl.by_yaml.tools` 并将其加入 curated public modules 列表。
- `tools` 模块 MUST 使用显式 `__all__` 白名单,并只导出少量高价值能力:
  - `load_output_config`
  - `derive_base_module_path`
  - `OutputConfigDict`(TypedDict)

选择该方案的原因:
- 维持 `scalim.dsl.by_yaml` 顶层入口的“运行入口 + 运行期契约”定位,避免成为杂货铺。
- 将下游集成常用的工具能力集中到一个稳定面,便于后续扩展与回归治理。

替代方案与取舍:
- 直接在 `scalim.dsl.by_yaml` 顶层 re-export: 导入最短,但会持续增加顶层杂项符号,与入口最小化目标冲突。
- 继续让下游依赖 `runtime.*`: 与 public surface governance 冲突,且在重构中易碎。
- 分散为 `...introspection` / `...references`: 语义更细,但对下游而言需要多处导入;本轮优先“单一稳定工具面”。

### Decision: `load_output_config()` 返回结构以 TypedDict 固化,运行期仍返回 `dict`

- 定义 `OutputConfigDict`(TypedDict) 仅用于类型层表达稳定契约;运行期返回值保持 `dict`。
- 契约采用“可加字段但不改名/不删字段”的 semver 规则:
  - 新增 key: 允许(向后兼容)
  - 修改/删除/改语义: 需要 major

### Decision: 内置 callable 语法固定为 `^<id>`(plain string)

- 采用 plain string `^<id>` 作为唯一内置 callable 引用语法,避免 YAML tag 语义与额外 parser 复杂度。
- `<id>` 采用稳定的 `/` 分段命名,通过一份显式“builtin callable 词表”(vocabulary)映射到具体 callable。
  - 词表支持调用方自定义(可扩展/覆盖默认词表),以满足下游集成的受控扩展点需求
  - 默认词表仅提供少量 Scalim 内置 id(保守暴露;可审计)
- 该语法在所有“期待 Python callable 引用”的位置均可使用(例如 `main_source.loader`、`sources.*.loader`、`fields.*.call_by`、`sources.*.normalize.call_by`、`retry.should_retry` 等)。

### Decision: `^<id>` 解析绕过 allowlist,但不改变 allowlist 必需性

- `^<id>` 的解析与执行 MUST 不依赖 `allowed_modules/allowed_functions`(避免迫使下游把 `scalim.*` 加入 allowlist)。
- `run/compile` 与 `ConfigToIRConverter` 等入口对 allowlist 的必需性保持不变(缺失 allowlist MUST fail-fast),以符合既有安全规范(`yaml-dsl-allowlist-policy`)。

### Decision: 不遗留 Open Questions

本轮不保留“待决定模块命名/导出范围/返回契约”等不确定项;以上决策即为实现 SSOT。

## Risks / Trade-offs

- [公共表面增长] → 通过 curated public modules + `__all__` 白名单 gate,确保增长是显式且可审计的。
- [下游对返回结构产生强依赖] → 通过 TypedDict/文档明确 semver 规则,并将变更纳入回归测试与 OpenSpec 规范。
- [工具模块引入额外导入成本] → `tools` 为独立模块,仅在下游需要时导入;不增加默认运行入口导入负担。

## Migration Plan

- 仓库内:
  - public-surface gate 增加 `scalim.dsl.by_yaml.tools` 的导入 smoke 与 `__all__` 断言。
  - 文档/示例中涉及“输出字段配置/相对引用基准推导”的推荐用法,统一迁移为 `scalim.dsl.by_yaml.tools`。
  - 文档/示例中涉及 Scalim 内置 callable 的推荐用法统一迁移为 `^<id>`(避免写内部模块路径)。
- 下游:
  - `scalim.dsl.by_yaml.runtime.introspection.load_output_config` → `scalim.dsl.by_yaml.tools.load_output_config`
  - `scalim.dsl.by_yaml.runtime.references.derive_base_module_path` → `scalim.dsl.by_yaml.tools.derive_base_module_path`
  - `scalim.workflow.loaders:sheetbook_sheet_rows`(或其它内置 callable) → `^workflow/sheetbook_sheet_rows`
