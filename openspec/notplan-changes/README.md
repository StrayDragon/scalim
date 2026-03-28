# notplan-changes

本目录用于存放**尚未进入 OpenSpec 正式变更工作流**的草案与备忘(例如 proposal/design/tasks),方便先沉淀想法、讨论记录与候选方案。

## 边界与约束

- 本目录**不是** `openspec/changes/` 下的 active change；不会被 `openspec list` / `openspec instructions ...` 等命令识别为“可推进的变更”。
- 本目录内容仍属于 `openspec/` 范围：会被 `just openspec-check` 的 `sanitize` 扫描(避免把私有字面量带入可共享工件)。
- 这里的草案不要求完备、也不要求可实现；当你准备推进时再“转正”为 active change。

## 如何转正为 active change

1. 用 `openspec new change <name>` 创建变更目录(建议遵循 `c<priority>-<kebab-case>` 命名)。
2. 将本目录下对应草案的 proposal/design/specs/tasks 迁移到新建的 change 目录。
3. 运行 `just openspec-check` 与 `just qa`，确保 sanitize/validate 与 repo 门禁全部通过。
4. 完成实施后按流程 `openspec sync` / `openspec archive`。

