## ADDED Requirements

### Requirement: fields validator 热点必须按规则职责拆分并保持稳定 validator 入口
系统 MUST 允许将 `config_parsing/validators/fields.py` 按规则职责拆分为多个内部子模块,例如字段通用校验、output 字段校验、issue 收集或辅助逻辑,但 `config_parsing.validator` 与既有稳定导入路径 MUST 保持可用且行为等价.

#### Scenario: fields validator 拆分后稳定入口保持
- **WHEN** 维护者拆分 `config_parsing/validators/fields.py`
- **THEN** 调用方通过 `IMPL_ROOT.dsl.by_yaml.config_parsing.validator` 的既有关键类型导入 MUST 继续成功
- **AND** YAML 校验输出与错误语义 MUST 与重构前保持等价

### Requirement: runtime conversion 热点必须按阶段职责拆分并保持编译链路边界
系统 MUST 允许将 `runtime/conversion.py` 按阶段职责拆分为内部协作单元,至少包括 registry/helper、Config→IR 转换、运行请求映射等边界,且不得重新把多阶段职责聚回单一热点实现.

#### Scenario: conversion 拆分后编译链路边界清晰
- **WHEN** 维护者重构 `runtime/conversion.py`
- **THEN** Config→IR 转换、运行请求映射与辅助 registry 逻辑 MUST 具备可独立验证的边界
- **AND** 现有 YAML runtime 入口行为 MUST 与重构前保持一致
