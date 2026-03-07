# package-identity Specification

## Purpose
TBD - created by archiving change projectlib-rename-uv-lib-migration. Update Purpose after archive.
## Requirements
### Requirement: PyPI 发行名为 PROJECT_DIST_NAME
系统 MUST 使用 `PROJECT_DIST_NAME` 作为唯一对外 PyPI 发行名(distribution name).
系统 MUST NOT 以 `PROJECT_DIST_NAME` 作为对外发布名.

#### Scenario: 用户通过 PyPI 安装
- **WHEN** 用户执行 `pip install PROJECT_DIST_NAME`
- **THEN** Python 环境中应可导入 `PROJECT_DIST_NAME` 根包

### Requirement: 顶层导入根包为 PROJECT_IMPORT_ROOT
系统 MUST 以 `PROJECT_DIST_NAME` 作为顶层导入根包名(root package).
系统 MUST NOT 在发行物中包含顶层包 `PROJECT_DIST_NAME`(不提供兼容层).

#### Scenario: 新导入路径可用
- **WHEN** 调用方执行 `import PROJECT_DIST_NAME`
- **THEN** 导入 MUST 成功

#### Scenario: 旧导入路径不可用
- **WHEN** 调用方执行 `import PROJECT_DIST_NAME`
- **THEN** 导入 MUST 失败(例如抛出 `ModuleNotFoundError`)

### Requirement: CLI 命令名为 PROJECT_CLI_NAME
系统 MUST 提供 `PROJECT_CLI_NAME` 作为命令行入口,并保持其子命令树与现有 `PROJECT_CLI_NAME` 语义一致(仅命名变更).

#### Scenario: CLI 可运行
- **WHEN** 用户执行 `PROJECT_CLI_NAME --help`
- **THEN** 命令 MUST 返回 0 且输出帮助信息

### Requirement: 使用 uv 标准 lib 结构与 uv_build 后端
系统 MUST 采用 `uv init --lib` 的标准库结构进行分发:
- 运行时包 MUST 位于 `src/IMPL_ROOT/`.
- build backend MUST 为 `uv_build`.
- `uv build` 生成的 wheel/sdist MUST 仅包含运行时必要文件(代码/资源/元数据),不得携带仓库的开发资产目录.

#### Scenario: wheel 内容边界可控
- **WHEN** 执行 `uv build --wheel`
- **THEN** wheel 顶层 SHOULD 仅包含 `PROJECT_DIST_NAME/` 与对应的 `*.dist-info/`(以及标准 wheel 元数据)

#### Scenario: sdist 不包含开发资产目录
- **WHEN** 执行 `uv build --sdist`
- **THEN** sdist 中 MUST NOT 包含 `tests/`、`docs/`、`notebooks/`、`frontend/`、`artifacts/` 等非运行时目录

### Requirement: 可选依赖通过 extras 暴露
系统 MUST 通过 extras 提供可选能力依赖(例如 JSON Schema 校验 CLI).
当缺少可选依赖导致功能不可用时,系统 MUST 输出明确的安装指引,且安装名以 `PROJECT_DIST_NAME[...]` 为准.

#### Scenario: CLI 缺少 jsonschema 时提示安装 PROJECT_DIST_NAME[cli]
- **GIVEN** 运行环境未安装 `jsonschema`
- **WHEN** 用户执行需要 JSON Schema 的子命令(例如 `PROJECT_CLI_NAME yaml-dsl schema validate`)
- **THEN** 系统 MUST 提示安装 `PROJECT_DIST_NAME[cli]`
