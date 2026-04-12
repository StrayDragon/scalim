## Context

当前 `workflow` / `sinks` 的并发安全主要靠两类“锁”兜底：

- **进程内锁**：`workflow` 执行期的共享可变状态（`artifacts/ctx/resources` 等）通过 `threading.Lock` + joinable get-or-create 的方式实现互斥/等待/诊断。
- **跨进程锁**：围绕最终输出路径创建 `<final_path>.scalim.lock` 文件来 fail-fast（`workflow/resources_base.py` 与 `sinks/_internal/*`）。

这套方案在单机脚本场景能工作，但在“服务端多请求并发”的场景会带来明显负担：

- **锁冲突**：不同请求写同一路径时要么互斥等待，要么 fail-fast；两者都会放大尾延迟与运维复杂度。
- **目录污染**：在用户产物路径旁生成 `.scalim.lock` 等文件（以及失败时的残留）会影响可维护性与用户体验。
- **推理成本高**：joinable/timeout/diagnostics/force stale 等逻辑让实现难以局部推断，重构与演进成本高。

本变更希望用“**单写者（actor/controller）+ 版本化输出（D-2）**”从根上减少共享可变状态与跨进程互斥的需求。

约束：

- `src/scalim/` 运行时必须兼容 **Python 3.6**。
- 不手工修改任何 `*.gen.*` 与 injected blocks（见 repo doc governance 规则）。

## Goals / Non-Goals

**Goals:**

- 引入 **版本化输出（D-2）**：将 YAML 中 `resources.books.*.path` / `resources.files.*.path`（以及 workflow 对应字段）语义升级为 **输出 root 目录**（不是最终文件路径）；最终文件路径由 `version_id` + `<book_id>/<file_id>` 推导；并通过 `manifest/latest.json` 提供稳定入口。
- 版本化输出写入前 MUST 自动创建 root 及其父目录（`mkdir(parents=True, exist_ok=True)`），并只在 root 下创建框架自管目录（`versions/`、`manifest/`）。
- 框架 **不再在用户产物路径旁生成** `<file>.scalim.lock` 写锁文件；跨进程并发通过“版本隔离”天然消解。
- `workflow` 并发执行路径（组 B）采用 **单写者** 模式：共享状态只允许由 controller 更新；并发线程只做计算与结果回传。
- 保留 staging → publish 的原子性，且在 publish 完成后原子更新 latest 指示（last-writer-wins，但不丢历史版本）。

**Non-Goals:**

- 不引入跨主机/跨文件系统的分布式一致性（例如基于 DB/etcd 的强一致“latest”）。
- 不在本变更内实现自动清理/GC（保留所有版本；后续可加 retention/prune 能力）。
- 不追求全仓库“彻底无锁”（缓存、第三方库 IO 等处的锁可保留）；本变更优先覆盖组 B/D 的关键路径。

## Decisions

### Decision 1: 选择 D-2（版本化输出 + manifest/latest 指示）

将“最终输出路径”的概念升级为“**输出 root 目录**”，并按 run 生成版本化目录：

- 用户配置：`path` 为目录（output root）。
- 每次运行生成一个 `version_id`：
  - workflow: `version_id` MUST 等于 `workflow_exec_id`
  - standalone demand: `version_id` MUST 等于 `run_id`
- `version_id` MUST 是安全的路径段（不得包含路径分隔符、`..` 等；默认生成的 `workflow_exec_id/run_id` 满足该约束）。
- 运行产物落在：`<root>/versions/<version_id>/...`
- latest 指示落在：`<root>/manifest/latest.json`（原子 replace）

这样，多进程并发写同一个 `<root>` 时不会争抢同一最终文件路径，因此无需 `<final>.scalim.lock`。

备选方案与取舍：

- **继续使用 lockfile**：仍会产生目录污染与锁冲突；在服务端多并发请求下风险更高。
- **单文件“latest 直接覆盖”**：不保留历史版本，难以回溯诊断；并发覆盖不可控。
- **symlink latest**：跨平台/权限/打包分发复杂；JSON 指示更通用、可扩展。

