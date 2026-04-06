## Context

我们目前在 2 个位置分别实现了“这是不是 Scalim YAML DSL / 该按 demand 还是 workflow 处理”的判定：

- `extras/vscode-scalim/`：用于决定是否自动启动 LSP，以及单文件 schema 绑定（`yaml.schemas`）
- `packages/scalim-yaml-dsl-lsp/`：用于 server 侧决定是否发布 diagnostics/提供语义能力，以及选择 demand/workflow 的诊断边界

现状主要依赖启发式（schema modeline / `$import` / 顶层 key hint / 路径约定），这会带来：

- 与 schema（DSL 事实来源）产生漂移：DSL 演进时启发式需要手工同步
- 扩展与 server 判定不一致：可能出现“schema 绑定与 LSP 语义边界不一致”的体验
- 对非 DSL YAML 的污染风险：误触发 diagnostics / go-to-definition

与此同时，DSL 的 JSON schema（`src/scalim/dsl/by_yaml/schema/*.gen.json`）是生成物，天然包含“顶层必选字段 required”这一稳定信号：

- demand: `required=["name","main_source"]`
- workflow: `required=["workflow"]`

本变更将把 required 作为探测/分类的 SSOT 信号，并保留对“正在编写中的 YAML”的 permissive 降级策略。

## Goals / Non-Goals

**Goals:**
- 以 schema 顶层 `required` 作为 SSOT，统一 VSCode 扩展与 LSP server 的 DSL 探测与 demand/workflow 分类逻辑。
- 对未写全 required 的 YAML（新建/半成品）保留 permissive fallback：只要出现 DSL 专属语法特征，就仍然视为 DSL 以支持编辑体验（尤其是 go-to-definition/Quick Fix）。
- 性能可控：schema required 读取需缓存（进程内），避免每次请求重复 IO/JSON parse。

**Non-Goals:**
- 不引入白名单目录/allowlist 目录配置（用户遇到误触发可临时禁用扩展）。
- 不修改任何 `*.gen.*` 生成物；本变更仅“读取并使用” schema required。
- 不扩展新的 LSP 语义能力，仅调整 gating 与分类信号源。

## Decisions

### Decision 1: required keys 来自 schema JSON（而不是硬编码）

**选择**：从 `demand.gen.json` / `workflow.gen.json` 读取顶层 `required`，并在进程内缓存。

**理由**：
- required 是 schema 生成物内的稳定字段，天然与 DSL schema 演进同步
- 避免“代码硬编码 required”随时间漂移

**替代方案**：硬编码 required keys。  
**否决原因**：维护成本高、容易失配。

### Decision 2: DSL 探测采用 “required 优先 + DSL 专属特征 fallback”

**选择**：
- 若 YAML 根 mapping 满足 workflow required（`workflow` 存在）且其值为 mapping，则判定为 workflow DSL。
- 否则若满足 demand required（`name` 与 `main_source` 同时存在），判定为 demand DSL。
- 否则若出现 DSL 专属特征（如 `$import/$init_var`、`loader/call_by`、schema modeline 指向 scalim schema），判定为“可能是 DSL”（permissive）。
- 否则视为非 DSL，不启用 DSL 语义（避免污染）。

**理由**：
- workflow 的 required 过于宽（仅 `workflow`），增加 “值为 mapping” 的结构约束可显著降低误判。
- “required-only” 过于严格，会导致新建/半成品 YAML 无法触发语义能力；fallback 用 DSL 专属特征兜底。

**替代方案**：strict required-only。  
**否决原因**：对编辑体验不友好，且与 0-config 目标冲突。

### Decision 3: VSCode 扩展的 required 来源与降级策略

**选择**：
- 若已解析到 schemaPaths（来自 `scalim-cli yaml-dsl schema path`），扩展读取 schema JSON 的 required 进行分类并绑定单文件 schema。
- 若 schemaPaths 不可用（例如用户仅安装了 server 而没有 `scalim-cli`），扩展退化为现有的文本启发式（保持可用性）。

**理由**：扩展不应为了获取 required 而引入额外 provisioning/安装行为；同时仍可保持最佳努力的 0-config。

## Risks / Trade-offs

- [风险] workflow required 仅包含 `workflow`，仍可能与其他领域 YAML 冲突  
  → [缓解] 增加“值为 mapping”结构约束，并要求存在 DSL 专属特征时才能 permissive 启用。
- [风险] permissive fallback 仍可能误触发少量 YAML  
  → [缓解] fallback 仅使用 DSL 专属语法（`$import/$init_var`、`loader/call_by`、schema modeline）而非泛化 key（如 `workflow`）。
- [风险] IO/JSON parse 带来的性能损耗  
  → [缓解] 进程内缓存 required（LSP 侧可用 `functools.lru_cache`；扩展侧缓存到运行时内存并基于 mtime 判断是否需要刷新）。

