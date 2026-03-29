## ADDED Requirements

### Requirement: editor schema MUST be derived from the canonical Python schema output

系统 MUST 明确一个 canonical 的 YAML DSL schema 输出位置（Python 侧生成）,并要求 editor 侧 schema 仅从该 canonical 输出复制/打包.

约束:
- editor schema 分发脚本 MUST 只有一个入口（单点复制/打包）
- repo MUST 提供 drift gate,确保 editor schema 与 canonical schema 保持一致

#### Scenario: schema drift between Python and editor is rejected
- **WHEN** Python 侧 schema 发生变化但 editor schema 未同步
- **THEN** drift gate MUST fail-fast 并提示对应的生成入口

