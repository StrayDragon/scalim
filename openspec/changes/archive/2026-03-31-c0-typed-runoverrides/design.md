## Context

当前 `scalim.dsl.by_yaml.RunOverrides` 将 `outputs/resources/outputs_defaults` 设计为 YAML-shaped `dict/list[dict]`:

- 下游在 “动态选字段/动态导出路径/动态 sheet” 场景中往往直接拼接这些 dict。
- 框架内部为了保持语义一致,分别在:
  - by_yaml runtime 编译链路中解析/校验这些 dict
  - workflow 编译链路中再次解析一份“同形 overrides mapping”
  造成实现重复、口径漂移风险与维护成本上升。

此外,dict 结构缺少类型约束与工厂方法:
- IDE/类型系统无法提供稳定提示
- schema 演进时下游更容易踩到“结构细节变化”导致的破坏
- 错误定位往往依赖运行时校验路径字符串,不够稳定可控

本变更希望在不新增导入模块(尽量不引入新的 `scalim.dsl.by_yaml.*` 子模块)的前提下,把 overrides 的公共契约收敛成一组强类型 dataclasses,并在框架内部完全移除 dict 解析路径。

## Goals / Non-Goals

**Goals:**
- 将 `RunOverrides.outputs/resources/outputs_defaults` 从 YAML-shaped dict 契约升级为强类型 dataclasses(明确 BREAKING)。
- 保持现有能力边界不扩张: 仍只承诺 detail outputs 的最小子集,不引入 `where/from/aggregate` 等 overrides。
- by_yaml runtime 与 workflow 编译链路统一消费同一套 typed overrides,避免“双实现”。
- 提供覆盖主流导出场景的 `@classmethod` 工厂方法,让下游更少手写结构、更多走标准构造。
- 不新增新的 public 模块;新增类型优先放在现有稳定契约文件中,并由 `scalim.dsl.by_yaml` facade 导出。
- Python 3.6 运行时兼容保持不变。

**Non-Goals:**
- 不修改 demand/workflow YAML schema(仅调整 Python 侧 overrides 输入结构)。
- 不提供 dict 旧写法兼容层/弃用期(一次性升级)。
- 不新增新的运行入口(例如不引入 `run_export()`),仍使用 `run/compile/run_workflow`。
- 不在本变更中收缩 `scalim.sinks` / `scalim.ob.*` 等其它领域的 public surface(若需收缩,另开 change 管理)。

## Decisions

### Decision 0: hard shrink internal import paths (库 API 暴露收缩)

为防止下游固化内部实现路径(并随着迭代被频繁破坏),本变更同时执行一次明确的 BREAKING 收缩:

- 将 `scalim.dsl.by_yaml.config_parsing.*` 视为内部实现路径,并从包树中移除该导入路径(旧路径将 `ModuleNotFoundError`)。
- 内部实现移动到 `scalim.dsl.by_yaml._internal.config_parsing.*` 并由框架内部引用(下游若强行依赖,只能显式依赖带 `_internal` 的路径,自担风险)。
- 保留并强化稳定入口:
  - `scalim.dsl.by_yaml`(运行入口 + typed overrides 契约)
  - `scalim.dsl.by_yaml.tools`(工具/自省)
  - `scalim.dsl.by_yaml.workflow*`(workflow 稳定入口)

此决策与 typed overrides 一起,目标是让“对外可依赖的点”更少、更强约束、更可回归。

### Decision 1: typed overrides 作为 public contract,定义在现有契约文件中

- 在 `src/scalim/dsl/by_yaml/runtime/contracts.py` 中新增 overrides dataclasses(作为稳定契约的一部分)。
- `scalim.dsl.by_yaml` facade(`src/scalim/dsl/by_yaml/__init__.py`) 将这些类型加入 `__all__` 作为推荐入口。
- 不新增 `scalim.dsl.by_yaml.exports` / `scalim.dsl.by_yaml.overrides` 等新模块,避免公共入口扩张。

### Decision 2: 输出 overrides 只表达“detail outputs 的最小子集”

保持既有边界: `RunOverrides.outputs` 仅允许表达:
- `name`
- `fields`(有序 field_id 列表)
- `to`(book/sheet 绑定) 或 `container`(csv 文件输出) 二选一
- `write`(仅在 book 绑定时允许)

显式禁止:
- `where`
- `from`
- `aggregate`

### Decision 3: IO-only overrides 使用 typed overlay,不再接受 YAML-shaped patch

- `RunOverrides.resources` 与 `RunOverrides.outputs_defaults` 改为 typed dataclasses,保持 overlay 语义:
  - 仅允许覆盖 IO 层字段(books 的路径/预算/导出配置/写入默认值等)
  - 不允许触及输出定义层字段(例如 outputs.fields 以外的表达式/聚合等)

### Decision 4: 内部实现不再将 typed overrides “转回 dict 再解析”

框架内部在运行期编译时:
- 直接把 overrides dataclasses 映射为内部 schema dataclasses(例如 `OutputTargetConfig`/`ResourcesConfig`/`BookConfig` 等)
- 沿用既有 outputs 编译流水线(`compile_output_composition_from_yaml`)以保持语义一致
- 完全移除 dict 解析路径,避免出现“看似 typed,实则仍依赖 dict 结构细节”的隐性耦合

### Decision 5: 旧 dict 输入 fail-fast,并带可操作迁移提示

虽然不保留兼容,但为了减少排错成本:
- 当调用方仍传入旧的 `dict/list[dict]` 结构时,系统必须在编译期 fail-fast
- 错误信息必须明确指出:
  - 已不再支持 YAML-shaped overrides
  - 推荐的 typed dataclasses 与工厂方法用法
  - 指向稳定逻辑路径(例如 `RunOverrides.outputs`)

## Risks / Trade-offs

- [Breaking surface] → 通过 OpenSpec 明确 BREAKING,并在文档/示例/测试中一次性升级,避免“隐式兼容”导致长期治理失败。
- [语义对齐风险] runtime 与 workflow 链路都涉及 overrides; → 以同一组行为回归用例覆盖两条链路,并增加“typed vs legacy rejected”的专用用例。
- [类型过多导致学习成本上升] → 提供少量高价值工厂方法覆盖主流场景,并在文档中只展示工厂方法与最小组合用法。

## Migration Plan

- 以明确的 BREAKING 版本发布(建议 `0.6.0`),并在 release note/用户指南中给出最小迁移示例:
  - 旧: `RunOverrides(outputs=[{...}])`
  - 新: `RunOverrides(outputs=(OutputOverride(...),))` 或 `RunOverrides.<factory>(...)`
- 文档/示例统一只保留新写法,不保留双写法对照(避免下游继续复制旧结构)。

## Further Shrink Opportunities (out of scope)

外部已经升级到 `scalim==0.5.1` 后,仍可考虑在后续 change 中继续收缩破坏面:

- 收紧 allowlist 的“自引用”脚枪: 默认拒绝 `allowed_modules` 中出现 `scalim` 前缀,强制使用 `^builtin` 或 `builtin_callables` 扩展点(需要评估对内部测试/示例的影响)。
- 收窄或分层 `scalim.sinks` 的导出面(若确有大规模下游依赖与 churn 风险)。
