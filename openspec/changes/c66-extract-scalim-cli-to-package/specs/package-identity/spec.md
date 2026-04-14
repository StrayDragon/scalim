# package-identity (delta) Specification

## MODIFIED Requirements

### Requirement: CLI 命令名为 PROJECT_CLI_NAME
系统 MUST 提供 `PROJECT_CLI_NAME` 作为命令行入口,并保持其子命令树与现有 `PROJECT_CLI_NAME` 语义一致(仅命名变更).

补充约束（分发边界）：

- `PROJECT_CLI_NAME` MUST 由独立 CLI 发行物提供（例如 `scalim-cli`），并允许该发行物使用更高的 Python 版本约束（例如 requires-python >=3.10）。
- runtime 主包（`PROJECT_DIST_NAME` / `src/IMPL_ROOT/`）MUST 保持 Python 3.6 兼容且不承载 CLI 入口实现。

#### Scenario: CLI 可运行
- **WHEN** 用户在 Python>=3.10 环境安装并执行 `PROJECT_CLI_NAME --help`
- **THEN** 命令 MUST 返回 0 且输出帮助信息

### Requirement: 可选依赖通过 extras 暴露
系统 MUST 通过 extras 提供可选能力依赖(例如 JSON Schema 校验 CLI).
当缺少可选依赖导致功能不可用时,系统 MUST 输出明确的安装指引,且安装名以 `PROJECT_DIST_NAME[...]` 为准.

更新后的约束（CLI 拆包后）：

- CLI 的运行所需依赖（例如 `jsonschema`）MUST 由 CLI 发行物自身声明并随 CLI 安装满足（不再要求通过 runtime 主包 extras 间接安装）。
- 当用户缺少 CLI 发行物而尝试使用 CLI 能力时，文档与指引 MUST 明确安装 `scalim-cli`（或等价 CLI 发行物）。

#### Scenario: 用户安装 runtime 主包不自动获得 CLI
- **WHEN** 用户仅安装 `PROJECT_DIST_NAME`（不安装 CLI 发行物）
- **THEN** 系统 MUST NOT 假设 `PROJECT_CLI_NAME` 命令可用（命令不存在是允许且预期的）

