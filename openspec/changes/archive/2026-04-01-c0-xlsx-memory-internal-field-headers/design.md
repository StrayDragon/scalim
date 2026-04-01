## Context

`xlsx_memory` 应当是 workflow 内部数据容器,但当前实现允许结果侧表头语义进入内部链路。用户可见的 `name` / 自定义 header 原本只应在写出 `csv` / `xlsx` / `export_xlsx` 时参与表头映射,不应影响内部索引、对齐、读取与关联。

本次变更采用一步到位的破坏性收紧:

- 内部链路只认 canonical field key
- `align_by=header` 对 `xlsx_memory` 非法
- display header 只属于结果侧导出元信息

当前运行时仍以 `field_id` 作为主要 canonical key,后续若引入自动推理等价物或唯一前缀形式(如 `source.field_id` / `demand.source.field_id`),也应视为同一类“内部 canonical key”问题,而不是 header 问题。

约束:

- Python 3.6 runtime 兼容
- 不扩大到值类型保留问题
- 不新增 DSL surface
- 不改变 `xlsx_file` / `csv_file` 的结果写出 header 语义

## Goals / Non-Goals

**Goals:**
- 明确 `xlsx_memory` 内部语义只允许 canonical field key
- 禁止 `xlsx_memory` 使用 `align_by=header`
- 保留 `export_xlsx` 的 display header 显示能力
- 将导出 header 元数据收敛到 `sheetbook` plan 内部结构
- 以最小实现面完成语义纯化,减少与进行中的其它 workflow change 交叉

**Non-Goals:**
- 不解决值类型字符串化或 typed-memory 设计
- 不引入新的 book kind
- 不修改全局 `DEFAULT_OUTPUT_HEADER_BY`
- 不让 display header 继续参与内部 append/mismatch 语义

## Decisions

### 1. `xlsx_memory` 内部只保留 canonical field key

`xlsx_memory` 的内部 header baseline、`book_sheet_rows` 返回键、sheetbook 内部 rows 对齐语义都只允许 canonical field key。当前实现上,这意味着使用 `field_id` 作为 SSOT。

这条规则适用于:

- workflow-managed artifact → sheetbook 写入
- sheetbook 内部存储
- `iter_sheetbook_sheet_rows` / `book_sheet_rows`
- append 对齐与 mismatch 检查

### 2. `align_by=header` 对 `xlsx_memory` 直接非法

既然 header 被定义为结果侧元信息,它就不再有资格参与内部数据容器的 append 对齐。对 `xlsx_memory`:

- 允许: `align_by=field_id`
- 禁止: `align_by=header`

推荐直接 fail-fast,而不是隐式降级或兼容别名。这样语义最清晰,迁移成本也一次性暴露。

### 3. 导出 header 元数据存放在 `sheetbook` plan 内部结构

导出 header 元数据不放到通用 `InMemoryCsv` artifact,也不放到 YAML DSL surface,而是仅放在 `sheetbook` plan 中:

- 内部 rows 仍只带 canonical field key
- `sheetbook` 在 commit/export 时读取导出 header metadata 渲染最终表头
- `book_sheet_rows` 永远不接触这类元数据

选择这一位置的原因:

- 它是 `xlsx_memory` 专属语义
- 不污染通用 workflow-managed artifact 契约
- 不需要在 compile 阶段把结果侧元信息提前下沉到更宽的 IR 面

### 4. 同一 sheet 的导出 header metadata 建立单一确定性基线

每个 `xlsx_memory` sheet 在首次写入时建立导出 header metadata baseline。后续写入:

- 可复用同一 baseline
- 不允许静默替换
- 若新写入需要不同导出 header,直接 fail-fast

这样可以避免导出结果随 segment 顺序漂移。

## Risks / Trade-offs

- [破坏性更改] → 任何依赖 `xlsx_memory + align_by=header` 的配置都会失败; 这是刻意暴露语义错误,迁移路径应改为 canonical field key
- [sheetbook plan 结构变复杂] → 增加导出 header metadata,但范围限定在 `xlsx_memory`
- [现有测试需整体改写] → 需要把原先“header 可参与内部对齐”的断言改成 fail-fast 断言
- [canonical key 未来可能扩展] → 本 change 先以当前 `field_id` 实现,规范文字使用 canonical key 保持前向兼容
- [类型丢失仍存在] → 明确延后,避免 scope 爆炸

## Migration Plan

1. 先修改 OpenSpec,明确 `xlsx_memory` 的内部/结果边界
2. 实现时在 workflow compile 或 runtime 校验阶段拒绝 `xlsx_memory + align_by=header`
3. 调整 `sheetbook` plan 结构,在内部 canonical field key 之外单独保存导出 header metadata
4. 增加回归测试:
   - `header_fields_output_by=name` 时 `book_sheet_rows` 仍返回 canonical field key
   - `xlsx_memory + align_by=header` fail-fast
   - `export_xlsx` 仍按结果侧 header metadata 导出
5. 用 `just openspec-check` 与最小 pytest 子集校验

回滚策略:

- 若实现中发现与并行 change 冲突,可先保留 OpenSpec 工件,延后 runtime patch
- 不接受保留半兼容语义; 要么完整禁止 `align_by=header`,要么不合并实现

## Open Questions

- canonical key 在实现层是否仍直接等同于 `field_id`,还是需要提前为唯一前缀键预留抽象层。
- `sheet` / `overwrite` 模式下导出 header metadata baseline 的重建规则,是否需要和 append 共用一个 helper 抽象。
- 对 `xlsx_memory` 非法 `align_by=header` 的报错路径,是放在 compile 阶段还是 runtime 阶段更符合现有校验结构。
