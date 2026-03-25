## Why

下游常见的“报表 UI 动态选字段”场景需要在**不改 YAML 文件**的前提下,运行时动态指定:

- 导出字段列表(顺序敏感)
- 输出路径
- 输出类型(Excel 单 sheet / CSV)
- 表头策略(按 `field_id` 或按字段 `name`)

当前 by-yaml 运行入口虽然保留了 `overrides.output.*` 的能力,但它是围绕历史顶层 `output:`/单输出模式设计的;而现行 YAML authoring surface 已收敛为 `outputs:`(多输出编排),并且在启用 `outputs`(或 Python-only 的 `output_composition`,本 change 将移除)时会忽略 `overrides.output.*`。

在没有统一标准的情况下,下游容易被迫使用 `template_vars`(LiteJinja2 预编译)等 workaround 来动态生成 `outputs/fields`,但这会带来 LSP/schema 校验体验变差、调试与迁移成本上升的问题。

因此需要把“运行时动态输出”收敛为**单一推荐做法**: demand YAML 只承载需求本体,输出编排由调用侧通过与 YAML 结构一致的 overrides 片段显式提供。

## Repro / Current Pain

### 复现: 运行期想动态改导出字段,但 `overrides.output.*` 不生效

1) 编写一个 demand YAML,使用顶层 `outputs:` 来描述输出(Excel 单 sheet,并指定 `fields` 列表)。  
2) Python 侧调用 `run(...)` 时通过 `overrides.output.*` 传入“本次运行的字段列表/输出路径/sheet”等覆盖参数。  
3) 结果: 一旦 YAML 中存在 `outputs`(或调用侧传 `output_composition`),运行期会忽略 `overrides.output.*`,导致动态字段/动态输出无法生效。  

### 复现: 被迫使用模板 workaround,但 LSP/schema 体验退化

1) 为了动态生成 `outputs[*].fields`,下游改用 `template_vars`(LiteJinja2) + `{% for ... %}` 生成 YAML 片段。  
2) 结果: 编辑器 YAML LSP/schema 校验会频繁报错/失效,并引入“先渲染再校验”的额外调试链路。  

### 复现: 旧顶层 `output:` 已 fail-fast,存量写法无法继续

历史单输出 authoring 的 `output:` 已不再是可用的 YAML 语法表面,下游若仍依赖旧形态会直接被 schema/validator 拒绝。

## What Changes

- **BREAKING**: 重设计 `RunOverrides` 的“输出覆盖”形态,引入 `overrides.outputs`(YAML-shaped `list[dict]`),用于在不修改 demand YAML 的前提下运行时指定输出。
  - 统一推荐: demand YAML 默认不声明 `outputs`,由调用侧提供 overrides 输出片段驱动导出。
  - 本轮仅承诺明细输出(detail)的最小子集: `name/container/fields`(顺序敏感),未来按需扩展到 `where/from/aggregate/...`。
- **BREAKING**: 移除历史 `overrides.output.*`(单输出模式覆盖)以避免“传参但被忽略”的误用陷阱;单输出导出统一通过 `outputs/overrides.outputs` 表达。
- **BREAKING**: 从 `run/compile` 与 `RunOptions` 中移除 Python-only `output_composition` 参数/字段,避免绕开 YAML-shaped overrides 的标准做法。
- **BREAKING**: 将 `outputs[*].container.header_fields_output_by` 默认值从 `field_id` 调整为 `name`(更符合人读报表默认预期)。
- 新增一个 YAML 顶层校验开关 `validate_unique_field_names: bool`,用于默认启用“字段展示名(name)不得重复”的预检查,并允许显式关闭(仅对不需要该约束的场景开放)。
  - 该校验以“有效展示名”为准: `name` 为空时回退为 `field_id`。
  - 该校验仅在 effective outputs 使用 `container.include_header: true`(显式或默认) 且 `container.header_fields_output_by: name` 时触发;当开关显式为 false 时无条件跳过。
- `template_vars` 仍保留为高级 workaround,但不作为“动态选字段/动态输出”的标准推荐路径。

## Requirements

### Must Have

- demand YAML 应可复用: 顶层 `outputs:` 在 authoring 层应保持“可选”(默认可不声明),以便同一份 demand 可在不同运行中复用不同输出策略。
- 运行期必须可动态指定单输出 Excel 单 sheet 导出策略,至少包含:
  - 导出字段列表(顺序敏感)
  - 输出路径
  - sheet 名
  - 表头输出策略(按 `field_id` 或按字段 `name`)
- overrides 的“输出覆盖”应与 YAML 结构同形,以降低下游认知成本并减少维护分叉(避免维护两套输出语义/两套字段描述方式)。
- 字段展示名唯一性校验默认启用,并提供显式关闭开关:
  - 校验对象为“有效展示名”: `field.name` 为空时回退到 `field_id`
  - 失败时错误信息应可诊断(至少包含冲突的展示名与相关字段定位信息)
  - 触发条件: 仅当 effective outputs 使用 `include_header: true`(显式或默认) 且 `header_fields_output_by: name`
  - 开关: `validate_unique_field_names: false` 可显式关闭

### Nice to Have (Follow-ups)

- 为未来“按 name 选字段/按 name 生成 header”等能力打底: 在字段展示名唯一时,可提供稳定的 `field_id` ↔ `field.name` 映射工具(重复时 fail-fast)。
- 提供一个稳定的、只读的 demand 配置遍历/视图接口(避免把内部 schema dataclass 直接当公共 API),便于生态做 introspection 与工具化。

### Non-Goals (This Change)

- 不把 `template_vars` 变成主路径;它仍只作为高级 workaround。
- 不提供/推广 Python-only 的“注入式 output_composition”扩展点作为普通用户能力入口;输出编排统一通过 YAML `outputs` 或 `overrides.outputs` 表达。

## Capabilities

### New Capabilities
- `yaml-dsl-output-overrides`: 提供与 YAML `outputs` 结构一致的运行时输出覆盖能力,作为 UI 动态选字段/动态输出路径的唯一推荐做法。

### Modified Capabilities
- `dsl-runtime-structure`: 更新 overrides 的公开契约与优先级,将输出覆盖从历史 `output` 语义迁移为 YAML `outputs` 结构,并收敛默认 facade 的扩展点暴露范围。
- `yaml-dsl-schema`: 新增/更新与输出覆盖相关的 schema hover/校验提示,并新增字段展示名唯一性校验开关的 authoring surface。

## Impact

- 影响的核心代码/接口集中在:
  - `src/scalim/dsl/by_yaml/runtime/contracts.py` 与 `runtime/entrypoints.py`(overrides 契约与入口签名/优先级)
  - `src/scalim/dsl/by_yaml/runtime/compiler.py`(输出覆盖编译与 request 构建)
  - `src/scalim/dsl/by_yaml/schema_dsl/models/**` 与 `src/scalim/dsl/by_yaml/schema/demand.gen.json`(新增校验开关与 hover 文案)
  - `src/scalim/dsl/by_yaml/config_parsing/validator.py`(字段展示名唯一性预检查)
  - docs/tests/examples(迁移到单一推荐做法,避免推广 Python-only output_composition 与模板 workaround)
