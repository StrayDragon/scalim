## Context

- 代码基线:
  - shared core: `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`
  - server: `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`
  - cursor extraction: `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/cursor_extraction.py`
- 当前能力已覆盖 diagnostics / hover / completion / definition 的基础闭环，但在大型 workspace 下仍有结构性短板:
  - 重复 IO/解析：`ast.parse`、fragment YAML 读取/解析会在 hover/completion/definition 中反复发生
  - 事件循环阻塞：server handler 里直接执行同步 IO/parse，容易卡顿
  - 多候选不稳定：definition 可能产生多 `Location`，但缺少统一的“稳定排序/去重”规则
  - 失败不可诊断：主要依赖 `warnings: Tuple[str, ...]`，缺少结构化“解析链路”
  - Quick Fix 分散：`textDocument/codeAction` 逻辑堆叠在 handler 内，不利于后续扩展

约束/护栏:
- 全程静态：只读文件 + `ast.parse` + YAML parse；不执行用户代码，不 shell-out。
- 不引入 workspace-wide 全量索引：保持 on-demand + cache。
- anchor YAML（当前打开文档）的语义 SSOT 必须来自 LSP 内存态文本，避免 mtime/磁盘不一致。

## Goals / Non-Goals

**Goals:**
- 统一“解析 → 多候选 locations → 稳定排序/去重”的输出模型（definition/hover/diagnostics/日志共用）。
- 引入 `(path, mtime_ns)` 维度的 AST/YAML/文本缓存（LRU + 容量上限）。
- 并发请求去重：同文件同版本的读/parse 只做一次（in-flight dedup）。
- 引入 `ResolutionTrace` 作为第一等产物，用于:
  - definition 失败/降级解释
  - diagnostics（hint/warn 的失败原因）
  - VSCode 扩展“诊断包”收集
- 将 Quick Fix 收敛为 provider/registry 模式，为后续 `yaml-dsl-lsp-sugar-support` / `yaml-dsl-entity-navigation` / `yaml-dsl-editor-effective-expansion` 等变更提供统一入口。

**Non-Goals:**
- 不新增 `^<id>` / imports alias / preset / YAML entity navigation 等语义（由后续 changes 负责）。
- 不做跨 session 持久化缓存（进程重启即清空）。
- 不改变 LSP 协议层（继续使用标准 request + `workspace/executeCommand`）。

## Decisions

### 1) 结构化链路: `ResolutionTrace`

- 在 shared core 新增:
  - `ResolutionTrace(query, steps, locations, warnings)`
  - `ResolutionStep(action, input, output, rejected, reason)`
- trace 产出策略:
  - 正常 definition 请求默认不把完整 trace 返回给 client（避免噪声），但 server 内可记录 debug 日志
  - 当解析失败或降级时（例如只有 fallback location），hover/command 可显示 trace 摘要
  - VSCode 诊断包通过 command 获取最近一次 trace（若可用）

### 2) 多候选排序与去重（稳定、可测试）

- internal 统一用 `LocationCandidate` 表达候选，包含:
  - `priority`: `P0_IMPL` / `P1_DECL_OR_CONSTRUCT` / `P2_FALLBACK`
  - `file_path` + `range`
  - `label`（仅用于 trace/hover）
- 排序键（稳定）:
  - `(priority, file_path, start_line, start_col)`
- 去重键:
  - `(file_path, start_line, start_col, end_line, end_col)`
- 将现有 python resolver 中的返回列表映射到优先级（统一规则）:
  - method/function/class 的真实定义点 → P0
  - obj 赋值/构造点、class 声明点 → P1
  - import/re-export/alias/兜底绑定点 → P2

### 3) 缓存: `(path, mtime_ns)` LRU（只用于磁盘依赖）

- 在 shared core 新增缓存模块（例如 `scalim_yaml_dsl_lsp/cache.py`），提供:
  - `read_text_cached(path, mtime_ns) -> str`
  - `parse_python_ast_cached(path, mtime_ns) -> ast.Module`
  - `load_yaml_mapping_cached(path, mtime_ns) -> (mapping, location_index)`
- key 统一为 `(str(path), mtime_ns)`：
  - mtime 变化自动生成新 key，旧条目由 LRU 淘汰
- 默认 `maxsize=128`（允许通过 server 初始化参数或环境变量覆盖）
- anchor YAML 文本不走 mtime cache：
  - 由 `server.py` 的 `state[uri].text` 作为 SSOT
  - cache 主要覆盖 Python 模块文件与 import fragment 文件

### 4) 并发去重 + 事件循环保护

- server 侧维护 `inflight: dict[str, asyncio.Task]`:
  - key 例如 `("ast", path, mtime_ns)` / `("yaml", path, mtime_ns)`
  - 若已有 task，后续请求直接 await
- 对重 IO/parse 的路径使用 `asyncio.to_thread(...)`:
  - 避免阻塞 pygls event loop
  - 统一用 `_safe_*` wrapper 捕获异常并降级为“空结果 + 诊断信息”

### 5) Quick Fix provider/registry（可扩展）

- 在 server 引入:
  - `QuickFixProvider.can_fix(ctx, diagnostic) -> bool`
  - `QuickFixProvider.provide(ctx, diagnostic) -> List[CodeAction]`
  - `QuickFixRegistry` 维护有序 providers（稳定顺序=稳定 UX）
- 将现有 quick fixes 迁移为 providers:
  - 创建最小 `scalim.yaml`
  - 修复 `yaml_dsl.import_roots`（最小/宽松）
  - 修复 `yaml_dsl.lsp.python_roots`（最小/宽松）
  - 解释 Python 引用解析失败（展示 trace/摘要）
- 为后续 changes 预留扩展位:
  - alias/preset/builtin 的修复（`yaml-dsl-lsp-sugar-support`）
  - unknown entity id 的提示/修复（`yaml-dsl-entity-navigation`）
  - imports 越界/展开失败的更精准修复（`yaml-dsl-editor-effective-expansion`）

### 6) 文档/生成边界与 drift gates（必须）

- 手工编辑范围:
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/**`
  - （如需）`src/scalim/dsl/yaml_dsl/_internal/**` 内的 SSOT 解析/展开逻辑
- 禁止手改:
  - 任意 `*.gen.*`
  - 任意 `<!-- BEGIN AUTOGEN:* -->` / `<!-- END AUTOGEN:* -->` 区块内部
- Drift gates（本变更落地前后都应通过）:
  - `just qa`
  - `just openspec-check`

## Risks / Trade-offs

- [缓存与未保存编辑不一致] → anchor 文档只读 LSP 内存态；缓存仅用于磁盘依赖（Python 模块 / fragment YAML）。
- [线程化引入竞态/难排障] → 缓存函数保持纯函数 + 只读 IO；in-flight key 严格包含 mtime/version；trace 记录关键 rejected reason。
- [排序规则改变用户感知] → 用 fixtures 覆盖主要形态（`class.method`、`obj.method`、import re-export），并保证排序稳定。
- [trace 体积/隐私] → trace 不包含 YAML 正文；只记录动作/路径/原因；必要时裁剪为“最后 N 步摘要”。
