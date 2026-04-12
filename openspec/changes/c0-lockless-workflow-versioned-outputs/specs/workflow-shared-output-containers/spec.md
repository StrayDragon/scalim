# workflow-shared-output-containers Specification

## ADDED Requirements

### Requirement: workflow controller MUST be the sole writer of workflow-managed shared state

当 workflow 以并发模式执行（`max_concurrency > 1`）时，系统 MUST 将所有 workflow-managed 的共享可变状态更新收敛到单一 controller（单写者/actor）执行上下文中：

- `WorkflowArtifactsDirectory` 的 publish/get/discard
- `WorkflowCtxStore` 的 publish/resolve
- `WorkflowResourceManager` 的 create/write/commit/discard

并发线程（worker）MUST 仅负责纯计算（例如执行 `run_ir`）并将结果回传给 controller；worker MUST NOT 直接写入上述共享状态。

#### Scenario: worker threads do not mutate workflow-managed state
- **GIVEN** workflow 启用并发执行（`max_concurrency=2`）
- **WHEN** 两个 demand nodes 并发运行并产生 outputs
- **THEN** 系统 MUST 仅在 controller 上下文中发布 artifacts/ctx/resource 写入
- **AND** 任一 worker 线程调用上述 publish/commit 接口 MUST 被视为实现错误并导致 fail-fast

### Requirement: workflow shared resources MUST publish into versioned output roots and update manifest/latest

当 workflow 最终 commit 共享输出资源（books/files）时，系统 MUST 按版本化输出（D-2）协议发布：

- 产物 MUST 写入 `<root>/versions/<workflow_exec_id>/...`
- 系统 MUST 写入 `<root>/versions/<workflow_exec_id>/manifest.json`
- 系统 MUST 原子更新 `<root>/manifest/latest.json`
- 系统 MUST NOT 在产物路径旁生成 `<final_path>.scalim.lock`

#### Scenario: concurrent workflows publish to the same root without mutual exclusion
- **GIVEN** 两个独立 workflow 进程并发写入同一输出 root（`./out`）
- **WHEN** 两个 workflow 都成功完成 publish
- **THEN** `./out/versions/<wf_exec_id_1>/` 与 `./out/versions/<wf_exec_id_2>/` MUST 同时存在
- **AND** `./out/manifest/latest.json` MUST 始终为可解析 JSON
- **AND** `./out/**/*.scalim.lock` MUST 不存在

