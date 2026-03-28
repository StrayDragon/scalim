## Why

Scalim 的 YAML DSL 与输出 sinks 同时具备“强表达力”和“易误用”两面：用户配置可通过 imports/模板/引用解析影响运行时行为；输出 CSV/Excel 往往会被下游（尤其是 Excel）直接打开。当前实现中仍存在若干安全脚枪（例如 CSV 公式注入、模板渲染 DoS 风险、unsafe/trusted 入口扩散），需要在规模化采用与更广泛共享之前，先把默认行为与治理边界收紧为“安全默认、明确 opt-in”。

## What Changes

- CSV sinks 增加 **公式注入防护**（默认 escape，可显式 opt-out 允许写公式/原样写出）。
- YAML `template_vars` 预编译增加 **资源上限**（例如渲染后最大文本长度），避免不可信模板导致内存/CPU 放大。
- 将高风险能力的“使用路径”明确化并可治理：
  - `trusted_allow_all_modules` / wildcard allowlist 相关能力仍保留为显式 trusted/unsafe 语义，但文档/skills 禁止引用，避免扩散为“公开 API 教程”。
  - `unsafe_entrypoints` 继续作为非公开入口存在时，必须可审计且具备强 warning，并在 repo 治理层面避免被误用。
- （非目标）本变更不扩展 `openspec/sanitize_rules.yaml`（隐私/发布治理规则保持现状；组织私有字面量继续放本地 rules 文件）。

## Capabilities

### New Capabilities

- （无）

### Modified Capabilities

- `sinks-contracts`: 增补/细化 CSV 输出的公式注入防护要求，使 CSV 与 Excel sinks 在“疑似公式字符串”处理上具备一致的安全默认与显式 opt-out。
- `yaml-template-vars-precompile`: 增补模板渲染资源上限要求（例如渲染后最大长度/错误信息不泄露值），将其从“功能能力”升级为可审计的安全边界。

## Impact

- 受影响代码（SSOT）：`src/scalim/sinks/_internal/sink_csv.py`、`src/scalim/_internal/utils/excel.py`（复用转义策略）、`src/scalim/dsl/by_yaml/config_parsing/template_precompile.py`、`src/scalim/vendor/litejinja2/`（渲染限制）、`src/scalim/dsl/by_yaml/runtime/unsafe_entrypoints.py`（治理与审计）。
- 受影响规范（SSOT）：`openspec/specs/sinks-contracts/spec.md`、`openspec/specs/yaml-template-vars-precompile/spec.md`（本 change 将提供对应的增量 specs）。
- 受影响文档/技能：
  - 文档 SSOT 位于 `docs/doc/**`，其中 `.gen.` 与 `BEGIN/END AUTOGEN` 区块为生成物/注入区块（禁止手改；入口 `just gen-docs`）。
  - skills SSOT 位于 `artifacts/skills/**`（若需要新增/更新示例，必须遵循 skills 抽取与文档治理规则）。

