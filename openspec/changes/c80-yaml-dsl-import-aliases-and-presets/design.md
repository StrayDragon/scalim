## Context

Imports v2 在放开 `../` 与子目录导入后，跨 demand 复用更顺，但也引入了两个治理诉求：

1) **路径口径**：希望在 authoring 时有稳定的“项目级根”（例如 `@/fragments/common.yaml`），避免目录移动导致相对路径大面积改动。
2) **安全边界**：跨目录读取后需要明确、可配置的“允许读取的 roots/aliases”，否则 imports 可能退化为“任意读文件”的通道。

同时，框架侧也可能沉淀一组高复用 YAML 片段（presets）。如果每个项目都复制一份，维护与升级成本会很高，因此需要一种“引用 scalim 内置 presets”的语法，并配套治理边界（只读、本地、可审计、不可任意读包内文件）。

当前实现现状：

- `src/scalim/dsl/by_yaml/config_parsing/imports.py`：
  - imports mapping 的 value 只允许相对 `.yaml/.yml` 路径；
  - 显式拒绝 `@/` 与 `COMMON:/` 一类“预留 alias 前缀”，并拒绝任意 URI scheme（`*://...`）；
  - 解析基准是当前 YAML 文件所在目录（`base_dir = yaml_path.parent`），最终 `.resolve()` 到绝对路径。
- `src/scalim/dsl/by_yaml/config_parsing/effective_yaml.py`：
  - `load_effective_demand_yaml()` 仅做 `template_vars` + `imports/$import` 展开，不做 schema/semantic 校验；
  - 暂无 “render explain / provenance” 输出能力。
- `src/scalim/dsl/by_yaml/schema_dsl/builder.py`：
  - 对顶层 `imports` 的 path 字符串做了 pattern 限制（明确禁止 `@/...`、`*://...`、`COMMON:/...`）。

约束：

- 运行时需兼容 Python 3.6（避免引入仅 3.8+ 可用的资源 API；优先用 stdlib `pkgutil.get_data` 等方案）。
- `scalim://` 必须离线、本地，只读已安装包资源；不得走网络。
- 任何 `.gen.*` 文件禁止手改；schema SSOT 在 `src/scalim/dsl/by_yaml/schema_dsl/`，生成入口见 `justfile`。

## Goals / Non-Goals

**Goals:**

- 支持可选的项目级配置文件 `scalim.yaml`：
  - `yaml_dsl.import_aliases`：配置 alias 前缀到目录映射（例如 `@` → `./`）
  - `yaml_dsl.import_allowed_roots`（可选）：限制 imports 目标必须落在允许 roots 内，越界 fail-fast
- 支持 `scalim://...` 形式的 imports，用于引用 scalim 内置 YAML presets：
  - 仅本地包资源（离线），并限制可引用范围（白名单/注册表）
  - render 时可展开为 effective YAML
- 失败时提供可诊断错误（至少包含解析基准与目标绝对路径；并保留 import trace 便于定位）
- 更新 YAML DSL schema，使编辑器侧能接受新语法（运行时校验仍为 SSOT）

**Non-Goals:**

- 不支持任意 URI scheme / 网络导入。
- 不放开绝对路径、Windows 盘符、UNC、反斜杠分隔符（保持可移植与可审计）。
- 不在本变更中引入 roundtrip YAML（注释/anchors 保留）能力（如需 `ruamel.yaml`，单独提案）。
- 不把 imports 治理扩展到 demand 之外的所有路径字段（仅针对 imports）。

## Decisions

### 1) `scalim.yaml` 作为项目级 imports 治理入口（可选）

新增一个轻量项目配置解析层（建议落在 `src/scalim/dsl/by_yaml/config_parsing/`）：

- 解析文件：`scalim.yaml`
- 顶层字段：`yaml_dsl`
  - `import_aliases: { "<prefix>": "<dir>" }`
  - `import_allowed_roots: [ "<dir>", ... ]`（可选）

定位策略（建议）：

- 从 demand YAML 文件所在目录开始向上查找 `scalim.yaml`，**最近者优先**（nearest wins）
- 若未找到则视为“无项目配置”，保持现有 imports v2 行为
- 为提升可维护性与在 CI/容器中的可预测性，推荐提供**显式 override**（Python API 或 CLI 参数，例如 `--scalim-yaml` / `--project-root`）：
  - override 存在时 MUST 以 override 为准（不得再向上查找）
  - override 不存在时才使用 nearest-wins 向上查找
  - MVP 可先落地 Python API override；CLI override 可后置但应在 design 中保留口径

### 2) Alias 应用发生在 imports path 归一化之前

对 `imports.<alias>` 的 value（路径字符串）做解析时：

1. 先尝试匹配 `yaml_dsl.import_aliases` 中配置的 prefix（建议做“最长前缀优先”，避免 `@` 与 `@@` 等冲突）。
2. 若匹配，要求路径形态为 `<prefix>/...`（例如 `@/fragments/common.yaml` 或 `COMMON:/x.yaml`），把 prefix 替换为其映射目录，并将剩余部分拼接到该目录下。
3. 对替换后的路径继续执行 imports v2 的安全校验与归一化（拒绝绝对路径、盘符、反斜杠；要求 `.yaml/.yml`）。

这样可以保证：

- 未配置时仍然拒绝预留前缀（避免把“看起来像 project-root”的语法误导成相对路径）。
- 配置存在时，alias 只是改变“解析基准目录”，后续安全边界仍由统一的校验与 allowed-roots 控制。

### 3) Allowed roots 在最终 `resolve()` 后强制校验（fail-fast）

当 `yaml_dsl.import_allowed_roots` 存在时：

