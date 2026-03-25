## Why

在 `0.4.0` 中,`YAML DSL` 存在少量“对下游非常有用”的内部 API,但它们不属于当前 **curated public surface**(也未被纳入 `scalim.dsl.by_yaml` 的官方稳定入口叙事),导致下游不得不依赖 `runtime.*` 等内部实现路径:

- `scalim.dsl.by_yaml.runtime.introspection.load_output_config`: 从 YAML 解析输出字段配置(`field_name_mapping` / `output_fields`),下游已有多处使用。
- `scalim.dsl.by_yaml.runtime.references.derive_base_module_path`: 由 `yaml_path + sys.path` 推导相对引用的 `base_module_path`,下游用于“相对引用 + fallback”场景。

由于这些路径位于内部实现子包,后续重构或公共表面收敛时很容易发生“内部路径漂移 → 下游 import 断裂”。下游的诉求并不是扩大全部内部模块为公共契约,而是希望对上述少量高价值能力提供 **稳定、可审计、可回归的公开替代入口**。

同时,下游在升级 loader/call_by 等 DSL 扩展点时,还希望能引用一批 Scalim 内置的“安全可调用对象”(例如 workflow 相关的内置 loader),但不希望:

- 在 YAML 中写冗长的 `scalim.some.deep.module:path` Python 引用(易受内部重构影响)；
- 为这些框架内置能力额外扩大 allowlist(更难审计/更容易误用)。

因此需要一个“Scalim 内置可调用对象快捷方式”语法(下游示例: `loader: \"::scalim:workbooksheet_toxxxx\"` / `!scalim` / `@scalim` 等),让框架能识别并将其解析为受控白名单中的内置 callable。

## What Changes

- 新增稳定工具模块 `scalim.dsl.by_yaml.tools`,作为 `YAML DSL` 的“下游集成工具面”(report/introspection/reference helpers)。
- 在 `scalim.dsl.by_yaml.tools` 中以显式 `__all__` 白名单公开以下能力(不改变其运行语义):
  - `load_output_config`
  - `derive_base_module_path`
  - `OutputConfigDict`(TypedDict): 固化 `load_output_config()` 的返回结构契约,同时保持运行期返回值仍为 `dict`。
- 将 `scalim.dsl.by_yaml.tools` 纳入 curated public modules 的回归门禁(导入 smoke + `__all__` 断言),确保这是“明确承诺”的公共表面,而不是偶然可导入的实现路径。
- 文档与示例(用户可见材料)补充推荐导入方式,将“从 runtime.* 导入”统一迁移为 `scalim.dsl.by_yaml.tools`。
- 新增一套内置 callable 引用语法: `scalim://py/<id>`(plain string,无需 YAML tag),用于在 loader/call_by/... 等位置引用 Scalim 内置、受控白名单的 callable:
  - 解析阶段将其视为合法 callable 引用(与 `module.path:function` 并列)
  - 运行期通过内置 registry 将 `<id>` 映射为具体 callable(不依赖内部模块路径)
  - 该语法的解析与执行 **不扩大 allowlist**: 内置 callable 可在不将 `scalim.*` 加入 allowlist 的情况下被安全使用
  - unknown `<id>` MUST fail-fast 并给出可操作的错误信息(例如提示可用 id 列表或指向文档)

## Capabilities

### New Capabilities
- `yaml-dsl-public-tools`: 为 `YAML DSL` 提供稳定的工具/自省公开入口,避免下游依赖 `runtime.*` 内部实现路径。
- `yaml-dsl-builtin-callables`: 为 loader/call_by 等 Python 引用扩展点提供 `scalim://py/<id>` 的内置 callable 快捷方式,避免下游依赖内部模块路径或扩大 allowlist。

### Modified Capabilities
- （无）

## Impact

- 受影响代码主要集中在:
  - `src/scalim/dsl/by_yaml/`(新增 `tools` facade,不改动现有 runtime 实现细节)
  - `src/scalim/dsl/by_yaml/config_parsing/**` 与 `src/scalim/dsl/by_yaml/runtime/**`(新增 builtin callable 引用语法的解析与解析器映射)
  - `tests/test_public_api_surface_hardening.py` 等 public-surface gate
  - `docs/doc/yaml-dsl/**`(补充/升级导入示例)
- SSOT:
  - 本 change 的 OpenSpec 工件位于 `openspec/changes/c20-yaml-dsl-public-tools/`
  - 合并到主线规范时,能力规范将进入:
    - `openspec/specs/yaml-dsl-public-tools/spec.md`
    - `openspec/specs/yaml-dsl-builtin-callables/spec.md`
- 文档治理:
  - 任何 `.gen.*` 文件与 `BEGIN/END AUTOGEN:*` 注入区块禁止手改;如需更新生成内容,应修改 SSOT 并运行 `just gen-docs`。
