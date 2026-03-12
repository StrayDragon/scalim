# Scalim YAML DSL Skill Examples

# region SCALIM-SKILL:minimal
name: minimal_demo
main_source:
  source_id: orders
  loader: "notebooks.marimo.demo_big_data_report._loaders:load_orders"
  fields:
    order_id:
      name: 订单ID
sources: {}
# endregion

# region SCALIM-SKILL:advanced
name: call_by_demo
main_source:
  source_id: orders
  loader: "notebooks.marimo.demo_big_data_report._loaders:load_orders"
  fields:
    quantity:
      name: 数量
      value_cast: int
    unit_price:
      name: 单价
    discount_rate:
      name: 折扣率
sources: {}
fields:
  order_amount:
    name: 订单金额(call_by)
    call_by: "notebooks.marimo.demo_big_data_report._loaders:calc_order_amount(quantity=quantity, unit_price=unit_price, discount_rate=discount_rate)"
# endregion
