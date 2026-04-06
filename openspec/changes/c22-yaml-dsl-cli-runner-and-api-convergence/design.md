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
- 输出行为 v1 以“YAML 自带 outputs/resources”为主；若 YAML 不声明 outputs,CLI 给出明确错误并提示用 YAML 补齐或改用 Python `RunOverrides.*`。
  - 后续若确实需要 CLI 侧的动态输出覆盖,再引入受控的 `--csv-file ...` / `--xlsx-file ...` sugar（映射到 `RunOverrides.csv_file/xlsx_file_single_sheet`）,避免引入新的通用 overrides DSL。

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
- 旧长签名入口迁移到 `scalim.dsl.by_yaml.legacy_entrypoints`（或等价内部模块）以便内部回归/过渡,但不再作为推荐/稳定导入路径对外承诺。
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
- [兼容成本] 同时存在旧签名与新 options 入口。→ 缓解: 冻结旧入口不再扩展；文档只推荐新入口；提供迁移指南与示例回归。
- [测试面扩大] CLI runner 引入新的集成路径。→ 缓解: 复用现有 public-api suite/notebooks fixture,并新增少量 CLI e2e 测试（以 “能跑 + fail-fast 错误信息稳定” 为准）。

## Migration Plan

1) 实现 CLI runner（demand/workflow）v1: 仅支持 YAML 内声明 outputs/resources 的场景 + JSON 注入 init/template vars。
2) 引入 `options=` 风格 Python 入口,并在文档/示例中切换推荐用法。
3) 将旧长签名入口标记为冻结/legacy,只做兼容修复不再扩展（是否发出 warning 由维护策略决定）。
4) 需要时补充 CLI 的受控输出覆盖 sugar（`--csv-file/--xlsx-file`）以覆盖“YAML 不写 outputs”场景。

## Open Questions

- CLI v1 是否需要支持 `RunOverrides.csv_file/xlsx_file_single_sheet` 的映射（用 flags 表达）,还是先强制要求 YAML 声明 outputs/resources？
- `scalim.yaml yaml_dsl.runner.*` 的字段集合是否要与 `RunOptions` 完全同构,还是只承载最小子集（推荐最小子集）？
- 旧长签名入口是否立即发出 deprecation warning,以及 warning 是否会影响下游日志治理？
