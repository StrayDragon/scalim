# language: zh-CN
# capability: yaml-dsl-file-resources
# purpose: 定义 demand/workflow 统一的 `resources.files` 文件输出资源入口,并约束 CSV 输出通过 `outputs[*].to.file` + `outputs[*].write` 绑定,取代 legacy `outputs[*].container`. [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-dsl-file-resources

  @req:r113 @human
  场景: demand and workflow YAML MUST support `resources.files` as the unified file-outp
    - 系统 MUST 提供 `resources.files` 作为非 book 文件输出的统一资源入口,并在 demand/workflow 两类 YAML 中保持一致: - demand: `resources.files.<file_id>` - workflow: `workflow.resources.files.<file_id>` 约束: - `<file_id>` MUST 为非空字符串且在同一 mapping 内唯一 - `resources.files.<file_id>` MUST 为 mapping - v1 仅允许 `csv_file: <mapping>` 分支写法 - `resources.files.<file_id>.csv_file.path` MUST 为非空字符串或 `{$init_var: <name>}` - `resources.files.<file_id>.csv_file.encoding` MAY 存在且 MUST 为非空字符串(默认 `utf-8`) - `resources.files.<file_id>.csv_file.path` 语义 MUST 为 **输出 root 目录**（版本化输出 D-2），而不是最终文件路径 - 相对路径 MUST 以声明该资源的 YAML 文件所在目录为基准解析 - 系统 MUST 基于 `file_id` 与 `version_id` 推导最终输出路径： - final path MUST 等价于 `<root>/versions/<version_id>/files/<file_id>.csv` - legacy `write_lock` 配置面 MUST 被移除；若用户仍提供该字段，系统 MUST fail-fast 并给出迁移提示 其中 `version_id` 取值约束： - standalone demand: `version_id` MUST 等于该 demand 的 `run_id` - workflow: `version_id` MUST 等于该 workflow 的 `workflow_exec_id` legacy `kind` discriminator MUST 被移除；若用户仍声明 `resources.files.<file_id>.kind`，系统 MUST fail-fast 并给出迁移提示（迁移到 `resources.files.<file_id>.csv_file: {...}` 分支写法）。 （demand-only）imports 支持： - demand YAML MAY 在 `resources.files.<file_id>` 节点级声明 `$import`（导入整个资源节点 mapping） - demand YAML MAY 在 `resources.files.<file_id>.csv_file` 分支级声明 `$import` - 当 `$import` 与本地键并存时，imports expansion MUST 以“导入值为 defaults、本地覆盖导入值”的语义合并 - workflow YAML MUST NOT 支持 `imports`/`$import`（schema 与 runtime 均 fail-fast）

  @req:r355 @human
  场景: temp-path creation for atomic file writes MUST mitigate TOCTOU in untrusted outp
    - 当系统需要为文件输出执行 “temp+replace” 原子写入时(例如 CSV/Excel 文件落盘),系统 MUST 降低在不可信输出目录中的 TOCTOU(time-of-check to time-of-use) 可利用性: - 系统 MUST 将临时文件放置在目标输出目录下的“私有临时目录”中(同文件系统/同父目录层级,保证后续 replace 原子性) - 私有临时目录 MUST 尽可能收紧权限,使其他用户/进程无法进入该目录替换临时文件条目(例如仅当前用户可访问) - 系统 MUST 允许第三方库按 path 写入临时文件(不强制要求 fd 写入),并在写入完成后以原子方式 replace 到最终输出路径 - 系统 SHOULD 在 replace 后对私有临时目录进行 best-effort 清理,避免长期残留

  @req:r476 @human
  场景: CSV outputs MUST bind via `outputs[*].to.file` and `outputs[*].write`
    - 系统 MUST 要求 CSV 输出通过统一 target model 绑定: - `outputs[*].to.file` MUST 为非空字符串 - `outputs[*].write.include_header` MAY 存在,默认 `true` - `outputs[*].write.header_fields_output_by` MAY 存在,默认 `name` - CSV 输出 MUST NOT 再使用 `outputs[*].container`

  @req:r559 @human
  场景: standalone demand MUST fail-fast when a referenced file resource is missing
    - 系统 MUST 在 standalone `compile/run` 中校验所有 `outputs[*].to.file` 的资源存在性: - 若 `to.file` 引用的 `resources.files.<id>` 缺失,系统 MUST fail-fast - 错误信息 MUST 包含缺失的 `file_id` - 错误信息 MUST 指向 `outputs[*].to.file` - 错误信息 MUST 提示在 YAML 或 overrides.resources.files 中补齐资源

  @req:r623 @human
  场景: workflow MUST merge `resources.files` with the same precedence model as books
    - 系统 MUST 对 `files` 资源采用与 `books` 相同的 merge precedence: 1. demand YAML 的 `resources.files` 2. workflow YAML 的 `workflow.resources.files` 3. Python overrides 的 `overrides.resources.files`
  @req:r113 @human
  场景: file-resource-passes-schema-validation
    - 必须成立：当 demand YAML 声明 `resources.files.detail.csv_file.path=./out`；那么 schema-only 校验 MUST 通过
    当 demand YAML 声明 `resources.files.detail.csv_file.path=./out`
    那么 schema-only 校验 MUST 通过

  @req:r113 @human
  场景: demand-node-level-import-passes-schema-only-validation
    - 必须成立：当 demand YAML 声明 `resources.files.detail.$import=common.resources.files.detail`；那么 schema-only 校验 MUST 通过
    当 demand YAML 声明 `resources.files.detail.$import=common.resources.files.detail`
    那么 schema-only 校验 MUST 通过

  @req:r113 @human
  场景: demand-branch-level-import-passes-schema-only-validation
    - 必须成立：当 demand YAML 声明 `resources.files.detail.csv_file.$import=common.resources.files.detail_csv_file`；那么 schema-only 校验 MUST 通过
    当 demand YAML 声明 `resources.files.detail.csv_file.$import=common.resources.files.detail_csv_file`
    那么 schema-only 校验 MUST 通过

  @req:r113 @human
  场景: legacy-kind-discriminator-is-rejected-with-migration-hint
    - 必须成立：当 用户仍声明 `resources.files.detail.kind=csv_file`；那么 schema-only 与 runtime 校验 MUST fail-fast
    当 用户仍声明 `resources.files.detail.kind=csv_file`
    那么 schema-only 与 runtime 校验 MUST fail-fast
  @req:r355 @human
  场景: temp-path-resides-in-a-private-directory-under-output-dir
    - 必须成立：假如 输出路径为 `/out/report.csv`；当 系统为该输出创建临时路径；那么 临时路径 MUST 位于 `/out/` 下的私有临时目录内(例如 `/out/.scalim-tmp-*/...`)
    假如 输出路径为 `/out/report.csv`
    当 系统为该输出创建临时路径
    那么 临时路径 MUST 位于 `/out/` 下的私有临时目录内(例如 `/out/.scalim-tmp-*/...`)

  @req:r355 @human
  场景: replace-remains-atomic-and-final-path-is-unchanged
    - 必须成立：假如 系统采用私有临时目录策略；当 临时文件写入完成并提交到最终输出路径；那么 系统 MUST 以原子 replace 的方式生成最终文件
    假如 系统采用私有临时目录策略
    当 临时文件写入完成并提交到最终输出路径
    那么 系统 MUST 以原子 replace 的方式生成最终文件
  @req:r476 @human
  场景: csv-output-binds-through-to-file
    - 必须成立：当 output 声明 `to.file=detail_csv`；那么 该 output MUST 绑定到对应文件资源
    当 output 声明 `to.file=detail_csv`
    那么 该 output MUST 绑定到对应文件资源
  @req:r559 @human
  场景: missing-file-resource-fails-fast
    - 必须成立：假如 output 声明 `to.file: detail_csv`；当 调用方执行 standalone compile/run；那么 系统 MUST fail-fast
    假如 output 声明 `to.file: detail_csv`
    当 调用方执行 standalone compile/run
    那么 系统 MUST fail-fast
  @req:r623 @human
  场景: workflow-overrides-demand-file-path
    - 必须成立：假如 demand 声明 `resources.files.detail: {csv_file: {path: ./out/a}}`；当 workflow 运行该 demand；那么 effective file path MUST 等于 workflow 声明值
    假如 demand 声明 `resources.files.detail: {csv_file: {path: ./out/a}}`
    当 workflow 运行该 demand
    那么 effective file path MUST 等于 workflow 声明值
