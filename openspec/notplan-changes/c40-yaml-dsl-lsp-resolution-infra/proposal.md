## Why

LSP server 当前已具备 diagnostics / hover / completion / definition 等基础能力，但存在几类结构性短板，在大型工程下尤为明显：

1. **单点结果、无排序**：definition 目前至多返回一个 location；当存在多个候选（例如 `module:obj.method` 的静态推断有多个 Klass 命中）时，用户只看到"第一个"，无法选择。
2. **无缓存、重复 IO**：每次 hover/completion 都重新读文件 + 解析 AST，大型 monorepo 下体感卡顿。
3. **失败不可解释**：解析失败时用户只看到"无结果"，无法知道"试了哪些 roots、选中了哪个模块文件、为何 rejected"。排障成本高。
4. **Quick Fix 模式不统一**：各 feature 各自实现 codeAction，没有统一的"诊断 → 修复建议"框架。

本提案聚焦：**加固 LSP server 的解析基础设施**，为后续 feature（c42 语法糖、c43 实体导航）提供可靠底座。

## Goals

- **G1：多候选排序**：所有"可产生多个定位点"的解析统一返回多 locations，并规定稳定排序规则。
- **G2：缓存与失效**：AST / YAML parse / 文件读取按 path + mtime 缓存，mtime 变化时失效。
- **G3：请求限流**：并发 LSP 请求（hover/completion/definition）共享 IO 队列，避免重复读同一文件。
- **G4：Resolution Trace**：解析过程输出结构化 trace（尝试了什么、选了什么、为何 rejected），供 diagnostics / hover / log 使用。
- **G5：Quick Fix 框架**：统一的 codeAction 注册模式：诊断 → 修复建议 → WorkspaceEdit/Command。

## Non-Goals

- 不引入新的语义 feature（`^<id>` / alias / preset 由 c42 负责；YAML ID 导航由 c43 负责）。
- 不引入 workspace-wide 全量索引（保持 on-demand 解析）。
- 不改变 LSP 协议层（继续使用 pygls 标准 capability 注册）。

## Proposal

### 1) 多候选 Location 与稳定排序

#### 现状

`textDocument/definition` 对 Python 引用返回单个 location（或空）。当静态推断产生多个候选时，只取第一个。

#### Expected Behavior

1) 所有"定位"类解析统一返回 `List[Location]`（可以为空）。
2) 排序规则（稳定、可测试）：
   - **P0（最优先）**：最接近真实实现的位置（例如 `Klass.method` 的 method 定义行）。
   - **P1**：声明点 / 构造点（例如 `obj = Klass()` 的赋值行）。
   - **P2**：import re-export / alias / stub / `TYPE_CHECKING` 块等"信息含量更低"的位置。
3) 同优先级内按文件路径字母序 → 行号排序。
4) 去重：同 URI + 同 range 合并为一个。

#### 接口变更

- core 解析函数签名从 `-> Optional[Location]` 改为 `-> List[Location]`。
- server 层直接透传（LSP spec 本身支持多 location）。

### 2) AST / YAML 解析缓存

#### 现状

每次 `resolve_reference` 都执行 `Path.read_text()` + `ast.parse()`，同一次 hover 内可能重复读同一文件。

#### Expected Behavior

1) 引入进程内缓存，key = `(path_str, mtime_ns)`。
2) 缓存内容：
   - `file_text: str`
   - `ast_tree: ast.AST`（Python 文件）
   - `yaml_data: Any`（YAML fragment 文件）
3) 失效策略：每次访问前比较 mtime；mtime 变化则丢弃并重新解析。
4) 容量上限：LRU，默认上限 128 个文件（可配置）。
5) 不跨 LSP session 持久化（进程重启即清空）。

#### Options & Trade-offs

- **进程内 dict + mtime（推荐）**：实现简单，无外部依赖，对单文件反复 hover/completion 场景收益最大。
- **SQLite / 文件缓存**：跨 session 持久化；收益有限但复杂度显著增加；暂不引入。

### 3) 请求限流

#### 现状

多个 hover/completion/definition 请求并发时，各自独立执行文件 IO，在大型 workspace 下可能出现 IO 抖动。

