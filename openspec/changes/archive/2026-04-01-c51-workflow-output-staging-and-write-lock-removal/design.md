## Context

workflow 的共享输出（合并 csv / 导出 xlsx）在运行期具备“阶段性中间态”。如果直接写到最终路径:

- 会污染最终路径（用户看到半成品/临时文件）
- 出错时很难保留现场
- 需要依赖 write lock 做互斥与治理,容易引入锁文件遗留/误回收等风险

因此需要在 workflow 层收敛为稳定、可配置的 staging → publish 机制。

约束:

- runtime 仍需兼容 Python 3.6
- publish 必须尽量原子（避免最终路径出现部分写入）
- staging 默认应便于排障（失败时默认保留）

## Goals / Non-Goals

**Goals**

- workflow 共享输出先写入 staging 唯一路径,成功后覆盖发布到最终路径。
- 新增 `workflow.options.output_staging` 控制 staging 目录名与清理策略。
- workflow runtime 不再依赖 write lock file 来保证共享输出可用性。

**Non-Goals**

- 不提供跨多进程/多容器的强互斥保证（若存在并发 publish 到同一路径,按 last-writer-wins 行为处理或由外部协调）。
- 不引入分布式锁服务作为默认方案。

## Decisions

1) **Staging layout**

- 对每个最终输出文件 `final_path`,staging 路径为:
  - `<final_dir>/<dir_name>/<workflow_exec_id>/<filename>`
- `dir_name` 缺省为 `.scalim-staging`,可通过 `workflow.options.output_staging.dir_name` 覆盖。

2) **Publish semantics**

- workflow 成功结束后,对 staging 产物执行覆盖发布:
  - 默认 `keep_on_success=false`: 通过 `rename/replace` 将 staging 文件原子替换到 `final_path`（同时清理 staging exec dir）
  - `keep_on_success=true`: staging 文件保留,通过“copy → replace(final)”实现原子发布

3) **Cleanup policy**

- `keep_on_success=false` 时: best-effort 删除空的 exec dir（`<final_dir>/<dir_name>/<workflow_exec_id>`）
- `keep_on_failure=true` 默认保留 staging,便于排障；若显式 `keep_on_failure=false`,在 `discard_all()` 中清理已生成的 staged outputs。

## Risks / Trade-offs

- [并发 publish 冲突] 多个 workflows 同时发布到同一路径时,最终结果取决于发布顺序 → 缓解:
  - 推荐每次 workflow 使用唯一路径作为最终导出路径,或由平台外部保证互斥
  - staging 的存在保证中间态不污染最终路径

