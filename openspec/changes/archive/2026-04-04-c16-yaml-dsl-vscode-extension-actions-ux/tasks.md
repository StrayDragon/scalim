本变更的所有实现与验证默认发生在扩展工程 `extras/vscode-scalim/`。

## 1. Quick Fix 映射

- [x] 1.1 将 server 的 `codeAction` 映射为 VSCode Quick Fix（保持语义来源于 server）
- [x] 1.2 实现 `executeCommand` 桥接：失败时输出可诊断信息（包含 command id 与参数摘要）
- [x] 1.3 对 actions 进行基础分组/命名优化（不改变语义）

## 2. Troubleshooting 命令

- [x] 2.1 命令：Restart server
- [x] 2.2 命令：Open logs / output channel
- [x] 2.3 命令：Show discovery summary
- [x] 2.4 命令：Open/Create `scalim.yaml`

## 3. 状态栏与可见性

- [x] 3.1 增加最小状态栏项（running/stopped、版本、project root）
- [x] 3.2 server 崩溃/启动失败时给出明显提示与下一步指引

## 4. 验证

- [x] 4.1 手动验证：缺失 `scalim.yaml` 时能通过 Quick Fix 创建并生效（diagnostics 改善）
- [x] 4.2 运行 `just openspec-check` 确认 OpenSpec 工件结构与 schema 校验通过
