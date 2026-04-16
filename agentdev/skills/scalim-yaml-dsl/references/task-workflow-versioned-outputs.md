# 版本化输出(D-2): 无锁并发 + `manifest/latest.json`

## 何时读取

- 你在服务端按请求并发跑 workflow/demand,希望输出天然隔离,避免互相覆盖
- 你希望彻底避免在“用户目标目录/最终文件旁边”落 `.scalim.lock` 或其他锁文件
- 你在写测试,希望用一个稳定入口定位本次运行产物,而不是依赖“固定最终文件路径”

本指引对应变更提案: `openspec/changes/c0-lockless-workflow-versioned-outputs/`（D-2；版本化输出；latest 指向当前版本）。

## 核心语义(v1)

- 用户配置的 `path` 语义升级为 **输出 root 目录**（不是最终文件路径）。
- 每次运行写入独立版本目录：`<root>/versions/<version_id>/...`
- 框架在 root 下只创建自管目录：`versions/` 与 `manifest/`（并自动 `mkdir(parents=True, exist_ok=True)` 创建父目录）
- `manifest/latest.json` 通过原子替换更新为“当前版本”（**last-writer-wins**；见下方并发建议）

> 注意：v1 不提供 tenant/namespace 维度；root 自身就是 namespace 边界。服务端多租户/多请求并发场景优先用“每请求一个 root”。

## 目录布局(约定)

```
<root>/
  versions/
    <version_id>/
      files/<file_id>.csv
      books/<book_id>.xlsx
      manifest.json
  manifest/
    latest.json
```

约定的路径推导（示例）：

- files: `<root>/versions/<version_id>/files/<file_id>.csv`
- books: `<root>/versions/<version_id>/books/<book_id>.xlsx`

其中：

- demand：`version_id` 取 `run.id`
- workflow：`version_id` 取 `workflow_exec_id`
- `manifest/latest.json` 至少包含 `version_id` 与 `version_manifest_relpath`

## 并发建议(服务端/多请求)

### 推荐：每请求一个 output root（最省心）

- 每个请求创建自己的 `out_root`（临时目录或按 request_id 组织的目录）
- 运行结束后通过稳定 facade 定位最新产物（例如 `scalim.shortcuts.resources.outputs.load_latest_outputs(out_root)`）
- 读取产物 bytes 并清理 root（或按业务需要保留）

### 不推荐：多个请求共享同一个 root

共享 root 时 `latest.json` 会被其他并发请求覆盖（last-writer-wins），因此：

- 不要用 `latest.json` 作为“本次请求结果”的定位方式
- v1 也不提供 `manifest/latest.<tenant>.json` 之类的变体
- 若你必须共享底层存储,请在上层把 root 按 tenant/namespace 拆分,并为每次请求保证唯一版本 id 的可追踪性

## 服务端返回 Excel bytes（示意写法）

下面示例以“中间过程可以落盘,最终返回内存 bytes”为目标。关键点是 **per-request root + finally 清理**：

```python
import shutil
import tempfile
from pathlib import Path

from scalim.dsl.yaml_dsl import RunOptions, run_workflow
from scalim.shortcuts.resources import outputs


def run_report_and_return_xlsx_bytes(
    workflow_yaml_path: str,
    *,
    book_id: str,
) -> bytes:
    out_root = Path(tempfile.mkdtemp(prefix="scalim-out-"))
    try:
        run_workflow(
            workflow_yaml_path,
            options=RunOptions(
                allowed_modules=frozenset({"myapp.loaders"}),
                init_vars={"out_root": str(out_root)},
            ),
        )

        xlsx_path = outputs.latest_book_path(out_root, book_id=str(book_id))
        return xlsx_path.read_bytes()
    finally:
        shutil.rmtree(out_root, ignore_errors=True)
```

## pytest 测试写法（推荐断言 facade 行为）

原则：测试中把 `path` 配成临时目录 root（例如 `tmp_path/"out"`），不要再断言固定的“最终文件路径”。

示例（workflow 运行后检查 workbook 产物）：

```python
from pathlib import Path

from scalim.dsl.yaml_dsl import RunOptions, run_workflow
from scalim.shortcuts.resources import outputs


def test_workflow_outputs_are_versioned(tmp_path: Path) -> None:
    out_root = tmp_path / "out"

    run_workflow(
        "path/to/workflow.yaml",
        options=RunOptions(
            allowed_modules=frozenset({"tests.fixtures.workflow_loaders"}),
            init_vars={"out_root": str(out_root)},
        ),
    )

    report_xlsx = outputs.latest_book_path(out_root, book_id="report")
    assert report_xlsx.exists()
    assert (report_xlsx.parent.parent / "manifest.json").exists()

    # 版本化输出后,不应在最终文件旁生成 `.scalim.lock`
    assert not any(out_root.rglob("*.scalim.lock"))
```

## YAML 迁移提示(从“文件路径”到“root”)

旧语义(示例)：`path` 是最终文件路径：

```yaml
resources:
  books:
    report:
      path: ./out/ecommerce_report.xlsx
```

新语义(示例)：`path` 是输出 root 目录：

```yaml
resources:
  books:
    report:
      path: {$init_var: out_root}  # 或 ./out
```

产物路径由框架推导为：

- `<out_root>/versions/<version_id>/books/report.xlsx`

如果你需要产物文件名更贴近业务命名,让 `book_id/file_id` 本身表达这个名字即可（v1 不提供单独的 `filename` 字段）。
