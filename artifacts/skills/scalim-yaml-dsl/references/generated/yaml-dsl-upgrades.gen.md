# YAML DSL Upgrades (Generated)

此文档由 `scripts/gen-agent-skill.py` 自动生成,来源: `references/upgrades/`。
用于在使用 skill 时快速定位 breaking/migration,避免在多处重复维护易变规则。

## 2026-03-10: yaml-field-extract
- SSOT: `references/upgrades/2026-03-10-yaml-field-extract.md`
- OpenSpec: `openspec/changes/archive/2026-03-10-yaml-field-extract/`
- Spec: `openspec/specs/yaml-field-extract/spec.md`
- Summary:
  这次升级把“源字段如何从 loader 返回的 row value 里取值”统一收敛到一个入口: `extract`。
  - `main_source.fields.*` / `sources.*.fields.*` 中，历史 `field: ...` **不再允许**（出现即 fail-fast）
  - `extract: <expr>` 成为**唯一**字段取值写法（包含 rename 与 nested 取值）
  - `extract` 支持 `dot + bracket` 路径表达式，覆盖嵌套 dict、dotted literal key、int key 场景
  - 明确 **不做** `"1" ↔ 1` 隐式 cast，避免歧义
  - 明确 **不支持** list/tuple 下标（`[1]` 永远表示 key=1，而不是 list index）
  OpenSpec 归档变更（含 proposal/design/spec/tasks）:
  - `openspec/changes/archive/2026-03-10-yaml-field-extract/`
  对应主规范:
  - `openspec/specs/yaml-field-extract/spec.md`

## 2026-03-10: yaml-source-normalize
- SSOT: `references/upgrades/2026-03-10-yaml-source-normalize.md`
- OpenSpec: `openspec/changes/archive/2026-03-10-yaml-source-normalize/`
- Spec: `openspec/specs/demand-dsl/spec.md`
- Summary:
  这次升级为 lookup `sources.*` 引入源代码级 `normalize`,用于在字段级 `extract` 之前对 `loader` 的整体返回值做一次整体结果归一化。
  - 新增 `sources.<id>.normalize`(显式拒绝 `main_source.normalize`)
  - 支持 `normalize.kind: index_by_key`:把 `list[row]` 归一化为 `key -> row`
  - `on_conflict` 默认 `error`,也可用 `first/last` 显式声明冲突策略
  - 归一化发生在 `extract` 之前;`extract` 仍然只负责从“单条 row value”里取字段
  OpenSpec 归档变更(含 proposal/design/spec/tasks):
  - `openspec/changes/archive/2026-03-10-yaml-source-normalize/`
  对应主规范:
  - `openspec/specs/demand-dsl/spec.md`
  - `openspec/specs/source-cache/spec.md`
  - `openspec/specs/yaml-dsl-schema/spec.md`
  - `openspec/specs/yaml-dsl-editor-core/spec.md`
  - `openspec/specs/yaml-dsl-agent-guidance/spec.md`

## 2026-03-11: yaml-params-template
- SSOT: `references/upgrades/2026-03-11-yaml-params-template.md`
- OpenSpec: `openspec/changes/archive/2026-03-11-yaml-inline-dynamic-params/`
- Spec: `openspec/specs/demand-dsl/spec.md`
- Summary:
  这次升级把 loader 的调用参数语义收敛到一个入口: `params` kwargs 模板(支持在任意嵌套位置注入运行时值),并引入 `runtime_vars` 作为编译期注入来源。
  - `main_source.params` / `sources.<id>.params` 统一视为“kwargs 模板”
  - 新增模板指令节点:
  - `{$keys: {as: set|list}}`: 注入 lookup keys
  - `{$rows: {cache_mode: batch|none}}`: 注入 batch rows(并影响调度与复用语义)
  - 新增 `runtime_vars` 注入与 `{$runtime: <name>}` 指令节点(编译期解析;不做子串插值)
  - **BREAKING**: `bind` / `to_bind` 已从稳定 YAML authoring surface 移除(出现即 fail-fast)
  - **BREAKING**: `cache_mode: preload_forever` 的预加载语义收敛:
  - 若 `sources.<id>.params` 非空: 预加载透传渲染后的 kwargs
  - 若为空: 预加载保持零参调用
  OpenSpec 归档变更（含 proposal/design/spec/tasks）:
  - `openspec/changes/archive/2026-03-11-yaml-inline-dynamic-params/`
  - `openspec/changes/archive/2026-03-11-yaml-loader-params-template/`
  对应主规范(节选):
  - `openspec/specs/demand-dsl/spec.md`
  - `openspec/specs/source-relations/spec.md`

