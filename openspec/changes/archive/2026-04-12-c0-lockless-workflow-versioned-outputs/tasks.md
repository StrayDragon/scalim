## 1. Versioned 输出协议（D-2）基础设施

- [x] 1.1 新增 `output_root` 解析与布局 helper：规范化 `<root>/versions/` 与 `<root>/manifest/` 目录创建（仅写自管目录）
- [x] 1.2 定义 `version_id` 选择策略：workflow 使用 `workflow_exec_id`；standalone demand 使用 `run_id`；校验 `version_id` 为安全路径段；检测 `<root>/versions/<version_id>/` 已存在时 fail-fast
- [x] 1.3 实现版本 manifest 写入：写 `<root>/versions/<version_id>/manifest.json`（包含 `version_id/created_at_unix_s/books/files` 等）
- [x] 1.4 实现 latest 指示原子更新：以临时文件 + atomic replace 更新 `<root>/manifest/latest.json`（last-writer-wins，且 JSON 永远完整）
- [x] 1.5 为并发场景补齐最小可测接口（例如读回 latest/manifest 的 helper），便于单测与回归用例

## 2. YAML DSL：books/files 的 authoring surface 升级（破坏性）

- [x] 2.1 更新 `resources.files.*` schema/compile：`path` 解释为输出 root 目录；移除/拒绝 `write_lock`；推导最终路径 `<root>/versions/<version_id>/files/<file_id>.csv`
- [x] 2.2 更新 `resources.books.*` schema/compile：`xlsx_file.path` 与 `xlsx_memory.export_xlsx.path` 解释为输出 root 目录；移除/拒绝 `write_lock`；推导最终路径 `<root>/versions/<version_id>/books/<book_id>.xlsx`
- [x] 2.3 更新错误诊断：当检测到 legacy `write_lock` 字段或旧“文件路径”语义时，fail-fast 并给出迁移提示（指向 `manifest/latest.json`）

## 3. Sinks：移除 lockfile 依赖并保持原子写出

- [x] 3.1 移除内建 CSV/Excel sinks 的 `<output_path>.scalim.lock` 逻辑（包括参数面 `write_lock` 与实现 `_acquire/_release_write_lock`）
- [x] 3.2 保持并验证 “私有临时目录 + atomic replace” 的写出语义不变（TOCTOU 缓解能力保留）
- [x] 3.3 更新 sinks 相关测试：删除对 lockfile 的断言/fixture，新增“无 lockfile 残留”的回归断言

## 4. Workflow 组 B：controller 单写者（actor）化

- [x] 4.1 调整 `WorkflowRunController`：worker 线程仅执行 `run_ir`；所有 artifacts/ctx/resources 更新仅在 controller 执行上下文发生
- [x] 4.2 将 workflow write nodes（写共享 book 的节点）改为由 controller 串行执行（不再提交到 `ThreadPoolExecutor`）
- [x] 4.3 移除/收敛 `WorkflowArtifactsDirectory` 与 `WorkflowCtxStore` 的 `threading.Lock`（在单写者模型下不再需要）
- [x] 4.4 收敛 `WorkflowResourceManager` 的 joinable/lock 复杂度：在单写者路径下移除不必要的 inflight/等待分支（保持行为可预测、易维护）

## 5. Workflow 组 D：共享资源 commit → 版本化输出发布

- [x] 5.1 调整 workflow shared resources 的 staged→publish：最终输出写入 `<root>/versions/<workflow_exec_id>/...`，并生成该版本的 `manifest.json`
- [x] 5.2 在 workflow 成功 commit 后更新 `<root>/manifest/latest.json`；失败则不更新 latest（历史版本不受影响）
- [x] 5.3 确保 workflow publish 不会在用户产物路径旁生成任何 `.scalim.lock` 文件（包括错误路径）

## 6. 回归测试与并发验证

- [x] 6.1 新增/更新 YAML DSL workflow 回归用例：同一 root 下两次运行产生两个版本目录；latest 指向当前版本；且无 `.scalim.lock` 残留
- [x] 6.2 新增并发回归用例：两个独立 workflow 进程/线程并发写同一 root 时版本并存、latest JSON 不损坏（last-writer-wins）
- [x] 6.3 执行质量门禁：`just openspec-check`（OpenSpec 校验）与 `just qa`（lint/tests/drift gates）

## 7. 规范与文档同步

- [x] 7.1 将本 change 的 delta specs 同步回 `openspec/specs/*/spec.md`（SSOT：本 change 的 `openspec/changes/.../specs/`；入口：`openspec sync specs` 或对应工作流）
- [x] 7.2 若 docs 站点存在 specs 注入区块，运行 `just gen-docs` 刷新（避免 injected-block drift）；验收：`just qa` 不再报文档漂移
- [x] 7.3 更新用户侧文档（SSOT 放在 skill）：在 `artifacts/skills/` 中补齐“服务端 per-request 输出 root + latest.json 定位 + 清理 + 并发注意事项 + 测试写法”的指引；`docs/doc/` 仅添加简短指向说明（不复制内容）
