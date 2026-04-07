# yaml-dsl-imports Specification

**状态: ✅ 已实现**

## Purpose
为 demand YAML 提供跨文件复用能力: 顶层 `imports` + **受 scope 限制**的 `$import`(编译期展开),并在 schema/语义校验前完成展开.

说明:
- `$import` 的允许范围以稳定 authoring surfaces 为准;详见 `openspec/specs/yaml-dsl-demand-imports-scope/spec.md`.

## Related Code (as implemented)
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/imports.py` (imports/$import 展开与合并)
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/loader.py` (文件路径入口自动展开)
- `src/IMPL_ROOT/dsl/yaml_dsl/_internal/config_parsing/validator.py` (校验基于展开后的最终配置)
- `src/IMPL_ROOT/cli/yaml_dsl.py` (CLI validate/schema validate 行为)
- `src/IMPL_ROOT/dsl/yaml_dsl/schema/demand.gen.json` (schema 支持 imports/$import)

## Requirements

### Requirement: Demand YAML supports top-level imports mapping
系统 MUST 支持在 demand YAML 顶层声明 `imports` 映射,其 key 为别名字符串, value 为片段文件路径字符串。
系统 MUST 在编译期加载对应片段文件,并允许后续 `$import` 通过别名引用片段内容。

#### Scenario: imports declares fragment alias
- **WHEN** demand YAML 包含 `imports: {common: ./common.yaml}`
- **THEN** 系统在展开阶段可以通过 `common` 别名定位并加载该 YAML 文件

### Requirement: imports path MUST support relative fragments (v2) without relying on git repo root
系统 MUST 放宽 `imports.<alias>` 的路径规则,使其在 v2 支持相对路径 fragments,并且不依赖 git repo root 推断。

当解析 demand YAML 时(包含被导入的 fragments):

- imports 路径解析基准 MUST 为**当前 YAML 文件**所在目录(确定性)
- imports MUST 支持以下相对文件路径形态(`.yaml/.yml`):
  - `./x.yaml`、`x.yaml`
  - `x/y.yaml`(子目录)
  - `../x.yaml`(父目录)

同时,系统 MUST 拒绝以下路径:

- 绝对路径(含 Windows 盘符/UNC)
- 任意 URI scheme(形如 `*://...`,包括 `file://`、`http(s)://`、`scalim://`)
- 预留的 alias 前缀/语法(例如 `@/x.yaml`、`COMMON:/x.yaml`)

#### Scenario: imports can reference a sibling fragment
- **GIVEN** demand YAML 位于 `./reports/demand.yaml`
- **AND** fragment 文件位于 `./reports/common.yaml`
- **WHEN** demand YAML 配置 `imports.common: ./common.yaml`
- **THEN** imports MUST 成功解析并加载该 fragment

#### Scenario: imports can reference a fragment in a child directory
- **GIVEN** demand YAML 位于 `./reports/demand.yaml`
- **AND** fragment 文件位于 `./reports/_shared/common.yaml`
- **WHEN** demand YAML 配置 `imports.shared: ./_shared/common.yaml`
- **THEN** imports MUST 成功解析并加载该 fragment

#### Scenario: imports can reference a fragment in a parent directory
- **GIVEN** demand YAML 位于 `./reports/demand.yaml`
- **AND** fragment 文件位于 `./_shared/common.yaml`
- **WHEN** demand YAML 配置 `imports.shared: ../_shared/common.yaml`
- **THEN** imports MUST 成功解析并加载该 fragment

#### Scenario: absolute paths and URI schemes are rejected
- **WHEN** `imports.common` 为 `/etc/passwd`、`C:\\secrets.yaml`、`file:///tmp/x.yaml`、`scalim://yaml-dsl/presets/common.yaml` 或 `@/fragments/common.yaml`
- **THEN** 校验 MUST 失败并提示仅支持相对文件路径(`.yaml/.yml`)

### Requirement: $import merges mapping fragments deterministically
系统 MUST 支持在允许的 mapping 节点内声明特殊键 `$import`,用于把片段文件中的某个 mapping 片段合并到当前 mapping。
允许范围 MUST 以稳定 authoring surfaces 为准;详见 `openspec/specs/yaml-dsl-demand-imports-scope/spec.md`。
系统 MUST 将 `$import` 引用字符串解析为 `<alias>(.<segment>)*`,其中每个 `<segment>` 必须匹配正则 `^[a-zA-Z_][a-zA-Z0-9_]*$`(不提供转义机制)。
系统 MUST 按以下确定性顺序合并:
1. 先合并 `$import` 列表中的所有片段(按顺序,后者覆盖前者)
2. 再合并当前 mapping(剔除 `$import` 本身),本地覆盖导入结果

#### Scenario: $import deep merges and local overrides
- **GIVEN** `common.sources` 中包含 `orders: {..., fields: {order_id: ...}}`
- **WHEN** 需求侧写 `sources: {$import: common.sources, orders: {fields: {order_id: {name: "订单ID"}}}}`
- **THEN** 最终 `sources.orders` MUST 同时包含片段中的未覆盖字段与本地覆写的 `name`

### Requirement: $import requires mapping fragments and fails fast on type mismatch
系统 MUST 要求 `$import` 引用的目标值为 mapping;否则校验 MUST 失败。
系统 MUST 在合并时执行类型一致性检查:
- mapping 与 mapping 才允许递归 deep-merge
- list 仅允许 replace(本地覆盖导入)
- scalar 仅允许覆盖
- 任意类型不匹配 MUST 报错(例如 mapping vs scalar),以避免静默覆盖导致结果不可信

#### Scenario: importing a non-mapping fragment is rejected
- **WHEN** `$import` 指向的目标值是 list 或 scalar
- **THEN** 校验 MUST 失败并提示 `$import` 只允许导入 mapping 片段

#### Scenario: merge type mismatch is rejected
- **GIVEN** 导入片段中 `relations.r1` 为 mapping
- **WHEN** 本地把同 key 写成字符串(或反之)
- **THEN** 校验 MUST 失败并指出冲突 key 的路径

### Requirement: Import graph cycles are rejected
系统 MUST 检测 import/include 的循环引用(跨文件链路)并 fail-fast。
错误信息 MUST 包含导入链路(文件路径序列),以便定位循环来源。
系统 MUST 施加最大展开深度上限(**20**),超过上限 MUST 报错以避免病态递归。

#### Scenario: cycle import is rejected with trace
- **GIVEN** A 导入 B, B 导入 C, C 导入 A
- **WHEN** 用户编译 A
- **THEN** 系统 MUST 报错并包含 `A -> B -> C -> A` 的导入链路

### Requirement: Validation runs on expanded final config
系统 MUST 在执行 schema-only 校验与语义 validator 之前完成 import 展开,并在“最终配置”上进行校验与编译(仅文件路径入口)。
系统 MUST 在校验错误中包含足够的来源信息,至少包含:
- 逻辑路径(例如 `sources.orders.fields.order_id`)
- import 链路信息(例如 `... imported from <file> via <ref> ...`)

#### Scenario: validator sees expanded config
- **WHEN** 用户在片段文件中定义 `sources.customers`
- **AND** 需求侧通过 `$import` 引入该片段
- **THEN** schema/validator MUST 认可最终存在的 `sources.customers` 并按其内容执行后续校验

#### Scenario: string-based validation rejects imports
- **WHEN** 用户使用纯文本入口(例如 `load_string` 或 `validate_yaml_text`)并包含 `imports` 或 `$import`
- **THEN** 系统 MUST fail-fast 并提示改用文件路径入口进行校验/编译
