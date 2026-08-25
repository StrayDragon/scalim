# language: zh-CN
# capability: execution-dense-batch
# purpose: 优化批次执行场景的内存占用与访问速度，通过 Dense 存储表示支持连续整数 row_id 的紧凑编码。 [scope-review-2026-07-13-c25-xlsx-ir-path-presence]
# scope: src/scalim/

功能: execution-dense-batch

  @req:r35 @human
  场景: Dense storage for contiguous integer row_id batches
    - 系统 MUST 支持在 row_id 连续整数场景下使用 Dense 存储表示以优化内存与性能；实现 MAY 在满足条件时启用该路径。 启用条件 MUST 可判定且可回退： - row_id MUST 为 int 且构成连续区间（存在可计算的 base_row_id 与 row_count） - 条件不满足时 MUST 回退到通用实现，语义不变

  @req:r279 @human
  场景: Dense and generic BatchContext semantic equivalence
    - 无论是否启用 Dense path，BatchContext 对外语义 MUST 等价，包括但不限于： - set_field_value/get_field_value - delete_field/delete_row_from_field/delete_row_from_all_fields - disable_row - get_field_keys/get_field_count/get_all_rows_for_field

  @req:r403 @human
  场景: Overlay context correctness under dense base context
    - 当 base context 为 Dense path 时，overlay context MUST 保持既有语义： - 读取优先 overlay，缺失回退 base - 写入仅落到 overlay，不影响 base
  @req:r35 @human
  场景: non-contiguous-row-id-falls-back-safely
    - 必须成立：当 执行路径出现非连续或非整数的 row_id；那么 系统 MUST 回退到通用实现并保持行为一致
    当 执行路径出现非连续或非整数的 row_id
    那么 系统 MUST 回退到通用实现并保持行为一致
  @req:r279 @human
  场景: set-get-delete-semantics-match
    - 必须成立：当 在同一批次内对同一字段执行 set/get 与 delete（字段或行级删除）；那么 Dense path 与通用实现结果 MUST 一致
    当 在同一批次内对同一字段执行 set/get 与 delete（字段或行级删除）
    那么 Dense path 与通用实现结果 MUST 一致
  @req:r403 @human
  场景: overlay-reads-fall-back-to-base
    - 必须成立：当 base 已设置某字段值且 overlay 未覆盖该字段/行；那么 overlay 读取 MUST 返回 base 值
    当 base 已设置某字段值且 overlay 未覆盖该字段/行
    那么 overlay 读取 MUST 返回 base 值
