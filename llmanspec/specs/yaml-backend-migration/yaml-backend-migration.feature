# language: zh-CN
# capability: yaml-backend-migration
# purpose: 定义 `scalim` 默认 YAML backend(外部依赖 `ruamel.yaml`, YAML 1.2) 的运行时契约, 并为 CLI 的 YAML round-trip 编辑能力建立稳定性门禁(no-op 字节级幂等 + minimal edit)。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: yaml-backend-migration

  @req:r102 @human
  场景: scalim YAML parsing MUST use PyPI `ruamel.yaml` (YAML 1.2) as the only runtime backend
    - 系统 MUST 使用外部依赖 `ruamel.yaml`(PyPI,`>=0.19.1`) 作为 `src/scalim/` 运行时 YAML 解析的唯一后端,并显式采用 YAML 1.2 语义。 该要求至少覆盖: - demand/workflow/CLI validate/imports/project-config 等所有 YAML 入口 - safe load / compose(location index) / parse error envelope - 不得再携带任何 vendored YAML 实现(`vendor/yamlx` 已删除)

  @req:r344 @human
  场景: duplicate key policy MUST match scalim defaults consistently
    - 系统 MUST 以一致的策略处理 YAML mapping 中的重复键: - 默认 MUST 开启 duplicate key 检测;检测到显式重复键时 MUST 报错并提供重复键出现处的行列定位。 - 当调用方显式关闭 duplicate key 检测时,MUST 允许重复键并采用 “后写覆盖前写(last-wins)” 的映射语义。

  @req:r466 @human
  场景: CLI YAML round-trip editing MUST be stable and byte-idempotent on no-op
    - 系统 MUST 使用 `ruamel.yaml` 的 round-trip 能力(`YAML(typ=\"rt\")`,带 authoring 发射器配置)对 YAML 文件进行编辑,并保证在不做业务变更时不引入无意义 diff。 该要求至少覆盖 `yaml-dsl upsert-lsp-comment`: - no-op round-trip(`load` 后立刻 `dump`) MUST 产出与输入文本字节级完全一致 - upsert 仅允许修改 schema modeline 所在行;不得无意义重排正文

  @req:r551 @human
  场景: migration MUST be gated by corpus parity and minimum-supported-python checks
    - 仓库 MUST 提供自动化门禁以降低后端升级风险,至少包含: - canonical YAML 语料的解析回归(确保默认 backend 可解析) - ruamel vs PyYAML(dev 依赖,仅迁移期 oracle)的 corpus parity 对拍 - 支持窗口下界(floor,见根 `ROADMAP.md`,当前 3.10)的 ruamel import + YAML parse smoke checks(经由 CI matrix 下界 job)
  @req:r102 @human
  场景: runtime-parsing-uses-yaml-1-2-semantics
    - 必须成立：当 系统以安全模式解析 YAML DSL 文本；那么 解析 MUST 基于 `ruamel.yaml` 的安全 loader
    当 系统以安全模式解析 YAML DSL 文本
    那么 解析 MUST 基于 `ruamel.yaml` 的安全 loader

  @req:r102 @human
  场景: yaml-backend-must-be-a-declared-runtime-dependency
    - 必须成立：当 用户按标准方式安装 `scalim`(或导出其依赖元数据)；那么 `ruamel.yaml>=0.19.1` MUST 出现在运行时依赖声明中(随安装自动可用)
    当 用户按标准方式安装 `scalim`(或导出其依赖元数据)
    那么 `ruamel.yaml>=0.19.1` MUST 出现在运行时依赖声明中(随安装自动可用)
  @req:r344 @human
  场景: duplicate-keys-raise-a-structured-error-by-default
    - 必须成立：当 YAML 文本包含显式重复键且未关闭检测；那么 解析 MUST 失败
    当 YAML 文本包含显式重复键且未关闭检测
    那么 解析 MUST 失败

  @req:r344 @human
  场景: last-wins-mapping-semantics-when-detection-is-disabled
    - 必须成立：当 YAML 文本包含重复键且调用方显式关闭检测；那么 解析 MUST 成功
    当 YAML 文本包含重复键且调用方显式关闭检测
    那么 解析 MUST 成功
  @req:r466 @human
  场景: no-op-round-trip-produces-identical-bytes
    - 必须成立：假如 输入 YAML 文本为合法文档；当 系统执行 `load` 后立刻 `dump` 且不做任何编辑；那么 输出 MUST 与输入字节级完全一致
    假如 输入 YAML 文本为合法文档
    当 系统执行 `load` 后立刻 `dump` 且不做任何编辑
    那么 输出 MUST 与输入字节级完全一致

  @req:r466 @human
  场景: upsert-only-changes-the-modeline-line
    - 必须成立：假如 输入 YAML 文本已包含或缺少 schema modeline；当 系统执行 upsert 写回；那么 输出 MUST 仅在 modeline 行发生变化
    假如 输入 YAML 文本已包含或缺少 schema modeline
    当 系统执行 upsert 写回
    那么 输出 MUST 仅在 modeline 行发生变化
  @req:r551 @human
  场景: canonical-corpus-is-continuously-validated
    - 必须成立：当 仓库运行变更相关的 QA/测试门禁；那么 canonical YAML 语料 MUST 被解析验证
    当 仓库运行变更相关的 QA/测试门禁
    那么 canonical YAML 语料 MUST 被解析验证

  @req:r551 @human
  场景: minimum-supported-python-runtime-remains-a-hard-gate
    - 必须成立：假如 `src/scalim/` 运行时边界为支持窗口下界(根 `ROADMAP.md`,floor 3.10)；当 运行 CI matrix 下界 job 的 smoke checks；那么 ruamel import 与关键 YAML runtime smoke checks MUST 在 floor Python 环境中通过
    假如 `src/scalim/` 运行时边界为支持窗口下界(根 `ROADMAP.md`,floor 3.10)
    当 运行 CI matrix 下界 job 的 smoke checks
    那么 ruamel import 与关键 YAML runtime smoke checks MUST 在 floor Python 环境中通过
