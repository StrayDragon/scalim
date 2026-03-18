## ADDED Requirements

### Requirement: schema MAY allow pathless CSV outputs for workflow-managed temp outputs
系统 SHALL 在 demand JSON schema 层允许 `outputs.*.container.path` 在受限场景下省略/为空，以避免 workflow authoring 被 schema-only 校验拦截；但必须在 hover 文案中明确约束：
- 该写法仅对 `container.type: csv` 适用
- 该写法仅在 workflow 托管 write nodes 消费的场景有效；standalone demand 编译/运行 MUST fail-fast 并提示该边界

#### Scenario: schema hover documents workflow-managed limitation
- **WHEN** 生成 `src/IMPL_ROOT/dsl/by_yaml/schema/demand.gen.json`
- **THEN** `outputs.*.container.path` 的 `markdownDescription` MUST 明确说明“pathless 仅 workflow 托管可用”的限制
