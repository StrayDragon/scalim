# workflow YAML 校验、订正与排错

## 何时读取

- 你在写/改 workflow YAML 时遇到校验失败或运行时报错
- 你需要定位 `depends_on` / `$ctx` / `resources.books` 的常见错误
- 你怀疑自己把 workflow YAML 当成 demand YAML 去跑了错误的校验命令

## 最小命令入口(先跑起来再排错)

workflow YAML 支持两类校验入口:

1) workflow-level full validate(静态/编译期;递归校验引用的 demands;不执行 workflow):

```bash
uv run scalim-cli yaml-dsl validate --type workflow <workflow.yaml>
```

2) schema-only 校验(结构/unknown-fields;依赖 `workflow.gen.json`):

```bash
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json <workflow.yaml>
```

更强诊断:

```bash
uv run scalim-cli yaml-dsl validate --type workflow --verbose <workflow.yaml>
uv run scalim-cli yaml-dsl validate --type workflow --json <workflow.yaml>

uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json --verbose <workflow.yaml>
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json --json <workflow.yaml>
```

本地编辑器补全/hover:

```bash
uv run scalim-cli yaml-dsl upsert-lsp-comment --type workflow --comment-style all <paths...>
```

```yaml
# yaml-language-server: $schema=.../workflow.gen.json
# $schema: .../workflow.gen.json
```

## 工作顺序(推荐)

1. 先用 `schema validate` 收敛结构/未知字段问题(显式指定 workflow schema)
2. 再用 `yaml-dsl validate --type workflow` 做跨文件/递归校验(包含 demands 语义校验与 outputs/books 绑定一致性)
3. validate 过了但 workflow 仍失败时,用 Python 入口跑一次,定位运行期的 fail-fast 校验(例如 cycle、ctx 越界、输出路径冲突等)

```python
from scalim.dsl.yaml_dsl import (
    BookBudgetPolicy,
    BookResourcePolicy,
    BookWritePolicy,
    DemandRunOptions,
    DemandRunSecurityOptions,
    ResourcesPolicy,
    WorkflowRunOptions,
    run_workflow,
)

run_workflow(
    "path/to/workflow.yaml",
    options=WorkflowRunOptions(
        demand=DemandRunOptions(security=DemandRunSecurityOptions(allowed_modules=frozenset(["myapp.loaders"]))),
        # 若 YAML 仍残留 write_defaults/budget,或需要非默认写入策略/预算护栏,在此配置
        resources_policy=ResourcesPolicy(
            books={"report": BookResourcePolicy(write=BookWritePolicy(), budget=BookBudgetPolicy(max_sheets=16, max_total_cells=2_000_000))}
        ),
    ),
)
```

## 常见错误与修复

### 1) 用错类型：对 workflow 强制跑了 demand validate

症状:

- 你运行了 `uv run scalim-cli yaml-dsl validate --type demand workflow.yaml`
- 输出看起来像 demand 校验,或报了与你的 workflow 字段无关的 unknown-fields

修复:

- workflow YAML 运行 `uv run scalim-cli yaml-dsl validate --type workflow workflow.yaml`
- 或省略 `--type` 让 CLI 自动推断(推荐 CI/脚本显式写 `--type workflow`)

### 2) 忘了 `--schema`，导致拿 demand schema 校验 workflow

症状:

- `yaml-dsl schema validate workflow.yaml` 报错集中在顶层结构/未知字段

修复:

- 加 `--schema src/scalim/dsl/yaml_dsl/schema/workflow.gen.json`

### 3) `depends_on` 引用不存在的 run id 或形成 cycle

症状:

- 运行期 fail-fast: “unknown run id” / “cycle detected …”

修复:

- 确保 `depends_on` 里每个 id 都存在于 `workflow.runs[*].id`
- 如果有环,按业务语义拆开或改写依赖方向
- 如果你在 Python 入口使用了 `WorkflowRunOptions(patches_by_run_id=...)`,也必须保证 `patches_by_run_id` 的 keys 都是合法的 `workflow.runs[*].id`(否则同样会 fail-fast 并列出已知 ids)。

### 4) `$ctx` 引用越界(不在 deps 可见范围)

症状:

- 下游 run 在 `init_vars` 里读取 `{$ctx: {node: A, key: ...}}` 时 fail-fast
- 报错提示“ctx 引用超出 deps 可见范围”

修复:

- 下游 run 必须显式 `depends_on: [A]`(或依赖闭包中包含 A)
- 避免把大对象塞进 ctx；只放小体量 summary/path 等

### 5) YAML 仍写 `write_defaults` / `budget`(已迁出)

症状:

- validate / parse / compile fail-fast: `write_defaults was removed from YAML authoring` 或 `budget was removed`
- 或运行期命中 Python `BookBudgetPolicy` 护栏(超限 fail-fast)

修复:

- 从 YAML `resources.books.*` 删除 `write_defaults` 与 `budget`(只留 identity: 推荐 `xlsx` + 可选 `path`)
- 在 Python 配置 `WorkflowRunOptions.resources_policy` / `DemandRunOptions.resources_policy`:
  - write → `BookWritePolicy`(构造只用 StrEnum)
  - budget → `BookBudgetPolicy(max_sheets=..., max_total_cells=...)`(启用时两者都要给;省略 = unlimited)
- 完整迁移: `references/upgrades/2026-07-12-book-write-policy-python-ssot.md`
- book identity 统一: `references/upgrades/2026-07-13-unified-xlsx-book-kind.md`
- `RunOverrides.resources` / `BookResourceOverride` 仍可覆盖 path/`allow_formulas`,但 **不能**再 overlay write/budget

### 6) 把“写入意图”或 runtime knobs 写进了 workflow YAML

症状:

- schema validate 报错 unknown-fields,或 full validate 报错“字段已移除/不支持”
- 例如出现 `workflow.options`、`resources.books.*.write_defaults`、旧 `writes` 字段

修复:

- workflow YAML 只声明 `workflow.resources.books`(共享 book identity)与 runs DAG
- 写到哪个 book/sheet 由 demand outputs 的 `to/write` 绑定表达,并由 workflow 编译期推导写入节点
- concurrency / cache_pool / failure_policy 等走 Python runtime entrypoints,不要写回 `workflow.options`

### 7) 输出路径冲突或共享资源路径被直接写入

症状:

- 运行期 fail-fast: 多个 nodes 写同一路径
- 或 workflow 已声明为共享输出资源的路径,却被某个 demand 直接写同一路径

修复:

- 要么每个 demand 输出到唯一路径
- 要么把共享输出收敛到 `workflow.resources.books` + demand outputs 的 `to/write` 绑定,避免多方直接写同一路径
- 相对 `path: ./out` 相对 **声明该路径的 YAML 文件目录**(workflow 托管 book → workflow YAML 目录),不是进程 cwd;环境相关 root 用绝对路径、`{$init_var: ...}` 或 `BookResourceOverride(path=...)`

### 8) 输出未绑定到 book/sheet 或 book_id 不存在

症状:

- workflow compile fail-fast: 缺少 `outputs[*].to.book`
- 或提示 book_id 不存在/冲突(需要统一声明)

修复:

- 为 Excel outputs 显式声明 book 绑定:
  - demand YAML: `outputs[*].to.book` + `outputs[*].to.sheet`
  - workflow YAML: `workflow.resources.books.<book_id>`(用于统一/覆盖共享 book 资源)
