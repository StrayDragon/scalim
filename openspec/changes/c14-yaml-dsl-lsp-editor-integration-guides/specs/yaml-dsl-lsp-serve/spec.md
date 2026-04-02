## ADDED Requirements

### Requirement: Serve contract MUST include a troubleshooting entrypoint
系统 MUST 提供可排障入口，用于让用户确认当前 workspace 的 project discovery 摘要：

- project_root
- scalim_yaml_path（可为空）
- python_roots
- allowed_yaml_roots

该信息 MUST 可通过日志或可查询命令获得（实现形式由 design 决定）。

#### Scenario: user can obtain discovery summary for an issue report
- **WHEN** 用户按文档执行排障步骤
- **THEN** 用户 MUST 能获得 discovery 摘要并可粘贴到 issue

