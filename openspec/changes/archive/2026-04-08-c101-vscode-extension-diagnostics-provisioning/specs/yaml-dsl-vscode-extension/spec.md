## ADDED Requirements

### Requirement: extension MUST provide a doctor command with actionable fixes

VSCode extension MUST 提供 `Scalim: Doctor` 预检命令，用于覆盖最常见的安装/配置失败路径，并对失败项提供可操作的修复引导（按钮/命令）。

#### Scenario: missing scalim.yaml is detected and guided
- **GIVEN** workspace 中缺失 `scalim.yaml`
- **WHEN** 用户运行 `Scalim: Doctor`
- **THEN** doctor MUST 报告失败项 “No scalim.yaml”
- **AND** MUST 提供“创建 scalim.yaml（从模板）/打开创建位置”的引导入口

### Requirement: diagnostic bundle MUST NOT include YAML contents

extension 的 “Copy Diagnostic Bundle” 功能 MUST 生成可粘贴到 issue 的诊断报告,且该报告 MUST NOT 包含用户 YAML 正文（隐私边界）。

#### Scenario: diagnostic bundle redacts YAML contents
- **GIVEN** workspace 中存在任意 YAML DSL 文件（含可能敏感内容）
- **WHEN** 用户执行 `Scalim: Copy Diagnostic Bundle`
- **THEN** 生成的文本 MUST 不包含 YAML 正文片段
- **AND** 仍 MUST 包含可用于排障的环境与 discovery 摘要（版本、Python 路径、scalim.yaml 路径、roots 摘要等）
