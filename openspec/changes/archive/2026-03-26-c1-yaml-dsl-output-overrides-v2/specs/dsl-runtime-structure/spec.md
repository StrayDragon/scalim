# dsl-runtime-structure Specification

## Purpose
更新 by_yaml runtime 的输出装配与 overrides 契约,使其与现行 YAML `outputs` authoring surface 对齐,并将“动态输出”收敛为单一路径: `overrides.outputs`。

## MODIFIED Requirements

### Requirement: official facade MUST preserve current extension seams

在公共表面收敛过程中，系统 MUST 保持当前已确认的受控扩展点继续可经由官方 facade 使用，而不是通过删减能力来完成“收敛”。

本轮至少包括：

- `sink`
- `components`
- `allowed_modules` / `allowed_functions`
- `allowed_yaml_roots`

系统 MUST 破坏性移除 by_yaml facade 的 Python-only 输出注入扩展点:
- `run/compile` 不再接受 `output_composition=...`
- `RunOptions` 不再暴露 `output_composition` 字段

execution 层内部仍会使用编译产物 `OutputCompositionSpec` 表达 composed outputs,但该对象不再作为 by_yaml facade 的可注入扩展点。

#### Scenario: public facade remains behavior-complete for supported extension seams
- **WHEN** 调用方通过 `IMPL_ROOT.dsl.by_yaml.run(...)` 或 `compile(...)` 使用上述受控扩展点
- **THEN** 系统 MUST 继续支持这些能力
- **AND** 公共表面收敛 MUST 体现为“入口与契约明确”,而不是静默删除这些受支持能力

### Requirement: runtime 支持 overrides 覆盖 YAML `output`
系统 SHALL 允许调用方在不修改 YAML 文件的情况下以**显式 overrides** 覆盖输出编排,以适配不同运行环境(例如临时输出路径、不同导出字段顺序、不同 sheet 名)。

系统 MUST 使用 `overrides.outputs` 作为输出覆盖的唯一形态,并破坏性移除历史 `overrides.output.*`。

`overrides.outputs` 的结构 MUST 与 YAML 顶层 `outputs` 的元素结构一致(YAML-shaped `list[dict]`),但本 change 仅承诺明细输出的最小子集: `name/container/fields`。

`overrides.outputs` 的语义 MUST 为“整体替换”(replace): 当其提供且非空时,系统 MUST 仅使用 `overrides.outputs` 作为 effective outputs,而不是对 YAML `outputs` 做 deep-merge。
当调用方显式提供 `overrides.outputs=[]` 时,系统 MUST fail-fast(避免静默“不导出任何东西”)。

#### Scenario: overrides 覆盖 outputs
- **GIVEN** YAML 配置包含 `outputs`
- **WHEN** 调用方提供 `overrides.outputs`
- **THEN** adapter 编译产出的输出编排 MUST 反映 `overrides.outputs` 的覆盖结果

### Requirement: YAML 缺省 output 时使用默认输出策略且 overrides 仍生效
系统 MUST 允许 YAML DSL 配置缺省顶层 `outputs` 节点。

当 `outputs` 缺省时,by_yaml runtime adapter MUST 以 execution 层的默认输出策略作为基线(例如默认不写文件),并在调用方提供 `overrides.outputs` 时正确应用覆盖。

#### Scenario: 缺省 outputs 但提供 overrides.outputs
- **WHEN** YAML 配置未声明顶层 `outputs`
- **AND** 调用方在 `compile/run` 中提供 `overrides.outputs`
- **THEN** adapter 编译产出的 effective outputs MUST 等于 `overrides.outputs`

#### Scenario: 缺省 outputs 且无 overrides
- **WHEN** YAML 配置未声明顶层 `outputs`
- **AND** 调用方未提供 `overrides.outputs`
- **THEN** adapter 编译产出的请求 MUST 仍为合法默认值
- **AND** 不应产生文件写出(除非调用方通过显式 sink/容器配置启用)

## REMOVED Requirements

### Requirement: `output.fields` 的双重语义必须在编译期拆解
**Reason**: 现行 YAML authoring surface 已收敛为 `outputs[*].fields` 的“有序 field_id 引用列表”,不再承担“字段 override(例如覆盖 name)”的双重语义;继续保留该 requirement 会误导下游把字段覆盖能力放到 outputs/overrides 中实现。

**Migration**: 若需要调整展示名/表头,应在字段定义处配置 `field.name` 并通过 `header_fields_output_by: name` 选择输出策略;若需要调整导出字段顺序,使用 `outputs[*].fields` 或 `overrides.outputs[*].fields` 的有序列表表达。

## ADDED Requirements

### Requirement: YAML `outputs` MUST compile into an output composition request
系统 MUST 将 YAML `outputs`(以及 `overrides.outputs`)编译为 execution 层的输出编排请求对象,并确保 execution/engine 不需要读取 YAML config 即可完成写出。

#### Scenario: execution does not read YAML config for outputs
- **WHEN** 调用方通过 by_yaml adapter 编译得到 execution request 并执行
- **THEN** execution/engine MUST 仅依赖编译产物中的输出编排对象完成写出
