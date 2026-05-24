---
llman_spec_valid_scope:
  - src/scalim/
llman_spec_valid_commands:
  - llman sdd validate tools-agent-skill-export --type spec --strict --no-interactive
llman_spec_evidence:
  - migrated from openspec
---

```toon
kind: llman.sdd.spec
name: "tools-agent-skill-export"
purpose: "定义 `scalim-yaml-dsl` skill 自动生成器的职责边界，确保自动化只负责受控参考产物，同时保证输出可校验、可重建、不会覆盖手工维护的 skill 本体。"
requirements[9]{req_id,title,statement}:
  r1,Safe Output Destination,"系统 MUST 默认输出到 `agentdev/skills/`,允许通过参数指定输出根目录,但必须拒绝写入用户 skill 目录(如 `~/.codex/skills`、`~/.claude/skills`、`/etc/codex/skills`)."
  r2,Skill Output Artifacts,"系统 MUST 仅生成和校验受控参考产物,不得再把完整 skill 包视为自动生成产物. 受控输出 MUST 位于 `agentdev/skills/scalim-yaml-dsl/references/`,并至少包含: - `references/syntax-catalog.gen.md` - `references/generated/cli-lsp-reference.gen.md` - `references/generated/example-full/ecommerce_report.gen.yaml`"
  r3,"Auto-Extracted References","系统 MUST 从 schema 与 CLI 实现自动导出受控参考产物,并从受控 notebook YAML 来源导出唯一 canonical example. 自动生成内容 MUST 覆盖: - YAML DSL 顶层字段与 definitions 的完整语法目录 - 与 authoring/validation 直接相关的 CLI/LSP 参考 - 单个 canonical full example 的导出结果"
  r4,Example Selection and Validation,"系统 MUST 仅导出一个 canonical full example,目标路径固定为 `agentdev/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.gen.yaml`. 该 canonical example MUST: - 仅通过静态读取 `notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml` 获得,不得执行 notebook - 在导出后通过 `PROJECT_CLI_NAME yaml-dsl schema validate` 与 `PROJECT_CLI_NAME yaml-dsl validate` 校验 - 不得在导出结果中固化机器相关的 YAML LSP `$schema` 头; LSP header 指引应通过 CLI/LSP reference 另行提供"
  r5,Deterministic Outputs and Validation Mode,"系统 MUST 保证受控参考产物输出确定性(稳定排序/无随机/无机器路径泄漏). 系统 MUST 提供校验模式,重建受控参考产物并逐字节比较受控输出;发现漂移即失败. 校验范围 MUST 仅包含生成器负责的受控输出,不得把手工维护的 skill 文件当作“应由生成器重建”的内容."
  r6,Manual Skill Files Are Preserved,"系统 MUST 将 `agentdev/skills/scalim-yaml-dsl/SKILL.md`、`agents/openai.yaml` 与非 generated references 视为手工维护文件. 生成器在 build 与 validate 模式下 MUST NOT 创建、覆盖、删除或重排这些手工维护文件."
  r7,Generated References Are Executably Validated,"系统 MUST 对生成出的 references 进行真实校验与测试,以证明生成逻辑可用而不是仅能“产出文本”. 至少 MUST 校验: - 受控 YAML 示例可通过 YAML DSL 校验 - generated CLI/LSP reference 中引用的关键命令与 schema path 来源真实存在 - 生成器测试覆盖 manual/generated 边界,例如“不覆盖 SKILL.md”"
  r8,Generated References Cover Workflow YAML,"系统 MUST 扩展 `scalim-yaml-dsl` skill 生成器,使受控生成 references 覆盖 workflow YAML 的语法与工具入口,并保持“schema/CLI/spec 为唯一真相”的导出策略. 至少 MUST 满足: - 生成器 MUST 将 `src/scalim/dsl/yaml_dsl/schema/workflow.gen.json` 视为 workflow YAML 的 canonical schema 输入,并将其纳入校验/回归输入集. - `references/syntax-catalog.gen.md` MUST 包含 workflow YAML 的语法索引,至少覆盖: - `workflow.runs[*]` 的关键字段: `id`、`demand`、`depends_on`、`init_vars`、`main_rows_from` - `workflow.options` 的关键字段: `max_concurrency`、`failure_policy`、`cache_pool`、`ctx` - `workflow.resources` 的关键字段: `books` - `references/generated/cli-lsp-reference.gen.md` MUST 提供 workflow YAML 的可复制命令入口,至少包含: - 仓库内 workflow schema-only 校验命令（显式 `--schema .../workflow.gen.json`） - `yaml-dsl upsert-lsp-comment --type workflow` 的指引"
  r9,"Generated syntax catalog MUST reflect workflow schema key paths (`books`, not le","系统 MUST 保证 `scalim-yaml-dsl` skill 的生成语法目录在 workflow YAML 部分输出的 key paths 与 canonical workflow schema 一致: - MUST 包含 `workflow.resources.books` - MUST NOT 输出任何已移除的 workflow IO authoring surface(legacy resource groups / workflow 写入 intents 等)"
scenarios[32]{req_id,id,given,when,then}:
  r1,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r1,默认输出目录,"",生成器在未指定输出根目录时运行,"受控产物输出到 `agentdev/skills/scalim-yaml-dsl/`"
  r1,禁止用户目录,"",输出根目录指向用户 skill 目录,生成器失败并提示拒绝写入
  r2,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r2,生成产物仅包含受控参考产物,"",生成器运行,它仅更新受控产物(不覆盖 `SKILL.md`/非 generated references)
  r2,生成产物仍可单独消费,"",生成器成功完成,每个受控产物都必须存在且可读取
  r3,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r3,"generated-syntax-catalog-覆盖完整","",生成器运行,syntax catalog 必须覆盖 schema 顶层字段与 definitions
  r3,"generated-cli-reference-可用于-skill-引用","",生成器运行,"CLI/LSP reference 必须包含 `yaml-dsl validate`、`yaml-dsl schema validate`、`yaml-dsl schema show` 与 `yaml-dsl schema path`"
  r3,"受控参考产物复用-openspec","",生成器导出 syntax catalog 或 CLI/LSP reference,它必须从相关 `openspec/specs/*/spec.md` 摘录 requirement 索引
  r4,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r4,"canonical-source-缺失","",`notebooks/marimo/demo_big_data_report/chapters_of_yaml_dsl/declared_yaml_dsl/ecommerce_report.yaml` 不存在,生成器退出非零并提示 canonical example 来源缺失
  r4,"不执行-notebooks","",生成器导出 canonical example,"它只能静态读取 YAML 源文件,不得执行 notebook 代码"
  r4,导出示例通过双重校验,"",生成器导出 canonical example,"测试必须验证导出结果同时通过 `yaml-dsl schema validate` 与 `yaml-dsl validate`"
  r4,"导出示例移除本机相关-schema-header","","源示例包含 `# yaml-language-server: $schema=...` 头部",导出结果必须移除该头部
  r5,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r5,重复构建一致,"",输入不变且运行两次,generated outputs 保持确定性一致
  r5,校验模式仅比较受控输出,"",已有 skill 目录下同时存在手工维护文件与 generated references,校验模式只比较生成器负责的受控文件
  r5,"发生-generated-reference-漂移","",已有 generated references 与新生成内容不同,校验模式返回非零并报告差异
  r6,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r6,"保留手工维护的-skill-md","",skill 目录中已存在手工维护的 `SKILL.md`,生成器运行后该文件内容保持不变
  r6,"保留手工维护-references","",skill 目录中存在 `references/` 下的非 generated 文档,生成器不得删除或重写这些文档
  r6,"仅清理过期-generated-文件","",`references/generated/` 中存在旧的受控残留文件,生成器可以清理这些陈旧 generated 文件
  r7,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r7,"生成示例通过-yaml-校验","",生成器导出 canonical YAML 示例,这些示例必须在测试中通过 YAML DSL 校验
  r7,"自定义输出目录不影响-generated-内容","","维护者通过 `--output-root` 指定自定义 skill 根目录",generated CLI/LSP reference 与 canonical example 不得泄漏该输出目录路径
  r7,"手工-自动边界有回归测试","",维护者修改生成器,测试必须验证生成器不会覆盖手工维护的 `SKILL.md` 或其它非 generated references
  r8,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r8,"generated-syntax-catalog-包含-workflow-语法索引","","维护者运行 `just gen-agent-skill`","`references/syntax-catalog.gen.md` 中必须可检索到 workflow YAML 的字段索引"
  r8,"generated-cli-lsp-reference-包含-workflow-命令入口","","维护者运行 `just gen-agent-skill`","`references/generated/cli-lsp-reference.gen.md` 必须包含 workflow schema-only 校验命令示例"
  r9,baseline,"","TODO: describe the trigger","TODO: describe the expected result"
  r9,"syntax-catalog-key-paths-match-workflow-schema","","维护者运行 `just gen-agent-skill`","`agentdev/skills/scalim-yaml-dsl/references/syntax-catalog.gen.md` 的 workflow \"Key Paths\" MUST 包含 `workflow.resources.books`"
```