### Decision 2: 输出 root 的目录布局（框架自管目录边界）

为避免“到处散落元数据/锁文件”，约定输出 root 下仅创建/写入以下自管目录：

- `<root>/versions/`：版本目录集合（用户真正关心的产物在这里）
- `<root>/manifest/`：框架元数据（latest 指示等）

除上述目录外，框架 MUST NOT 在 `<root>` 的其它位置创建 `.scalim.lock` 等文件。

同时，root 本身就是隔离域（namespace boundary）：

- v1 不引入 `tenant/namespace` 维度的 `latest` 指示（不生成 `latest.<tenant>.json` 之类的变体）。
- 服务端多租户场景 MUST 通过目录分层为每个租户/业务提供独立 root。

### Decision 3: 版本目录内的命名规则（稳定、可预测）

在 `<root>/versions/<version_id>/` 内，按资源类型组织：

- Books（`resources.books.*`）：`books/<book_id>.xlsx`
- Files（`resources.files.*`）：`files/<file_id>.csv`

命名规则以 `<book_id>/<file_id>` 为 SSOT，避免需要额外的“用户自定义文件名”字段（后续如确有需求再扩展）。

### Decision 4: latest 指示与版本 manifest（原子性与可诊断性）

为兼顾可诊断性与 latest 文件稳定：

- 每个版本在其目录内写入：`<root>/versions/<version_id>/manifest.json`
  - 内容包含：`version_id`、创建时间、产物相对路径（books/files）、以及可选的执行元信息（如 workflow_id）。
- root 下写入：`<root>/manifest/latest.json`
  - 内容至少包含：`version_id` 与 `version_manifest_relpath`（例如 `versions/<version_id>/manifest.json`）

原子性：

- `latest.json` 通过 “写临时文件 + atomic replace” 更新，保证并发下文件不会被写坏（JSON 总是完整）。
- `latest.json` 语义为 **last-writer-wins**；但历史版本目录永远保留，因此不会丢数据。

### Decision 5: 组 B 采用 workflow controller 单写者模型（去锁化边界）

在一次 workflow 执行内，定义明确的写入边界：

- **controller 线程**拥有所有共享可变状态的写权限：
  - `WorkflowCtxStore` 的 publish/resolve（以及 total-bytes 护栏）
  - `WorkflowArtifactsDirectory` 的 publish/get/discard
  - `WorkflowResourceManager` 的 get-or-create / write / commit / discard
  - workflow-level 的事件发射顺序与结果汇总
- **并发线程**只执行纯计算（例如 `run_ir`），并将 `ExecutionResult`（及可选捕获事件）回传给 controller；不得直接写共享状态。
- workflow write nodes（写共享 book 的节点）在 controller 线程按确定性顺序执行，从而不需要 `resources` 内部的 join/lock 复杂度。

该决策的关键点是：**并发保留在计算侧，串行化只发生在共享状态变更侧**。

### Decision 6: v1 不提供版本清理（prune/GC）

v1 版本化输出默认保留所有历史版本：

- 框架 MUST NOT 自动删除 `<root>/versions/<version_id>/...`
- v1 不提供 `scalim-cli outputs prune ...` 等清理命令

如需清理，调用方可通过外部任务按业务策略删除旧版本目录（该操作不需要框架锁）。

## Code Impact (Before/After)

本节把本提案的关键决策映射到“当前代码如何工作 / 变更后如何工作”的对照,用于评估实现成本、影响面与预期效果。

### D-2: Standalone demand 输出（YAML → OutputSpec → sink）

**Before（当前实现）**

