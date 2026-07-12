# notplan: streaming-xlsx-output（已收窄升格）

> **状态（2026-07-12）**: 本 notplan **不再整包激活**。  
> 宽表 close 峰已由 `write_only` 归档消化；列驻留 mid-close 释放经证据定为文档-only（A）。  
> **升格收窄**: active change [`c0-streaming-column-excel-sink`](../../changes/c0-streaming-column-excel-sink/proposal.md) —— 仅 Python opt-in sibling sink，禁止 YAML streaming knobs。  
> 下文保留为历史草案 / 风险清单；实现以 active change 的 proposal/design 为准。

---

## Why

本框架的核心设计目标是**极致的内存优化（FR023）**，但在宽表 Excel 输出场景下，当前实现未充分发挥列式写入的内存节省潜力。

### 核心问题：宽表场景的内存峰值过高

在宽表场景（如 200+ 列的订单详情报表）下，现有 `ColumnExcelSink` 存在以下问题：

1. **全量列缓存**：虽然支持按列写入，但所有列数据在内存中累积，直到 `close()` 时才转换并写入文件
   - 场景：10 万行 × 200 列
   - 内存峰值：~800MB（假设每单元格平均 40 字节）
   - 问题：即使某些列的数据源早已处理完成，其数据仍占用内存直到最后

2. **无法与字段依赖协同优化**：
   - 框架已支持字段依赖（`depends_on`），可以按依赖顺序加载数据源
   - 但 sink 层面无法利用这一点："数据源 A 加载完成 → 写入相关列 → **立即释放数据源 A 的内存**"
   - 结果：必须保留所有数据源内存直到 sink.close()

3. **列式 sink 的输出选择受限**：
   - `InMemoryColumnSink`：支持列式写入，但输出在内存中（无法直接返回 Excel 文件）
   - `ColumnExcelSink`：输出 Excel 文件，但必须全量缓存所有列

### 内存优化机会分析

```
当前 ColumnExcelSink 的内存曲线：
┌─────────────────────────────────────────────────────────────┐
│ 内存                                                         │
│  ▲                                                           │
│  │        ╔═════════════════════════════════════════╗         │
│  │        ║           所有列在内存中累积              ║         │
│  │        ║           (无法释放任何数据源)            ║         │
│  │        ╚═════════════════════════════════════════╝         │
│  │                                                           │
│  └──────────────────────────────────────────────────────────▶
│    数据源1完成  数据源2完成  数据源3完成      close()
│    (无法释放)   (无法释放)   (无法释放)       (一次性写入)
│
└─────────────────────────────────────────────────────────────┘

理想的流式列式写入内存曲线：
┌─────────────────────────────────────────────────────────────┐
│ 内存                                                         │
│  ▲                                                           │
│  │  ▓▓▓                                                     │
│  │  ▓▓▓  ░░░                                               │
│  │  ▓▓▓  ░░░  ▒▒▒                                         │
│  │  ▓▓▓  ░░░  ▒▒▒  ▬▬                                     │
│  │                                                           │
│  └──────────────────────────────────────────────────────────▶
│    数据源1完成  数据源2完成  数据源3完成      close()
│    (写入并释放) (写入并释放) (写入并释放)    (仅做文件收尾)
│
│  ▓▓▓ = 当前活跃数据源内存
│  ░░░ = 已写入列的内存（可释放）
│  ▒▒▒ = 正在写入的临时缓冲区（恒定大小）
│  ▬▬  = 文件句柄/流缓冲区（恒定大小）
└─────────────────────────────────────────────────────────────┘
```

### 核心场景：超宽表报表

**订单详情报表**（典型电商场景）：
```
字段分组（按数据源）：
┌──────────────────┬─────────┬──────────────┐
│ 数据源           │ 字段数  │ 内存（10万行）│
├──────────────────┼─────────┼──────────────┤
│ orders           │ 20列    │ ~80MB        │
│ customers        │ 15列    │ ~60MB        │
│ payments         │ 10列    │ ~40MB        │
│ items            │ 30列    │ ~120MB       │
│ shipping         │ 25列    │ ~100MB       │
│ products         │ 50列    │ ~200MB       │
│ metrics          │ 60列    │ ~240MB       │
├──────────────────┼─────────┼──────────────┤
│ 总计             │ 210列   │ ~840MB       │
└──────────────────┴─────────┴──────────────┘

当前方案内存峰值：~840MB（所有列累积）
流式列式写入峰值：~200MB（仅当前最大数据源 + 流缓冲区）

内存节省：~76%
```

