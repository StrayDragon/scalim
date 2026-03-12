## Why

业务报表迁移中,大量 “lookup 小表/维表” 的 loader 返回值形状并不总是 Scalim 最理想的 `mapping[key -> row]`:

- `list[row]` 需要转换为 keyed mapping(并处理 duplicate key)
- `mapping[key -> list[row]]` 需要 `take_first`
- `mapping[key -> nested_dict]` 需要拍平/重命名/投影
- 某些嵌套结构的 key 可能是 **int/enum 值**(而不是字符串),仅靠点路径 extract 无法表达

目前 YAML DSL 的 `normalize` 仅支持 `kind: index_by_key`,无法覆盖上述常见形状,导致业务不得不写大量 Python wrapper.
这直接阻碍“脚本变薄”和片段复用(尤其是 `preload_forever` 小表的通用 normalize).

最小脱敏样例中给出了典型形状与目标输出:
`openspec/changes/yaml-source-normalize-shapes/acceptance/mvp_demo/README.md`

## What Changes

- 扩展 YAML DSL 的 source-level `normalize` 能力,覆盖常见“非理想形状”:
  - `take_first`: `mapping[key -> list[row]]` 取第一条并归一化为 `mapping[key -> row]`(并定义 `on_empty` 策略)
  - `map_values`: 对 `mapping` 的 values 批量应用 normalization pipeline(例如 take_first + project_fields + rename)
  - `project_fields`: 对 row/nested mapping 做投影与重命名,并复用既有 `extract` 路径语法来定位(支持 int/enum key,例如 `"[1].clearn_reason_level"`)
- 提供受控扩展点 `normalize.call_by`(可选):
  - 复用现有 allowlist 安全边界与引用解析能力
  - 固定 contract: 输入与输出必须为 `Mapping`(否则 fail-fast),避免不可解释形状漂移
  - 用于覆盖 “无法用 declarative normalize 表达但又不想写 wrapper module” 的场景

## Decisions (确定化)

- `take_first` **不**处理顶层 `list[row]` 场景: list→keyed mapping 仍统一使用 `index_by_key` + `on_conflict`(现有写法),避免职责重叠与二义性.
- `normalize.call_by` 仅允许 **top-level(whole-result)** 使用,不作为 `map_values.steps` 的一步;需要 value-level 自定义时,在 `call_by` 内部自行遍历 `result.items()` 处理.
- `project_fields` 保持 **纯投影/重命名**(可注入 `from_key`),不引入常量/表达式赋值;常量/派生逻辑使用既有字段 `compute/call_by` 或 `normalize.call_by` 实现.

## Capabilities

### New Capabilities
- `yaml-source-normalize-shapes`: YAML 可声明更多 normalize 形状,显著减少迁移中的 Python wrapper.

### Modified Capabilities
- `yaml-source-normalize`: 在既有 `index_by_key` 之上扩展 normalize.kind 枚举与语义.
- `yaml-dsl-schema`: 更新 schema hover/validate,并补齐对 normalize pipeline 的结构化解释.

## Impact

- 受影响模块(预期):
  - `src/scalim/spec/ir/sources.py`(`SourceNormalizeIr.apply` 扩展更多 kind)
  - `src/scalim/dsl/by_yaml/schema_dsl/models/source.py` + schema 生成物
  - `src/scalim/dsl/by_yaml/config_parsing/validators/sources.py`(语义校验: kind/参数约束)
- 测试/验收:
  - 覆盖:
    - list -> map(on_conflict=first/last/error)(已存在,回归用例补齐)
    - nested dict flatten(含 int key) 的 normalize 行为与确定性
    - normalize.call_by 的 allowlist/contract 校验
