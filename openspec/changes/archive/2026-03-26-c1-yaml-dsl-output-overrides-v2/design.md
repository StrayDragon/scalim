## Context

下游常见集成形态:

- 需求方在报表 UI 中动态勾选字段 → 前端提交“选中字段列表”给后端
- 后端在不改动共享 demand YAML 的前提下,为本次运行动态指定:
  - 导出字段列表(顺序敏感)
  - 输出路径
  - Excel 单 sheet 导出(未来可能扩展到多输出/多 sheet)

现状痛点:

- YAML authoring surface 已收敛为 `outputs:`(多输出编排);旧顶层 `output:` 已 fail-fast。
- runtime 侧仍存在历史单输出覆盖 `overrides.output.*`,但在 YAML 声明 `outputs` 时会被忽略,导致“运行期动态字段/动态输出”无法与现行 `outputs:` 语义共存。
- 下游被迫使用 `template_vars`(LiteJinja2) 动态生成 `outputs[*].fields`,但模板语法会显著破坏 YAML LSP/schema 的编辑体验,并引入“先渲染再校验”的调试链路。

目标是把“运行期动态输出”收敛为**单一推荐做法**:

1) demand YAML 仅承载需求本体(源/关联/字段等),默认不声明 `outputs`；
2) 运行期通过与 YAML `outputs` 结构一致的 overrides 片段显式指定输出(以单输出 Excel 单 sheet 为主),并可演进到多输出。

## Goals / Non-Goals

**Goals:**
- 提供 YAML-shaped 的运行时输出覆盖能力,让下游无需模板渲染即可动态指定输出字段/路径/sheet/表头策略。
- 将“动态输出”标准化为唯一推荐路径: demand YAML 不声明 `outputs`,由调用侧 overrides 提供 `outputs` 片段。
- 新增默认启用的预检查: 字段展示名(有效 name)不得重复;并允许显式关闭该检查。
- 公共表面收敛: 普通用户不再依赖 Python-only `output_composition` 作为标准扩展点入口。

**Non-Goals:**
- 不把 `template_vars` 变成主路径;它仍仅作为高级 workaround。
- 不在本 change 中提供“按 name 选字段”的完整 helper API(可另开 change),但本 change 为其打底(唯一性约束)。
- 不在本 change 中引入新的“对外稳定 demand dataclass”;运行期 introspection 优先基于 `DemandIr`。

## Decisions

### Decision: `RunOverrides` 输出覆盖对齐 YAML `outputs` 结构

- 将历史 `overrides.output.*` 迁移为 `overrides.outputs`(YAML-shaped `list[dict]`),其元素结构与 YAML `outputs[*]` 对齐,但本轮**仅承诺明细输出(detail)**的最小子集:
  - 仅允许 keys: `name` / `container` / `fields`
  - 不支持 `where` / `from` / `aggregate` 等扩展能力(未来按需增量扩展)
- 调用侧以 plain `list[dict]` 传入(不暴露/不要求用户导入 Python-only `OutputCompositionSpec`)。

**优先级(高 → 低):**
1) `overrides.outputs`(若提供且非空): 作为本次运行的 effective outputs,并编译为 execution 层的 `OutputCompositionSpec`
2) YAML 内 `outputs`(若存在)
3) 默认输出策略: 无文件写出(仅当调用侧显式提供 `sink` 时保留数据)

**覆盖语义:**
- `overrides.outputs` 为 **replace**: 提供则整体替换 YAML `outputs`(不做 deep-merge/patch)
- `overrides.outputs=[]` MUST 视为配置错误并 fail-fast(避免静默“不导出任何东西”)

### Decision: 字段展示名唯一性校验默认启用,可显式关闭

- 定义“有效展示名(effective field display name)”:
  - 若 `field.name` 非空: 使用 `field.name`
  - 否则回退为 `field_id`
- 新增顶层开关 `validate_unique_field_names: bool`(默认启用;未声明视为 `true`)。
- 该校验仅在“本次运行的 effective outputs 中存在 `container.include_header: true`(显式或默认) 且 `container.header_fields_output_by: name`”时触发(避免在不输出 header 的场景下引入不必要的破坏性)；当开关显式为 `false` 时无条件跳过。
- 允许 YAML 侧显式关闭该校验(用于存量重复表头或过渡期配置)。