### 详细内存分析

**假设条件**：
- 每单元格平均 40 字节（包含 Python 对象开销）
- 10 万行数据
- 7 个数据源按依赖顺序加载

**当前 ColumnExcelSink**：
```
内存时间线：
┌─────────────────────────────────────────────────────────────┐
│ 内存                                                         │
│  ▼                                                           │
│  │████████████████████████████████████████████████████████   │
│  └──────────────────────────────────────────────────────────▶
│    t0        t1        t2        t3        t4        t5     │
│    orders    customers items     products  metrics   close   │
│    (+80MB)   (+60MB)   (+120MB)  (+200MB)  (+240MB)  (写入) │
│    └────────┴─────────┴─────────┴─────────┴─────            │
│            累积所有列（~840MB）                              │
└─────────────────────────────────────────────────────────────┘

峰值内存：840MB
持续时间：整个执行周期
```

**流式列式写入（理想情况）**：
```
内存时间线：
┌─────────────────────────────────────────────────────────────┐
│ 内存                                                         │
│  ▼                                                           │
│  │████░░░                                                    │
│  │████░░░▒▒▒▒▒                                               │
│  │████░░░▒▒▒▓▓▓▓▓▓▓▓                                          │
│  │████░░░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓                                    │
│  │████░░░▒▒▒▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▬▬▬▬▬▬▬                          │
│  └──────────────────────────────────────────────────────────▶
│    t0        t1        t2        t3        t4        t5     │
│    orders    customers items     products  metrics   close   │
│    (80MB)    (60MB)    (120MB)   (200MB)   (240MB)   (收尾)  │
│    └─flush─┘ └─flush─┘ └─flush─┘ └─flush─┘ └─flush─┘         │
│    (释放)    (释放)    (释放)    (释放)    (释放)            │
│                                                              │
│  ████ = 当前活跃数据源                                       │
│  ░░░░ = _RowBuilder 累积的行数据（可释放）                   │
│  ▒▒▒▒ = 待 flush 的列数据                                    │
│  ▓▓▓▓ = 正在 flush 的临时缓冲区（恒定 ~10MB）                │
│  ▬▬▬▬ = 文件句柄/流缓冲区（恒定 ~5MB）                       │
└─────────────────────────────────────────────────────────────┘

峰值内存：200MB（最大单数据源）+ 10MB（flush缓冲）+ 5MB（文件缓冲）= ~215MB
内存节省：840MB → 215MB（~74%）
```

### _RowBuilder 的内存开销分析

**关键问题**：`_RowBuilder` 本身的内存是否会抵消优化收益？

**_RowBuilder 的内存组成**：
```python
class _RowBuilder:
    _row_pending_fields: List[Set[str]]      # 约 1KB/行（指针集合）
    _row_values: List[List[FieldValue]]      # 约 8KB/行（值数组）
```

**对于 10 万行 × 210 列**：
- `_row_pending_fields`：10万 × 1KB ≈ 100MB
- `_row_values`：10万 × 8KB ≈ 800MB
- **总计**：~900MB（甚至比原始数据还大！）

**优化策略**：
1. **增量 flush 完整行**：一旦某行的所有字段都写入，立即写入文件并释放该行内存
2. **字段完成标记**：追踪"哪些字段已完成"，而不是"哪些字段待完成"
3. **分批处理**：每 10000 行为一个批次，批次结束后释放内存

**优化后的内存**：
```
批次大小：10000 行
_row_builder 内存：10000 × 9KB ≈ 90MB/批次
峰值内存：200MB（当前数据源）+ 90MB（_RowBuilder）+ 10MB（flush缓冲）= ~300MB
内存节省：840MB → 300MB（~64%）
```

## What Changes

### 核心目标：实现真正的流式列式写入

引入**流式列式 Excel sink**，与框架的字段依赖机制协同，实现：

