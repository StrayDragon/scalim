> 一句话描述: 建立 YAML→Python 引用同步机制（引用索引、一致性诊断与 CLI 入口），把 loader/`call_by` 等 Python 引用破坏问题前移到编辑期与 CI。

## Why

YAML DSL 通过 `loader:` / `call_by:` 等字段以字符串形式引用 Python 可调用对象；当 Python 侧重命名/移动实现时，这些引用会静默破坏，且 Python LSP/静态分析无法感知“在 YAML 中被使用”，导致重构与清理成本显著上升。

我们需要一套跨编辑器可复用、静态无副作用的“YAML → Python 引用同步”机制：让引用可被索引/诊断/修复，并把一致性问题前移到编辑期与 CI/提交前。

## What Changes

- 在 `scalim-yaml-dsl-lsp` 中引入 YAML→Python 引用同步子系统（增量、可缓存）：
  - 扫描 YAML 文档内的 `loader` / `call_by`（head）/ `retry.should_retry` 等 Python 引用，构建引用索引（symbol → YAML locations）。
  - 生成可被 IDE/静态工具消费的“引用标记”工件（例如 `.pyi`/marker 模块）以降低“未使用”误报并提供可追踪的引用来源。
  - 对 Python 侧变更做一致性检查：当被引用符号消失/重命名时，输出可诊断结果，并在 LSP 侧发布诊断与（可选）Quick Fix。
- 扩展项目配置 `scalim.yaml`（LSP/discovery 配置面）：
  - 新增 `yaml_dsl.lsp.reference_sync` 配置段（启用/路径/节流/扫描策略等）。
  - 更新 `scalim.yaml` JSON Schema 生成物以提供 IDE 补全与 schema-only 校验（SSOT 在 `src/scalim/dsl/yaml_dsl/schema_dsl/models/scalim_yaml.py`；生成物通过 `just gen-yaml-dsl-schema` 刷新）。
- 提供 CLI 自动化入口（用于 CI / pre-commit / 脚本化消费）：
  - `scalim-cli yaml-dsl check-consistency`：输出破坏引用的一致性问题（可 JSON）。
  - `scalim-cli yaml-dsl generate-yaml-python-ref-stubs`（命名待定）：生成/刷新引用标记工件与索引。
  - `scalim-cli yaml-dsl fix-consistency`（可选 MVP）：交互/半自动修复 YAML 引用字符串。

## Capabilities

### New Capabilities
- `yaml-dsl-lsp-python-ref-sync`: YAML DSL LSP 侧的 YAML→Python 引用索引、同步、诊断与（可选）修复能力。
- `yaml-dsl-cli-python-ref-sync`: 面向自动化的 YAML→Python 引用一致性检查/工件生成 CLI 契约。

### Modified Capabilities
- `yaml-dsl-lsp-server`: 扩展 LSP server contract（新增/增强与 YAML→Python 引用同步相关的请求、诊断与代码操作）。
- `yaml-dsl-project-config-schema`: 扩展 `scalim.yaml` schema 与解析面，覆盖 `yaml_dsl.lsp.reference_sync` 并纳入 SSOT→生成物→drift gate 链路。

## Impact

- 受影响代码（预期）：
  - `packages/scalim-yaml-dsl-lsp/src/scalim_yaml_dsl_lsp/`：新增引用扫描/索引/工件生成/一致性检查模块，并在 `server.py` 集成诊断与请求。
  - `src/scalim/dsl/yaml_dsl/_internal/config_parsing/project_config.py`：解析与校验 `yaml_dsl.lsp.reference_sync`（Python 3.6 边界）。
  - `src/scalim/dsl/yaml_dsl/schema_dsl/models/scalim_yaml.py`（SSOT）与 `src/scalim/dsl/yaml_dsl/schema/scalim_yaml.gen.json`（生成物）。
  - `packages/scalim-cli/`：新增/扩展 `yaml-dsl` 子命令（复用共享实现，避免复制语义）。
- 受影响工程治理：
  - `.scalim/` 作为生成目录需 gitignore；且生成物应避免进入 ruff/QA 的强约束路径（以保证本地生成后 `just qa` 稳定）。
