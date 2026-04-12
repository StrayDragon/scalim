## Why

当前 `workflow`/`sink` 的并发安全大量依赖锁（线程锁与 `.scalim.lock` 文件锁），导致实现复杂、推理成本高，并且在服务端多请求并发场景下容易出现锁冲突/目录污染，影响可维护性与稳定性。

我们希望通过“单写者 + 版本化输出”的协议化设计，从根上减少共享可变状态与跨进程互斥带来的约束，让并发运行在保持确定性与可观测性的同时更干净、更易维护。

## What Changes

- 引入 **版本化输出**：用户将输出配置为一个目录（root），每次运行写入一个独立版本子目录（例如 `<root>/<run_id>/...`），并在 root 下提供一个原子更新的“最新版本指示”（manifest/`latest.json`）。默认 `version_id` 直接使用 `workflow_exec_id/run_id`（可追踪、且本身已是 UUID4）；root 即隔离域（v1 不做 namespaced latest）；v1 不做 prune。若 root 或其父目录不存在，框架 MUST 自动创建（`mkdir(parents=True, exist_ok=True)`），并自动创建 `<root>/versions/` 与 `<root>/manifest/` 自管目录。
- 移除/收敛基于最终输出路径的 `.scalim.lock` 写锁文件：框架不再在用户产物路径旁生成 `<file>.scalim.lock`；跨进程并发的冲突通过“版本化目录”天然隔离。
- `workflow` 并发写入路径无锁化（组 B）：将 `workflow` 中涉及共享可变状态的写入（resources/artifacts/ctx/events 等）改为 **单写者（controller/actor）** 模式；并发线程只负责计算与产物回传，不直接触碰共享状态。
- 统一输出发布语义：保留 staging → publish 的原子性，但 publish 目标从“固定最终文件路径”调整为“版本化目录内的最终路径”，并在成功后更新 latest 指示。

## Capabilities

### New Capabilities
- `workflow-versioned-outputs`: 定义输出 root 目录下的版本化布局、latest 指示（manifest）格式、原子更新与并发语义。

### Modified Capabilities
- `workflow-shared-output-containers`: shared resources 的 commit/publish 语义扩展为“版本化输出”，并明确不在用户目录生成锁文件的约束。
- `yaml-dsl-books-resources`: `books.*.path`/`export_xlsx.path` 的 authoring surface 支持“目录 root”语义，并定义导出文件在版本目录中的命名规则。
- `yaml-dsl-file-resources`: `files.*.path` 的 authoring surface 支持“目录 root”语义，并定义导出文件在版本目录中的命名规则。
- `sinks-contracts`: sink 的并发写入安全从“路径锁文件”迁移到“版本化输出协议 + 原子 replace”，并明确框架产生的元数据/指示文件位置约束。

## Impact

- 受影响代码：
  - `src/scalim/workflow/*`（write nodes 执行模型、resource manager、artifacts/ctx 生命周期、publish/manifest 写入）
  - `src/scalim/sinks/_internal/*`（移除 `.scalim.lock` 写锁文件策略，或改为框架自管目录/协议化输出）
  - `src/scalim/dsl/yaml_dsl/*`（schema + compile/runtime 对输出 root 语义的支持）
- 受影响行为：
  - 最终产物路径从“固定文件路径”迁移为“root 下版本化目录”，用户需要改为读取 latest 指示或指定版本目录。
  - 服务端并发请求写同一路径不再发生互斥冲突（自然隔离为不同版本）。
