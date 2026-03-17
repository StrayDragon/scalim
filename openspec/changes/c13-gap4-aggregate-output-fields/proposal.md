## Why

下游大量 Excel 报表具有强约束的“输出合同”（固定列顺序、重复表头/分段表头、需要与旧实现对拍）。当前 Scalim 0.2.7 的 YAML DSL 在 `outputs.*.aggregate` 场景存在硬限制：

- 只要声明 `aggregate`，该 output 被视为 derived output，编译期 **禁止** `outputs.*.fields`，导致无法在 YAML 中精确控制 derived output 的列顺序；
- derived output 的字段缺少对显示名（包含重复表头）的“一等支持”。

这会直接阻断“旧报表迁移到 YAML DSL 并保持对拍”的落地路径（见 `.tmp/downstream_report/gaps/04_aggregate_output_no_fields.md`）。

## What Changes

- 允许 aggregate output 声明 `outputs.*.fields`，用于 **输出编排**（select + order），不改变聚合计算语义。
- 为 `aggregate.fields.<out_field_id>` 增加可选显示名（例如 `name`），在 `container.header_fields_output_by: name` 时作为表头输出；允许重复 name 以支持重复表头合同。
- 更新 schema hover/校验与运行时 derived output layout 编译，使报错可操作、行为可预测。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `demand-dsl`: 扩展 `outputs.*.aggregate` 的输出编排能力（aggregate output 允许 `fields`；aggregate field 支持显示名）。
- `yaml-dsl-schema`: demand schema MUST 覆盖上述新写法，并在 hover 中明确其用途是“输出合同编排”而非影响聚合语义。

## Impact

- YAML authoring：可在 derived output 中声明列顺序与表头显示名，显著降低迁移对拍成本。
- Runtime/code：改动集中在 `src/scalim/dsl/by_yaml/config_parsing/parsers/outputs.py` 与 `src/scalim/dsl/by_yaml/runtime/output_composition_yaml.py`。

