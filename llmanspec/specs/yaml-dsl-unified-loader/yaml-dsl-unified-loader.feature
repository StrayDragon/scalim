# language: zh-CN
# capability: yaml-dsl-unified-loader
# purpose: 提供统一的 YAML load facade，确保 DSL 所有入口（CLI、runtime、workflow、imports、project config）共享相同的解析行为和错误结构。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-unified-loader

  @req:r129 @human
  场景: YAML load MUST be centralized behind a single facade
    - 系统 MUST 提供一个统一的 YAML load facade,并要求 DSL 的所有入口复用该 facade(至少覆盖: CLI validate、compile/run、workflow validate、imports fragments、project config)。 该 facade 至少 MUST 支持： - 使用 vendored `ruamel.yaml` 作为唯一解析实现,并显式启用 YAML 1.2 语义边界 - duplicate key 检测（默认启用） - location index 构建（用于行列定位） - 统一的结构化错误输出（见 ErrorEnvelope 要求） - 对底层 parser API 的封装,使业务层不直接依赖 `PyYAML` / `ruamel.yaml` 的顶层符号或节点类型

  @req:r371 @human
  场景: YAML parse errors MUST use a stable ErrorEnvelope
    - 系统 MUST 以可机器消费的稳定结构表达 YAML parse/validate 错误（ErrorEnvelope）. ErrorEnvelope 至少 MUST 包含： - `code`（短码） - `message` - `source_path`（文件路径或逻辑来源） - `loc`（行/列,若可得） - `path`（YAML 路径,若可得）
  @req:r129 @human
  场景: cli-and-runtime-share-identical-parse-behavior
    - 必须成立：当 同一份 YAML 文本在 CLI validate 与 runtime compile/run 被解析；那么 两者对 duplicate key 的处理 MUST 一致
    当 同一份 YAML 文本在 CLI validate 与 runtime compile/run 被解析
    那么 两者对 duplicate key 的处理 MUST 一致

  @req:r129 @human
  场景: all-entry-points-use-the-ruamel-based-facade
    - 必须成立：当 demand/workflow/CLI/imports/project-config 等入口解析 YAML 文本；那么 这些入口 MUST 仅通过统一 facade 完成解析
    当 demand/workflow/CLI/imports/project-config 等入口解析 YAML 文本
    那么 这些入口 MUST 仅通过统一 facade 完成解析
  @req:r371 @human
  场景: errors-contain-location-without-leaking-sensitive-values
    - 必须成立：当 YAML parse 失败；那么 错误 MUST 包含 `source_path` 与 `loc`
    当 YAML parse 失败
    那么 错误 MUST 包含 `source_path` 与 `loc`