## 2026-03-13: demand-dsl-breaking
- SSOT: `references/upgrades/2026-03-13-demand-dsl-breaking.md`
- OpenSpec: `openspec/changes/archive/2026-03-12-yaml-dsl-micro-tunes/`
- Spec: `openspec/specs/demand-dsl/spec.md`
- Summary:
  本批次聚焦 YAML DSL 的几处语法收敛与可用性改良:
  - `relation` 支持 string ref: `relation: <relation_id>` 引用 `relations.<relation_id>`
  - `output.fields` 支持 string sugar:
  - `field_id` (例: `order_id`)
  - `source.field_id` (例: `customers.customer_name`;用于消歧;仅支持二段式)
  - **BREAKING**: runtime vars 统一为指令节点 `{$runtime: <name>}`;旧写法 `$runtime.<name>` 不再允许
  OpenSpec 归档变更（含 proposal/design/spec/tasks）:
  - `openspec/changes/archive/2026-03-12-yaml-dsl-micro-tunes/`
  对应主规范(节选):
  - `openspec/specs/demand-dsl/spec.md`
  - `openspec/specs/yaml-dsl-schema/spec.md`
  - `openspec/specs/yaml-runtime-vars/spec.md`
  - `openspec/specs/source-relations/spec.md`
  - `openspec/specs/yaml-dsl-micro-tunes/spec.md`
  下游同步盘点:
  - 仅用于盘点与行动: `.tmp/known-outer-paths-using-this-package.txt`（请勿在公开输出中复述其内容）
- Migration:
  1) 全量把 `$runtime.<name>` 占位符替换为 `{$runtime: <name>}`
  2) (可选) 将字段的 `relation: *anchor` 升级为 `relation: <relation_id>`
  3) (可选) 将 `output.fields` 的简单场景升级为 string list sugar

## 2026-03-13: derived-outputs-set-aggregations
- SSOT: `references/upgrades/2026-03-13-derived-outputs-set-aggregations.md`
- OpenSpec: `openspec/changes/archive/2026-03-13-derived-outputs-set-aggregations/`
- Spec: `openspec/specs/derived-outputs/spec.md`
- Summary:
  - 新增内置 metric op:
  - `count_distinct`(支持单字段与复合 key; `None` 按 SQL `COUNT(DISTINCT)` 语义忽略)
  - `count_true_gte(field_id, threshold)`(用于最小条件计数,覆盖 `repeat_paid_users`)
  - 扩展派生聚合装配 spec(用于 `output_composition.derived_targets`):
  - `DerivedGroupBySpec` 新增 `max_distinct` 与 `distinct_on_overflow=error|truncate`
  - 新增 `DedupBySpec` + `DerivedDedupByGroupBySpec`
  - 新增 `TwoStageGroupBySpec`(stage1 finalize → stage2 accumulate)
  - `parallel_mode="adaptive"` 一致性边界:
  - `dedup_by.on_conflict=first|last` 属于顺序依赖语义,在 `adaptive` 下会 fail-fast(建议切 `seq` 或改 `on_conflict=error`)
  - 诊断输出:
  - meta sheet 写入 `derived.<target_id>.fingerprint` 等对拍友好的稳定诊断字段
  - audit sheet 会额外记录截断等结构化审计行(不包含明细/聚合 key 具体值)
- Migration:
  - 若你仅使用基础 `group_by` + `count/sum/min/max/count_true`,不需要改动。
  - 若需要 distinct/去重/两阶段口径:
  - 优先设置合理的 `max_distinct` 与 `distinct_on_overflow`/`on_overflow`
  - 若必须使用 `first/last`,确保运行在 `parallel_mode="seq"` 以保持确定性与可对拍。

## 2026-03-13: yaml-dsl-outputs
- SSOT: `references/upgrades/2026-03-13-yaml-dsl-outputs.md`
- OpenSpec: `openspec/changes/archive/2026-03-13-yaml-dsl-outputs/`
- Spec: `openspec/specs/yaml-dsl-schema/spec.md`
- Summary:
  本批次将执行层既有能力(`output-composition` / `derived-outputs`)暴露为 YAML authoring surface:
  - demand YAML 顶层新增 `outputs`(有序列表): 支持同一次运行写入同一 workbook 的多 sheet
  - `outputs.*.where`: 安全表达式分发过滤(编译期静态分析依赖字段并注入 required fields)
  - `outputs.*.aggregate`: 派生汇总输出(同一次运行内产出汇总 sheet)
  - 顶层 `meta` / `audit`: 一键开启对拍友好产物
  - 顶层 `failure_policy` / `include_full_error_message`: 对齐 composed outputs 失败策略与错误信息脱敏
  OpenSpec 归档变更（含 proposal/design/spec/tasks）:
  - `openspec/changes/archive/2026-03-13-yaml-dsl-outputs/`
  对应主规范(节选):
  - `openspec/specs/yaml-dsl-schema/spec.md`
  - `openspec/specs/output-composition/spec.md`
  - `openspec/specs/derived-outputs/spec.md`
  下游同步盘点:
  - 仅用于盘点与行动: `.tmp/known-outer-paths-using-this-package.txt`（请勿在公开输出中复述其内容）
