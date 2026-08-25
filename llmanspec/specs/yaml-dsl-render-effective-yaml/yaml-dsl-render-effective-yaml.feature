# language: zh-CN
# capability: yaml-dsl-render-effective-yaml
# purpose: 提供用于 review/debug/对拍的库侧 API，将”作者写的 demand YAML”渲染为 effective YAML（展开后的单文件等价配置），避免 imports/template 复用在 review 时变成黑盒。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-render-effective-yaml

  @req:r125 @human
  场景: Library MUST render effective demand YAML by expanding template_vars and imports
    - 系统 MUST 提供一个用于 review/debug/对拍的**库侧 API**,将“作者写的 demand YAML”渲染为 effective YAML(展开后的单文件等价配置)。 该 API MUST 支持 `loads/dumps` 形态(或等价接口): - `load_effective_demand_yaml(<demand.yaml>, template_vars=...) -> mapping` - `dump_effective_demand_yaml(<mapping>) -> yaml_text` 渲染行为 MUST 至少包含: - 对 demand YAML 文本执行 template precompile(仅当调用方显式提供 template vars) - 对 demand YAML mapping 执行 imports/$import expansion 输出约束 MUST 满足: - 输出 MUST 不包含 `imports` 与 `$import`(已被展开) - 输出 MUST 保留 `{$init_var: ...}` / `$keys` / `$rows` 等指令节点(它们属于运行期模板 AST)

  @req:r367 @human
  场景: editor effective expansion MUST support outputs.fields flatten and YAML aliases
    - 为支撑 editor 侧导航与补全,系统 MUST 提供静态的 effective expansion 视图,至少覆盖: - YAML anchors/aliases 与 merge key 的展开（对当前打开文档以内存态文本为准） - `outputs[*].fields` 的 nested list flatten 规则（与运行时/validator 口径一致）
  @req:r125 @human
  场景: api-renders-effective-yaml-text
    - 必须成立：假如 调用方提供 `demand.yaml`；当 调用方执行 `dump_effective_demand_yaml(load_effective_demand_yaml(demand.yaml))`；那么 MUST 返回有效的 YAML 文本
    假如 调用方提供 `demand.yaml`
    当 调用方执行 `dump_effective_demand_yaml(load_effective_demand_yaml(demand.yaml))`
    那么 MUST 返回有效的 YAML 文本

  @req:r125 @human
  场景: api-fails-fast-on-import-expansion-errors
    - 必须成立：假如 demand YAML 的 imports 存在 cycle 或类型冲突；当 调用方执行 `load_effective_demand_yaml(demand.yaml)`；那么 MUST 失败(抛出异常)
    假如 demand YAML 的 imports 存在 cycle 或类型冲突
    当 调用方执行 `load_effective_demand_yaml(demand.yaml)`
    那么 MUST 失败(抛出异常)
  @req:r367 @human
  场景: outputs-fields-alias-is-expanded-for-navigation
    - 必须成立：假如 YAML 使用 anchor 定义字段列表 `detail_fields: &detail_fields [a, b]`；当 editor 侧请求 outputs.fields 的 completion/definition；那么 effective expansion MUST 将该 outputs.fields 视为展开后的有效列表（至少包含 `a`、`b`）
    假如 YAML 使用 anchor 定义字段列表 `detail_fields: &detail_fields [a, b]`
    当 editor 侧请求 outputs.fields 的 completion/definition
    那么 effective expansion MUST 将该 outputs.fields 视为展开后的有效列表（至少包含 `a`、`b`）
