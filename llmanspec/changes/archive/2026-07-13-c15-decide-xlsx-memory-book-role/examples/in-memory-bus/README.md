# MVP — in-memory bus vs file book（虚构）

本目录示例 **故意使用虚构 id/路径**，用于理解双 kind，不对应任何外部业务仓。

| 文件 | 角色 |
|---|---|
| `before.workflow.yaml` | 易误解写法：只看到两个 book，分不清为何要 memory |
| `after.workflow.yaml` | 对照：scratch=无 export 内存总线；report=落盘文件书 |
| `stage_a.demand.yaml` / `stage_b.demand.yaml` | 写入 scratch |
| `summary.demand.yaml` | `book_sheet_rows` 读 scratch，再写 report |

运行与否不作为本 draft 的强制门禁；优先给人读。
