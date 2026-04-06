## Context

本变更聚焦两个面向用户的入口面收敛:

1) **YAML-first 使用闭环不足**（CLI 不能 run）  
当前 `scalim-cli yaml-dsl` 主要提供:
- `validate` / `schema validate` / `schema show|path`
- `upsert-lsp-comment`

实现入口见 `src/scalim/cli/yaml_dsl.py`。它能帮助“写 YAML/校验 YAML/编辑器补全”,但无法直接把 `demand.yaml` 或 `workflow.yaml` 跑起来。

2) **Python 入口参数爆炸**（难以演进、用户必须关心内部细节）  
YAML DSL 的官方 Python 入口在 `src/scalim/dsl/by_yaml/runtime/entrypoints.py`:
- `run(yaml_path, *, allowed_modules, allowed_functions, resolver_trusted_mode, components, sink, overrides, guardrails, loader_retry, batch_size, ... )`
- `compile(...)`

这些函数内部会把参数组装成 `RunOptions`（`src/scalim/dsl/by_yaml/runtime/contracts.py`）再进入编译链路。但对用户来说,入口签名本身就已经成了“必须理解的大对象”,并且未来每新增一个运行期 knob 都会继续推高学习成本和维护成本。

约束与现实边界:
- 运行时需兼容 Python 3.6（核心运行时代码不使用 `from __future__ import annotations` 等）。
- 安全边界为硬约束: `allowed_modules/allowed_functions` 为空会 fail-fast（见 `src/scalim/dsl/by_yaml/runtime/compiler.py::_ensure_allowlist`）。
- 文档/示例必须以**当前代码实现**为事实来源；spec 与旧文档只能作为参考,不能反推实现。

## Goals / Non-Goals

**Goals:**
- 提供 YAML-first 的官方运行入口（CLI）,让“写 YAML → 校验 → 运行”成为闭环,且不要求用户写 Python wrapper。
- 让 Python 侧的 YAML 运行入口从“长签名函数”收敛为“稳定对象契约”,避免继续扩大公开签名。
- 保持 `YAML = authoring`、运行期策略仍由 Python/CLI 注入（不把 allowlist/并行/重试/护栏等塞回 demand YAML）。
- CLI 与 Python 入口共享同一套核心契约/实现（尽量复用 `RunOptions`/`RunOverrides` 以及现有 compiler/run_ir 链路）。

**Non-Goals:**
- 不引入 `dsl_version` 或并行 parser/validator/schema。
- 不把 workflow 扩张成“imports/片段组合系统”。
- 不新增 Web editor（仓库已明确转向 LSP/IDE 集成）。
- 不放宽安全边界（不会提供“默认 allow all imports”的便捷模式）。

## Decisions

### Decision 1: 新增 CLI runner（`scalim-cli yaml-dsl run` / `workflow run`）

**Before（现状）**
- 用户想运行 `demand.yaml` 必须写 Python:

```python
from scalim.dsl.by_yaml import RunOverrides, run

result = run(
    "path/to/demand.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    overrides=RunOverrides.csv_file(output_path="./out.csv", fields=["order_id"]),
    init_vars={"end_dt": "..."},
)
```

**After（目标）**
- 支持直接:

```bash
scalim-cli yaml-dsl run path/to/demand.yaml \
  --allowed-module myapp.loaders \
  --init-vars-json path/to/init_vars.json
```

以及 workflow:

```bash
scalim-cli yaml-dsl workflow run path/to/workflow.yaml \
  --allowed-module myapp.loaders \
  --init-vars-json path/to/init_vars.json
```

**关键约束（与当前实现一致）**
- allowlist 仍然必须显式提供（来自 CLI flags 或项目配置）,否则 fail-fast。
- `allowed_yaml_roots`、`template_vars/template_sandbox`、`parallel_mode/max_workers` 等运行期参数一律属于 CLI/Python 注入面,不进入 demand YAML。

**落地方案（推荐）**
- 在 `src/scalim/cli/yaml_dsl.py` 增加两个子命令:
  - `yaml-dsl run`
  - `yaml-dsl workflow run`
- CLI runner 内部直接复用现有入口:
  - demand: `scalim.dsl.by_yaml.run(...)`
  - workflow: `scalim.dsl.by_yaml.run_workflow(...)`
- `init_vars/template_vars` 使用 JSON 文件注入作为 v1（避免在 CLI 侧发明半套 YAML/表达式语法）。
  - `--init-vars-json <path>`（mapping）
  - `--template-vars-json <path>`（mapping）
- 输出行为 v1 以“**能跑就跑**”为主:
  - 若 YAML 声明了 `resources/outputs`（或 `workflow.resources.*` / demand 的 `resources/outputs`），则按声明写出文件。
  - 若 YAML **未声明任何 outputs**，仍然允许运行（运行时会走 `NullSink` 默认策略，不写文件、不保留数据），CLI 只输出“执行摘要”（例如 `total_rows/duration/output_path/outputs`）并提示用户如何补齐 outputs 或改用 Python `RunOverrides.*`/自定义 sink。
  - v1 **不提供** CLI 侧通用输出覆写 DSL；如未来确有需要，仅引入极少数受控 sugar（例如 `--csv-file/--xlsx-file` 映射到 `RunOverrides.csv_file/xlsx_file_single_sheet`），避免参数爆炸。