- `src/scalim/dsl/yaml_dsl/runtime/output_composition_yaml.py` 解析 `resources.books.*.path` / `resources.files.*.path` 为**最终文件路径**（例如 `./out/report.xlsx`、`./out/detail.csv`），并把 `write_lock` 写入 `OutputSpec.write_lock`。
- `src/scalim/execution/run_ir.py::_create_file_sink` 会创建 `CSVSink/ExcelSink(..., write_lock=output.write_lock)`。
- `src/scalim/sinks/_internal/sink_csv.py` / `src/scalim/sinks/_internal/excel.py` 在 `close()` 时可选创建 `<output>.scalim.lock` 并 fail-fast（目录污染 + 服务端并发冲突点）。

代码片段（当前）:

```python
# run_ir.py::_create_file_sink (节选)
return CSVSink(
    output_path=str(output.path),
    ...,
    write_lock=bool(output.write_lock),
)
```

**After（D-2）**

- YAML 中 `path` 解析为 **root 目录**（例如 `./out`），最终输出文件路径由框架推导:
  - `files/<file_id>` → `<root>/versions/<run_id>/files/<file_id>.csv`
  - `books/<book_id>` → `<root>/versions/<run_id>/books/<book_id>.xlsx`
- `OutputSpec.write_lock` 与 sink 的 `write_lock` 路径被移除,不再写入/读取 `.scalim.lock`。
- 成功写入后,框架会写入:
  - `<root>/versions/<run_id>/manifest.json`
  - 原子更新 `<root>/manifest/latest.json`（last-writer-wins,但历史版本保留）

代码形态（示意）:

```python
root = resolve_root_from_yaml(resources.files[file_id].path)
final_path = root / "versions" / run_id / "files" / (file_id + ".csv")
```

### D-2: workflow 共享资源 publish（staging → publish）

**Before（当前实现）**

- `WorkflowResourceManagerBase`（`src/scalim/workflow/resources_base.py`）对每个共享输出生成 staging 文件:
  - staging: `<final_dir>/.scalim-staging/<workflow_exec_id>/<filename>`
- `WorkflowResourceManagerBase._publish_staged_outputs()` 在 `write_lock=true` 时会创建 `<final_path>.scalim.lock`（fail-fast）并发布:
  - `Path(staged_path).replace(final_path)` 或 copy+replace

**After（D-2）**

- `final_path` 将是版本化目录下的文件路径（例如 `<root>/versions/<workflow_exec_id>/books/<book_id>.xlsx`），跨进程并发天然隔离,不再需要 `<final_path>.scalim.lock`。
- publish 仍保留 staging → replace 的原子性,但不再创建 lockfile。
- `commit_all()` 成功后,为每个参与写入的 root 写入版本 manifest 并更新 latest 指示（root 维度 last-writer-wins）。

### B: workflow controller 单写者（共享状态不再依赖 threading.Lock）

**Before（当前实现）**

- `src/scalim/workflow/execute_controller.py::_submit_one_ready_node()` 会把 write nodes 也提交到 `ThreadPoolExecutor`,导致并发线程会访问共享状态（`artifacts_dir/resource_manager/ctx_store`）。

代码片段（当前）:

```python
# execute_controller.py::_submit_one_ready_node (节选)
fut = self._executor.submit(
    self._run_workflow_write_node,
    node,
    artifacts_dir=self._artifacts_dir,
    resource_manager=self._resource_manager,
)
```

- 因为存在并发访问,当前共享状态内部必须通过锁兜底:
  - `src/scalim/workflow/artifacts.py`：`threading.Lock`
  - `src/scalim/workflow/resources_base.py`：`threading.Lock` + joinable inflight
  - `src/scalim/workflow/execute.py::WorkflowCtxStore`：`threading.Lock`

**After（组 B 单写者）**

- 只把 demand nodes 的纯计算（`run_ir`）提交到线程池并发执行。
- write nodes 在 controller 线程**同步执行**（或进入 controller actor 队列）,从而保证共享状态只被单一线程修改。
- 共享状态的锁可以逐步移除（或至少不再依赖其正确性）,并能显著简化“inflight/joinable/diagnostics”的复杂度边界。

