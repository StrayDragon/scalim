# notplan

本目录用于存放**尚未进入 llmanspec 正式变更工作流**的暂缓提案(例如 proposal/design/tasks),方便先沉淀候选方向与讨论记录。

## 边界与约束

- 本目录**不是** `llmanspec/changes/` 下的 active change；不会被 `llman sdd list` 识别为“可推进的变更”。
- 本目录内容属于 `llmanspec/` 范围：会被 `just llmanspec-sanitize` 扫描(避免把私有字面量带入可共享工件)。
- 这里的草案不要求完备、也不要求可实现；当你准备推进时再“转正”为 active change。

## 如何转正为 active change

1. 使用 `llman-sdd-propose` 创建正式变更(建议遵循 `c<priority>-<kebab-case>` 命名)。
2. 将本目录下对应草案的 proposal/design/specs/tasks 迁移到新建的 change 目录。
3. 运行 `just llmanspec-check` 与 `just qa`，确保 sanitize/validate 与 repo 门禁全部通过。
4. 完成实施后按流程 `llman sdd archive run <id>` 归档。

## 已转正（superseded）短指针

转正后 **删除 notplan 长文**，只留本表或各目录下 `SUPERSEDED` 短页，避免与 `llmanspec/changes/` 双源漂移：

| notplan 目录 | 替代 active change |
|--------------|-------------------|
| `c0-write-precompute-derived-fields` | `c10-write-precompute-derived-fields` |
| `c0-compute-rowwise-fusion` | `c20-compute-expr-rowwise-fusion`（范围已含安全外壳下无 `$ctx` 的 `call_by`） |
| `c0-perf-refloader-chunk-parallelism` | `c30-refloader-chunk-parallelism` |

