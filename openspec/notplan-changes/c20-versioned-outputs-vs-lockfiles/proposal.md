## Why

我们已经在执行层引入了 **versioned outputs(D-2)**（`output root` + `versions/<version_id>` + `manifest/latest.json`）来避免过去的
lockfile（`<final_path>.scalim.lock`）并发保护模式。

实现已经落地,但“为什么这么做/放弃什么/换来什么/在不同 Python 运行时下应如何理解并发语义”仍缺少一个集中、可被维护者回溯的
trade-off 记录。该 proposal 作为低优先级备忘,用于:

- 固化 **versioned outputs vs lockfile** 的优劣与适用场景边界
- 固化对 **Python 3.6 / 3.10 / 3.14t**（free-threaded / t-build）运行时差异的注意事项（尤其是并发与线程安全假设）
- 给出用户侧“前/后”示例与生成目录结构,方便下游迁移/适配

## Context / Current State

- 版本化输出核心布局:
  - `<root>/versions/<version_id>/books/<book_id>.xlsx`
  - `<root>/versions/<version_id>/files/<file_id>.csv`
  - `<root>/versions/<version_id>/manifest.json`
  - `<root>/manifest/latest.json`（原子 replace; last-writer-wins）
- 内建 sinks 合同: 不应再通过在最终文件旁创建 `.scalim.lock` 来实现并发保护；并发隔离优先由“版本化输出 + 唯一路径”完成。
- `path` 语义升级: YAML 中 `resources.books.*.path` / `resources.files.*.path` 当前语义为 **输出 root 目录**（不是最终文件路径）。

关联历史（已归档/或规范）:

- `openspec/changes/archive/2026-04-12-c0-lockless-workflow-versioned-outputs/`（D-2 设计/实现记录）
- `openspec/changes/archive/2026-04-12-c8-add-file-resource-write-lock/`（旧 lockfile 方向的设计记录；现已被 D-2 路线替代）
- `openspec/changes/archive/2026-04-12-c0-lockless-workflow-versioned-outputs/specs/sinks-contracts/spec.md`（移除 lockfile 合同的规范）

## Trade-offs

### A) 固定最终路径 + lockfile（旧）

**优点**

- 下游消费最简单：产物是固定路径（例如 `./out/report.xlsx`）,无需读取 `latest.json` 或解析 manifest。
- 并发语义明确：同一目标路径的并发写入可显式 fail-fast（或扩展为等待/超时/排队）。

**缺点**

- 目录污染：锁文件与 staging/诊断文件会出现在“用户产物路径附近”,影响体验与可维护性。
- 残留风险：进程异常退出易留下 stale lock,后续运行需要人工介入或额外 stale/force 机制。
- 服务端多请求并发场景成本高：
  - 要么互斥等待,放大尾延迟；
  - 要么 fail-fast,把“冲突”转嫁给调度与运维。
- 实现不可避免走向复杂：joinable/timeout/diagnostics/stale 等逻辑一旦引入,很难局部推断与演进。

### B) output root + versioned outputs（现）

**优点**

- 天然并发隔离：并发写同一 root 时,写入发生在不同 `versions/<version_id>/...` 目录,避免“争抢同一最终文件路径”的互斥需求。
- 元数据边界清晰：框架自管内容集中在 `<root>/versions/` 与 `<root>/manifest/`；不在用户最终文件旁制造额外文件。
- 可回溯可诊断：历史版本保留,每次运行可用 `<root>/versions/<version_id>/manifest.json` 完整描述产物。

**缺点 / 代价**

- 下游消费需要“多一步”: 固定路径变为“读 `latest.json` → 定位版本目录 → 读取产物”。
- `latest.json` 的并发语义是 **last-writer-wins**：
  - 多请求共享同一个 root 时,`latest` 不再适合作为“本次请求结果”的定位方式；
  - 推荐以 root 作为 namespace：服务端场景优先 “per-request/per-tenant 一个 root”。
- 历史版本默认不清理：需要后续的 retention/prune/GC 能力（或业务侧定期清理）。

## Runtime Support Notes (3.6 / 3.10 / 3.14t)

### Python 3.6（运行时下限）

- 约束: `src/scalim/` 必须保持 Python 3.6 兼容（语法 + 依赖边界）。
- 实践: 将运行时代码限制在 3.6 语法子集,可自然运行在 3.10+ 与未来版本。

### Python 3.10（主流运行时 + dev tooling 边界）

- 更丰富的 typing/stdlib 让开发体验更好；但只要运行时代码保持 3.6 子集,无额外兼容负担。
- 依赖生态（numpy/pandas/openpyxl 等）在 3.10+ 可使用更新版本；3.6 需要更严格的版本边界治理。

### Python 3.14t（free-threaded / t-build 的并发语义）

> 备注：这里以“无 GIL / free-threaded build”这类运行时为目标约束,不绑定最终实现细节。

- 关键变化：线程更接近“真并行”,历史上依赖 GIL 的隐式互斥会更容易暴露数据竞争。
- 对框架的启示：
  - 不应依赖 GIL 作为正确性手段；
  - “controller 单写者 + 版本化输出”的设计更接近可验证的并发边界：把并发留在纯计算侧,共享状态与 IO 发布边界串行化/受控化。

## User-Facing Before/After (YAML)

### Before（旧语义：path=最终文件路径；已迁移/不再支持）

```yaml
resources:
  files:
    detail_csv: { kind: csv_file, path: ./out/detail.csv, write_lock: true }
  books:
    report: { kind: xlsx_file, path: ./out/report.xlsx, write_lock: true }
```

### After（现语义：path=输出 root 目录；产物按 version_id 推导）

```yaml
resources:
  files:
    detail_csv: { kind: csv_file, path: ./out }
  books:
    report: { kind: xlsx_file, path: ./out }
```

## Output Layout (Generated Files)

```
out/
  manifest/
    latest.json
  versions/
    <version_id>/
      manifest.json
      books/
        report.xlsx
      files/
        detail_csv.csv
```

## Open Questions / Follow-ups (Low Priority)

- Retention/GC: 是否需要内建 `prune` 能力（按时间/数量/空间）？
- Stable path adapter: 对“必须固定最终路径”的下游,是否提供官方“读 latest → copy/rename/symlink 到稳定路径”的 adapter（或 CLI）？例如将 `./out/versions/<id>/books/report.xlsx` 物化为 `./out/latest/report.xlsx` 供下游固定路径读取。
- Namespace: 是否需要在同一 root 下支持 `latest.<tenant>.json` / 多指针（当前约定 root 自身是 namespace）？
- DX: 是否增加 `scalim-cli outputs` 子命令（例如 `latest --root ...`、`manifest --root ...`）方便脚本化消费？
