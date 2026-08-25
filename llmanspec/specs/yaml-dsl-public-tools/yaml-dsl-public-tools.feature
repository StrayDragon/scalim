# language: zh-CN
# capability: yaml-dsl-public-tools
# purpose: 为 YAML DSL 的下游集成提供稳定”工具/自省”公开入口，避免下游依赖 runtime 的内部实现模块路径。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-public-tools

  @req:r124 @human
  场景: tools MUST expose `load_output_config` with a stable dict contract
    - 系统 MUST 通过 tools 模块暴露输出配置自省能力。 `load_output_config()` MUST 返回 `dict`（运行期）且其结构契约 MUST 稳定。该 `dict` 至少包含以下 keys： - `params` - `field_name_mapping` - `output_fields` - `outputs` 系统 MUST 提供 `OutputConfigDict`（TypedDict）作为类型层契约，用于描述上述结构。

  @req:r366 @human
  场景: tools MUST expose `derive_base_module_path`
    - 系统 MUST 通过 tools 模块暴露相对引用基准推导能力。 该函数的行为 MUST 与现有实现一致：根据 `yaml_path + sys.path` 推导相对引用的 `base_module_path`。

  @req:r487 @human
  场景: tools module MUST be a curated public module
    - 系统 MUST 提供 tools 模块作为稳定公开模块，并将其纳入 curated public surface 回归门禁（导入 smoke + `__all__` 白名单断言）。 该模块 MUST 使用显式 `__all__` 白名单控制导出，避免随内部重构意外扩大公共承诺面。
  @req:r124 @human
  场景: load-output-config-returns-the-required-keys
    - 必须成立：假如 一个合法的 demand YAML 文件路径；当 调用方执行 tools 模块的 load_output_config；那么 返回值 MUST 为 `dict`
    假如 一个合法的 demand YAML 文件路径
    当 调用方执行 tools 模块的 load_output_config
    那么 返回值 MUST 为 `dict`
  @req:r366 @human
  场景: derive-base-module-path-returns-a-module-path
    - 必须成立：假如 `yaml_path` 位于某个 `sys.path` 前缀目录下；当 调用方执行 tools 模块的 derive_base_module_path；那么 返回值 MUST 为字符串模块路径（允许为空字符串表示根包）
    假如 `yaml_path` 位于某个 `sys.path` 前缀目录下
    当 调用方执行 tools 模块的 derive_base_module_path
    那么 返回值 MUST 为字符串模块路径（允许为空字符串表示根包）
  @req:r487 @human
  场景: tools-module-is-importable-and-uses-explicit-all
    - 必须成立：当 调用方导入 tools 模块；那么 导入 MUST 成功
    当 调用方导入 tools 模块
    那么 导入 MUST 成功
