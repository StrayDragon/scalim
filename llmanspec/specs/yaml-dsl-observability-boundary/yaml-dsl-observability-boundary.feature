# language: zh-CN
# capability: yaml-dsl-observability-boundary
# purpose: 将 observability 配置从 YAML 主线移除，迁移到 Python/CLI runtime entrypoints，并在迁移期内提供可执行的迁移警告。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-observability-boundary

  @req:r121 @human
  场景: YAML mainline MUST NOT treat `observability.*` as authoring surface
    - 主线 YAML MUST 不再把 `observability.*` 作为稳定 authoring surface: - demand / workflow schema MUST 从主线 YAML 中移除 `observability.*` - 主线 parser / validator MUST 不再把 observability 视为业务建模字段

  @req:r363 @human
  场景: known legacy observability keys MUST fail-fast with migration hints
    - 系统 MUST 对已知 legacy YAML observability.* key 执行 fail-fast（不得再 warning 后忽略继续运行）: - 错误信息 MUST 明确 observability 已从 YAML 主线移除 - 错误信息 MUST 指向 Python / CLI runtime entrypoint 的迁移路径 - 普通未知字段 MUST 继续按现有 unknown-field 规则处理,不得一律当作 observability 处理

  @req:r484 @human
  场景: observability integration MUST be owned by runtime entrypoints
    - 可观测性集成 MUST 由 Python / CLI runtime entrypoints 承载: - runtime entrypoints MUST 能承载自定义 hooks / observers / viz 配置 - YAML 主线 MUST 不再重复建模这些 integration surfaces

  @req:r565 @human
  场景: docs, skills, notebooks and examples MUST migrate away from YAML observability a
    - 仓库内面向用户的材料 MUST 不再把 YAML `observability.*` 作为推荐写法: - docs MUST 以 runtime entrypoints 作为 SSOT - skills / notebooks / examples MUST 同步迁移
  @req:r121 @human
  场景: new-yaml-authoring-does-not-include-observability-blocks
    - 必须成立：当 用户编写新的 demand 或 workflow YAML；那么 `observability.*` MUST NOT 作为推荐或受支持的主线路径出现
    当 用户编写新的 demand 或 workflow YAML
    那么 `observability.*` MUST NOT 作为推荐或受支持的主线路径出现

  @req:r363 @human
  场景: legacy-observability-key-fails-fast
    - 必须成立：假如 某个旧 YAML 仍包含已知的 observability.logging 或等价 key；当 用户执行 validate 或运行入口解析；那么 系统 MUST fail-fast 并给出迁移到 Python/CLI runtime entrypoints 的提示
    假如 某个旧 YAML 仍包含已知的 observability.logging 或等价 key
    当 用户执行 validate 或运行入口解析
    那么 系统 MUST fail-fast 并给出迁移到 Python/CLI runtime entrypoints 的提示
  @req:r484 @human
  场景: custom-observer-is-attached-without-yaml-observability-confi
    - 必须成立：当 用户需要挂接自定义 hook、observer 或内部观测工具；那么 系统 MUST 通过 Python / CLI runtime entrypoints 完成装配
    当 用户需要挂接自定义 hook、observer 或内部观测工具
    那么 系统 MUST 通过 Python / CLI runtime entrypoints 完成装配
  @req:r565 @human
  场景: user-facing-materials-no-longer-teach-yaml-observability-blo
    - 必须成立：当 用户阅读仓库中的 YAML DSL 文档、skills 或 notebooks；那么 这些材料 MUST 不再把 `observability.*` 作为主线 authoring 示例
    当 用户阅读仓库中的 YAML DSL 文档、skills 或 notebooks
    那么 这些材料 MUST 不再把 `observability.*` 作为主线 authoring 示例
