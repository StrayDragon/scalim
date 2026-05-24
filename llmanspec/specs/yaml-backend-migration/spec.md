---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate yaml-backend-migration --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "yaml-backend-migration"
purpose: "定义 `scalim` 默认 YAML backend 迁移到 vendored `ruamel.yaml`(YAML 1.2) 的运行时契约, 并为 CLI 的 YAML round-trip 编辑能力建立稳定性门禁(no-op 字节级幂等 + minimal edit)。"
requirements[4]{req_id,title,statement}:
  r1,scalim YAML parsing MUST use vendored `ruamel.yaml` (YAML 1.2) as the only runti,"系统 MUST 使用 vendored `ruamel.yaml` 作为 `src/scalim/` 运行时 YAML 解析的唯一后端,并显式采用 YAML 1.2 语义。 该要求至少覆盖: - demand/workflow/CLI validate/imports/project-config 等所有 YAML 入口 - safe load / compose(location index) / parse error envelope - vendors-sync 下的可导入性(不得依赖外部安装包)"
  r2,duplicate key policy MUST match scalim defaults consistently,"系统 MUST 以一致的策略处理 YAML mapping 中的重复键: - 默认 MUST 开启 duplicate key 检测;检测到显式重复键时 MUST 报错并提供重复键出现处的行列定位。 - 当调用方显式关闭 duplicate key 检测时,MUST 允许重复键并采用 “后写覆盖前写(last-wins)” 的映射语义。"
  r3,"CLI YAML round-trip editing MUST be stable and byte-idempotent on no-op","系统 MUST 使用 vendored `ruamel.yaml` 的 round-trip 能力(`YAML(typ=\\\"rt\\\")`)对 YAML 文件进行编辑,并保证在不做业务变更时不引入无意义 diff。 该要求至少覆盖 `yaml-dsl upsert-lsp-comment`: - no-op round-trip(`load` 后立刻 `dump`) MUST 产出与输入文本字节级完全一致 - upsert 仅允许修改 schema modeline 所在行;不得无意义重排正文"
  r4,migration MUST be gated by corpus parity and Python 3.6 runtime checks,"仓库 MUST 提供自动化门禁以降低一次性切换风险,至少包含: - canonical YAML 语料的解析回归(确保新默认 backend 可解析) - ruamel vs vendored PyYAML 的 corpus parity 对拍(用于迁移期风险控制) - Python 3.6 环境下的 vendored import + YAML parse smoke checks(建议通过 docker)"
scenarios[12]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,"runtime-parsing-uses-yaml-1-2-semantics","",系统以安全模式解析 YAML DSL 文本,解析 MUST 基于 vendored `ruamel.yaml` 的安全 loader
  r1,"runtime-does-not-rely-on-external-yaml-installations",运行环境未安装任何名为 `yaml`/`ruamel.yaml` 的第三方包,运行时解析 YAML DSL 文本,解析 MUST 成功
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,"duplicate-keys-raise-a-structured-error-by-default","",YAML 文本包含显式重复键且未关闭检测,解析 MUST 失败
  r2,"last-wins-mapping-semantics-when-detection-is-disabled","",YAML 文本包含重复键且调用方显式关闭检测,解析 MUST 成功
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"no-op-round-trip-produces-identical-bytes",输入 YAML 文本为合法文档,系统执行 `load` 后立刻 `dump` 且不做任何编辑,输出 MUST 与输入字节级完全一致
  r3,"upsert-only-changes-the-modeline-line",输入 YAML 文本已包含或缺少 schema modeline,系统执行 upsert 写回,输出 MUST 仅在 modeline 行发生变化
  r4,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r4,"canonical-corpus-is-continuously-validated","",仓库运行变更相关的 QA/测试门禁,canonical YAML 语料 MUST 被解析验证
  r4,"python-3-6-vendored-runtime-remains-a-hard-gate",`src/scalim/` 运行时边界要求兼容 Python 3.6,运行变更相关的 py36 smoke checks,vendored import 与关键 YAML runtime smoke checks MUST 在 Python 3.6 环境中通过
```