1. **边处理边写入边释放**：数据源处理完成后，立即写入相关列，释放该数据源占用的内存
2. **内存峰值仅取决于当前最大数据源**：而不是所有列的总和
3. **与 FR023 内存优化目标对齐**：充分利用框架已有的按列释放能力

### 核心能力：StreamingColumnExcelSink

```python
class StreamingColumnExcelSink(IColumnSink):
    """流式列式写入 Excel sink（内存优化核心）"""
    
    def __init__(
        self,
        output_path: str,
        field_names: List[str],
        header_names: Optional[List[str]] = None,
        sheet_name: str = "Sheet1",
        include_header: bool = True,
        flush_mode: str = "auto",  # 新增：flush 策略
    ):
        """
        flush_mode 选项：
        - "auto":    自动检测字段依赖，按数据源完成时机 flush（推荐）
        - "manual":  手动调用 flush_column()，由调用方控制
        - "on_close": 累积所有列，close() 时一次性写入（向后兼容）
        """
```

### 与字段依赖的协同优化

**关键洞察**：框架已支持字段依赖，可以识别哪些字段来自同一数据源。

```yaml
# demand.yaml
main_source:
  source_id: orders
  loader: "myapp:load_orders"
  fields:
    order_id: {name: 订单ID}
    amount: {name: 金额}

sources:
  customers:
    loader: "myapp:load_customers"
    key: customer_id
    fields:
      customer_name: {name: 客户名称}
      tier: {name: 等级}

  products:
    loader: "myapp:load_products"
    key: product_id
    fields:
      product_name: {name: 产品名称}
      category: {name: 类别}

relations:
  orders_to_customers:
    steps:
      - from: orders.customer_id
        to: customers.customer_id

outputs:
  - name: detail
    fields: [order_id, amount, customer_name, tier, product_name, category]
```

**执行流程与内存释放**：

```
1. 加载 orders 数据源
   └─> 写入 order_id, amount 列
   └─> flush_column(["order_id", "amount"])
   └─> 释放 orders 数据源内存 ✅

2. 加载 customers 数据源（依赖 orders.customer_id）
   └─> 写入 customer_name, tier 列
   └─> flush_column(["customer_name", "tier"])
   └─> 释放 customers 数据源内存 ✅

3. 加载 products 数据源（依赖 items.product_id）
   └─> 写入 product_name, category 列
   └─> flush_column(["product_name", "category"])
   └─> 释放 products 数据源内存 ✅

4. close()：仅做文件收尾，无需额外内存
```

### 设计约束

- **列顺序保证**：必须维护 `row_ids` 的稳定顺序，确保不同数据源的行正确对齐
- **原子性保证**：文件输出仍使用临时文件 + 原子替换
- **向后兼容**：`flush_mode="on_close"` 时行为与现有 `ColumnExcelSink` 一致

## Capabilities

### New Capabilities

- **`streaming-column-excel`**: 核心能力
  - 定义列式流式写入的语义与 API 契约
  - 定义 `flush_mode` 策略（auto/manual/on_close）
  - 定义与字段依赖的协同机制
  - 定义内存释放边界（何时可以释放数据源内存）

- **`source-group-tracking`**（辅助能力）：
  - 追踪字段与数据源的归属关系
  - 识别"同一数据源的所有字段"这一原子单元
  - 在数据源处理完成时触发 flush 信号

### Modified Capabilities

- **`column-sink`**（IColumnSink 扩展）：
  - 扩展接口，增加 `flush_columns(fields: List[str])` 方法
  - 允许调用方显式触发"已写入列的持久化与内存释放"

- **`output-composition`**：
  - 支持流式 sink 的多输出组合
  - 在 RouterRowSink 层面感知列式 sink 的 flush 时机

## Impact

### 代码影响面

- **新增**：
  - `src/scalim/sinks/_internal/streaming_excel.py`（`StreamingExcelSink` / `StreamingColumnExcelSink`）
  - `src/scalim/sinks/api.py`（导出新增 sink）
  - `src/scalim/sinks/__init__.py`（更新 `__all__`）

- **修改**：
  - `src/scalim/execution/output_composition.py`（支持流式 sink 的路由）
  - `src/scalim/dsl/yaml_dsl/`（YAML 配置解析）