- Migration:
  1) 将所有顶层 `output:` 升级为 `outputs:`(list)
  2) 将旧 `output.*` 的输出策略迁移到 `outputs.*.container.*`
  3) 将旧 `output.fields` 重写为 `outputs.*.fields: [field_id, ...]`
  4) 若存在重复 `field_id`,先在 YAML 中重命名(必要时用 `extract` 指向真实 data_key)
  5) 多 sheet 分发:
  - 增加多个 outputs
  - 用 `where` 表达式区分
  - 共享 workbook 时为每个 output 显式设置 `container.sheet` 并建议开启 `write_lock: true`
  6) 需要汇总 sheet 时,新增一个带 `aggregate` 的 output
  7) (可选) 启用 `meta: true` / `audit: true` 以输出对拍信息

## 2026-03-13: yaml-reuse-workflow
- SSOT: `references/upgrades/2026-03-13-yaml-reuse-workflow.md`
- OpenSpec: `openspec/changes/archive/2026-03-13-yaml-dsl-imports/`
- Spec: `openspec/specs/yaml-dsl-imports/spec.md`
- Summary:
  本批次聚焦 YAML DSL 的“复用与编排”能力:
  - demand YAML 新增跨文件复用: 顶层 `imports` + 任意 mapping 内 `$import`(编译期展开)
  - 新增 workflow YAML + Python 入口 `scalim.dsl.by_yaml.run_workflow(...)` 编排多个 demand
  - workflow 可选启用 `share_preload_cache`: 跨 runs 共享 `cache_mode: preload_forever` 的预加载结果,并在启动前做规格冲突预检查
  OpenSpec 归档变更（含 proposal/design/spec/tasks）:
  - `openspec/changes/archive/2026-03-13-yaml-dsl-imports/`
  - `openspec/changes/archive/2026-03-13-yaml-dsl-workflow/`
  对应主规范(节选):
  - `openspec/specs/yaml-dsl-imports/spec.md`
  - `openspec/specs/yaml-dsl-workflow/spec.md`
  - `openspec/specs/yaml-dsl-schema/spec.md`
  - `openspec/specs/yaml-dsl-cli-validation/spec.md`
  - `openspec/specs/yaml-dsl-editor-core/spec.md`
  - `openspec/specs/source-cache/spec.md`
  下游同步盘点:
  - 仅用于盘点与行动: `.tmp/known-outer-paths-using-this-package.txt`（请勿在公开输出中复述其内容）
- Migration:
  1) (可选) 将重复的 mapping 片段抽到同级 fragment YAML,在主文件用 `imports/$import` 复用
  2) 确保所有使用 `imports/$import` 的场景都走“文件路径入口”(不要走纯文本入口)
  3) 需要多 demand 编排时,新增 workflow YAML 并从 Python 调用 `run_workflow(...)`
  4) 若启用 `share_preload_cache=true`,确保同一 `source_id` 的 preload 规格在所有 runs 中一致

## 2026-03-13: yaml-source-normalize-shapes
- SSOT: `references/upgrades/2026-03-13-yaml-source-normalize-shapes.md`
- OpenSpec: `openspec/changes/archive/2026-03-12-yaml-source-normalize-shapes/`
- Spec: `openspec/specs/yaml-source-normalize/spec.md`
- Summary:
  本批次扩展 `sources.<id>.normalize` 的声明式能力,用于减少“lookup 小表/维表”场景的 Python wrapper:
  - 新增 `normalize.kind: take_first`
  - 新增 `normalize.kind: project_fields`
  - 新增 `normalize.kind: map_values`(values pipeline)
  - 新增受控扩展点 `normalize.call_by`(whole-result `Mapping -> Mapping`,受 allowlist 约束)
  OpenSpec 归档变更（含 proposal/design/spec/tasks）:
  - `openspec/changes/archive/2026-03-12-yaml-source-normalize-shapes/`
  对应主规范(节选):
  - `openspec/specs/yaml-source-normalize/spec.md`
  - `openspec/specs/yaml-dsl-schema/spec.md`
  下游同步盘点:
  - 仅用于盘点与行动: `.tmp/known-outer-paths-using-this-package.txt`（请勿在公开输出中复述其内容）
- Migration:
  1) 识别 wrapper 形状:
  - `mapping[key -> list[row]]` → 优先用 `take_first`/`map_values`
  - `mapping[key -> nested_dict]` → 优先用 `project_fields`
  2) 若业务存在 int/enum key 的 nested dict,用 bracket path 表达(例如 `"[1].x"`)
  3) 只有在 declarative normalize 无法表达且不想引入 wrapper module 时,再使用 `normalize.call_by`
