## ADDED Requirements

### Requirement: Reference sync MUST build and persist a YAML→Python reference index (incremental)
当 `scalim.yaml yaml_dsl.lsp.reference_sync.enabled=true` 时，系统 MUST 构建并持久化 YAML→Python 引用索引：

- 索引 MUST 写入到 `<project_root>/<scalim_dir>/index/refs.gen.json`（默认 `scalim_dir=".scalim"`）。
- 索引 MUST 为可 JSON 序列化对象，且 MUST 包含：
  - `version`（整数，便于后续结构演进）
  - `generated_at`（UTC ISO8601 字符串）
  - `project_root`（绝对路径字符串）
  - `python_roots`（绝对路径字符串数组；来自 project discovery）
  - `references`（mapping：`symbol_key` → 结构化引用数据）
  - `yaml_files`（mapping：`yaml_file` → mtime 与引用列表，用于增量失效）
- `symbol_key` MUST 使用 `"{module_path}:{entry_attr}"` 形式（其中 `call_by` 使用 head reference，不包含参数段）。
- 索引更新 MUST 支持增量：当某个 YAML 文件内容变化时，系统 MUST 仅更新该 YAML 的引用集合，并回收旧引用。

#### Scenario: changed YAML updates index incrementally
- **GIVEN** 某 YAML 包含 `loader: "pkg.mod:func"`
- **WHEN** 系统对该 YAML 执行引用扫描并落盘索引
- **THEN** `refs.gen.json.references` MUST 包含键 `pkg.mod:func`
- **AND** 该键下的 `yaml_refs` MUST 至少包含该 YAML 文件的一条引用记录

### Requirement: Scanner MUST extract Python references from YAML DSL fields (static, no side effects)
系统 MUST 以静态方式从 YAML DSL 中抽取 Python 引用，并满足：

- 扫描 MUST 覆盖至少以下字段：
  - `loader`
  - `call_by`（仅 head：`(` 之前的引用前缀）
  - `retry.should_retry`
- 扫描 MUST 支持 YAML block scalar（`|`/`>` 及其变体）与 multiline 字符串值。
- 扫描 MUST NOT 执行用户代码；只允许文件读取与 AST 解析（若需要）。
- 对无法解析的引用字符串，系统 MUST 降级为“忽略该引用 + 可诊断信息”（不得 crash）。

#### Scenario: call_by string yields head reference
- **WHEN** YAML 包含 `call_by: "pkg.mod:fn(x=a)"`
- **THEN** 扫描结果 MUST 产出引用 `pkg.mod:fn`
- **AND** 参数段 MUST NOT 进入 `symbol_key`

### Requirement: Stub/marker artifacts MUST be generated deterministically for referenced symbols
系统 MUST 生成可被 IDE/工具消费的引用标记工件，并满足：

- 工件 MUST 写入到 `<project_root>/<scalim_dir>/stubs/`（默认 `.scalim/stubs/`）。
- 对每个被引用的 Python module，系统 MUST 生成一个对应的 `.pyi` 文件（镜像包路径）。
- 每个被引用的符号 MUST 在 stub 中出现一个 `def <name>(...) -> ...: ...` 的 stub 声明。
- stub 内容 MUST 包含机器可识别的标记行：`# pragma: scalim-yaml-ref`，并包含该符号的 YAML 引用明细（至少包含 `path/line/field/ref`）。
- 输出 MUST 稳定（同一索引输入产生字节级一致的输出，排序稳定）。

#### Scenario: stubs include pragma marker and YAML refs
- **GIVEN** 索引中存在 `pkg.mod:func` 且其 `yaml_refs` 非空
- **WHEN** 系统生成 stubs
- **THEN** 对应 stub 文件 MUST 包含 `# pragma: scalim-yaml-ref`
- **AND** MUST 包含至少一条 YAML 引用明细（含 `path` 与 `ref`）

### Requirement: Consistency check MUST report broken YAML→Python references
系统 MUST 能对引用索引执行一致性检查，并满足：

- 当某个 `symbol_key` 无法被静态解析到任何 Python 定义位置时，系统 MUST 将其报告为不一致项。
- 不一致项 MUST 至少包含：
  - `symbol_key`
  - 受影响的 YAML 引用列表（文件路径 + 行号 + 字段类型）
  - 可读的失败原因（例如“module not found / attribute missing”）

#### Scenario: deleted Python symbol yields inconsistency
- **GIVEN** 索引中存在 `pkg.mod:func`
- **WHEN** `pkg.mod:func` 在文件系统/AST 静态解析下不可解析
- **THEN** 一致性检查结果 MUST 包含该 `symbol_key` 的不一致项