- **测试**：
  - `tests/sinks/test_streaming_excel.py`（新增）
  - `tests/execution/test_output_composition.py`（扩展）

### 性能与资源

- **内存占用**：从 O(行数 × 列数) 降低到 O(列数) 或 O(批次大小)
- **磁盘 I/O**：直接响应场景下从 2 次降低到 0 次
- **TTFB**：首字节延迟从"等待全部生成"降低到"第一批数据生成完成"

### 兼容性

- **向后兼容**：现有 `ExcelSink` / `ColumnExcelSink` 行为不变
- **配置兼容**：未启用 `streaming: true` 时，使用原有 sink
- **格式兼容**：输出文件与现有 Excel 文件完全兼容

### 风险与限制

1. **openpyxl write_only 限制**：
   - 无法读取已写入的单元格
   - 无法使用某些高级格式化功能
   - 单个 sheet 最大行数限制（1,048,576 行）

2. **列式流式转换开销**：
   - `StreamingColumnExcelSink` 需要在内部维护列缓存，close() 时转换为行
   - 对于极端宽表（>500 列），转换阶段可能有性能开销

3. **HTTP 响应流集成**：
   - 需要处理连接中断、超时等边界情况
   - 无法在写入失败时回滚已发送的响应

## Implementation Sketch

### Phase 1: 核心实现 - StreamingColumnExcelSink

```python
# src/scalim/sinks/_internal/streaming_column_excel.py

class StreamingColumnExcelSink(IColumnSink):
    """流式列式写入 Excel sink（FR023 内存优化核心）"""
    
    def __init__(
        self,
        output_path: str,
        field_names: List[str],
        header_names: Optional[List[str]] = None,
        sheet_name: str = "Sheet1",
        include_header: bool = True,
        flush_mode: str = "auto",  # "auto" | "manual" | "on_close"
        flush_batch_size: int = 0,  # flush_mode=auto 时的批大小（0=立即flush）
    ):
        self.output_path = output_path
        self.field_names = field_names
        self.header_names = header_names or field_names
        self.sheet_name = sheet_name
        self.flush_mode = str(flush_mode)
        self.flush_batch_size = int(flush_batch_size)
        
        # 使用 openpyxl write_only 模式（内存恒定）
        self._wb = Workbook(write_only=True)
        self._ws = self._wb.create_sheet(title=self.sheet_name)
        
        # 行顺序与列数据
        self._row_ids: List[Hashable] = []
        self._columns: Dict[str, Dict[Hashable, FieldValue]] = {}
        
        # flush 策略状态
        self._field_source_map: Dict[str, str] = {}  # field -> source_id
        self._source_pending_fields: Dict[str, Set[str]] = {}  # source_id -> pending fields
        self._header_written = False
        self._closed = False
        
        if include_header:
            self._write_header()
    
    def set_row_ids(self, row_ids: "SinkRowKeySeq") -> None:
        """设置行顺序（必须在第一次 write_column 之前调用）"""
        if self._row_ids:
            raise RuntimeError("row_ids already set")
        self._row_ids.extend(row_ids)
    
    def register_source_fields(self, source_id: str, fields: List[str]) -> None:
        """
        注册数据源与字段的归属关系（由框架调用）
        
        当数据源 source_id 处理完成时，框架调用此方法告知：
        "以下字段来自 source_id，可以 flush 了"
        """
        self._source_pending_fields[str(source_id)] = set(str(f) for f in fields)
        for field in fields:
            self._field_source_map[str(field)] = str(source_id)
    
    def write_column(self, field_key: str, values: ColumnValues) -> None:
        """写入单列数据（累积）"""
        if self._closed:
            raise RuntimeError("Sink is closed")
        
        field = str(field_key)
        if field not in self._columns:
            self._columns[field] = {}
        self._columns[field].update(values)
        
        # auto flush 模式：检查是否该 flush 了
        if self.flush_mode == "auto" and self._can_flush_field(field):
            self._flush_field(field)
    
    def write_columns(self, columns: ColumnBatch) -> None:
        """批量写入列"""
        for field, values in columns.items():
            self.write_column(field, values)
    
    def flush_columns(self, fields: List[str]) -> None:
        """
        显式 flush 指定列（flush_mode=manual 时使用）
        
        将指定列转换为行并写入文件，然后释放这些列的内存
        """
        if self.flush_mode != "manual":
            return  # auto 模式下自动处理
        
        for field in fields:
            self._flush_field(str(field))
    
    def _can_flush_field(self, field: str) -> bool:
        """检查指定字段是否可以 flush"""
        if self.flush_batch_size > 0:
            # 批量模式：累积足够的列再 flush
            pending_count = sum(
                1 for pending in self._source_pending_fields.values()
                if field in pending
            )
            return pending_count >= self.flush_batch_size
        return True
    
    def _flush_field(self, field: str) -> None:
        """
        Flush 单列：转换为行并写入文件，释放内存
        
        关键优化：只写入这一列的数据，其他列继续累积
        """
        if field not in self._columns:
            return
        
        # 1. 将列数据转换为行并写入
        column_data = self._columns[field]
        for row_id in self._row_ids:
            if row_id in column_data:
                # 注意：这里需要维护"已写入的行"状态
                # 首次写入时创建行，后续写入时追加列
                # 实现细节见下文
                pass
        
        # 2. 释放该列内存
        del self._columns[field]
        
        # 3. 从待处理集合中移除
        source_id = self._field_source_map.get(field)
        if source_id and source_id in self._source_pending_fields:
            self._source_pending_fields[source_id].discard(field)
    
    def _write_header(self) -> None:
        """写入表头"""
        if not self._header_written:
            self._ws.append(self.header_names)
            self._header_written = True
    
    def close(self) -> None:
        """关闭并保存文件"""
        if self._closed:
            return
        
        # 1. flush 所有剩余列
        remaining_fields = list(self._columns.keys())
        for field in remaining_fields:
            self._flush_field(field)
        
        # 2. 原子写入文件
        temp_path = create_temp_path(self.output_path, ".xlsx.tmp")
        try:
            self._wb.save(temp_path)
            atomic_replace_temp_path(temp_path, self.output_path)
        finally:
            self._wb.close()
            self._closed = True
```

