export const TIME_TOOLTIPS = {
  eventTimestamp: "事件时间(UTC).来自 viz_events.jsonl 的 timestamp(time.time() 秒).",
  lastUpdated: "界面更新时间(UTC).表示最后一次加载/应用回放数据的时间,不等于执行耗时/完成时间.",
  stageSpan: "阶段耗时(ms).来自 stage_span.duration_ms(按批次汇总的 wall-clock 耗时),不等于单个 task 的并发时序."
} as const;

