# yaml-dsl-allowed-paths-policy Specification

## Purpose
TBD - created by archiving change c25-yaml-path-escape-hardening. Update Purpose after archive.
## Requirements
### Requirement: resolved YAML paths MUST be constrained by allowed roots
系统 MUST 对以下路径解析/加载统一施加 allow-roots 校验：

- demand YAML 的 imports fragments
- workflow YAML 的 `runs[*].demand`
- workflow 的 path aliases（alias base + 相对路径拼接结果）

对任一将要读取的 YAML 路径，系统 MUST：

1. 先解析得到 `resolved_path`（包含规范化与 symlink resolution）
2. 再校验 `resolved_path` MUST 位于调用方声明的 `allowed_yaml_roots` 之一的目录树内

若不满足，系统 MUST fail-fast，并在错误信息中包含：

- raw path
- base_dir（解析基准）
- resolved path
- allowed roots 列表

#### Scenario: imports path traversal fails fast without allow roots
- **GIVEN** demand YAML 位于 `/a/b/reports/demand.yaml`
- **WHEN** demand YAML 配置 `imports.shared: ../../secrets.yaml`
- **AND** 调用方未显式将 `/a/b`（或更上层）加入 allowed roots
- **THEN** imports expansion MUST fail-fast
- **AND** 错误 MUST 包含 resolved path 与 allowed roots 的诊断信息

#### Scenario: explicit allowed roots enables controlled cross-directory imports
- **GIVEN** demand YAML 位于 `/a/b/reports/demand.yaml`
- **AND** fragment 文件位于 `/a/b/_shared/common.yaml`
- **WHEN** demand YAML 配置 `imports.shared: ../_shared/common.yaml`
- **AND** 调用方显式配置 `allowed_yaml_roots` 包含 `/a/b`
- **THEN** imports expansion MUST 成功并加载该 fragment