**替代方案与取舍**
- 方案 A（全靠 flags）: CLI 每次都要求传完整 allowlist/roots/模板/并行参数。优点是实现简单；缺点是体验差、难以复现、脚本参数爆炸。
- 方案 B（推荐,项目默认 + flags 覆盖）: 从 `scalim.yaml` 读取项目默认（见 Decision 2）。优点是直觉、易复现；代价是需要扩展 `scalim.yaml` schema 与解析。

### Decision 2: 扩展 `scalim.yaml` 承载 runner 默认值（不污染 demand YAML）

**Before（现状）**
`scalim.yaml`（`src/scalim/dsl/by_yaml/_internal/config_parsing/project_config.py`）目前主要承载:
- imports 相关: `import_aliases` / `import_allowed_roots`
- editor 相关: `editor.python_roots` / `kind_overrides`

**After（目标）**
新增可选段落（示意,最终以实现为准）:

```yaml
# scalim.yaml
yaml_dsl:
  runner:
    allowed_modules: ["myapp.loaders"]
    allowed_functions: []
    allowed_yaml_roots: ["./shared_yaml"]
    template_sandbox: "safe"
    parallel_mode: "seq"
    max_workers: 0
```

取舍说明:
- 这里放的是“项目级默认运行策略”,属于 CLI/Python 注入面,不改变 demand YAML 的 authoring surface。
- 安全边界不变: 没有 allowlist 默认值时仍 fail-fast。

### Decision 3: Python 入口收敛为 options-object（停止参数膨胀）

**Before（现状）**
用户侧常见写法是直接调用长签名:

```python
from scalim.dsl.by_yaml import run

_ = run(
    "path/to/demand.yaml",
    allowed_modules=frozenset(["myapp.loaders"]),
    parallel_mode="adaptive",
    max_workers=8,
    template_vars={"dt": "2026-04-06"},
    rendered_yaml_max_len=200_000,
)
```

**After（目标）**
对外提供稳定入口:

```python
from scalim.dsl.by_yaml import RunOptions, run

options = RunOptions(
    allowed_modules=frozenset(["myapp.loaders"]),
    parallel_mode="adaptive",
    max_workers=8,
    template_vars={"dt": "2026-04-06"},
)
_ = run("path/to/demand.yaml", options=options)
```

**推荐策略（一步到位,避免长期兼容负担）**
- 将 `scalim.dsl.by_yaml.run/compile` 收敛为 **options-object 唯一入口**（breaking）。
- 不保留旧长签名入口（不引入兼容层）,仓库内所有调用点与用户材料一次性升级到新写法。
- 仓库内所有用户材料（docs/notebooks/skills）一律升级到新写法,并通过 gate 防止回退到旧写法。

这么做的收益是:
- 公共 API 从“参数集合”变成“对象契约”,新增能力不会继续扩张公开签名。
- 维护者可以更自由地调整/重排 knobs（在 `RunOptions` 内做新增/拆分/分组）,而不被旧签名绑死。

**替代方案（更温和,但会长期背负双入口）**
- 新增 `run(..., options=...)` 同时保留旧参数列表,并冻结旧入口不再扩展。
- 优点: 下游迁移压力小。
- 缺点: 长期存在两套入口,文档/示例/支持成本上升,并且旧入口仍会被误用形成隐式依赖。

## Risks / Trade-offs

- [安全误用] CLI runner 让“运行 YAML”更容易,也更容易被误用为“任意执行”。→ 缓解: 仍强制 allowlist；默认严格；任何“放宽模式”只允许在显式开关下启用并强告警。
- [配置分散] runner 默认值进 `scalim.yaml` 会让配置面变大。→ 缓解: 只放“运行时默认值”,并保持字段集合小而确定；复杂覆写仍通过 CLI flags 或 Python 注入。
- [破坏性升级] `run/compile` 从长签名收敛为 options-object 唯一入口会导致下游需要迁移。→ 缓解: 仓库内用户材料一次性升级；提供明确的“前后对照”示例与迁移说明；用 gate 阻止旧写法回流。
- [测试面扩大] CLI runner 引入新的集成路径。→ 缓解: 复用现有 public-api suite/notebooks fixture,并新增少量 CLI e2e 测试（以 “能跑 + fail-fast 错误信息稳定” 为准）。

## Migration Plan

1) 实现 CLI runner（demand/workflow）v1: 允许无 outputs 的 YAML 也能运行（不落盘,仅摘要）+ JSON 注入 init/template vars。
2) 引入 `options=` 风格 Python 入口,并在文档/示例中切换推荐用法。
3) 破坏性移除旧长签名入口,将仓库内所有用户材料（docs/notebooks/skills）一步到位升级到 options-object 新写法。
4) 若未来确实需要 CLI 的受控输出覆盖 sugar（`--csv-file/--xlsx-file`），仅作为增量能力引入（不作为 v1 必需）。

## Resolved Notes (2026-04-07)

- CLI runner v1 支持“无 outputs 也能跑”（不落盘,仅摘要）；v1 不引入输出覆写 flags。
- `scalim.yaml yaml_dsl.runner.*` 只承载最小子集（不追求与 `RunOptions` 同构）。
- `run/compile` 一步到位收敛为 options-object 唯一入口；仓库内用户材料同步升级，避免长期双入口维护成本。
