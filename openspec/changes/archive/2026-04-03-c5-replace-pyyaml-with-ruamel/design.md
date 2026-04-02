## Context

仓库当前在 `src/scalim/vendor/yamlx/` 下同时 vendors 了 `PyYAML` 与 `ruamel.yaml`,但 `src/scalim/` 的运行时 YAML 解析仍以 `PyYAML` 为默认入口(`scalim.vendor.yamlx.yaml`)。与此同时,YAML 解析/定位/duplicate key/error 的实现分散在多个模块(统一 loader、workflow loader、CLI validate、validator、project config、imports)。这导致:

- YAML 1.1 vs 1.2 语义边界不明确(尤其是 bool-like 标量)。
- 同一份 YAML 在不同入口可能出现行为漂移(错误结构、定位口径、重复键语义)。
- 无法稳定实现“保留注释/格式/anchors”的 YAML 编辑(例如 schema modeline 的批量 upsert)。

本 change 采取“一步到位迁移”策略: 默认 YAML backend 直接切换到 vendored `ruamel.yaml`(YAML 1.2 语义),同时保留 vendored `PyYAML` 源码/扩展以满足 vendors 同步审计与紧急排障需要(不作为主线运行时入口)。

约束与文档治理:

- `src/scalim/` 运行时必须兼容 Python 3.6,并且在 vendors-sync 下不依赖外部安装包。
- 本 change 的手工 SSOT 包括 `openspec/changes/...` 工件、`src/scalim/vendor/README.md` 与 `src/scalim/vendor/yamlx/SOURCE.md`。
- 任意 `.gen.*` 文件与 `<!-- BEGIN AUTOGEN:... -->` 注入区块均不得手改;如需更新由 `just gen-docs` 刷新生成物。

## Goals / Non-Goals

**Goals:**

- 将 `src/scalim/` 运行时 YAML 解析默认后端切换为 vendored `ruamel.yaml`(`YAML(typ=\"safe\")` + YAML 1.2 语义)。
- 在现有架构内收敛 YAML 解析为单一事实来源:safe load、duplicate key 策略、compose/location index、parse error → ErrorEnvelope。
- 将 `yaml-dsl upsert-lsp-comment` 的写入实现迁移到 `ruamel.yaml` 的 round-trip(`typ=\"rt\"`),并引入“no-op 字节级幂等”门禁:`load` 后立即 `dump` MUST 与原文完全一致。
- 保留 vendored `PyYAML` 代码在 `src/scalim/vendor/yamlx/`(便于审计/对拍/紧急排障),但主线代码允许与 `ruamel.yaml` 紧耦合,不再维护双后端运行时切换。

**Non-Goals:**

- 不提供一个面向第三方调用方的通用“YAML 编辑 SDK”;round-trip 能力先服务内部 CLI/工具链。
- 不承诺保持 YAML 1.1 的旧标量语义(例如 `on/yes/no` 作为 bool);这是本变更的明确 BREAKING 语义边界。
- 不移除 vendored `PyYAML`(本 change 仅改变默认运行时入口)。
- 不在本 change 内重构 `notebooks/marimo/` 或 `packages/` 的运行时边界;它们仅作为样本语料与回归参考。

## Decisions

### 1) 默认 YAML backend: vendored `ruamel.yaml` + YAML 1.2(一次性切换)

- 解析:使用 `ruamel.yaml.YAML(typ=\"safe\")` 并显式启用 YAML 1.2 语义。
- 目的:清晰化语义边界,并为后续编辑能力(`typ=\"rt\"`)建立同源基础。
- 替代方案:
  - 继续用 PyYAML:无法提供稳定的 round-trip 编辑能力,且 YAML 1.1/1.2 边界仍不清晰。
  - 运行时可切换双后端:会把复杂度长期留在代码中,与“一步到位迁移”目标冲突。

### 2) 继续使用现有统一 loader 模块作为“窄 facade”,不引入新的包层级

