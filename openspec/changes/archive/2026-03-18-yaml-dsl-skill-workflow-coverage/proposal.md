## Why

过去两天的变更把 workflow YAML 的 authoring surface 明显扩展了（例如 `runs[*].depends_on/init_vars`、`options.ctx`、`resources.*`、`runs[*].write_to`、以及 sheetbook 相关能力），同时 schema/实现也随之演进。
但目前 docs（尤其 `docs/doc/yaml-dsl/workflow.md`）与 `artifacts/skills/scalim-yaml-dsl/` skill 产物仍以 demand YAML 为主，导致：

- 使用方在写 workflow 时缺少权威指引，容易写出 schema 过不了或语义误解的配置；
- Agent/助手的路由与最小命令入口不完整，容易给出错误的校验/排错建议；
- OpenSpec index 中存在 “TBD” 元信息，影响“已覆盖/已实现”的可见性与可信度。

## What Changes

- 补齐 docs 对 workflow YAML 的覆盖，确保与当前 `src/scalim/dsl/by_yaml/schema/workflow.gen.json` 对齐（runs DAG、ctx、resources、write_to、并发契约、校验入口等）。
- 扩展 `scalim-yaml-dsl` agent skill：在任务路由与最小命令中纳入 workflow authoring/validate/debug。
- 扩展 skill 生成器：在 generated references 中纳入 workflow schema 的语法目录/索引，并将 workflow 相关 OpenSpec specs 纳入 requirement map（保持 doc governance：`.gen.` 文件与 AUTOGEN block 不手改，走生成入口）。
- 新增一条 upgrades 批次文档（SSOT 在 skill references），用于把近期 workflow DAG/ctx/resources/sheetbook 的 breaking/migration 信息收敛为可检索入口（docs 对应页面由 `just gen-docs` 生成）。
- 修复 `workflow-sheetbook-resources` spec 的元信息（补齐 Purpose/状态），消除 `openspec-index.gen.md` 的 “TBD” 观感问题。

本变更不引入运行时行为变更；目标是 **文档/skill 与已实现能力对齐**，并建立可重复生成与漂移门禁。

## Capabilities

### New Capabilities

- (none)

### Modified Capabilities

- `yaml-dsl-agent-guidance`: 扩展手工维护 skill 的任务路由与命令入口,覆盖 workflow authoring/validate/debug.
- `agent-skill-export`: 扩展受控生成 references 的覆盖面,使其纳入 workflow schema 与 workflow 相关 OpenSpec requirement map.

## Impact

- Docs site：`docs/doc/yaml-dsl/*`
  - 任何包含 `.gen.` 的文件为生成物；任何 `<!-- BEGIN/END AUTOGEN:<id> -->` 区块为受控注入区块（禁止手改区块内部）。
  - 生成入口：`just gen-docs`。
- Skill package：`artifacts/skills/scalim-yaml-dsl/`
  - 受控生成的 references 与输入/输出校验和在 `artifacts/skills/scalim-yaml-dsl.build-manifest.json`。
  - 生成入口：`just gen-agent-skill`；漂移校验：`just validate-agent-skill`。
- Generator/tooling：`packages/scalim-misc/src/scalim_misc/agent_skill_gen.py`（扩展生成内容范围；注意 `src/scalim/` 的 Python 3.6 运行时边界不受影响）。
- OpenSpec specs 元信息：`openspec/specs/workflow-sheetbook-resources/spec.md`（仅补齐 Purpose/状态，不改 REQUIREMENTS）。
