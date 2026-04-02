• 结论（基于代码现状）

  - normalize.index_by_key.on_none: skip 这个需求很“干净”：改动点集中、默认行为不变
    （仍 raise）、收益明确，我倾向于做。
  - “同一 demand 多 output 追加到同一 sheet”可以做，但不能只改掉一个 duplicate 检测就
    结束：xlsx_memory(sheetbook) 还会影响 book_sheet_rows(ref.node=...) 的快照语义；
    而“非 workflow 的直接导出 Excel”（ExcelWorkbookSink 路径）要做则需要一套“共享
    sheet 的 sink 生命周期/表头策略”的设计，工作量明显更大。

  ———

  需求 1：多 output → 同一 sheet（追加）

  你指出的两个报错点是对的：

  1. xlsx_memory(sheetbook) 的 duplicate producer 检测

  - 位置：src/scalim/workflow/resources_sheetbook.py:332 起的逻辑，只要同一 sheet 里出
    现相同 input_node_id（= run.id / producer_node_id）就直接报 Duplicate sheetbook
    write...，完全没看 input_output_id。
  - 但 workflow 编译时写节点确实是 input_node_id=run.id、
    input_output_id=out_cfg.name（也就是 output name）：src/scalim/dsl/by_yaml/
    workflow_compile.py:1297。
  - 所以“同一 demand 多 output 写同一 sheet”在 xlsx_memory 下必然撞墙。

  2. book_sheet_rows 快照截断语义会被你这个需求打破（这是隐藏成本）

  - 位置：src/scalim/workflow/resources_sheetbook.py:618–623：它用 “遇到第一个
    seg.producer_node_id == ref.node 就截断”。
  - 目前之所以能这么写，是因为前面的 duplicate producer 保证了“同一 sheet 里同一
    producer 最多出现一次”。
  - 一旦允许同一 producer 多段写入同一 sheet（你要的多 output 追加），
    ref.node=<run.id> 的“快照”如果还按 first occurrence 截断，会漏掉该 node 后续追加的
    段，等于快照语义错误。
      - 这意味着：要支持该需求，iter_sheetbook_sheet_rows 必须改成按 last
        occurrence（或同等语义）来确定 cutoff。

  额外发现：xlsx_file(workbook) 在 workflow 的 apply_workbook_append 本身没有“同一
  producer 写同一 sheet 只能一次”的限制（src/scalim/workflow/resources_workbook.py:192
  起），所以 workflow + xlsx_file 其实天然更接近你想要的行为；真正卡住的是
  xlsx_memory(sheetbook)。

  可选实现路线（按风险/工作量排序）

  - 方案 A（我推荐的 MVP，覆盖 workflow 的核心场景）：
      - 在 sheetbook_append 中把“重复写入检测”从 producer_node_id 粗粒度，升级为
        (producer_node_id, input_output_id) 粒度：同一 output 不允许写两次，但允许同一
        demand 的不同 output 追加到同一 sheet。
      - 同时把 iter_sheetbook_sheet_rows 的 cutoff 改成 last occurrence，保证
        book_sheet_rows 快照包含该 node 的所有追加段。
      - 这条线基本不需要引入新 DSL 语法，只是把现有能力补齐到“append 模式”的直觉语义。
  - 方案 B（更安全、更显式，但要改 DSL/校验）：
      - 引入你提的 outputs.*.append_to（或同等级显式开关），并在编译期校验：同一
        (book_id, sheet) 被多个 outputs 复用时必须显式声明，否则报错，避免“手滑重复
        sheet 名”被悄悄当成追加。
  - 方案 C（把 standalone demand 直接导出 Excel 也一起支持）：
      - 需要动 ExcelWorkbookSink/output_composition，因为现在同名 sheet 直接报错（src/
        scalim/sinks/_internal/excel.py:381–384）。
      - 更关键的是：derived output 的 AggregatingRowSink.close() 会关闭自己的
        out_sink（src/scalim/execution/derived_outputs.py:1215–1236），所以“多个
        output 共享同一个 sheet sink”必须引入“可复用/引用计数/不关闭底层”的 wrapper 设
        计，否则第一个 output close 了，后续 output 就写不进去了。
      - 这条线不适合当 MVP，除非你明确说“非 workflow 路径也必须同样支持”。

  ———

  需求 2：normalize.index_by_key 支持 on_none: skip

  现状与痛点吻合：

  - 位置：src/scalim/spec/ir/_sources.py:533–546，
    _normalize_index_by_key_extract_key() 遇到 None 直接 raise ValueError。
  - 你的 workaround（上游 where 过滤掉 None）在语义上确实别扭，而且会把“key 缺失”逻辑
    散落在多处 output 里。

  实现代价评估（低）：

  - 增加一个配置项 normalize.on_none（默认 raise，可选 skip），只影响
    kind=index_by_key。
  - 需要同步改三层：
      - YAML schema/model：src/scalim/dsl/by_yaml/schema_dsl/models/
        source.py（NormalizeConfig）
      - YAML validator：src/scalim/dsl/by_yaml/_internal/config_parsing/validators/
        sources.py（_validate_normalize_index_by_key）
      - YAML → IR 转换：src/scalim/dsl/by_yaml/runtime/_internal/
        conversion_sources.py（_convert_source_normalize_index_by_key）
      - IR 执行：SourceNormalizeIr / _normalize_index_by_key 的 loop 里对 None key 做
        continue（仅当 on_none=skip）

  风险点也清晰：这会“吞掉”部分行；但因为默认仍是 raise，只有显式启用才会改变行为，属于
  安全扩展。

  ———

  我需要你确认 1 个关键问题（决定需求 1 的范围）
  你希望“多 output 追加到同一 sheet”只在 **workflow 托管写入（resources.books + write
  node + sheetbook/workbook）**生效，还是也要覆盖 单次 demand 直接导出
  Excel（output_composition/ExcelWorkbookSink） 这条路径？
