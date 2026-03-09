## MODIFIED Requirements

### Requirement: Skill Output Artifacts
系统 MUST 仅生成和校验受控的 generated references 与构建清单,不得再把完整 skill 包视为自动生成产物.

受控输出 MUST 位于 `artifacts/skills/scalim-yaml-dsl/references/generated/` 与 output_root 下的 `scalim-yaml-dsl.build-manifest.json`,并至少包含:
- `references/generated/syntax-catalog.md`
- `references/generated/cli-lsp-reference.md`
- `references/generated/example-full/ecommerce_report.yaml`

系统 MUST NOT 再要求生成器创建以下手工维护文件:
- `SKILL.md`
- `references/dsl-reference.md`
- `references/usage-guide.md`
- `references/examples/*.yaml`
- 手工维护的 task/playbook references

#### Scenario: 生成产物仅包含 generated references
- **WHEN** 生成器运行
- **THEN** 它仅更新 `references/generated/` 下的受控产物与 `scalim-yaml-dsl.build-manifest.json`
- **THEN** 它不得要求 `SKILL.md` 也是生成产物的一部分

#### Scenario: 旧布局不再是生成契约
- **WHEN** 维护者运行生成器
- **THEN** 生成器不得再把 `references/dsl-reference.md`、`references/usage-guide.md` 或 `references/examples/*.yaml` 视为必产物

#### Scenario: 生成产物仍可单独消费
- **WHEN** 生成器成功完成
- **THEN** `references/generated/` 下的每个产物都必须存在且可读取
- **THEN** build manifest 必须记录这些受控输出文件

### Requirement: Auto-Extracted References
系统 MUST 从 schema 与 CLI 实现自动导出 generated references,并从受控 notebook YAML 来源导出唯一 canonical example,保持渐进披露友好的组织方式.

自动生成内容 MUST 覆盖:
- YAML DSL 顶层字段与 definitions 的完整语法目录
- 与 authoring/validation 直接相关的 CLI/LSP 参考
- 单个 canonical full example 的导出结果

系统 MUST 将“全量罗列语法/API”的职责放在 generated references 中,而不是塞进单个 `SKILL.md`.
系统 MUST NOT 再生成 minimal / advanced / relations-compute 示例集合或 examples index.

#### Scenario: generated syntax catalog 覆盖完整
- **WHEN** 生成器运行
- **THEN** syntax catalog 必须覆盖 schema 顶层字段与 definitions
- **THEN** catalog 中必须保留 enum/default/examples 或等价的约束信息

#### Scenario: generated CLI reference 可用于 skill 引用
- **WHEN** 生成器运行
- **THEN** CLI/LSP reference 必须包含 `yaml-dsl validate`、`yaml-dsl schema validate`、`yaml-dsl schema show` 与 `yaml-dsl schema path`

#### Scenario: canonical example 来源固定
- **WHEN** 生成器运行
- **THEN** 它必须从 `notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` 导出唯一 canonical example
- **THEN** 不得额外生成 minimal / advanced / examples index 形式的示例产物

### Requirement: Example Selection and Validation
系统 MUST 仅导出一个 canonical full example,目标路径固定为 `artifacts/skills/scalim-yaml-dsl/references/generated/example-full/ecommerce_report.yaml`.

该 canonical example MUST:
- 仅通过静态读取 `notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` 获得,不得执行 notebook
- 在导出后通过 `PROJECT_CLI_NAME yaml-dsl schema validate` 与 `PROJECT_CLI_NAME yaml-dsl validate` 校验
- 在内容包含位置敏感引用时(例如 `$schema` header),保留或重写为从导出目标位置可正确解析的形式

系统 MUST NOT 再要求 `# region SCALIM-SKILL:<tag>` 标注、notebooks > tests 的示例优先级竞争,或 minimal / relations / compute 示例齐备.

#### Scenario: canonical source 缺失
- **WHEN** `notebooks/marimo/examples/demo_big_data_report/by_yaml_dsl/ecommerce_report.yaml` 不存在
- **THEN** 生成器退出非零并提示 canonical example 来源缺失

