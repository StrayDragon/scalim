## Context

当前 YAML DSL 的 `lookup_cast` 为扁平对象结构：

- `lookup_cast: {name: auto|int|str|sep_first, sep?: ","}`

这一结构在 authoring 阶段不够“自描述”，并且会产生一个明显的脚枪：

- `sep` 只对 `sep_first` 有意义，但在语法上对任意 `name` 都是合法字段；
- 当前 runtime validator 仅校验 `name` 是否在枚举中（未对 `sep` 做条件约束），因此错误会被延迟到更后面的阶段暴露。

同时，`lookup_cast` 既用于：

- `sources.*.lookup_cast`：定义 loader 返回映射的 key space 的 canonical cast（落到 `KeyIr.cast`）
- `relations.*.steps[*].lookup_cast`：在关联/lookup 前对上游 `from` 值做 cast（step 级优先）

本变更只调整 YAML authoring surface 与 schema/validator 的约束表达；IR 结构与运行期 cast 语义保持不变。

约束：

- 破坏性升级：不做兼容层，不再支持旧写法 `lookup_cast: {name: ...}`。
- 运行期需保持 Python 3.6 兼容（`src/scalim/`）。
- 文档/Schema 生成物不得手工修改：`.gen.` / `BEGIN/END AUTOGEN` / `docs/site/**` 均需通过生成入口刷新。

## Goals / Non-Goals

**Goals:**

- 将 `lookup_cast` 改为 one-of 分支结构，保证“同一个节点上只能选择一种 cast”，并把参数约束前置到 schema/validator：
  - `lookup_cast: {auto: {}}`
  - `lookup_cast: {int: {}}`
  - `lookup_cast: {str: {}}`
  - `lookup_cast: {sep_first: {sep: ","}}`（`sep` 可省略，默认 `","`）
- schema-only（JSON Schema）与 runtime validator 同步表达约束：`sep` 仅允许出现在 `sep_first` 分支。
- 解析/编译产物保持不变：最终仍生成 `LookupCastSpecIr(name, sep)`，运行期 cast registry 与 `lookup_cast_id` 不变。
- 升级全部内置文档、示例与测试到新语法，并提供清晰的迁移报错信息。

**Non-Goals:**

- 不改变任何 cast 的运行期语义（`auto/int/str/sep_first` 行为保持一致；`auto` 仍拒绝 float lookup key）。
- 不新增 cast 类型、不更名 `lookup_cast` 概念、不引入 `dsl_version` 或并行 parser。
- 不在本变更中系统性重构其它配置对象；仅做一次轻量审视并记录结论（例如 `normalize` 已具备较强的 one-of/互斥约束）。

## Decisions

### Decision: keep outer key `lookup_cast`, switch inner shape to one-of keyed object

选择：

- 保持概念名 `lookup_cast`（与现有 docs/IR/代码路径对齐）。
- 将内部从 `{name, ...}` 改为 one-of 分支键对象 `{auto|int|str|sep_first: {...}}`。

理由：

- 直接把“选择哪种 cast”变成 YAML 结构（可读性更强），并天然支持“互斥 + 分支参数”。
- `sep` 仅在 `sep_first` 分支存在，schema 与 IDE hover 能更准确地提示与报错。
- 避免 `as_int/as_str` 这类重复前缀（外层已叫 `lookup_cast`），降低冗余心智。

备选方案：

- 继续 `{name: ..., sep?: ...}`，只在 validator 增加条件检查：能解决延迟报错，但 IDE/schema 补全与 hover 仍不直觉。
- 使用 `lookup_cast: {name: sep_first, params: {sep: ","}}`：结构更统一但更啰嗦，且仍需要额外的互斥约束。

### Decision: schema MUST fail-fast, validator adds a targeted migration hint for legacy shape

即使 schema-only 已会因 `oneOf` 失败而报错，运行期 validator 仍应在检测到旧形态 `{name: ...}` 时给出更直接的迁移提示（包含可照抄的替换片段）。

理由：

- 用户最常见的迁移路径就是“照着旧文档写”，纯 `oneOf` 报错通常不够可读。
- validator 是最终 fail-fast 边界，提供更精确的错误路径与建议可减少排障时间。

### Decision: do a quick audit for similar footguns; no refactor for `normalize`

结论（当前仓库实现现状）：

- `normalize` 已通过 schema 的 `allOf + oneOf + not` 组合表达“kind 与字段互斥/必填”规则，属于较直觉与 fail-fast 的结构；本变更不额外改动它。
- `lookup_cast` 是目前最明显的“扁平结构 + 分支参数”的脚枪点，优先修复。

## Risks / Trade-offs

- [BREAKING] 旧 YAML 将无法通过校验 → 提供明确的 validator 迁移提示，并同步升级文档/fixtures 降低迁移成本。
- [Drift risk] schema 生成物/站点输出易漂移 → 在实现中明确 SSOT 边界，并通过既有 `just gen-yaml-dsl-schema` / `just gen-docs` / `just qa` 门禁兜底。
- [Surface area] 变更涉及 schema_dsl、解析器、校验器、docs、tests → 拆分为“SSOT 修改 → 生成物刷新 → fixtures/tests 升级”顺序实施，降低回归风险。

## Migration Plan

1. 修改 schema SSOT（`LOOKUP_CAST_SCHEMA` + 相关描述文案）并更新 runtime validator/解析器到新语法。
2. 为旧写法 `lookup_cast: {name: ...}` 增加显式错误与可复制的迁移建议。
3. 升级 docs 与所有示例/fixtures 为新语法。
4. 运行生成入口刷新生成物（schema 与 docs site）。
5. 跑 `just qa` / `just openspec-check` 验证无漂移、无回归。
