# agent-skill-export Specification

**状态: ✅ 已实现**
## Purpose
描述 PROJECT_NAME YAML DSL Skill 自动导出的范围与约束,覆盖安全输出位置、示例抽取、生成产物、路径归一化、清单一致性与校验流程.

## Context
实现位于 `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py` 与 `scripts/gen-agent-skill.py`,用于生成 PROJECT_NAME YAML DSL Skill 产物与校验输出漂移.
## Related Code (as implemented)
- `packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`
- `scripts/gen-agent-skill.py`
- `tests/test_agent_skill_generator.py`
- `justfile` (`gen-agent-skill`, `validate-agent-skill`)
## Requirements
### Requirement: Safe Output Destination
系统 MUST 默认输出到 `artifacts/skills/`,允许通过参数指定输出根目录,但必须拒绝写入用户 skill 目录(如 `~/.codex/skills`、`~/.claude/skills`、`/etc/codex/skills`).

#### Scenario: 默认输出目录
- **WHEN** 生成器在未指定输出根目录时运行
- **THEN** 产物输出到 `artifacts/skills/scalim-yaml-dsl/`

#### Scenario: 禁止用户目录
- **WHEN** 输出根目录指向用户 skill 目录
- **THEN** 生成器失败并提示拒绝写入

### Requirement: Skill Output Artifacts
系统 MUST 生成完整 Skill 目录与引用产物,至少包含:
- `SKILL.md`
- `references/dsl-reference.md`
- `references/usage-guide.md`
- `references/examples/*.yaml`

#### Scenario: 生成产物完整
- **WHEN** 生成器运行
- **THEN** 上述文件均存在且可读取,且 `references/examples/` 至少包含 1 个 YAML 示例

### Requirement: SKILL.md Structure
系统 MUST 生成带 frontmatter 的 `SKILL.md`,并校验 `name`/`description` 约束(长度、字符集、禁止保留词、禁止 XML 标签).
正文 MUST 包含 `## Instructions` 与 `## Examples` 段落,展示顶层字段列表、最小示例与 relations/compute 示例,并包含:
- `uv run PROJECT_CLI_NAME yaml-dsl validate <file.yaml>` (完整校验,使用内部 validator)
- `uv run PROJECT_CLI_NAME yaml-dsl schema validate <file.yaml>` (schema-only 快速校验)
- `PROJECT_CLI_NAME yaml-dsl schema show` 或 `PROJECT_CLI_NAME yaml-dsl schema path` (schema 获取)

#### Scenario: Frontmatter 校验失败
- **WHEN** `name` 或 `description` 不满足约束
- **THEN** 生成器退出非零并报告问题

#### Scenario: 段落与指令存在
- **WHEN** Skill 被生成
- **THEN** `SKILL.md` 含 Instructions/Examples 段落与校验指令

### Requirement: Auto-Extracted References
系统 MUST 从 notebooks/marimo/examples 与 tests 自动抽取示例与 DSL 规则,生成 `references/dsl-reference.md`.
`references/dsl-reference.md` MUST 包含 schema 顶层字段与 definitions 的覆盖索引,并附加 OpenSpec Requirement/Scenario 摘要.

#### Scenario: 覆盖索引完整
- **WHEN** 生成器运行
- **THEN** `dsl-reference.md` 覆盖索引包含顶层字段与 definitions

### Requirement: Example Selection and Validation
系统 MUST 按 notebooks > tests 的优先级选择 minimal 与 relations/compute 示例,并支持 `# region SCALIM-SKILL:<tag>` 标注.
系统 MUST 仅静态读取 `notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/*.yaml` 作为完整 YAML DSL 示例输出,且不得执行 notebooks.
系统 MUST 在缺少 minimal/relations/compute 示例或完整 YAML 示例时失败.
系统 MUST 对示例执行 YAML DSL 校验;示例包含未知字段时生成器 MUST 失败.
测试 MUST 验证 notebooks/marimo/examples 内所有标注示例可通过 YAML DSL 校验.

#### Scenario: notebooks 优先
- **WHEN** notebooks 与 tests 同时提供示例
- **THEN** 优先选用 notebooks 示例

#### Scenario: 完整 YAML 示例缺失
- **WHEN** `demo_big_data_report/by_yaml_dsl` 下无可用 YAML 示例
- **THEN** 生成器退出非零并提示缺失来源

#### Scenario: 不执行 notebooks
- **WHEN** 生成器抽取完整 YAML 示例
- **THEN** 仅通过读取 YAML 文件生成 references 产物,不执行 notebook 代码

#### Scenario: 示例包含未知字段
- **WHEN** 示例 YAML 包含未知字段
- **THEN** 生成器退出非零并报告校验错误

### Requirement: Path Normalization
系统 MUST 将示例中的绝对路径归一化:
- 仓库内路径使用 `$REPO_ROOT/<relative>`
- 仓库外路径使用 `$LOCAL_PATH/<basename>` 并在行尾标注 `external`
归一化映射 MUST 记录在 `build-manifest.json` 的 `path_normalization` 中.

#### Scenario: 本机路径归一化
- **WHEN** 示例包含绝对路径
- **THEN** `SKILL.md` 展示归一化路径并标注 external,清单记录映射

### Requirement: Deterministic Manifest and Validation Mode
系统 MUST 输出 output_root 下的 `scalim-yaml-dsl.build-manifest.json`(默认 output_root 为 `artifacts/skills`),记录输入/输出校验和、覆盖索引与 `path_normalization`,并保证排序确定性.
系统 MUST 提供校验模式,重建输出并逐字节比较,发现漂移即失败.

#### Scenario: 重复构建一致
- **WHEN** 输入不变且运行两次
- **THEN** `build-manifest.json` 与产物字节级一致

#### Scenario: 发生漂移
- **WHEN** 已有输出与新生成内容不同
- **THEN** 校验模式返回非零并报告差异

### Requirement: Schema Hover Metadata
系统 MUST 在生成的 JSON Schema 中提供 `markdownDescription` 与 `examples`,用于 YAML LSP hover,并可通过 `PROJECT_CLI_NAME yaml-dsl schema show` 获取.

#### Scenario: metadata 输出
- **WHEN** schema 生成
- **THEN** 输出 schema 中包含 `markdownDescription` 与 `examples`

### Requirement: User-Oriented Guidance Links
系统 MUST 在 `SKILL.md` 中提供简洁的 DSL 上手指引(包含关键警示/规则)并链接到 `references/usage-guide.md` 与 `references/examples/` 以获取完整说明与示例.

#### Scenario: 指引与链接存在
- **WHEN** 生成器运行
- **THEN** `SKILL.md` 含有指向 `references/usage-guide.md` 与 `references/examples/` 的链接或说明
