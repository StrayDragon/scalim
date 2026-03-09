## 1. Execution Composition Layer

- [ ] 1.1 引入多输出目标的运行时模型与组合器,确保单输出路径保持兼容
- [ ] 1.2 定义同容器多逻辑输出的命名与冲突校验,支持 workbook 多 sheet 一类容器场景
- [ ] 1.3 实现运行级失败策略,明确主输出与派生输出的提交顺序和降级行为

## 2. Derived Output Aggregation

- [ ] 2.1 实现派生输出的增量聚合接口与生命周期(初始化、批次累计、收尾输出)
- [ ] 2.2 实现二阶段/后置聚合作为兜底模式,用于列式输出或不可增量指标
- [ ] 2.3 增加聚合状态资源控制,覆盖高基数键、近似算法和必要的落盘/溢出策略

## 3. Containers, Events, And Compatibility

- [ ] 3.1 盘点并接通现有 sink/container 能力,确保多输出与同容器输出能复用现有实现而不破坏单输出行为
- [ ] 3.2 补齐多输出/派生输出对应的 instrumentation 与事件顺序约束,确保 `adaptive` 模式下结果可解释
- [ ] 3.3 明确并实现 `seq|adaptive` 下的聚合一致性边界,必要时对不安全路径做限制或 fail-fast

## 4. Docs, Examples, And Verification

- [ ] 4.1 更新用户文档与示例,明确 v1 仅支持 IR/Python 配置,并给出“详情 + 汇总”以及同 workbook 多 sheet 的示例
- [ ] 4.2 新增单元与集成测试,覆盖多输出组合、派生汇总、容器命名冲突、失败策略与资源控制
- [ ] 4.3 运行 `openspec validate add-derived-outputs --strict --no-interactive` 并补充必要的实现期校验命令说明