- `src/scalim/dsl/by_yaml/_internal/config_parsing/yaml_load.py` 继续作为统一入口(load + location + ErrorEnvelope),但其内部实现改为 ruamel。
- 目的:最小化结构调整成本,同时让所有入口共享同一行为。
- 替代方案:
  - 新建独立 vendored 包(例如 `vendor/yamldoc`):会放大迁移面与组织成本;本次不做。

### 3) Duplicate key 策略保持现有口径

- 默认 `detect_duplicate_keys=True` 时:显式重复键 MUST 报错,并给出重复键出现处的行列定位(ErrorEnvelope 结构一致)。
- 当调用方显式关闭检测时:允许重复键,语义保持“后写覆盖前写(last-wins)”,以对齐当前 PyYAML 行为与既有调用预期。

### 4) Location index 与 parse error 仍以“AST mark → 1-based 行列”为口径

- 位置索引继续提供:根、mapping key、sequence item 的行列定位,并与 `normalize_yaml_diagnostic_path()` 的路径规则匹配。
- parse error 继续通过 `safe_yaml_parse_error_message()` 生成不回显正文的消息,并封装为稳定的 ErrorEnvelope。

### 5) Round-trip 编辑(`typ=\"rt\"`)引入稳定性门禁(no-op 字节级幂等)

- `yaml-dsl upsert-lsp-comment` 使用 `ruamel.yaml.YAML(typ=\"rt\")` 进行读写,目标是保留注释/格式/anchors。
- 必须实现两类门禁:
  - **No-op gate**:对 canonical YAML 文件执行 `load` → `dump` 必须字节级完全一致(否则视为不安全,命令应失败并提示)。
  - **Minimal edit gate**:upsert 仅允许修改 schema modeline 所在行;正文不得无意义重排。
- 预期需要对 round-trip 的 dump 参数做稳定化(例如缩进/宽度、quotes、anchors always_dump、indent guess),并以测试锁定。

### 6) 回滚策略:保留 vendored PyYAML 代码,依赖“代码回滚”而非运行时开关

- 本 change 不引入运行时 backend toggle。
- 若出现紧急问题:通过 revert/patch 回滚到上一个默认 backend(PyYAML)是可行的,因为 vendored PyYAML 代码仍在仓库内。

## Risks / Trade-offs

- `[YAML 1.1→1.2 标量语义变化]` → 用户 YAML 若依赖 `on/yes/no` 作为 bool 会出现行为变化。缓解:以 corpus parity 对拍与 fixtures 回归证明对 repo 样本无影响,并在 release notes/错误提示中明确边界。
- `[ruamel duplicate key 行为与 PyYAML 不一致]` → ruamel 默认会抛 DuplicateKeyError。缓解:在统一 loader 内实现与现有一致的 duplicate key 策略,并用测试锁定(含 last-wins 分支)。
- `[round-trip dump 稳定性]` → 可能出现 doc marker、缩进、anchors、换行风格等非预期变化。缓解:no-op gate + minimal edit gate + 选定 canonical YAML 作为黄金样本。
- `[导入链路/无外部依赖约束]` → 必须确保 vendors-sync 下仍可用。缓解:spec 要求 + py36 docker smoke check。

## Migration Plan

1. 更新本 change 的 OpenSpec 工件(proposal/design/specs/tasks)以反映“一步到位迁移 + ruamel rt 编辑”。
2. 将统一 loader、workflow loader、CLI validate/imports/project-config 的 YAML 解析收敛到 ruamel-based 实现(不新增独立包层级)。
3. 将 `yaml-dsl upsert-lsp-comment` 切换到 ruamel round-trip,并落地 no-op/minimal-edit 门禁。
4. 增补回归与门禁:
   - corpus parity(ruamel vs vendored PyYAML)对拍 tests(用于迁移期风险控制)
   - py36 docker smoke checks(vendored import + parse)
   - round-trip no-op gate tests
5. 若实现影响 docs/specs 注入区块或生成物:仅通过 SSOT + `just gen-docs` 刷新;禁止手改生成物。
6. 运行 `just openspec-check` 与相关 QA/py36 checks 完成验收。

## Open Questions

(无)