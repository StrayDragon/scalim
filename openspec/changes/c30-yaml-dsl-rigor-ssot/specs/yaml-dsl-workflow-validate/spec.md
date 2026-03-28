## ADDED Requirements

### Requirement: workflow validate MUST share YAML load and error envelope with demand compile

系统 MUST 要求 workflow validate 与 demand compile/run 在以下方面保持一致：
- YAML load（包括 duplicate key 检测）
- imports fragments 的处理（若 workflow 支持）
- location index 与 ErrorEnvelope 结构

#### Scenario: same YAML yields the same failure in workflow validate and compile
- **GIVEN** 某份 workflow YAML 包含 duplicate keys 或语法错误
- **WHEN** 维护者分别运行 workflow validate 与相同 loader 入口
- **THEN** 两者 MUST 产生一致的错误结构与定位口径

