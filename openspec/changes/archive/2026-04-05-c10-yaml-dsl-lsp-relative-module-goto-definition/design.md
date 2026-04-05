## Context

YAML DSL 的 Python 引用语法支持相对模块引用（前导 `.`），并且在 runtime resolver 里已经具备将其规范化为绝对模块的能力。
但 editor semantics core (`packages/scalim-yaml-dsl-lsp`) 在 `resolve_python_definition()` 中对 `module_path.startswith(".")` 直接降级为 warning 并返回空 locations，
导致 LSP server 的 definition/hover/completion 在常见写法下不可用。

LSP 侧的约束：

- 静态解析：仅允许文件系统读取 + AST 解析；不得执行用户代码
- 无副作用：不得改写进程级全局（例如 `sys.path`）
- 解析失败必须可诊断降级：返回空结果 + warnings，不得 crash

## Goals / Non-Goals

**Goals:**
- 支持 `.mod` / `..mod` 等相对模块引用的 go-to-definition / hover / completion
- 解析规则与 runtime 的相对模块规范化一致（前导点表示向上层级）
- 失败时给出明确 warnings（缺少 base、越界等），并保持 deterministic 行为

**Non-Goals:**
- 不尝试在 editor 侧复刻完整的 Python import 语义（例如 site-packages/环境变量 `PYTHONPATH`）
- 不引入任何 `sys.path` 读写/注入，也不引入执行用户代码的 fallback
- 不在本变更内引入新的 schema 字段或改变 YAML DSL 的运行时语义

## Decisions

### 1) `base_module_path` 的推导来源：`yaml_path` + `python_roots`

在 editor/LSP 语境下，我们已经有 project discovery 的 `python_roots`（来自 `scalim.yaml`）。
它们等价于“静态 import 搜索根目录集合”，可用来替代 runtime 中 `sys.path` 的角色。

实现策略：
- 使用 `yaml_path.parent` 作为 `yaml_dir`
- 选择满足 `yaml_dir` 位于某个 `python_root` 之下的候选 roots
- 将 `yaml_dir.relative_to(python_root)` 的目录段用 `.` 拼接为 `base_module_path`
- 只接受目录段均为合法 Python 标识符（`isidentifier()`）的候选
- 在多个候选同时存在时，选择“模块路径段最多”的候选（更符合“越深越具体”的直觉），并用稳定的 tie-break 保证 deterministic

若 `yaml_dir` 不在任何 `python_roots` 下，则无法推导 base：
- definition/hover/completion 返回空结果
- warnings 提示：补充 `yaml_dsl.editor.python_roots` 或改用绝对引用

### 2) 相对模块的规范化发生在 core（而非 server）

为保证 editor semantics SSOT：
- 相对模块解析与错误语义统一实现在 `packages/scalim-yaml-dsl-lsp/scalim_yaml_dsl_lsp/core.py`
- LSP server 仅负责把 document 的 file path 传入 core（从 URI 转换）

这避免 server 层复制规则，并保持未来其它 editor 集成的一致性。

### 3) API 变更：为 Python 引用能力增加 `anchor_path`

为了在 core 内完成相对模块规范化，core 需要知道“当前 YAML 的入口路径”：
- 在 `resolve_python_definition()` / `hover_python_reference()` / `complete_python_reference()` 增加可选参数 `anchor_path`
- 绝对模块引用场景不依赖该参数；仅当 module_path 以 `.` 开头时才需要

LSP server 调用时传入 `anchor_path=_uri_to_path(uri)`。

### 4) Warnings 口径

相对模块引用失败的 warnings 需要可诊断且可行动：
- base 缺失：明确指出 `anchor_path` 与 `python_roots` 的不匹配，并提示修复手段
- 越界：指出 dot-count 与 base 的层级不匹配
- 成功规范化时不强制输出 warnings（避免噪声）；仅在 debug log 中输出（如需要）

## Risks / Trade-offs

- [Ambiguity] YAML 目录可能同时被多个 `python_roots` 覆盖 → 通过“最长模块路径 + 稳定 tie-break”确保 deterministic，并在必要时提示调整 `python_roots` 顺序/范围。
- [Namespace packages] 目录缺少 `__init__.py` 仍可能是 namespace package → core 的模块定位仍走 `PathFinder.find_spec(..., path=[...])`，不依赖 `__init__.py`，保持现状。
- [Behavior drift] editor 侧相对模块规则与 runtime 不一致 → 复用相同的点数/层级算法，并以单测覆盖关键案例减少漂移风险。