#### Expected Behavior

1) 共享 IO 队列：同一文件的读 + 解析在同一时刻只执行一次，后续请求 await 结果。
2) 对不同文件的请求可并行。
3) 实现方式：`asyncio.Lock` per path（或简单的 `dict[str, asyncio.Task]` 去重）。

#### 非目标

- 不做全局请求排队（LSP 请求本身由 pygls event loop 管理）。
- 不对 completion 做防抖（由 client 侧 `completionItem.resolve` 或 VSCode 自身的 debounce 负责）。

### 4) Resolution Trace（结构化诊断）

#### 现状

解析失败时返回空结果；用户和开发者都无从得知"为什么失败"。

#### Expected Behavior

1) 每次解析（无论成功/失败）产生一条 `ResolutionTrace`：
   ```
   @dataclass
   class ResolutionTrace:
       query: str              # 原始查询（如 "module:func"）
       steps: List[Step]       # 解析步骤
       result: List[Location]  # 最终结果（可为空）
   ```
   每个 `Step` 记录：
   - `action: str`（例如 "resolve_module"、"find_attribute"、"check_allow_roots"）
   - `input: str`
   - `output: str | None`
   - `rejected: bool`
   - `reason: str | None`（如果 rejected，说明原因）

2) Trace 的消费方式：
   - **Diagnostics**：当 result 为空时，从 trace 提取最后一步的 reason 生成 Diagnostic（severity: hint 或 warning）。
   - **Hover**：对"部分降级"的结果（例如只找到 P2 级别 location），在 hover 文本末尾附加 trace 摘要。
   - **Log**：DEBUG 级别输出完整 trace（供开发/排障）。

3) 不在 normal flow 下向用户暴露完整 trace（只在失败/降级时有选择地展示关键信息）。

### 5) Quick Fix 框架

#### 现状

codeAction 分散在各 feature handler 中，没有统一的"诊断 → 修复"注册模式。

#### Expected Behavior

1) 定义 `QuickFixProvider` 协议：
   ```python
   class QuickFixProvider:
       def can_fix(self, diagnostic: Diagnostic) -> bool: ...
       def fix(self, diagnostic: Diagnostic) -> CodeAction: ...
   ```
2) Server 维护一个 `List[QuickFixProvider]`，在 `textDocument/codeAction` 中按顺序匹配。
3) 每个 feature（Python ref、imports alias、preset 等）注册自己的 provider。
4) 所有 `CodeAction` 的 edit/command 必须是 workspace-scoped 且可撤销。

#### 与 c42 / c43 的关系

c42 的 "alias 未配置 → Quick Fix" 和 c43 的未来 Quick Fix 都注册为 provider 实例。本提案只提供框架，不注册具体 provider。

## Validation（fixture 覆盖）

- **Multi-location**：
  - Python ref 解析返回多个候选 → 验证排序符合 P0 > P1 > P2 规则。
  - 去重：同 URI + 同 range 只出现一次。
- **缓存**：
  - 同一文件连续 2 次 resolve → 第 2 次不触发 IO（mock 验证）。
  - 文件修改后 mtime 变化 → 缓存失效，重新解析。
- **限流**：
  - 并发 2 个请求查同一文件 → 只执行 1 次 IO。
- **Resolution trace**：
  - 解析成功 → trace 记录所有步骤。
  - 解析失败（模块不存在 / allow-roots 越界 / 符号未找到）→ trace 的最后一步标记 rejected + reason。
  - trace → Diagnostic 转换正确。
- **Quick Fix 框架**：
  - 注册一个 test provider → codeAction 返回对应的 CodeAction。
  - 未注册 provider 的 diagnostic → codeAction 不包含该修复。

## Impact（涉及模块）

- shared core：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/core.py`
  - 解析函数签名变更（单 location → 多 location）
  - 缓存模块新增
  - ResolutionTrace dataclass + trace 消费逻辑
- server：`packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/server.py`
  - codeAction handler 重构（provider 模式）
  - 限流中间件
- specs（后续转正时）：
  - `openspec/specs/yaml-dsl-lsp-server/spec.md`
