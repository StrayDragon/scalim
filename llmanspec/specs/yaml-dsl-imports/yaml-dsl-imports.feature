# language: zh-CN
# capability: yaml-dsl-imports
# purpose: 为 demand YAML 提供跨文件复用能力: 顶层 `imports` + 的 `$import`(编译期展开),并在 schema/语义校验前完成展开. 说明: - `$import` 的允许范围以稳定 authoring surfaces 为准;详见 yaml-dsl-demand-imports-scope 规范. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-imports

  @req:r115 @human
  场景: Demand YAML supports top-level imports mapping
    - 系统 MUST 支持在 demand YAML 顶层声明 `imports` 映射,其 key 为别名字符串, value 为片段文件路径字符串。 系统 MUST 在编译期加载对应片段文件,并允许后续 `$import` 通过别名引用片段内容。

  @req:r357 @human
  场景: imports path MUST support relative fragments (v2) without relying on git repo ro
    - 系统 MUST 放宽 `imports.<alias>` 的路径规则,使其在 v2 支持相对路径 fragments,并且不依赖 git repo root 推断。 当解析 demand YAML 时(包含被导入的 fragments): - imports 路径解析基准 MUST 为**当前 YAML 文件**所在目录(确定性) - imports MUST 支持以下相对文件路径形态(`.yaml/.yml`): - `./x.yaml`、`x.yaml` - `x/y.yaml`(子目录) - `../x.yaml`(父目录) 同时,系统 MUST 拒绝以下路径: - 绝对路径(含 Windows 盘符/UNC) - 任意 URI scheme(形如 `*://...`,包括 `file://`、`http(s)://`、`scalim://`) - 预留的 alias 前缀/语法(例如 `@/x.yaml`、`COMMON:/x.yaml`)

  @req:r478 @human
  场景: $import merges mapping fragments deterministically
    - 系统 MUST 支持在允许的 mapping 节点内声明特殊键 `$import`,用于把片段文件中的某个 mapping 片段合并到当前 mapping。 允许范围 MUST 以稳定 authoring surfaces 为准;详见 `llmanspec/specs/yaml-dsl-demand-imports-scope/spec.toon`。 系统 MUST 将 `$import` 引用字符串解析为 `<alias>(.<segment>)*`,其中每个 `<segment>` 必须匹配正则 `^[a-zA-Z_][a-zA-Z0-9_]*$`(不提供转义机制)。 系统 MUST 按以下确定性顺序合并: 1. 先合并 `$import` 列表中的所有片段(按顺序,后者覆盖前者) 2. 再合并当前 mapping(剔除 `$import` 本身),本地覆盖导入结果

  @req:r560 @human
  场景: $import requires mapping fragments and fails fast on type mismatch
    - 系统 MUST 要求 `$import` 引用的目标值为 mapping;否则校验 MUST 失败。 系统 MUST 在合并时执行类型一致性检查: - mapping 与 mapping 才允许递归 deep-merge - list 仅允许 replace(本地覆盖导入) - scalar 仅允许覆盖 - 任意类型不匹配 MUST 报错(例如 mapping vs scalar),以避免静默覆盖导致结果不可信

  @req:r624 @human
  场景: Import graph cycles are rejected
    - 系统 MUST 检测 import/include 的循环引用(跨文件链路)并 fail-fast。 错误信息 MUST 包含导入链路(文件路径序列),以便定位循环来源。 系统 MUST 施加最大展开深度上限(**20**),超过上限 MUST 报错以避免病态递归。

  @req:r671 @human
  场景: Validation runs on expanded final config
    - 系统 MUST 在执行 schema-only 校验与语义 validator 之前完成 import 展开,并在“最终配置”上进行校验与编译(仅文件路径入口)。 系统 MUST 在校验错误中包含足够的来源信息,至少包含: - 逻辑路径(例如 `sources.orders.fields.order_id`) - import 链路信息(例如 `... imported from <file> via <ref> ...`)
  @req:r115 @human
  场景: imports-declares-fragment-alias
    - 必须成立：当 demand YAML 包含 `imports: {common: ./common.yaml}`；那么 系统在展开阶段可以通过 `common` 别名定位并加载该 YAML 文件
    当 demand YAML 包含 `imports: {common: ./common.yaml}`
    那么 系统在展开阶段可以通过 `common` 别名定位并加载该 YAML 文件
  @req:r357 @human
  场景: imports-can-reference-a-sibling-fragment
    - 必须成立：假如 demand YAML 位于 `./reports/demand.yaml`；当 demand YAML 配置 `imports.common: ./common.yaml`；那么 imports MUST 成功解析并加载该 fragment
    假如 demand YAML 位于 `./reports/demand.yaml`
    当 demand YAML 配置 `imports.common: ./common.yaml`
    那么 imports MUST 成功解析并加载该 fragment

  @req:r357 @human
  场景: imports-can-reference-a-fragment-in-a-child-directory
    - 必须成立：假如 demand YAML 位于 `./reports/demand.yaml`；当 demand YAML 配置 `imports.shared: ./_shared/common.yaml`；那么 imports MUST 成功解析并加载该 fragment
    假如 demand YAML 位于 `./reports/demand.yaml`
    当 demand YAML 配置 `imports.shared: ./_shared/common.yaml`
    那么 imports MUST 成功解析并加载该 fragment

  @req:r357 @human
  场景: imports-can-reference-a-fragment-in-a-parent-directory
    - 必须成立：假如 demand YAML 位于 `./reports/demand.yaml`；当 demand YAML 配置 `imports.shared: ../_shared/common.yaml`；那么 imports MUST 成功解析并加载该 fragment
    假如 demand YAML 位于 `./reports/demand.yaml`
    当 demand YAML 配置 `imports.shared: ../_shared/common.yaml`
    那么 imports MUST 成功解析并加载该 fragment

  @req:r357 @human
  场景: absolute-paths-and-uri-schemes-are-rejected
    - 必须成立：当 `imports.common` 为 `/etc/passwd`、`C:\\secrets.yaml`、`file:///tmp/x.yaml`、`scalim://yaml-dsl/presets/common.yaml` 或 `@/fragments/common.yaml`；那么 校验 MUST 失败并提示仅支持相对文件路径(`.yaml/.yml`)
    当 `imports.common` 为 `/etc/passwd`、`C:\\secrets.yaml`、`file:///tmp/x.yaml`、`scalim://yaml-dsl/presets/common.yaml` 或 `@/fragments/common.yaml`
    那么 校验 MUST 失败并提示仅支持相对文件路径(`.yaml/.yml`)
  @req:r478 @human
  场景: import-deep-merges-and-local-overrides
    - 必须成立：假如 `common.sources` 中包含 `orders: {..., fields: {order_id: ...}}`；当 需求侧写 `sources: {$import: common.sources, orders: {fields: {order_id: {name: "订单ID"}}}}`；那么 最终 `sources.orders` MUST 同时包含片段中的未覆盖字段与本地覆写的 `name`
    假如 `common.sources` 中包含 `orders: {..., fields: {order_id: ...}}`
    当 需求侧写 `sources: {$import: common.sources, orders: {fields: {order_id: {name: "订单ID"}}}}`
    那么 最终 `sources.orders` MUST 同时包含片段中的未覆盖字段与本地覆写的 `name`
  @req:r560 @human
  场景: importing-a-non-mapping-fragment-is-rejected
    - 必须成立：当 `$import` 指向的目标值是 list 或 scalar；那么 校验 MUST 失败并提示 `$import` 只允许导入 mapping 片段
    当 `$import` 指向的目标值是 list 或 scalar
    那么 校验 MUST 失败并提示 `$import` 只允许导入 mapping 片段

  @req:r560 @human
  场景: merge-type-mismatch-is-rejected
    - 必须成立：假如 导入片段中 `relations.r1` 为 mapping；当 本地把同 key 写成字符串(或反之)；那么 校验 MUST 失败并指出冲突 key 的路径
    假如 导入片段中 `relations.r1` 为 mapping
    当 本地把同 key 写成字符串(或反之)
    那么 校验 MUST 失败并指出冲突 key 的路径
  @req:r624 @human
  场景: cycle-import-is-rejected-with-trace
    - 必须成立：假如 A 导入 B, B 导入 C, C 导入 A；当 用户编译 A；那么 系统 MUST 报错并包含 `A -> B -> C -> A` 的导入链路
    假如 A 导入 B, B 导入 C, C 导入 A
    当 用户编译 A
    那么 系统 MUST 报错并包含 `A -> B -> C -> A` 的导入链路
  @req:r671 @human
  场景: validator-sees-expanded-config
    - 必须成立：当 用户在片段文件中定义 `sources.customers`；那么 schema/validator MUST 认可最终存在的 `sources.customers` 并按其内容执行后续校验
    当 用户在片段文件中定义 `sources.customers`
    那么 schema/validator MUST 认可最终存在的 `sources.customers` 并按其内容执行后续校验

  @req:r671 @human
  场景: string-based-validation-rejects-imports
    - 必须成立：当 用户使用纯文本入口(例如 `load_string` 或 `validate_yaml_text`)并包含 `imports` 或 `$import`；那么 系统 MUST fail-fast 并提示改用文件路径入口进行校验/编译
    当 用户使用纯文本入口(例如 `load_string` 或 `validate_yaml_text`)并包含 `imports` 或 `$import`
    那么 系统 MUST fail-fast 并提示改用文件路径入口进行校验/编译
