## Context

PRD：`.tmp/prd/c0-yaml-python-ref-sync.md` 希望解决一个长期痛点：YAML DSL 通过 `loader:` / `call_by:` 等字段引用 Python 可调用对象，但这些引用对 Python 生态是“不可见”的——重构/重命名会静默破坏，且 LSP/静态分析易把被 YAML 使用的函数标记为未使用。

代码现状（可行性走读结论，细节以实现为准）：

- YAML DSL LSP server 位于 `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/`：
  - `server.py` 已具备 per-document state + debounce `_DID_CHANGE_DEBOUNCE_SECS` + pending task cancel 的更新模式，适合作为“增量引用同步”的调度器。
  - `cache.py` 已具备 mtime-keyed LRU cache（text/AST/YAML mapping），适合用于 YAML/Python 解析的性能兜底。
  - `core.py` 已具备 Python 引用静态解析与定位（`resolve_python_definition()`）以及对 `call_by` head 的 cursor extraction 支持（`cursor_extraction.py` 内 `_parse_call_by_head()`）。
- 项目配置 `scalim.yaml` 的解析与 schema SSOT 在 `src/scalim/`（Python 3.6 runtime boundary）：
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/project_config.py` 负责解析/校验 `yaml_dsl.lsp.*`（未知字段 fail-fast）。
  - `src/scalim/dsl/yaml_dsl/schema_dsl/models/scalim_yaml.py` 为 `scalim.yaml` schema SSOT；生成物为 `src/scalim/dsl/yaml_dsl/schema/scalim_yaml.gen.json`，通过 `just gen-yaml-dsl-schema` 刷新（禁止手工编辑）。

因此该 PRD 的核心方案在工程上可落地：绝大多数“静态解析 + 缓存 + 防抖”基础设施已存在，需要新增的是“全文件引用扫描 + 索引持久化 + 一致性检查/修复 UX + 工件生成”。

## Goals / Non-Goals

**Goals:**

- 建立一套静态、可增量更新的 YAML→Python 引用索引（symbol → YAML locations），并落盘到项目级生成目录（默认 `.scalim/`）。
- 在 LSP 侧提供可跨编辑器复用的能力：
  - 查询某个 YAML 文档的引用列表（用于“在 YAML 中使用”/QuickPick 等 UI）。
  - 一致性检查：当引用的 Python 符号不可解析/已消失时，产出可诊断结果，并可选发布 LSP diagnostics + Quick Fix。
- 提供 CLI 自动化入口（CI / pre-commit / 脚本化消费），以“脱离编辑器也能跑”的方式落地一致性检查与工件刷新。
- 明确 SSOT/生成物边界与 drift gate：
  - `scalim.yaml` 仍由 `schema_dsl` 作为 SSOT 生成；引用同步新增的配置必须进入该链路。
  - `.scalim/` 为生成目录，必须 gitignore，且不应进入仓库提交。

**Non-Goals:**

- 不尝试让 Python LSP 的 rename 自动改写 YAML 字符串（该能力属于跨语言重构，MVP 以“检测 + 提示 + Quick Fix/CLI 修复”为主）。
- 不引入 DSL 多版本/并行 parser（遵循 YAML DSL 主线原则）。
- 不在 LSP server 中执行用户代码；Python 解析一律 filesystem + AST（复用既有实现）。
- 不在本变更内交付 JetBrains 原生插件（可通过通用 LSP 方法 + 诊断先覆盖；IDE 侧专属 UI 作为后续增量）。

## Decisions

1. **生成目录：默认使用 `<project_root>/.scalim/`（gitignore）**
   - 目录下包含：
     - `index/refs.gen.json`：引用索引（增量更新）。
     - `stubs/` 或 `markers/`：引用标记工件（用于降低“未使用”误报、提供可追踪来源；具体形式见下方决策）。
     - `diagnostics/`：一致性检查输出（可选落盘，便于 UI/CLI 消费）。
   - 写入必须原子化（临时文件 + rename），并对并发写入做锁（文件锁或进程内锁）。

2. **引用索引：以“符号为主键 + YAML 文件 mtime”为核心的紧凑 JSON**
   - 主键建议使用 `"{module_path}:{entry_attr}"`（与既有引用语法一致；`call_by` 取 head）。
   - `yaml_files` 记录每个 YAML 的 `mtime_ns` 与其引用列表，用于快速增量失效与回收旧引用。
   - 版本化（`version`）以支持后续结构演进。

3. **扫描策略：复用 YAML mapping loader + 遍历 dict/list，抓取 `loader`/`call_by`/`retry.should_retry`**
   - YAML 解析：优先复用 `scalim.dsl.yaml_dsl.compiler_frontend.lsp_support.load_yaml_mapping_text(...)`（与现有 LSP diagnostics 对齐）。
   - `call_by` 解析：复用 cursor extraction 的 head 规则（`(... )` 前缀 trim），并允许 multiline block scalar。
   - 位置（line/column）策略：
     - 优先使用现有 `locations`（若 loader 返回该信息）定位 key/value。
     - 无法精确定位时降级到“文件级 + best-effort 行号”（不得阻塞或 crash）。

4. **更新触发：在 LSP `didOpen/didChange` 路径中做防抖增量更新；全量扫描交给 CLI**
   - LSP server 已有 `_DID_CHANGE_DEBOUNCE_SECS` 与 pending task cancel 模式，可直接复用以避免编辑期抖动。
   - LSP 侧只对“当前打开/变更的 YAML 文档”做增量更新；避免启动时扫描整个仓库导致卡顿。
   - 全量构建/回收（遍历 yaml_roots）通过 CLI 执行，适用于 CI 或手动刷新。

5. **一致性检查：以索引为输入，复用 `resolve_python_definition()` 做静态解析**
   - 结果输出为结构化列表（broken refs / unresolved refs / optional suggested fix）。
   - “建议修复”策略 MVP 可先用简单启发式（如 `difflib.get_close_matches` 或同模块内近似符号名）；更强的重命名追踪留作后续。

6. **引用标记工件：先实现“可被 IDE 消费”的最小形态，并允许后续切换**
   - PRD 倾向生成 `.pyi` stubs；但不同 Python 工具链对 dot-dir、stubPath 的默认行为存在不确定性。
   - MVP 方案建议：
     - 生成 `.pyi` stubs（镜像包结构，包含 `# pragma: scalim-yaml-ref` + YAML 引用明细注释）。
     - 同时提供 VSCode 扩展/文档建议（把 `.scalim/stubs` 接入到 Python analysis 的 stubPath/extraPaths），确保“跨 IDE”可落地。
   - 备选方案（若 `.pyi` 在某些 IDE 不生效）：生成 `.py` marker 模块（仅 import 引用目标，不执行），以提升 rename/find-references 的可见性。

