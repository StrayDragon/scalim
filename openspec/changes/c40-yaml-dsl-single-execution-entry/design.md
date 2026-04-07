## Context

当前 `scalim.yaml` 在同一份文件中同时承载：

- YAML fragments imports 的治理与安全边界（`yaml_dsl.import_aliases` / `yaml_dsl.import_allowed_roots`）
- 编辑器/LSP 的 project discovery（`yaml_dsl.editor.python_roots` / `yaml_dsl.editor.kind_overrides`）
- CLI runner 的运行期默认值（`yaml_dsl.runner.*`，尤其是 allowlist 与并行/模板策略）

其中 `yaml_dsl.runner` 只对 CLI 生效，而 Python 的官方执行入口 `scalim.dsl.by_yaml.run/compile/run_workflow` 仅接受 `RunOptions`，不会隐式读取 `scalim.yaml`。这造成：

- 用户误以为“项目里配置了 `scalim.yaml` 就能直接 run”，实际 Python 仍会因缺少 allowlist fail-fast。
- 同一份运行期策略在 CLI 与 Python 形成两个维护入口，容易漂移。

本变更选择 **方向 A：只保留一个执行入口（Python）**，将 CLI 收敛为“校验/工具”，并将 `scalim.yaml` 收敛为“authoring/tooling 配置”。

## Goals / Non-Goals

**Goals:**

- 只保留一个官方“执行”入口：Python `scalim.dsl.by_yaml.run/compile/run_workflow`。
- 移除 `scalim-cli yaml-dsl run` / `scalim-cli yaml-dsl workflow run`，避免在 CLI 中形成第二套执行路径与运行期默认值治理。
- `scalim.yaml` 仅承载与“YAML authoring 与编辑器体验”相关的项目级配置：
  - imports 治理（alias/roots）
  - LSP/discovery（python roots、kind overrides）
- 通过命名澄清职责：将 `yaml_dsl.editor` 重命名为 `yaml_dsl.lsp`。
- 不做兼容层：旧键名/旧段落要求下游一次性升级（提供迁移说明与可选的机械化升级工具，但不在 runtime 留兼容逻辑）。

**Non-Goals:**

- 不修改 imports v2 的语义与合并规则（deep-merge / list replace / allow-roots 越界 fail-fast）。
- 不调整运行时 allowlist/resolver 的安全策略（仍要求显式 allowlist；不引入“隐式信任模式”）。
- 不在本变更中引入 Django 风格“import Python settings 作为默认配置”的机制（避免把 CLI/LSP 引入执行用户代码的风险）。

## Decisions

### 1) `yaml_dsl.editor` → `yaml_dsl.lsp`（BREAKING）

原因：

- “editor” 容易被理解为“影响运行”的配置面；而实际用途是 LSP/discovery 与静态解析。
- “lsp” 更准确表达其消费者（`scalim-yaml-dsl-lsp` 与编辑器集成），也更利于和 runtime policy 边界区分。

落地：

- 更新 `scalim.yaml` schema DSL 与生成 schema（`scalim_yaml.gen.json`）。
- 更新 LSP shared core 与 server 的解析路径、code actions 的写入路径。
- 更新 docs 与 skill reference，统一示例配置块。

### 2) 移除 `yaml_dsl.runner`（BREAKING）

原因：

- runner 段本质是 CLI 的 defaults，而不是运行时契约；与 `RunOptions` 并存造成误会与双维护。
- 运行期策略（allowlist、并行、模板 sandbox）应由“执行入口”装配，且必须显式（更可审计、更不隐式）。

落地：

- 删除 `scalim.yaml` 解析中的 `YamlDslRunnerConfig` 与相关字段。
- 从 `openspec/specs/yaml-dsl-project-config-schema/spec.md` 中移除对 `yaml_dsl.runner.*` 的要求，并补充“项目配置不承载运行期策略 defaults”的约束。

### 3) 移除 CLI 执行子命令（BREAKING）

原因：

- 与“单执行入口”目标冲突：CLI run 实质上是第二套执行入口，即使内部复用 by_yaml 入口，也会迫使维护 defaults、help、错误信息与文档口径。
- CLI 的最佳定位是“authoring/tooling”：validate/schema/modeline 等静态工具；执行应落到 Python（可接入 observability、hooks、sink、统一运行上下文）。

落地：

- 从 `src/scalim/cli/yaml_dsl.py` 删除 `run` 与 `workflow run` 子命令及其参数/实现。
- 同步更新用户文档与 skill docs：不再出现 `scalim-cli yaml-dsl run` 与 `scalim.yaml yaml_dsl.runner` 的说明。

替代路径（文档层面）：

- 提供最小 Python wrapper 示例（脚本/模块），用于“命令行一键执行”需求，但执行仍由 Python `RunOptions` 显式装配。

## Risks / Trade-offs

- [易用性回退] 习惯用 CLI 直接跑 YAML 的用户需要迁移到 Python wrapper。→ 缓解：提供最小可复制的 runner 脚本示例，并在错误信息/文档中指向该路径。
- [破坏性升级] `scalim.yaml` 键名迁移会导致 LSP/discovery 与 imports 治理在升级窗口内报错。→ 缓解：提供明确的迁移指南；LSP code action 可选增加“Rename editor→lsp”的 quick fix（纯文本 edit，无副作用）。
- [生态引用] 下游可能在文档/脚本里引用 `scalim-cli yaml-dsl run`。→ 缓解：在 changelog/upgrade guide 中列出删除项与替代方案；必要时提供单版本过渡提示（仅文档层面，不做兼容实现）。

## Migration Plan

1. **升级 `scalim.yaml`**
   - 将 `yaml_dsl.editor` 重命名为 `yaml_dsl.lsp`
   - 删除 `yaml_dsl.runner` 段落
2. **迁移执行方式**
   - 将原先 CLI run 的执行方式迁移到 Python wrapper（显式传入 `RunOptions.allowed_modules/allowed_functions` 等运行期策略）
3. **更新文档与团队模板**
   - `docs/doc/yaml-dsl/**`、`artifacts/skills/scalim-yaml-dsl/**`、示例命令统一口径：CLI 只做 validate/schema；执行只走 Python
4. **漂移门禁**
   - 更新 OpenSpec specs 与 schema 生成物后，运行 `just openspec-check` 与 schema/doc 生成任务（由现有 gate 兜底）。

## Open Questions

- 是否需要一个专门的“迁移/升级”CLI 子命令（例如把 `yaml_dsl.editor` 自动改写为 `yaml_dsl.lsp`）以降低升级成本？该命令属于 tooling，不会引入执行入口，但会增加维护面。
> 不需要, 注意 artifacts/skills/scalim-yaml-dsl 需要更新即可

- 对外沟通是否需要在一个发布周期内保留“旧命令被删除”的明确提示（文档/错误信息层面），以减少用户升级惊讶。
> 不需要