**校验范围:**
- 校验对象为 demand 内全部字段(源字段 + 派生字段)的有效展示名全局唯一(未来为“按 name 选字段”等能力打底)。

### Decision: `header_fields_output_by` 默认值调整为 `name`(破坏性变更)

- 将 `outputs[*].container.header_fields_output_by` 的默认值从 `field_id` 调整为 `name`。
- 目的:
  - 对多数“人读报表(Excel/CSV)”场景更符合直觉,减少重复配置
  - 与 `validate_unique_field_names` 的默认启用形成闭环: 默认输出中文表头 + 默认避免歧义

**迁移/兼容:**
- 若下游依赖稳定的 `field_id` 表头(程序化消费/对拍),应显式设置 `header_fields_output_by: field_id`。
- 若存量配置存在重复 `field.name`,可先修复重复或临时设置 `validate_unique_field_names: false`(不推荐长期使用)。

### Decision: 文档与生成边界收敛(避免 drift)

- JSON Schema(`src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`)为生成物,禁止手改;任何新增/调整必须修改 SSOT(`src/IMPL_ROOT/dsl/by_yaml/schema_dsl/models/**`)并运行 `just gen-yaml-dsl-schema`。
- 若需要更新 docs-site 的生成页/注入区块,必须修改 SSOT 并运行 `just gen-docs`；避免手改 `.gen.*` 与 `BEGIN/END AUTOGEN:*` 区块。
- 变更完成前使用 `just openspec-check` 作为 OpenSpec 工件漂移门禁。

### Decision: 移除 `output_composition` 运行期参数(破坏性收敛)

- 对外推荐路径仅保留:
  - YAML `outputs`
  - YAML-shaped overrides `overrides.outputs`
- `run/compile` 与 `RunOptions` 中的 `output_composition` 参数/字段将被移除,避免 Python-only 路径绕开 YAML-shaped overrides 的标准做法。
- execution 层内部仍会使用编译产物 `OutputCompositionSpec` 表达 composed outputs,但该对象不再作为 by_yaml facade 的可注入扩展点。

## Risks / Trade-offs

- [BREAKING: overrides 契约变更] → 提供清晰错误信息与迁移指南;仓库内 docs/examples 全量迁移,避免“多套做法并存”。
- [运行期 overrides 复用 outputs 编译链路] → 复用现有解析/编译逻辑减少语义分叉;补充单测覆盖(单输出 Excel 单 sheet)。
- [字段 name 唯一性约束影响存量配置] → 提供显式关闭开关;错误信息需包含冲突列表与定位信息。
- [BREAKING: 移除 `output_composition` 注入扩展点] → 若确有内部/高级场景需要直接构造 composed outputs,应改为走 execution 层入口(`run_ir`)或未来单独的 unsafe/internal API,避免污染普通用户 facade。
- [BREAKING: 移除 `overrides.output.*` 单输出覆盖] → 单输出文件导出统一通过 `outputs/overrides.outputs` 表达;无 `outputs` 时默认不写文件,仅由显式 `sink` 决定是否保留数据。

## Migration Plan

- 代码:
  - 引入 `overrides.outputs` 并将其纳入 `run/compile` 的输出装配优先级。
  - 将历史 `overrides.output.*` 移除并在构造期 fail-fast(TypeError),避免“旧能力还在但被忽略”的误用陷阱。
  - 将 `output_composition` 从 `run/compile` 与 `RunOptions` 中移除,并同步更新 `unsafe_*` 与 `workflow` 入口的参数拼装。
  - 实现字段展示名唯一性预检查(默认启用)并接入 `yaml-dsl validate` 与 runtime compile。
- 文档/示例:
  - 统一升级为“demand YAML 不声明 outputs + Python overrides.outputs 指定输出”的标准做法。
  - `template_vars` 仅作为高级/非推荐 workaround 说明。
- 生成物:
  - 变更涉及 schema 时,修改 SSOT 后运行 `just gen-yaml-dsl-schema` 以更新 `demand.gen.json` 与 drift 测试基线。

## Open Questions

- overrides.outputs 的未来扩展范围: 是否需要支持 `where/from/aggregate` 等能力(本 change 先只支持明细输出的最小子集)。
