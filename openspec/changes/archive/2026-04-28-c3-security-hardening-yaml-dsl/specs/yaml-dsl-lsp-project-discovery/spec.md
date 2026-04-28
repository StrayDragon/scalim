## ADDED Requirements

### Requirement: lsp python_roots MUST remain dev-only and allow external directories

系统 MUST 将 `scalim.yaml` 的 `yaml_dsl.lsp.python_roots` 作为编辑器/LSP 的静态解析搜索路径,并将其视为 dev-only 配置(不作为安全边界)。

系统 MUST 采用最小校验语义:
- `python_roots[*]` MUST 按以下规则解析:
  - 若为相对路径: MUST 以 `project_root` 为基准解析(解析后允许落在 `project_root` 外,不做 fail-fast)
  - 若为绝对路径: MUST 按绝对路径处理
- 对于空字符串/空白字符串等不可用项: 系统 MUST 产生 warning,并且 MUST 忽略该项(不得因为该项导致项目配置加载失败)
- 对于解析后 **不存在** 或 **不是目录** 的项: 系统 MUST 产生 warning,并且 MUST 忽略该项(不得因为该项导致项目配置加载失败)
- 对于解析后存在且为目录的项: discovery MUST 接受该路径作为 python root

#### Scenario: relative python_root may resolve outside project_root and is accepted
- **GIVEN** `project_root=/repo/project`
- **WHEN** `python_roots=["../outside"]` 且解析后的目录存在
- **THEN** discovery MUST 接受该路径作为 python root

#### Scenario: absolute python_root is allowed for explicit external roots
- **WHEN** `python_roots` 项为绝对路径且存在且为目录
- **THEN** discovery MUST 接受该路径作为 python root

#### Scenario: invalid python_root is ignored with warning
- **GIVEN** `project_root=/repo/project`
- **WHEN** `python_roots=["./missing-dir"]` 且解析后的路径不存在或不是目录
- **THEN** system MUST 输出 warning,并且 discovery MUST 不包含该路径

#### Scenario: blank python_root is ignored with warning
- **GIVEN** `project_root=/repo/project`
- **WHEN** `python_roots=[""]`
- **THEN** system MUST 输出 warning,并且 discovery MUST 不包含该路径
