# language: zh-CN
# capability: tools-agent-skill-export
# purpose: 定义 `scalim-yaml-dsl` skill 自动生成器的职责边界，确保自动化只负责受控参考产物，同时保证输出可校验、可重建、不会覆盖手工维护的 skill 本体。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: tools-agent-skill-export

  @req:r79 @human
  场景: Safe Output Destination
    - 系统 MUST 默认输出到 `agentdev/skills/`,允许通过参数指定输出根目录,但必须拒绝写入用户 skill 目录(如 `~/.codex/skills`、`~/.claude/skills`、`/etc/codex/skills`).

  @req:r323 @human
  场景: Skill Output Artifacts
    - 系统 MUST 仅生成和校验受控参考产物,不得再把完整 skill 包视为自动生成产物. 受控输出 MUST 位于 `agentdev/skills/scalim-yaml-dsl/references/`,并至少包含: - `references/syntax-catalog.gen.md` - `references/generated/cli-lsp-reference.gen.md` - `references/generated/example-full/ecommerce_report.gen.yaml`

  @req:r446 @human
  场景: Auto-Extracted References
    - 系统 MUST 从 schema 与 CLI 实现自动导出受控参考产物,并从受控 notebook YAML 来源导出唯一 canonical example. 自动生成内容 MUST 覆盖: - YAML DSL 顶层字段与 definitions 的完整语法目录 - 与 authoring/validation 直接相关的 CLI/LSP 参考 - 单个 canonical full example 的导出结果

  @req:r535 @human
  场景: Example Selection and Validation
    - 系统 MUST 仅导出一个 canonical full example,目标路径固定为 `agentdev/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml`. 该 canonical example MUST: - 仅通过静态读取 `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml` 获得,不得执行 notebook - 在导出后通过 `PROJECT_CLI_NAME yaml-dsl schema validate` 与 `PROJECT_CLI_NAME yaml-dsl validate` 校验 - 不得在导出结果中固化机器相关的 YAML LSP `$schema` 头; LSP header 指引应通过 CLI/LSP reference 另行提供

  @req:r609 @human
  场景: Deterministic Outputs and Validation Mode
    - 系统 MUST 保证受控参考产物输出确定性(稳定排序/无随机/无机器路径泄漏). 系统 MUST 提供校验模式,重建受控参考产物并逐字节比较受控输出;发现漂移即失败. 校验范围 MUST 仅包含生成器负责的受控输出,不得把手工维护的 skill 文件当作“应由生成器重建”的内容.

  @req:r660 @human
  场景: Manual Skill Files Are Preserved
    - 系统 MUST 将 `agentdev/skills/scalim-yaml-dsl/SKILL.md`、`agents/openai.yaml` 与非 generated references 视为手工维护文件. 生成器在 build 与 validate 模式下 MUST NOT 创建、覆盖、删除或重排这些手工维护文件.

  @req:r702 @human
  场景: Generated References Are Executably Validated
    - 系统 MUST 对生成出的 references 进行真实校验与测试,以证明生成逻辑可用而不是仅能“产出文本”. 至少 MUST 校验: - 受控 YAML 示例可通过 YAML DSL 校验 - generated CLI/LSP reference 中引用的关键命令与 schema path 来源真实存在 - 生成器测试覆盖 manual/generated 边界,例如“不覆盖 SKILL.md”

  @req:r738 @human
  场景: Generated References Cover Workflow YAML
    - 系统 MUST 扩展 `scalim-yaml-dsl` skill 生成器,使受控生成 references 覆盖 workflow YAML 的语法与工具入口,并保持“schema/CLI/spec 为唯一真相”的导出策略. 至少 MUST 满足: - 生成器 MUST 将 `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json` 视为 workflow YAML 的 canonical schema 输入,并将其纳入校验/回归输入集. - `references/syntax-catalog.gen.md` MUST 包含 workflow YAML 的语法索引,至少覆盖: - `workflow.runs[*]` 的关键字段: `id`、`demand`、`depends_on`、`init_vars`、`main_rows_from` - `workflow.options` 的关键字段: `max_concurrency`、`failure_policy`、`cache_pool`、`ctx` - `workflow.resources` 的关键字段: `books` - `references/generated/cli-lsp-reference.gen.md` MUST 提供 workflow YAML 的可复制命令入口,至少包含: - 仓库内 workflow schema-only 校验命令（显式 `--schema .../workflow.gen.json`） - `yaml-dsl upsert-lsp-comment --type workflow` 的指引

  @req:r768 @human
  场景: Generated syntax catalog MUST reflect workflow schema key paths (`books`, not le
    - 系统 MUST 保证 `scalim-yaml-dsl` skill 的生成语法目录在 workflow YAML 部分输出的 key paths 与 canonical workflow schema 一致: - MUST 包含 `workflow.resources.books` - MUST NOT 输出任何已移除的 workflow IO authoring surface(legacy resource groups / workflow 写入 intents 等)
  @req:r79 @human
  场景: 默认输出目录
    - 必须成立：当 生成器在未指定输出根目录时运行；那么 受控产物输出到 `agentdev/skills/scalim-yaml-dsl/`
    当 生成器在未指定输出根目录时运行
    那么 受控产物输出到 `agentdev/skills/scalim-yaml-dsl/`

  @req:r79 @human
  场景: 禁止用户目录
    - 必须成立：当 输出根目录指向用户 skill 目录；那么 生成器失败并提示拒绝写入
    当 输出根目录指向用户 skill 目录
    那么 生成器失败并提示拒绝写入
  @req:r323 @human
  场景: 生成产物仅包含受控参考产物
    - 必须成立：当 生成器运行；那么 它仅更新受控产物(不覆盖 `SKILL.md`/非 generated references)
    当 生成器运行
    那么 它仅更新受控产物(不覆盖 `SKILL.md`/非 generated references)

  @req:r323 @human
  场景: 生成产物仍可单独消费
    - 必须成立：当 生成器成功完成；那么 每个受控产物都必须存在且可读取
    当 生成器成功完成
    那么 每个受控产物都必须存在且可读取
  @req:r446 @human
  场景: generated-syntax-catalog-覆盖完整
    - 必须成立：当 生成器运行；那么 syntax catalog 必须覆盖 schema 顶层字段与 definitions
    当 生成器运行
    那么 syntax catalog 必须覆盖 schema 顶层字段与 definitions

  @req:r446 @human
  场景: generated-cli-reference-可用于-skill-引用
    - 必须成立：当 生成器运行；那么 CLI/LSP reference 必须包含 `yaml-dsl validate`、`yaml-dsl schema validate`、`yaml-dsl schema show` 与 `yaml-dsl schema path`
    当 生成器运行
    那么 CLI/LSP reference 必须包含 `yaml-dsl validate`、`yaml-dsl schema validate`、`yaml-dsl schema show` 与 `yaml-dsl schema path`

  @req:r446 @human
  场景: 受控参考产物复用-llmanspec
    - 必须成立：当 生成器导出 syntax catalog 或 CLI/LSP reference；那么 它必须从相关 `llmanspec/specs/*/spec.toon` 摘录 requirement 索引
    当 生成器导出 syntax catalog 或 CLI/LSP reference
    那么 它必须从相关 `llmanspec/specs/*/spec.toon` 摘录 requirement 索引
  @req:r535 @human
  场景: canonical-source-缺失
    - 必须成立：当 `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml` 不存在；那么 生成器退出非零并提示 canonical example 来源缺失
    当 `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml` 不存在
    那么 生成器退出非零并提示 canonical example 来源缺失

  @req:r535 @human
  场景: 不执行-notebooks
    - 必须成立：当 生成器导出 canonical example；那么 它只能静态读取 YAML 源文件,不得执行 notebook 代码
    当 生成器导出 canonical example
    那么 它只能静态读取 YAML 源文件,不得执行 notebook 代码

  @req:r535 @human
  场景: 导出示例通过双重校验
    - 必须成立：当 生成器导出 canonical example；那么 测试必须验证导出结果同时通过 `yaml-dsl schema validate` 与 `yaml-dsl validate`
    当 生成器导出 canonical example
    那么 测试必须验证导出结果同时通过 `yaml-dsl schema validate` 与 `yaml-dsl validate`

  @req:r535 @human
  场景: 导出示例移除本机相关-schema-header
    - 必须成立：当 源示例包含 `# yaml-language-server: $schema=...` 头部；那么 导出结果必须移除该头部
    当 源示例包含 `# yaml-language-server: $schema=...` 头部
    那么 导出结果必须移除该头部
  @req:r609 @human
  场景: 重复构建一致
    - 必须成立：当 输入不变且运行两次；那么 generated outputs 保持确定性一致
    当 输入不变且运行两次
    那么 generated outputs 保持确定性一致

  @req:r609 @human
  场景: 校验模式仅比较受控输出
    - 必须成立：当 已有 skill 目录下同时存在手工维护文件与 generated references；那么 校验模式只比较生成器负责的受控文件
    当 已有 skill 目录下同时存在手工维护文件与 generated references
    那么 校验模式只比较生成器负责的受控文件

  @req:r609 @human
  场景: 发生-generated-reference-漂移
    - 必须成立：当 已有 generated references 与新生成内容不同；那么 校验模式返回非零并报告差异
    当 已有 generated references 与新生成内容不同
    那么 校验模式返回非零并报告差异
  @req:r660 @human
  场景: 保留手工维护的-skill-md
    - 必须成立：当 skill 目录中已存在手工维护的 `SKILL.md`；那么 生成器运行后该文件内容保持不变
    当 skill 目录中已存在手工维护的 `SKILL.md`
    那么 生成器运行后该文件内容保持不变

  @req:r660 @human
  场景: 保留手工维护-references
    - 必须成立：当 skill 目录中存在 `references/` 下的非 generated 文档；那么 生成器不得删除或重写这些文档
    当 skill 目录中存在 `references/` 下的非 generated 文档
    那么 生成器不得删除或重写这些文档

  @req:r660 @human
  场景: 仅清理过期-generated-文件
    - 必须成立：当 `references/generated/` 中存在旧的受控残留文件；那么 生成器可以清理这些陈旧 generated 文件
    当 `references/generated/` 中存在旧的受控残留文件
    那么 生成器可以清理这些陈旧 generated 文件
  @req:r702 @human
  场景: 生成示例通过-yaml-校验
    - 必须成立：当 生成器导出 canonical YAML 示例；那么 这些示例必须在测试中通过 YAML DSL 校验
    当 生成器导出 canonical YAML 示例
    那么 这些示例必须在测试中通过 YAML DSL 校验

  @req:r702 @human
  场景: 自定义输出目录不影响-generated-内容
    - 必须成立：当 维护者通过 `--output-root` 指定自定义 skill 根目录；那么 generated CLI/LSP reference 与 canonical example 不得泄漏该输出目录路径
    当 维护者通过 `--output-root` 指定自定义 skill 根目录
    那么 generated CLI/LSP reference 与 canonical example 不得泄漏该输出目录路径

  @req:r702 @human
  场景: 手工-自动边界有回归测试
    - 必须成立：当 维护者修改生成器；那么 测试必须验证生成器不会覆盖手工维护的 `SKILL.md` 或其它非 generated references
    当 维护者修改生成器
    那么 测试必须验证生成器不会覆盖手工维护的 `SKILL.md` 或其它非 generated references
  @req:r738 @human
  场景: generated-syntax-catalog-包含-workflow-语法索引
    - 必须成立：当 维护者运行 `just gen-agent-skill`；那么 `references/syntax-catalog.gen.md` 中必须可检索到 workflow YAML 的字段索引
    当 维护者运行 `just gen-agent-skill`
    那么 `references/syntax-catalog.gen.md` 中必须可检索到 workflow YAML 的字段索引

  @req:r738 @human
  场景: generated-cli-lsp-reference-包含-workflow-命令入口
    - 必须成立：当 维护者运行 `just gen-agent-skill`；那么 `references/generated/cli-lsp-reference.gen.md` 必须包含 workflow schema-only 校验命令示例
    当 维护者运行 `just gen-agent-skill`
    那么 `references/generated/cli-lsp-reference.gen.md` 必须包含 workflow schema-only 校验命令示例
  @req:r768 @human
  场景: syntax-catalog-key-paths-match-workflow-schema
    - 必须成立：当 维护者运行 `just gen-agent-skill`；那么 `agentdev/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 的 workflow "Key Paths" MUST 包含 `workflow.resources.books`
    当 维护者运行 `just gen-agent-skill`
    那么 `agentdev/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 的 workflow "Key Paths" MUST 包含 `workflow.resources.books`