#### Scenario: 不执行 notebooks
- **WHEN** 生成器导出 canonical example
- **THEN** 它只能静态读取 YAML 源文件,不得执行 notebook 代码

#### Scenario: 导出示例通过双重校验
- **WHEN** 生成器导出 canonical example
- **THEN** 测试必须验证导出结果同时通过 `yaml-dsl schema validate` 与 `yaml-dsl validate`

#### Scenario: 导出示例保留可用的 schema header
- **WHEN** 源示例包含 `# yaml-language-server: $schema=...` 头部
- **THEN** 导出结果中的 header 必须可从生成后的文件位置正确解析到真实 schema

### Requirement: Deterministic Manifest and Validation Mode
系统 MUST 输出 output_root 下的 `scalim-yaml-dsl.build-manifest.json`,记录 generated references 的输入/输出校验和与覆盖索引,并保证排序确定性.

系统 MUST 提供校验模式,重建 generated references 并逐字节比较受控输出;发现漂移即失败.
校验范围 MUST 仅包含生成器负责的受控输出,不得把手工维护的 skill 文件当作“应由生成器重建”的内容.

#### Scenario: 校验模式仅比较受控输出
- **WHEN** 已有 skill 目录下同时存在手工维护文件与 generated references
- **THEN** 校验模式只比较 `references/generated/` 与 manifest 中登记的文件
- **THEN** 不得因为手工维护文件内容不同而报告生成漂移

#### Scenario: 发生 generated reference 漂移
- **WHEN** 已有 generated references 与新生成内容不同
- **THEN** 校验模式返回非零并报告差异

## ADDED Requirements

### Requirement: Manual Skill Files Are Preserved
系统 MUST 将 `artifacts/skills/scalim-yaml-dsl/SKILL.md` 与非 generated references 视为手工维护文件.
生成器在 build 与 validate 模式下 MUST NOT 创建、覆盖、删除或重排这些手工维护文件.

#### Scenario: 保留手工维护的 SKILL.md
- **WHEN** skill 目录中已存在手工维护的 `SKILL.md`
- **THEN** 生成器运行后该文件内容保持不变

#### Scenario: 保留手工维护 references
- **WHEN** skill 目录中存在 `references/` 下的非 generated 文档
- **THEN** 生成器不得删除或重写这些文档

### Requirement: Generated References Are Executably Validated
系统 MUST 对生成出的 references 进行真实校验与测试,以证明生成逻辑可用而不是仅能“产出文本”.

至少 MUST 校验:
- 受控 YAML 示例可通过 YAML DSL 校验
- generated CLI/LSP reference 中引用的关键命令与 schema path 来源真实存在
- 生成器测试覆盖 manual/generated 边界,例如“不覆盖 SKILL.md”

#### Scenario: 生成示例通过 YAML 校验
- **WHEN** 生成器导出或索引 YAML 示例
- **THEN** 这些示例必须在测试中通过 YAML DSL 校验

#### Scenario: 手工/自动边界有回归测试
- **WHEN** 维护者修改生成器
- **THEN** 测试必须验证生成器不会覆盖手工维护的 `SKILL.md` 或其它非 generated references

## REMOVED Requirements

### Requirement: SKILL.md Structure
**Reason**：`SKILL.md` 改为手工维护的 task-driven skill 本体,不再适合由生成器按 schema dump 方式自动拼装.
**Migration**：将 `SKILL.md` 的维护迁移到 hand-authored workflow,生成器只生成 `references/generated/` 并由测试校验 manual/generated 边界.

### Requirement: Path Normalization
**Reason**：旧规范面向任意示例的绝对路径归一化与 `path_normalization` 清单字段,不再适用于单个仓库内 canonical example 布局.
**Migration**：若 canonical example 含位置敏感引用,仅对该引用做最小必要重写以保证导出后可用;不再要求通用 `path_normalization` 映射契约.

### Requirement: User-Oriented Guidance Links
**Reason**：面向使用者的 guidance 必须由手工维护的 skill 本体控制,而不是由生成器把链接模板硬编码进产物.
**Migration**：把用户导向、任务分流与引用顺序迁移到手工维护的 `SKILL.md` 与配套 manual references 中.