### 预期效果（可观测行为变化）

- 不再生成任何 `<final_path>.scalim.lock` 文件；输出目录污染显著下降。
- 服务端多请求并发写同一个 root 时:
  - 每个请求写入自己的 `<root>/versions/<version_id>/...`（互不覆盖）
  - `manifest/latest.json` 可能被最后完成的请求覆盖（last-writer-wins）,但不丢历史版本
- workflow 并发性能:
  - 计算（`run_ir`）仍可并发
  - 写入共享输出资源的阶段被串行化（换取无锁与可维护性）

## User-Facing Testing (What Changes)

本节面向“写测试的用户/调用方”,给出一套稳定、可维护的测试写法,避免测试继续依赖“固定最终文件路径”的旧语义。

### 推荐测试入口：`manifest/latest.json`

原则：

- 测试用例把 `path` 指向一个临时目录作为 output root（例如 `tmp_path/"out"`）
- 运行完成后通过 `<root>/manifest/latest.json` 找到当前版本
- 再从 `<root>/versions/<version_id>/...` 断言产物存在/内容正确

`latest.json` 读取 helper（示意）：

```python
from pathlib import Path
import json


def read_latest(root: Path) -> dict:
    return json.loads((root / "manifest" / "latest.json").read_text("utf-8"))


def current_version_dir(root: Path) -> Path:
    latest = read_latest(root)
    version_id = str(latest["version_id"])
    return root / "versions" / version_id
```

### Standalone demand：pytest 示例

假设 YAML 中将 file/book 的 `path` 配置为 `{$init_var: out_root}`（root 目录）,测试中注入临时路径：

```python
from pathlib import Path

from scalim.dsl import yaml_dsl


def test_demand_outputs_are_versioned(tmp_path: Path) -> None:
    out_root = tmp_path / "out"

    result = yaml_dsl.run(
        "report.demand.yaml",
        options=yaml_dsl.RunOptions(
            allowed_modules=frozenset({"scalim_misc"}),
            init_vars={"out_root": str(out_root)},
        ),
    )

    # 1) 仍可直接用返回值断言本次运行的最终文件路径
    assert result.output_path is not None
    assert Path(result.output_path).exists()

    # 2) 更稳定的“外部入口”：latest -> version dir
    vdir = current_version_dir(out_root)
    assert (vdir / "files" / "detail.csv").exists()
    assert (vdir / "books" / "report.xlsx").exists()

    # 3) 目录干净：不应出现 `.scalim.lock`
    assert list(out_root.rglob("*.scalim.lock")) == []
```

说明：

- 写测试时“关心 root”，不要再把 `path` 当作最终文件路径。
- 如需稳定读取“当前版本”，以 `latest.json` 为入口（适配服务端并发/多次运行）。

### Workflow：pytest 示例（root 是 shared resources 的入口）

workflow 通常会在 `workflow.resources.books/files` 声明共享输出资源（其 `path` 同样是 root 目录）。
测试推荐直接对这些 root 读取 `latest.json` 并断言版本目录内产物存在：

```python
from pathlib import Path

from scalim.dsl import yaml_dsl


def test_workflow_shared_outputs_are_versioned(tmp_path: Path) -> None:
    out_root = tmp_path / "out"

    _ = yaml_dsl.run_workflow(
        "report.workflow.yaml",
        options=yaml_dsl.RunOptions(
            allowed_modules=frozenset({"scalim_misc"}),
            init_vars={"out_root": str(out_root)},
        ),
    )

    vdir = current_version_dir(out_root)
    assert (vdir / "books" / "shared_workbook.xlsx").exists()
```

### 并发测试注意事项

- 若你用同一个 root 并发跑多个请求：`latest.json` 是 last-writer-wins；测试如果只关心“每次运行都留下自己的版本目录”,应断言 `versions/<version_id>` 目录集合增长,而不是断言 latest 指向某个固定版本。
- 多租户/多请求建议测试时就用不同 root（root 即 namespace boundary）。

