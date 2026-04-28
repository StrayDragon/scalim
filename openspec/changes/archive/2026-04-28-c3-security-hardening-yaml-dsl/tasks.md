## 1. Resolver Defense-In-Depth (S-1)

- [x] 1.1 在 `SecurePythonReferenceResolver` 的属性链解析/遍历路径中增加逐级 denylist 校验(覆盖 `DANGEROUS_FUNCTIONS`/`__`/`lambda`)
- [x] 1.2 补齐单测: class-style 引用在 trusted-mode 下仍必须拒绝 denylist 属性名

## 2. LSP python_roots Path Semantics (S-3)

- [x] 2.1 调整 `yaml_dsl.lsp.python_roots` 的解析语义: 相对路径以 `project_root` 为基准解析但允许落在 `project_root` 外(不做 fail-fast);绝对路径允许 external。
- [x] 2.2 对于不可用 python_root(空字符串/空白字符串,或解析后不存在/非目录): MUST 输出 warning 并忽略该项(不得因为该项导致 `load_yaml_dsl_project_config(...)` 失败)。
- [x] 2.3 更新/补齐单测:
  - `../` 逃逸路径在目录存在时应被接受
  - 缺失目录的 python_root 不再 raise,而是 warning + 忽略,并且项目配置仍可加载
  - 空字符串 python_root 不再 raise,而是 warning + 忽略,并且项目配置仍可加载
  - warning 文本需包含 raw/project_root/resolved,便于诊断

## 3. Verification

- [x] 3.1 运行 `just qa`
- [x] 3.2 运行 `just openspec-check`