### 核心算法：增量式行构建

**挑战**：openpyxl 的 `write_only` 模式是**行导向**的，无法直接追加列。

**解决方案**：维护"已写入列的行缓存"，增量式构建完整行。

```python
class _RowBuilder:
    """增量式行构建器（支持按列追加）"""
    
    def __init__(self, field_names: List[str], row_ids: List[Hashable]):
        self.field_names = field_names
        self.row_ids = row_ids
        self.num_rows = len(row_ids)
        
        # 行状态机
        self._row_pending_fields: List[Set[str]] = [
            set(field_names) for _ in range(self.num_rows)
        ]
        self._row_values: List[List[FieldValue]] = [
            [None] * len(field_names) for _ in range(self.num_rows)
        ]
        self._field_index = {f: i for i, f in enumerate(field_names)}
    
    def append_column(self, field: str, values: Dict[Hashable, FieldValue]) -> List[int]:
        """
        追加一列，返回"完整行"的行号列表
        
        完整行 = 该行的所有字段都已写入
        """
        field_idx = self._field_index[field]
        completed_rows = []
        
        for row_idx, row_id in enumerate(self.row_ids):
            if row_id not in values:
                continue
            
            # 写入单元格
            self._row_values[row_idx][field_idx] = values[row_id]
            
            # 标记字段已完成
            self._row_pending_fields[row_idx].discard(field)
            
            # 检查是否所有字段都已完成
            if not self._row_pending_fields[row_idx]:
                completed_rows.append(row_idx)
        
        return completed_rows
    
    def get_completed_rows(self, row_indices: List[int]) -> List[List[FieldValue]]:
        """获取指定索引的完整行"""
        return [self._row_values[i] for i in row_indices]
    
    def release_rows(self, row_indices: List[int]) -> None:
        """释放已写入行的内存"""
        for i in row_indices:
            self._row_values[i] = []
            self._row_pending_fields[i] = set()
```

### Phase 2: 框架集成 - 字段依赖追踪

