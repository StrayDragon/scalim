# testing-quality (delta) Specification

## MODIFIED Requirements

### Requirement: 测试分类与默认执行
- 测试套件 MUST 使用 `bench` marker 标识基准用例.
- 默认（本地/轻量）测试入口 MUST 运行所有非 bench 测试,并以快速反馈为优先（不得隐式强制开启 xdist + coverage 门禁）。
- 质量门禁（CI/qa）入口 MUST 显式启用重型参数（例如 xdist 并行 + coverage 统计 + coverage gate），并运行所有非 bench 测试。
- 非 bench 测试 MUST 在质量门禁入口中参与覆盖率统计与覆盖率阈值校验。

#### Scenario: 默认执行非 bench 测试
- **WHEN** 使用默认（本地/轻量）测试命令执行 pytest
- **THEN** 运行所有非 bench 测试且不包含 bench

#### Scenario: qa/ci gate runs coverage explicitly
- **WHEN** 使用质量门禁入口（CI/qa）执行测试
- **THEN** 测试 MUST 显式启用 coverage 统计与覆盖率阈值门禁
- **AND** 运行范围 MUST 覆盖所有非 bench 测试

