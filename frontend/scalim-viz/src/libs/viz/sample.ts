import type { VizGraphSnapshot, VizEvent } from '$domain/types';

export const sampleSnapshot: VizGraphSnapshot = {
  nodes: [
    { id: 'source:orders', type: 'source', data: { label: 'orders' }, position: { x: -400, y: 40 } },
    { id: 'loader:orders', type: 'loader', data: { label: 'orders' }, position: { x: -200, y: 40 } },
    { id: 'field:order_id', type: 'field', data: { label: '订单ID' }, position: { x: 40, y: 40 } },
    { id: 'field:profit', type: 'derived', data: { label: '利润' }, position: { x: 300, y: 120 } },
    { id: 'stage:stage0', type: 'stage', data: { label: 'stage0', level: 0 }, position: { x: 0, y: -40 } }
  ],
  edges: [
    { id: 'e1', source: 'source:orders', target: 'loader:orders', type: 'loads_from' },
    { id: 'e2', source: 'loader:orders', target: 'field:order_id', type: 'loads_from' },
    { id: 'e3', source: 'field:order_id', target: 'field:profit', type: 'depends_on' },
    { id: 'e4', source: 'stage:stage0', target: 'field:order_id', type: 'in_stage' }
  ],
  meta: {
    schema_version: 'vizgraph/v1',
    created_at: Date.now() / 1000,
    target_fields: ['profit']
  },
  stages: [{ stage_id: 'stage0', level: 0, field_keys: ['order_id'] }]
};

const now = Math.floor(Date.now() / 1000);

export const sampleEvents: VizEvent[] = [
  {
    schema_version: 'vizevent/v1',
    run_id: 'run_sample',
    event_type: 'run_started',
    timestamp: now - 60,
    node_ref: { type: 'pipeline', id: 'pipeline' },
    payload: { batch_size: 100, targets: ['profit'] }
  },
  {
    schema_version: 'vizevent/v1',
    run_id: 'run_sample',
    event_type: 'batch_started',
    timestamp: now - 55,
    node_ref: { type: 'batch', id: 'batch:1' },
    payload: { batch_num: 1, row_count: 100 }
  },
  {
    schema_version: 'vizevent/v1',
    run_id: 'run_sample',
    event_type: 'loader_called',
    timestamp: now - 52,
    node_ref: { type: 'loader', id: 'loader:orders' },
    payload: { loader_name: 'orders', duration_ms: 12, result_count: 100 }
  },
  {
    schema_version: 'vizevent/v1',
    run_id: 'run_sample',
    event_type: 'field_computed',
    timestamp: now - 45,
    node_ref: { type: 'field', id: 'field:order_id' },
    payload: { field_key: 'order_id', result_type: 'string', is_null: false }
  },
  {
    schema_version: 'vizevent/v1',
    run_id: 'run_sample',
    event_type: 'field_computed',
    timestamp: now - 40,
    node_ref: { type: 'field', id: 'field:profit' },
    payload: { field_key: 'profit', result_type: 'float', is_null: false }
  },
  {
    schema_version: 'vizevent/v1',
    run_id: 'run_sample',
    event_type: 'row_written',
    timestamp: now - 36,
    node_ref: { type: 'batch', id: 'batch:1' },
    payload: { row_id: 'row_1', field_count: 2, row_index: 0, batch_num: 1 }
  },
  {
    schema_version: 'vizevent/v1',
    run_id: 'run_sample',
    event_type: 'batch_finished',
    timestamp: now - 30,
    node_ref: { type: 'batch', id: 'batch:1' },
    payload: { batch_num: 1, duration_ms: 120 }
  },
  {
    schema_version: 'vizevent/v1',
    run_id: 'run_sample',
    event_type: 'run_finished',
    timestamp: now - 20,
    node_ref: { type: 'pipeline', id: 'pipeline' },
    payload: { total_batches: 1, total_duration_ms: 140 }
  }
];