## Risks / Trade-offs

- **[Python 工具链默认不扫描 dot 目录 / 不自动加载 stubPath]** → Mitigation：提供明确的 editor integration 指南；VSCode 扩展优先做自动配置；必要时引入 `.py` marker 备选。
- **[编辑期全量扫描导致卡顿]** → Mitigation：LSP 侧只增量扫描打开文档；全量扫描放到 CLI；并在实现中使用 semaphore + batch/cooldown。
- **[YAML 位置信息不稳定/不精确]** → Mitigation：以 best-effort 为准；diagnostics 必须可降级到文件级位置，同时在索引中保留 `yaml_path` 便于定位。
- **[索引并发写入/损坏]** → Mitigation：原子写入 + lock；读取端容错（JSONDecodeError → 空索引）。

## Migration Plan

- 引入 `yaml_dsl.lsp.reference_sync` 默认 enabled 但对缺失目录完全降级
- `.scalim/` 写入前确保目录存在且可写；失败时仅输出 warning，不影响既有 LSP 核心能力（definition/hover/diagnostics）。
- CLI 与 LSP 共用同一套索引/扫描实现，逐步将“最佳实践”沉淀到文档与 fixtures。

## Open Questions

- `scalim.yaml` 配置面最终落点：`yaml_dsl.lsp.reference_sync` vs 更细粒度拆分（例如 `index`/`stubs`/`diagnostics` 分段）。
> `yaml_dsl.lsp.reference_sync` 

- `.pyi` stubs 的“跨 IDE 零配置”是否可达成；若不可达成，marker 模块应采用何种目录/命名以兼容 `just qa`（ruff）与 Python LSP 同时稳定。
> 可达成默认生成这个到 .scalim/ 中 然后我们开发项目中的相关配置要忽略掉这种自动生成的组件

- Python 变更触发机制：是否引入 LSP 的 `workspace/didChangeWatchedFiles`（由 VSCode 扩展配置 watcher）以提升“重命名后即时提示”的体验。
> 需要 这个机制很好 用于快捷提醒 仅vscode 提供 但是 lsp core 负责支持 并且建议其他接入比如可能的 jetbrains ide 等要后续接入这个特性
