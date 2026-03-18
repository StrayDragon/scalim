# workflow YAML 校验、订正与排错

## 何时读取

- 你在写/改 workflow YAML 时遇到校验失败或运行时报错
- 你需要定位 `depends_on` / `$ctx` / `resources` / `write_to` 的常见错误
- 你怀疑自己把 workflow YAML 当成 demand YAML 去跑了错误的校验命令

## 最小命令入口(先跑起来再排错)

workflow YAML **只支持 schema-only 校验**(没有 `yaml-dsl validate` 的 internal validator). 仓库内建议显式指定 workflow schema:

```bash
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json <workflow.yaml>
```

更强诊断:

```bash
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json --strict --verbose <workflow.yaml>
uv run scalim-cli yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json --json <workflow.yaml>
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

1. 确认你在校验的是 workflow YAML,并且使用了 workflow schema(`--schema .../workflow.gen.json`)
2. 先用 `schema validate --strict` 收敛结构/未知字段问题
3. schema 过了但 workflow 仍失败时,用 Python 入口跑一次,定位运行期的 fail-fast 校验(例如 cycle、ctx 越界、输出路径冲突等)

```python
from scalim.dsl.by_yaml import run_workflow

run_workflow(
    "path/to/workflow.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
)
```

## 常见错误与修复

### 1) 用错命令：对 workflow 跑了 `yaml-dsl validate`

症状:

- 你运行了 `uv run scalim-cli yaml-dsl validate workflow.yaml`
- 输出看起来像 demand 校验,或报了与你的 workflow 字段无关的错误

修复:

- workflow YAML 只用 `yaml-dsl schema validate --schema src/scalim/dsl/by_yaml/schema/workflow.gen.json workflow.yaml`

### 2) 忘了 `--schema`，导致拿 demand schema 校验 workflow

症状:

- `yaml-dsl schema validate workflow.yaml` 报错集中在顶层结构/未知字段

修复:

- 加 `--schema src/scalim/dsl/by_yaml/schema/workflow.gen.json`

### 3) `depends_on` 引用不存在的 run id 或形成 cycle

症状:

- 运行期 fail-fast: “unknown run id” / “cycle detected …”

修复:

- 确保 `depends_on` 里每个 id 都存在于 `workflow.runs[*].id`
- 如果有环,按业务语义拆开或改写依赖方向

### 4) `$ctx` 引用越界(不在 deps 可见范围)

症状:

- 下游 run 在 `init_vars` 里读取 `{$ctx: {node: A, key: ...}}` 时 fail-fast
- 报错提示“ctx 引用超出 deps 可见范围”

修复:

- 下游 run 必须显式 `depends_on: [A]`(或依赖闭包中包含 A)
- 避免把大对象塞进 ctx；只放小体量 summary/path 等

### 5) `resources.sheetbooks.*` 缺少 budget 护栏

症状:

- schema validate 报错: 缺少 `budget.max_sheets/max_total_cells`

修复:

- 每个 sheetbook 资源必须声明 `budget.max_sheets` 与 `budget.max_total_cells`

### 6) `write_to` intent 互斥违反

症状:

- schema validate 报错: `write_to` 结构不匹配/oneOf 不通过
- 你在同一个 run 里同时写了多个 intent key(例如同时 `sheetbook_sheet` + `sheetbook_append`)

修复:

- 同一个 run 的 `write_to` 下最多一个 intent key
- 需要多个写入动作时,拆为多个 runs(并按顺序排在 `workflow.runs` 中)

### 7) 输出路径冲突或共享资源路径被直接写入

症状:

- 运行期 fail-fast: 多个 nodes 写同一路径
- 或 workflow 已声明为共享输出资源的路径,却被某个 demand 直接写同一路径

修复:

- 要么每个 demand 输出到唯一路径
- 要么把共享输出收敛到 `workflow.resources.*` + `write_to` 的机制,避免多方直接写同一路径
