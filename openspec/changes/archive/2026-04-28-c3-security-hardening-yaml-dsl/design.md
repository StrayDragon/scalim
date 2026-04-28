## Context

- S-1 位置: `src/scalim/dsl/yaml_dsl/runtime/references.py` 中 class-style 引用解析会逐级 `getattr(obj, attr_name)` 遍历属性链。
  - 当前安全检查主要在 `SecurePythonReferenceResolver._security_check(reference)` 完成(基于“引用字符串”的 denylist)。
  - 但属性遍历本身缺少逐级 denylist 防御,属于 defense-in-depth 缺口: 一旦未来出现绕过 `_security_check` 的路径或子类复用基类解析逻辑,可能形成“trusted 模式下更松”的空窗。

- S-3 位置: `src/scalim/dsl/yaml_dsl/_internal/config_parsing/project_config.py` 中 `_resolve_dir_allow_external` 用于解析 `scalim.yaml yaml_dsl.lsp.python_roots`。
  - 该函数允许 `(project_root / raw).resolve(...)` 后不做 `relative_to(project_root)` 校验。
  - 相对路径可通过 `../` 逃逸到 project_root 外。

## Goals / Non-Goals

Goals:
- Resolver 属性遍历路径具备逐级 denylist 防御(即使上游校验未来变动,仍尽量不出现“裸 getattr 链”)。
- LSP `python_roots` 保持 dev-only 的最小校验: 对解析后不可用的路径输出 warning 并忽略,避免单个无效项导致项目配置加载失败;允许 external roots,不再将“禁止相对路径逃逸 project_root”作为硬约束。

Non-Goals:
- 不改变 allowlist/trusted-mode 的整体策略(仍由显式门控与 warning 约束)。
- 不把 LSP python_roots 变成“完全禁止外部路径”(仍允许 absolute external)。

## Decisions

1. Secure resolver 逐级遍历校验
- 在 `SecurePythonReferenceResolver` 中覆盖/增强 class-style 解析过程:
  - 在每一步 `getattr` 前对 `attr_name` 做 denylist 检查(至少覆盖 `DANGEROUS_FUNCTIONS` 与 `__`/`lambda` 模式)
  - 对 dotted-style 入口同样做一致检查
- 目标是 defense-in-depth: 即使未来 `_security_check` 被重构/拆分,属性遍历本身仍是安全的。

2. LSP python_roots 的路径语义
- 若配置值为绝对路径: 允许(前提: 存在且为目录)。
- 若配置值为相对路径: 以 `project_root` 为基准解析;解析后允许在 `project_root` 外(不做 fail-fast)。
- 若 python_root 为空/空白字符串,或解析后路径不存在/不是目录: MUST 输出 warning,并且 MUST 忽略该项(不得导致项目配置加载失败)。
- 错误/警告信息应包含 raw/project_root/resolved,便于诊断。

## Risks / Trade-offs

- [风险] `python_roots` 允许 external roots,可能导致误配置扫描到非预期目录。
  - 缓解: 若需要,后续可加“warn on escape”的弱约束;但不做硬限制。

- [风险] resolver 逐级校验可能与上游 `_security_check` 形成重复。
  - 缓解: 这是刻意的 defense-in-depth;实现应保持轻量,避免引入额外 import/复杂度。

## Migration Plan

- 对 LSP 用户: 无强制迁移;相对路径仍按 `project_root` 解析,external roots 允许。
- 对 resolver 用户: 无迁移(仅增强安全检查)。

## Open Questions

- 是否要增加 “relative path resolves outside project_root 时输出 warning” 的弱约束?
  - 当前倾向: 本变更先保持最小校验以避免 LSP 噪音,仅在该设置在真实逻辑不可执行(不存在/非目录)时输出 warning 并忽略。