### 服务端场景：返回 Excel bytes（允许临时落盘）

如果你的“内存返回”只要求 **HTTP 响应阶段拿到 bytes**（允许在服务端临时目录写文件后再读回内存）,推荐模式是：

- 每个请求创建一个**独立 output root**（例如 `/tmp/scalim/<request_id>`）
- workflow 正常写盘到该 root 的版本目录
- 运行完成后读取该 root 的 `manifest/latest.json` 定位本次版本,把目标 `.xlsx` 文件读入内存/或按文件流式返回
- 最后 `rm -rf <root>` 清理整个目录

示意代码（伪代码,以 per-request root 为准,天然无并发冲突）：

```python
import json
import shutil
import tempfile
from pathlib import Path

from scalim.dsl import yaml_dsl


def run_workflow_and_return_xlsx_bytes(*, workflow_yaml: str, book_id: str) -> bytes:
    out_root = Path(tempfile.mkdtemp(prefix="scalim-out-"))
    try:
        _ = yaml_dsl.run_workflow(
            workflow_yaml,
            options=yaml_dsl.RunOptions(
                allowed_modules=frozenset({"scalim_misc"}),  # 仅示意: 以你实际 allowlist 为准
                init_vars={"out_root": str(out_root)},       # YAML 中 resources.*.path 使用 {$init_var: out_root}
            ),
        )
        latest = json.loads((out_root / "manifest" / "latest.json").read_text("utf-8"))
        version_id = str(latest["version_id"])
        xlsx_path = out_root / "versions" / version_id / "books" / (book_id + ".xlsx")
        return xlsx_path.read_bytes()
    finally:
        shutil.rmtree(str(out_root), ignore_errors=True)
```

备注：

- 若 `.xlsx` 很大,服务端通常更推荐“文件句柄流式返回”（避免把整个文件一次性读入内存）；清理可放到响应完成后的回调/后台任务。
- 若你使用“共享 root 多请求并发写入”模式,请勿通过 `latest.json` 来定位“本次请求”的结果（会 last-writer-wins）；应基于本次请求的 `version_id` 精确定位对应版本目录。

## Risks / Trade-offs

- [Breaking DSL] `resources.books.*.path` / `resources.files.*.path` 从“文件路径”升级为“目录 root”，会破坏依赖旧语义的用户配置 → 提供清晰迁移说明（读取 `manifest/latest.json` 获取稳定入口）。
- [Storage growth] 默认保留所有版本，root 目录会增长 → 先保证正确性与可诊断性，后续引入 retention/prune。
- [latest 语义] 并发写同一个 root 时，`latest.json` 会被最后完成的运行覆盖 → 通过“版本目录保留”避免数据丢失；服务端可在业务层按 request-id 固定读取对应版本。
- [FS 原子性] atomic replace 依赖同文件系统 rename 语义；某些网络文件系统的保证较弱 → 先约束为本地/标准 POSIX FS；必要时在实现中加入更保守的 fsync 策略（可选）。

## Migration Plan

1. OpenSpec：补齐 `workflow-versioned-outputs` 新 capability spec，并对 `books/files/sinks/workflow` 的相关 spec 做增量修改（本变更）。
2. DSL：升级 YAML schema + compile/runtime，将 `path` 解释为 output root；移除/废弃 `write_lock` 相关配置面。
3. Runtime：
   - 输出发布改为写入 `<root>/versions/<version_id>/...`，并写 `manifest.json` + 更新 `manifest/latest.json`。
   - workflow 执行改为 controller 单写者；共享状态不再需要 `threading.Lock`（或逐步移除）。
4. 测试与回归：替换所有依赖 `<final>.scalim.lock` 的测试断言；新增并发写同一 root 的回归用例（验证“不同版本并存 + latest 原子更新”）。

## Open Questions

本变更已消除影响可实施性的开放问题；后续新增能力（如 retention/prune、多租户命名空间）将以独立 change 方式推进。
