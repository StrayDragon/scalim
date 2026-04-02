## Context

仓库目前已经存在项目级配置文件 `scalim.yaml`，用于 YAML DSL 的 imports 治理与 editor/LSP project discovery（nearest-wins, zero-config fallback）。但与 demand/workflow 不同，`scalim.yaml` 缺少可绑定的 JSON Schema，因此：

- IDE 补全/结构校验缺失，用户只能靠文档 + 运行时/CLI 报错试错
- LSP/IDE 集成需要读取 `scalim.yaml` 作为 discovery 输入，但缺少 schema 会降低落地意愿

同时仓库已经具备成熟的 schema generation pipeline：

- SSOT：`src/scalim/dsl/by_yaml/schema_dsl/**`
- 生成物：`src/scalim/dsl/by_yaml/schema/{demand,workflow}.gen.json`
- 生成入口：`just gen-yaml-dsl-schema`
- drift gate：`tests/test_yaml_schema_generation.py`

因此更符合主线的做法，是把 `scalim.yaml` 纳入同一条“SSOT → 生成物 → drift gate”的管线，而不是手写 schema 或引入新的并行生成方式。

## Goals / Non-Goals

**Goals:**

- 提供 `scalim.yaml` 的 canonical JSON Schema 生成物，用于编辑器补全/校验。
- 复用现有 schema generation 入口（`just gen-yaml-dsl-schema`），并补齐 drift gate，避免生成物漂移。
- 明确 docs/生成物边界：哪些文件可手写、哪些是生成物、对应的刷新入口与验收口径。
- 不改变 `scalim.yaml` 的可选性：未配置时仍保持 zero-config fallback。

**Non-Goals:**

- 不改变 project discovery 的语义（nearest-wins/override 规则不变；不做跨层合并）。
- 不在本 change 内交付 VSCode 扩展或 LSP server 发行物（仅提供 schema 与规范/文档）。
- 不引入新的控制面配置文件（不新增平行的 `*.config.yaml`）。

## Decisions

1) **Schema scope：聚焦 `yaml_dsl` 区域**

- schema v1 仅覆盖当前 `scalim.yaml` 的稳定使用面：`yaml_dsl.import_aliases` / `yaml_dsl.import_allowed_roots` / `yaml_dsl.editor.*`。
- 其它顶层 key 保持可扩展（避免把 `scalim.yaml` 锁死为“只能承载 YAML DSL 配置”的单一用途）。

2) **Schema SSOT：复用 `schema_dsl` 而不是手写 JSON**

- 在 `src/scalim/dsl/by_yaml/schema_dsl/` 增加 project-config 对应的 meta model（类似 demand/workflow 的 dataclass meta + builder）。
- 生成物写入 `src/scalim/dsl/by_yaml/schema/`（与现有 demand/workflow schema 同目录，便于发现与引用）。

3) **命名：提供稳定可引用路径**

- 生成物文件名采用稳定且不与需求/workflow 混淆的命名（例如 `scalim_yaml.gen.json` 或 `project_config.gen.json`）。
- 文档侧给出 IDE 绑定示例（`$schema` header / YAML language server 配置）。

4) **drift gate：与现有 schema generation 一致**

- 扩展现有的 schema generation 测试或新增专门测试，确保生成结果与仓库内 `.gen.json` 保持一致。
- 在 `just qa` 的漂移门禁下自然覆盖（不单独引入新的 CI 入口）。

5) **多层配置（大型项目）语义不变，但文档要讲清**

- `scalim.yaml` 仍是 nearest-wins（从入口 YAML 向上找最近的 `scalim.yaml`），因此大型仓库可以存在多份配置文件，不要求“全项目唯一一份”。
- schema 仅描述“单个 `scalim.yaml` 文件的结构”，不影响 discovery 选择哪个文件。

## Risks / Trade-offs

- [schema 过严导致未来扩展被误报] 若 schema 把顶层/子节点完全封死，未来扩展会在旧 schema 下报错 → 缓解：v1 仅对 `yaml_dsl` 关键结构做强约束，顶层保持扩展口；并通过生成入口刷新。
- [命名/绑定路径不稳定] schema 文件名/路径若频繁变化，会降低 IDE 绑定价值 → 缓解：选择稳定命名；变更通过文档与迁移说明协调。
- [多层 scalim.yaml 引发排障成本] 用户不知道“实际使用的是哪份配置” → 缓解：discovery 输出包含 `scalim_yaml_path`，并在 docs 中强调查看该信息用于排障。

## Migration Plan

- 引入新 schema 生成物并纳入 `just gen-yaml-dsl-schema`。
- 更新 docs 给出 `scalim.yaml` schema 绑定方式。
- 无运行时行为变更；现有项目可选择性引入 `scalim.yaml` 并绑定 schema。

## Open Questions

- 生成物命名最终采用 `scalim_yaml.gen.json` 还是 `project_config.gen.json`？
- schema 对未知字段的策略：是否在 `yaml_dsl` 子树内启用严格 `additionalProperties: false`（更强约束）？