- 将 roots 解析为绝对目录（建议相对 `scalim.yaml` 所在目录）
- 每个 imports 目标在 `Path(...).resolve()` 后必须满足：至少在某个 root 目录树下
  - Python 3.6 兼容做法：`resolved.relative_to(root)` 捕获 `ValueError`
- 越界直接抛错，错误信息至少包含：
  - 解析基准（当前 YAML 文件所在目录 / scalim.yaml 所在目录）
  - 目标绝对路径
  - 命中的 alias（若有）
 - roots containment 的实现与错误格式 MUST 复用 `yaml-path-escape-hardening` 的 allow-roots helper（避免两套策略与诊断字段漂移）

### 4) `scalim://...` presets 采用“注册表 + 本地资源加载”

`scalim://` 解析策略：

- 仅接受 `scalim://` scheme；其他 `*://` 仍拒绝
- 将 URI 解析为 preset id（例如 `yaml-dsl/presets/common.yaml`）
- 通过白名单/注册表映射 preset id → 资源位置（或资源内容），拒绝未知 id

资源承载建议：

- 将 YAML presets 作为包内资源文件随发行物发布，并用 stdlib `pkgutil.get_data` 读取（兼容 Python 3.6 与 zipimport）
- presets 内部不应再引用任意文件路径；如需复用，建议只允许引用其它 `scalim://...` preset（仍走注册表）

### 5) Explain / provenance 作为可选输出，不破坏现有 API

保持 `load_effective_demand_yaml()` 的返回类型不变，新增可选 API（示例）：

- `load_effective_demand_yaml_explain(...) -> (effective_yaml, explain)`

explain 输出至少能标识每个导入片段的来源：

- file：绝对路径
- preset：`scalim://...` preset id（或注册表 key）

实现上可复用现有 `YamlImportExpansionError.trace` 思路，但需要让 trace item 能表达“非 Path 来源”（preset）。可选方案：

- 扩展 `ImportTraceItem` 为包含 `source: str`（file path 或 preset id），避免强行伪造 `Path("scalim://...")`
- 或者独立维护 `explain` 结构，不改现有错误 trace（先最小改动）

> 推荐：`explain` 使用结构化返回（dict/list）作为 SSOT；CLI 若需要“人类友好”展示，可在 CLI 层做渲染，但底层结构必须统一且可复用。

### 6) Schema 边界：编辑器 schema 放宽，运行时校验为 SSOT

由于 alias 与 `scalim://` 的可用性取决于项目配置与注册表，JSON schema 无法精确表达所有约束。

策略：

- 在 `schema_dsl` 中放宽 `imports.*` 的 path pattern，使其接受：
  - 现有相对路径形式
  - `@/...` 与 `NAME:/...` 形式（允许但不保证运行时通过）
  - `scalim://...` 形式
- 运行时仍以 `imports.py` 的校验与 `allowed_roots` / preset registry 为准，并提供更强诊断

## Risks / Trade-offs

- [风险] 向上查找 `scalim.yaml` 可能让行为“隐式依赖目录结构”。
  → 缓解：nearest-wins + 明确错误诊断；后续提供显式 override 参数。

- [风险] alias 放宽后可能被误用成任意读文件的捷径。
  → 缓解：`import_allowed_roots` 强制边界（可选但推荐）；仍拒绝绝对路径/盘符/反斜杠；默认无 `scalim.yaml` 时继续拒绝预留前缀。

- [风险] presets 若允许任意包内路径会成为“读取发行物任意文件”的通道。
  → 缓解：注册表白名单；仅允许预定义 id；不提供直接 path passthrough。

- [风险] schema 放宽会让编辑器接受一些运行时会拒绝的字符串。
  → 缓解：在 schema 的 `markdownDescription` 中明确“运行时为准”，并确保运行时错误信息可诊断。

## Migration Plan

0. 前置依赖：先完成并稳定 `yaml-path-escape-hardening` 的 allow-roots helper 与错误格式（本变更必须复用）。
1. 实现 `scalim.yaml` 解析与定位（nearest-wins + 可选显式 override），并为 imports 解析提供可选 project config。
2. 在 `imports.py` 中接入 alias 展开与 allowed-roots 校验（复用 allow-roots helper；见 `yaml-path-escape-hardening`），保持默认行为不变（无配置时仍拒绝预留前缀与 URI scheme）。
3. 实现 `scalim://` preset registry 与本地资源加载，并在 render 中展开。
4. （可选）新增 explain/provenance 输出 API（结构化 SSOT），并在 preset/file 导入时记录来源。
5. 更新 schema SSOT（`src/scalim/dsl/by_yaml/schema_dsl/`），运行 `just gen-yaml-dsl-schema` 与 `just gen-yaml-dsl-editor-schema` 刷新生成物。
6. 增加测试覆盖 alias/roots/presets，并验收 `just qa` + `just openspec-check`。

## Open Questions

- `import_allowed_roots` 的推荐默认值：未配置时是否默认等价于“仅允许在 scalim.yaml 所在目录树下”？（规范目前为 MAY，建议保持“未配置则不启用检查”。）
> 保持“未配置则不启用检查”

- preset id 的命名与版本治理：是否需要把 `scalim://` 解析限定为固定前缀（例如 `scalim://yaml-dsl/presets/<name>`）并在文档中列举可用清单。
> 可以 也可以后置

- explain 输出的稳定格式：返回结构（dict/list）还是面向日志/CLI 的文本；是否需要与 `YamlImportExpansionError.trace` 统一。
> 结构化文本会好一些 如果要做cli 我们可以简单的处理人类友好 最好能统一

- 是否必须提供显式 override（避免仅依赖向上查找）？  
> 推荐提供：MVP 先落地 Python API override；CLI override 可后置，但必须保持“override 优先、nearest-wins 其次”的稳定规则，避免 CI/容器差异导致隐式行为变化。
