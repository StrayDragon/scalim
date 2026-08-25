# language: zh-CN
# capability: planning-deterministic-ordering
# purpose: 定义 PROJECT_NAME 的稳定顺序最小契约，用于保证 planning/执行在相同输入下可复现，并避免 `PYTHONHASHSEED` 等非确定性因素影响结果。 本 spec 覆盖执行计划构建顺序、拓扑排序输出的 tie-break 规则、以及 keys 绑定列表的稳定顺序要求。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: planning-deterministic-ordering

  @req:r69 @human
  场景: 跨哈希种子的执行顺序可重复
    - 系统 SHALL 使执行计划的 `field_order` 与 compute 算子顺序在相同输入模型下不受 `PYTHONHASHSEED` 影响. 系统 SHALL 在同层可执行节点间使用稳定 tie-break 规则.

  @req:r313 @human
  场景: 拓扑排序输出稳定且具 tie-break 规则
    - 系统 MUST 提供稳定的拓扑排序:在相同的 nodes/edges 输入下,`topological_sort` 输出顺序 MUST 可重复且不受 `PYTHONHASHSEED` 影响. 当同一层存在多个可输出节点时,系统 MUST 使用稳定 tie-break 规则(例如按节点 key 的稳定排序)来决定输出顺序.

  @req:r436 @human
  场景: keys-list 绑定参数顺序可重复
    - 系统 SHALL 在 `$keys.as=list` 路径输出稳定顺序的 keys 列表. 系统 SHALL 通过 `build_stable_lookup_key_list` 作为公开 helper 名称提供稳定排序实现. `build_stable_lookup_key_list` MUST 作为唯一公开函数名;旧名 `stable_lookup_keys_list` MUST NOT 继续公开.
  @req:r69 @human
  场景: 不同-hash-seed-计划一致
    - 必须成立：当 对同一 demand/targets 分别在不同 `PYTHONHASHSEED` 下构建计划；那么 `field_order` 必须一致
    当 对同一 demand/targets 分别在不同 `PYTHONHASHSEED` 下构建计划
    那么 `field_order` 必须一致
  @req:r313 @human
  场景: 同图多次排序结果一致
    - 必须成立：假如 相同的节点集合与依赖边集合；当 多次调用 `IMPL_ROOT.utils.graph.topological_sort(...)` 进行排序；那么 输出顺序必须一致
    假如 相同的节点集合与依赖边集合
    当 多次调用 `IMPL_ROOT.utils.graph.topological_sort(...)` 进行排序
    那么 输出顺序必须一致
  @req:r436 @human
  场景: 不同-hash-seed-下-ids-列表一致
    - 必须成立：当 loader params 模板使用 `$keys: {as: list}` 且输入 lookup_keys 集合相同；那么 传递给 loader 的 keys 列表顺序必须一致
    当 loader params 模板使用 `$keys: {as: list}` 且输入 lookup_keys 集合相同
    那么 传递给 loader 的 keys 列表顺序必须一致

  @req:r436 @human
  场景: helper-名称统一
    - 必须成立：当 调用方从 `IMPL_ROOT.spec.ir.binding` 导入稳定排序 helper；那么 `build_stable_lookup_key_list` 导入 MUST 成功
    当 调用方从 `IMPL_ROOT.spec.ir.binding` 导入稳定排序 helper
    那么 `build_stable_lookup_key_list` 导入 MUST 成功
