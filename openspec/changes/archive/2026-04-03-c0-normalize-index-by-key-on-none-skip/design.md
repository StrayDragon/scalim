## Context

当前 `normalize.kind=index_by_key` 在遍历 loader 返回的 `list[row]` 时,一旦遇到 `key_field` 存在但值为 `None` 的 row 就会 fail-fast。
在真实数据(占位行/不完整回填/上游脏数据)中这很常见,导致用户不得不在每个使用点分散地手写过滤逻辑(例如 `where`/自定义 `call_by`),难以审计且容易漏掉。

本变更引入一个显式策略开关 `normalize.on_none: skip` 用于收敛“遇到 `None` key 如何处理”的决策到 source 层一次完成。

## Goals / Non-Goals

**Goals:**
- 为 `normalize.kind=index_by_key` 增加 `on_none` 策略: `raise|skip`,默认 `raise`(保持现有行为)
- `on_none=skip` 时,仅跳过 `key_field` 存在且值为 `None` 的 row,并继续处理其它 row
- 在 schema/validator 层提供明确的约束与错误信息: `on_none` 仅在 `index_by_key` 下允许

**Non-Goals:**
- 不改变 `key_field` 缺失(KeyError)的 fail-fast 边界
- 不改变 `key_field` 值非 hashable(TypeError)的 fail-fast 边界
- 不为其它 normalize kind 增加或复用 `on_none`(避免静默无效配置)
- 不支持 composite key 的 `index_by_key`

## Decisions

### 1) 配置形态与默认值

- `normalize.on_none` 作为 `normalize.kind=index_by_key` 的可选字段。
- 取值:
  - `raise`: 遇到 `key_field is None` fail-fast (默认)
  - `skip`: 遇到 `key_field is None` 跳过该 row

这样既保持默认行为不变,也让“吞掉 row”成为显式 opt-in。

### 2) 约束分层: schema + validator 双重保障

- **Schema (JSON Schema / hover)**: 负责编辑器体验与 schema-only 校验,并且尽可能表达:
  - 仅当 `normalize.kind=index_by_key` 时允许 `normalize.on_none`
  - `normalize.on_none` 的枚举值为 `raise|skip`
- **运行时 validator**: 负责最终权威校验与错误信息质量,必须在 schema 表达不足或被绕过时仍能:
  - 拒绝非 `index_by_key` 下出现的 `on_none`
  - 在 fail-fast 时给出明确路径与修复建议(例如提示 `on_none=skip`)

### 3) 运行时语义: “None key” 只影响单条 row

实现侧将 `index_by_key` 的 loop/抽 key 逻辑扩展为:
- 若 row 缺失 `key_field`: 仍 fail-fast (KeyError)
- 若 `key_value is None`:
  - `on_none=raise`: fail-fast (现有行为)
  - `on_none=skip`: `continue` 跳过该 row
- 若 `key_value` 非 hashable: 仍 fail-fast (TypeError)
- 其它逻辑(如 duplicate key 的 `on_conflict`)保持不变

### 4) 生成物边界与 drift gate

本变更涉及 YAML schema/hover 的更新,相关 `*.gen.*` 文件为生成物,禁止手工编辑。
预期流程为:
- 修改 schema SSOT(例如 schema_dsl/models 下的模型与字段描述)
- 通过既有入口重新生成:
  - 优先使用 `just gen-docs` 刷新站内 injected blocks 与 `docs/doc/**/*.gen.md`
  - 并通过 repo 的质量门禁/漂移检查确保 `src/scalim/dsl/by_yaml/schema/*.gen.json` 等生成物同步
- 变更共享/发布前运行 `just openspec-check`

### 5) fail-fast 错误信息策略(可定位 + 可行动)

为降低排障成本,本变更将 `index_by_key` 相关 fail-fast 的错误信息统一为“可定位 + 可行动”的风格:

- 错误信息 MUST 至少包含:
  - `source_id`
  - `normalize.kind=index_by_key` 语境
  - `key_field` 名称
  - row 的 `index`(枚举序号)
  - 关键配置路径(例如 `sources.<id>.normalize.key_field` / `sources.<id>.normalize.on_none`)
- 对于 `key_field is None` 且 `on_none=raise` 的情况,错误信息 MUST 明确建议用户改用 `sources.<id>.normalize.on_none: skip`(显式 opt-in)
- 异常类型保持现有语义边界不变:
  - `key_field` 缺失仍为 `KeyError`
  - `key_field is None` 仍为 `ValueError`(当 `on_none=raise`)
  - `key_field` 值非 hashable 仍为 `TypeError`

> NOTE: 为避免泄露数据/扩大日志体积,错误信息不包含整条 row 内容,仅包含 index 与字段名等定位信息。

### 6) `on_none=skip` 的可观测性(跳过计数)

`on_none=skip` 是显式吞掉 row 的策略,需要提供“可审计”的观测信号,让用户能发现与统计被跳过的数量。

决策:

- 当 `normalize.kind=index_by_key` 且 `on_none=skip` 时,实现侧 MUST 统计本次 normalize 过程中因 `key_field is None` 而被跳过的 row 数量(`skipped_none_rows`)
- 该计数 MUST 作为执行事件的一部分可被捕获(用于 scalim-viz / hooks / 自定义 observers):
  - 优先将 `skipped_none_rows` 暴露在 `loader_call` 事件 payload 的可选字段中(而不是仅放在 `Event.meta`),
    以便现有 `EventDispatchObserver`(typed handlers) 也能读取到该信息
- 默认不额外输出 warning 日志,避免在高频 loader 调用场景造成噪音;需要时由订阅方决定如何展示/聚合

## Risks / Trade-offs

- [风险] `on_none=skip` 会吞掉部分 row,可能掩盖上游数据问题 → [缓解] 明确为 opt-in,并在文档/错误信息中强调语义
- [风险] schema 条件约束可能难以完全表达 → [缓解] validator 作为权威兜底,确保非 `index_by_key` 使用 `on_none` 时必定 fail-fast

## Migration Plan

- 实现:
  - 扩展 YAML 模型/解析层以承载 `normalize.on_none`
  - 更新 validator: 限定 `on_none` 仅用于 `index_by_key`
  - 更新转换与 IR normalize runtime: `skip` 仅跳过 `key_field is None` 的 row
  - 新增/更新测试覆盖: 默认 fail-fast 与 `skip` 行为 + schema/validator 约束
- 回滚:
  - 移除 `on_none` 字段与逻辑即可回到现有 fail-fast 行为(默认值不变使回滚风险低)
