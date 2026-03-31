## ADDED Requirements

### Requirement: YAML backend migration MUST be staged behind a repository-owned facade

系统 MUST 通过仓库自有的 YAML facade/adapter 管理默认 YAML 后端,并且 MUST 使 `src/scalim/` 运行时代码不再直接依赖某个第三方实现暴露的顶层 API 形状。

该 facade 至少 MUST 支持:
- safe load / duplicate key 检测
- YAML 位置索引构建
- 统一 parse error / validation error 结构
- 可阶段性地在 vendored `PyYAML` 与 vendored `ruamel.yaml` 之间切换内部实现

#### Scenario: candidate backend can be evaluated without rewriting business call sites
- **GIVEN** 仓库正在评估一个新的 vendored YAML backend
- **WHEN** 维护者切换 facade 的内部 backend 选择
- **THEN** `src/scalim/` 业务层 call sites MUST 继续通过仓库自有 facade 工作
- **AND** 评估过程 MUST NOT 依赖业务层直接调用第三方已移除或不稳定的顶层 API

#### Scenario: default switch can be deferred when parity gates are not yet met
- **GIVEN** facade 已存在且候选 backend 可被接入
- **WHEN** parity 验证发现 Python 3.6、真实 YAML 样本或错误结构仍存在 blocker
- **THEN** 系统 MUST 允许继续保留现有默认 backend
- **AND** MUST 不要求回退业务层调用代码

### Requirement: default backend switch MUST be gated by corpus parity and Python 3.6 runtime checks

系统 MUST 在将新的 vendored YAML backend 设为默认值之前,对真实 YAML 样本语料和 Python 3.6 vendored runtime 做验证。

验证范围至少 MUST 包含:
- `tests/fixtures/` 下的代表性 YAML 样本
- `notebooks/marimo/**/declared_yaml_dsl/*.yaml` 下的 canonical demo / workflow 样本
- Python 3.6 下的 vendored import / load / compose / duplicate key / parse error smoke checks

#### Scenario: sample corpus parity is checked before enabling the new default backend
- **WHEN** 维护者准备将新的 vendored YAML backend 设为默认值
- **THEN** 系统 MUST 先对真实 YAML 样本语料执行 parity 检查
- **AND** MUST 记录是否存在 load 结果、duplicate key、parse location 或 dump 风格的阻塞性差异

#### Scenario: Python 3.6 vendored runtime remains a hard gate
- **GIVEN** 项目运行时边界仍要求兼容 Python 3.6
- **WHEN** 维护者评估新的 vendored YAML backend
- **THEN** vendored import 与关键 YAML runtime smoke checks MUST 在 Python 3.6 环境中通过
- **AND** 若该 gate 未通过,新的 backend MUST NOT 被设为默认值