```python
# src/scalim/execution/executor/operators/write.py

class WriteOperator:
    """写入操作符（集成字段依赖追踪）"""
    
    def execute(self, context: ExecutionContext) -> None:
        sink = context.sink
        
        # 追踪字段与数据源的归属
        source_id = context.current_source_id
        output_fields = context.output_fields
        
        # 通知 sink：这些字段来自 source_id
        if isinstance(sink, StreamingColumnExcelSink):
            sink.register_source_fields(
                source_id=source_id,
                fields=[f.field_id for f in output_fields]
            )
        
        # 写入数据
        for batch in context.batches:
            sink.write_batch(batch)
        
        # 数据源处理完成，触发 flush
        if isinstance(sink, StreamingColumnExcelSink):
            sink.on_source_complete(source_id)
```

### Phase 3: YAML 配置扩展

```yaml
# demand.yaml
outputs:
  - name: detail
    to: {book: report, sheet: 明细}
    write:
      streaming: true           # 启用流式写入
      flush_mode: auto          # auto | manual | on_close
      flush_batch_size: 0       # 0=立即flush，>0=批量flush
    fields: [order_id, customer_name, ...]
```

## Open Questions

### 核心问题

1. **openpyxl write_only 的行追加限制**：
   - openpyxl 的 `write_only=True` 模式是**行导向**的，`append()` 只能追加整行
   - 如何高效地实现"按列累积，增量转换为行"？
   - `_RowBuilder` 的内存开销是否会抵消优化收益？

2. **字段依赖追踪的精确性**：
   - 框架如何准确识别"哪些字段来自同一数据源"？
   - 对于跨数据源的计算字段（如 `sum(amount)`），如何确定 flush 时机？
   - 派生字段（derived fields）如何处理？

3. **行顺序保证**：
   - 按列 flush 时，如何确保不同数据源的行正确对齐？
   - `row_ids` 的设置时机与顺序保证机制？

### 性能问题

4. **flush 颗粒度**：
   - 每列立即 flush vs 批量 flush（如每 10 列）的性能差异？
   - `flush_batch_size` 的最佳实践值？

5. **超宽表的转换开销**：
   - 对于 500+ 列的极端宽表，`_RowBuilder` 的内存占用？
   - 是否需要"分批 flush + 分批转换"（如每 10000 行一个批次）？

### 集成问题

6. **与现有 sink 的兼容性**：
   - `StreamingColumnExcelSink` 是否应实现 `IColumnSink` 接口？
   - 现有 `ColumnExcelSink` 是否需要标记为 deprecated？

7. **YAML 配置语法**：
   - `write: {streaming: true}` 是否足够直观？
   - 是否需要 `flush_mode` 的显式配置，还是自动推断？

## Alternatives Considered

### 方案 A：继续使用 ColumnExcelSink（现状）

**优点**：
- 已实现，无需修改
- 适合小数据量（<1万行）

**缺点**：
- 宽表场景内存峰值过高（所有列累积）
- 无法与字段依赖协同释放内存
- 10万行 × 200列 ~ 800MB 内存峰值

### 方案 B：InMemoryColumnSink + 手动转换为 Excel

**优点**：
- 支持列式写入
- 可在转换前进行后处理

**缺点**：
- 转换阶段仍有内存峰值
- 需要额外的转换步骤
- 无法边处理边释放

### 方案 C：改用 CSV 格式

**优点**：
- CSV 天然支持流式写入
- 内存占用极低

**缺点**：
- 用户明确要求 Excel 格式
- CSV 不支持多 sheet、公式、格式化

### 方案 D：分批生成多个 Excel 文件

**优点**：
- 每批内存可控

**缺点**：
- 用户需要合并多个文件
- 体验不佳

### 为什么选择流式列式写入（本提案）

1. **与 FR023 目标对齐**：充分利用框架已有的按列释放能力
2. **内存优化显著**：宽表场景可节省 70%+ 内存
3. **对用户透明**：API 兼容，仅需配置启用
4. **与字段依赖协同**：自动识别数据源完成时机

## References

- openpyxl write_only 模式文档：https://openpyxl.readthedocs.io/en/stable/optimized.html#write-only-mode
- Flask 流式响应：https://flask.palletsprojects.com/en/latest/patterns/streaming/
- 现有 ExcelSink 实现：`src/scalim/sinks/_internal/excel.py`
