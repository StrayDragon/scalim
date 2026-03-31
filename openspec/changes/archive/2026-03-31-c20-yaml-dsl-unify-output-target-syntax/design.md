## Context

当前输出 DSL 同时维护两条 authoring path:

- CSV: `outputs[*].container`
- books: `resources.books` + `outputs[*].to` / `outputs[*].write`

这不只是文法不一致,而是带来整条链路的重复分支:

- schema DSL / generated schema
- loader / validator / runtime overrides
- output composition / workflow compile / validate
- docs / examples / skills

同时,近期 books 侧已经逐步收敛到 `to/write` 语义,继续保留 `container` 只会让未来新增目的地时继续复制第三套/第四套 surface。

约束:

- 运行时核心代码必须兼容 Python 3.6
- `.gen.*` 与 injected blocks 不能手改,必须通过生成入口刷新
- 本仓库已明确接受破坏性 DSL 收敛,不需要保留旧写法兼容层

## Goals / Non-Goals

**Goals:**

- 把 output authoring surface 统一为 `resources + to + write`
- 为 CSV 提供与 books 对称的资源入口 `resources.files`
- 让 `overrides.outputs`、workflow validate/compile、runtime output composition 共用同一套输出模型
- 删除 `outputs[*].container` 并提供明确迁移路径与 fail-fast 诊断
- 明确 SSOT 与生成边界:
  - 手工修改: `openspec/specs/**`、`src/scalim/dsl/by_yaml/schema_dsl/**`、相关 loader/runtime/docs SSOT
  - 生成物: `src/scalim/dsl/by_yaml/schema/*.gen.json`、`docs/doc/**/*.gen.md`
  - 生成入口: `just gen-docs`、`uv run python scripts/gen-yaml-dsl-schema.py`

**Non-Goals:**

- 不引入泛化的“任意 sink 资源系统”; 本次仅新增 `resources.files` 且仅覆盖 CSV
- 不为旧 `container` 提供兼容解析、自动迁移或 silent fallback
- 不重做 books 的 append/sheet 行为模型; 仅把 CSV 收敛到同一 target model
- 不在 `resources.books.write_defaults` 中新增通用 header 选项; 该处继续只承载 book 专属写入语义

## Decisions

### 1. 引入 `resources.files`，并将 CSV 绑定迁移到 `to.file`

新增资源面:

- `resources.files.<file_id>`
- v1 仅支持 `kind=csv_file`

资源属性:

- `path`: 必填,支持字符串或 `{$init_var: ...}`
- `encoding`: 可选,默认 `utf-8`

输出绑定改为:

- `outputs[*].to.file`

理由:

- `path` / `encoding` 本质上是资源属性,不是 write policy
- `to.file` 与 `to.book` 对称,能把“写到哪里”与“怎么写”清晰分层

替代方案:

- 继续保留 `container` 给 CSV: 否决,会永久保留双模型
- 直接把 `path/encoding` 塞进 `write`: 否决,语义层级错误

### 2. `outputs[*].to` 成为目标绑定的唯一入口

统一后的 `to` 规则:

- 必须且只能声明一个目标:
  - `to.file`
  - `to.book`
- `to.sheet` 仅允许与 `to.book` 同时出现
- `outputs[*].container` 完全移除并 fail-fast

理由:

- 目标绑定是 destination 选择,必须集中在 `to`
- exact-one-of 规则能避免 file/book 双绑定或无绑定的歧义

### 3. `outputs[*].write` 承载通用写入策略，book 专属字段继续保留

统一后的 `write` 分层:

- 通用字段:
  - `include_header`
  - `header_fields_output_by`
- book 专属字段:
  - `mode`
  - `align_by`
  - `header_policy`
  - `on_mismatch`
  - `on_conflict`

语义约束:

- `write.include_header` 对 file 输出生效
- `write.include_header` 对 `book + mode=sheet` 生效
- `book + mode=append` 仍以 `header_policy` 为准; 此时 `include_header` 若显式出现则 fail-fast,避免双重语义
- `write.header_fields_output_by` 对 file/book 都生效,默认 `name`

理由:

- `header_fields_output_by` 是用户关心的跨目标一致策略,应统一
- append 已有稳定 header policy,不应与 `include_header` 重叠

### 4. `resources.books.write_defaults` 仅保留 book 专属默认值

保留:

- `mode`
- `align_by`
- `header_policy`
- `on_mismatch`
- `on_conflict`

不新增:

- `include_header`
- `header_fields_output_by`

理由:

- 通用 header 选项若放入 book defaults,会再次制造“books 比 files 多一层通用默认语义”的不对称
- 之前已经确认该入口不希望开放,本 change 维持这一收口

### 5. runtime / workflow / validate 使用同一套 effective target 归一化规则

统一后的编译思路:

- loader/parser 先把 YAML/overrides 解析成统一 target config
- runtime compiler / output composition / workflow compile 都从该统一模型推导 effective output target
- unique display name 校验按统一规则触发:
  - file: `write.include_header=true` 且 `write.header_fields_output_by=name`
  - book:
    - `mode=sheet` 且 `include_header=true` 且 `header_fields_output_by=name`
    - `mode=append` 且 header 会被输出(`header_policy!=never`) 且 `header_fields_output_by=name`

理由:

- 若 validate/runtime/workflow 仍各自复制判断条件,后续非常容易再次漂移

## Risks / Trade-offs

- [BREAKING] 旧 CSV YAML 全部需要迁移到 `resources.files + to.file` → 缓解: 统一 fail-fast 文案,并在 proposal/spec/tasks 中明确迁移模板
- [Scope] 该变更会触及 schema、runtime、workflow、docs、skills 多个区域 → 缓解: 以 capability 增量 spec 驱动,并要求 drift gates
- [Semantic overlap] `include_header` 与 books `append.header_policy` 容易冲突 → 缓解: 在 design 中明确 `append` 禁止显式 `include_header`
- [Workflow impact] workflow validate / write-node 推导需同步认识 `to.file` → 缓解: 将其作为独立 modified capability 写入 specs 与 tasks

## Migration Plan

1. authoring 迁移
   - 删除 `outputs[*].container`
   - 为 CSV 新增 `resources.files.<id>`
   - 将 CSV output 改写为 `to.file + write`
   - books 保持 `to.book + write`

2. 代码迁移
   - 先扩展 schema_dsl / models / keys
   - 再切 loader / validator / runtime compiler
   - 最后切 workflow compile/validate 与文档示例

3. 生成与门禁
   - 运行 `uv run python scripts/gen-yaml-dsl-schema.py`
   - 运行 `just gen-docs`
   - 运行 `just openspec-check`
   - 运行针对性 pytest,最终过 `just qa`

## Open Questions

- (none)
