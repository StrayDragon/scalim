## 1. Public Tools Facade

- [ ] 1.1 新增稳定公开模块 `scalim.dsl.by_yaml.tools`(实现文件位于 `src/scalim/dsl/by_yaml/tools.py`)
- [ ] 1.2 在 `tools` 中公开 `load_output_config` 与 `derive_base_module_path`,并提供 `OutputConfigDict`(TypedDict,使用 `vendor/compact/typing_extensionsx.py`)
- [ ] 1.3 为 `tools` 模块补充显式 `__all__` 白名单,与规范 `yaml-dsl-public-tools` 对齐

## 2. Builtin Callable References (`scalim://py/<id>`)

- [ ] 2.1 新增内置 callable registry(SSOT),实现 `scalim://py/<id>` → callable 的显式映射与 fail-fast unknown-id 错误
- [ ] 2.2 扩展 loader/call_by 引用校验: 允许 `scalim://py/<id>` 与 `scalim://py/<id>(...)` 作为合法引用(与 Python 引用并列)
- [ ] 2.3 扩展运行期 resolver: 解析 `scalim://py/<id>` 时绕过 allowlist 检查并从 registry 返回 callable
- [ ] 2.4 提供至少一个内置 id: `scalim://py/workflow/sheetbook_sheet_rows`,并补单元测试覆盖
- [ ] 2.5 更新 YAML JSON Schema 与用户文档(SSOT + `just gen-docs`),将 `scalim://py/<id>` 纳入 loader/call_by 字段说明与示例

## 3. Public Surface Gates

- [ ] 3.1 更新 curated public modules 列表,将 `scalim.dsl.by_yaml.tools` 纳入 `tests/test_public_api_surface_hardening.py` 的 `_CURATED_PUBLIC_MODULES`
- [ ] 3.2 在 `tests/test_public_api_surface_hardening.py` 的 `_EXPECTED_PUBLIC_ALL` 中新增 `scalim.dsl.by_yaml.tools` 的 `__all__` 断言集合
- [ ] 3.3 增加/调整 import smoke/回归用例,覆盖 `load_output_config` 与 `derive_base_module_path` 的可调用性与最小行为(至少包含 required keys)

## 4. Docs / User-Visible Materials

- [ ] 4.1 在 `docs/doc/yaml-dsl/` 增补下游迁移指引: 从 `runtime.*` 内部路径迁移到 `scalim.dsl.by_yaml.tools`
- [ ] 4.2 在 `docs/doc/yaml-dsl/` 增补内置 callable 快捷方式用法: `scalim://py/<id>`(并解释其不要求把 `scalim.*` 加入 allowlist)
- [ ] 4.3 若触及任何 `.gen.*` 文件或 `BEGIN/END AUTOGEN:*` 注入区块: 仅修改 SSOT 并运行 `just gen-docs`(禁止手改生成物/注入区块内部)
- [ ] 4.4 运行 user-visible materials gate(随 `just qa`),确保不出现 `scalim.dsl.by_yaml.runtime.` / `config_parsing.` / `schema_dsl.` 等内部路径推广

## 5. Validation

- [ ] 5.1 运行 `just openspec-check` 校验 OpenSpec 工件(含 sanitize + `openspec validate`)
- [ ] 5.2 运行 `just qa` 确认 public-surface gate 与文档门禁通过
