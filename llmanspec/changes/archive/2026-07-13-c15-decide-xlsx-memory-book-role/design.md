# Design — decide-xlsx-memory-book-role

## Decision

**Keep** `xlsx_file` + `xlsx_memory`.

| Kind | 用户心智（本 change） | 终点 |
|---|---|---|
| `xlsx_file` | 文件书：版本化输出 root → `.xlsx` | 必落盘 |
| `xlsx_memory` | 内存书：typed plan；导出可选 | 可纯内存总线 |

`sheet` 只是 `to.sheet`，不是第三种 kind。

## Why not merge into xlsx_file

合并会把「中间指标总线」绑到磁盘 path/版本化布局，增加 IO 与路径配置，且改变「无可导出文件」的失败/可见性语义。匿名盘点显示该总线模式真实存在 → **拒绝默认 deprecate**。

## Rejected options

| 选项 | 状态 | 原因 |
|---|---|---|
| 删除 `xlsx_memory`，一律 `xlsx_file` | 拒绝（本 change） | 破坏无 export 总线 |
| 把 memory 改名为 `xlsx_sheet` | 拒绝 | 更像「单 sheet」，误导更大 |
| 本 change 合并 workbook/sheetbook 实现 | 不做 | 实现债另案；与产品 keep 正交 |

## Privacy

- 外部用量报告仅作决策输入；**不得**把真实 path / 业务名抄进本仓库任何工件。
- MVP 只用虚构 id：`scratch` / `report` / `stage_a` / `stage_b` / `summary`。

## MVP 对照意图

- **Before**：作者以为 `xlsx_memory` ≈ 忘了写 path 的 `xlsx_file`。
- **After**：同一编排里同时出现「无 export 的 scratch 总线」+「xlsx_file 最终报表」，语义一眼可分。

## Implementation posture

本 draft **默认不 apply 代码**。review 可勾选：skills/docs 补一句心智模型；rename/unify 另开 change。
