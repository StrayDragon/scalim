## Why

`YAML DSL` 的安全边界主要依赖:
- allowlist/trusted-mode 的显式门控
- Python 引用解析器的 denylist(危险模块/函数)
- 路径解析的“within roots”校验

`_REPORT.md` 中的 S-1/S-3 都属于 Low 级别,但它们会形成长期的审计噪音与潜在的误用空间:
- S-1: 在 resolver trusted 模式下,属性链遍历的实现缺少逐级的危险函数防御(依赖上游校验,防御深度不足)
- S-3: `scalim.yaml` 的 `yaml_dsl.lsp.python_roots` 解析允许相对路径通过 `../` 逃逸出 `project_root` (虽然仅用于 LSP,仍应避免“意外外部访问”)

我们希望在不改变主要功能的前提下,把这两处做成“默认更安全、更难误用”的实现。

## What Changes

- Resolver 防御深度:
  - 在实际属性遍历(`getattr` 链)过程中逐级校验 denylist(危险函数/模式),避免未来某条路径绕过上游 `_security_check` 时出现空窗。
- LSP project config 路径解析(放松约束;dev-only):
  - `yaml_dsl.lsp.python_roots` 仅用于开发时的 LSP/编辑器静态解析搜索路径,不应被当作安全边界。
  - 系统仅做最小校验:
    - 允许 external roots,不再对“相对路径是否逃逸 project_root”做 fail-fast。
    - 当某个 python_root 不可用(空字符串/空白字符串,或解析后不存在/不是目录)时,系统仅输出 warning 并忽略该项,不得因为该项导致项目配置加载失败。
- 补齐回归测试与错误信息断言,确保诊断可复现。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `yaml-dsl-allowlist-policy`: resolver 在 trusted-mode 下仍需保持 denylist 的防御深度(逐级属性遍历校验)。
- `yaml-dsl-lsp-project-discovery`: `python_roots` 的语义应保持 dev-only 且允许 external roots(最小校验,不做严格安全限制)。

## Impact

- 受影响代码:
  - `src/scalim/dsl/yaml_dsl/runtime/references.py`
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/project_config.py`
- 受影响测试:
  - 需要新增/调整 resolver 与 project config 的单测覆盖
- 风险:
  - LSP 配置仍可能引用 project_root 外路径,但这是刻意允许的 dev-only 行为;不会把其提升为安全约束。
