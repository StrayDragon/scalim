# Apache Fory 与 scalim 的跨语言数据层（2026-09-26）

> **状态**：notplan 选型备忘，不是 active change。不改运行时、不引入依赖。
> **触发**：姊妹仓 xylitol 调研 Fory 时对照到本仓「宽表 / 多语言数据层」是否该接 Fory。
> **转正门槛**：出现「非 Python 的表数据生产者/消费者」或「必须跨语言读 IR 快照」的真实需求后再 `llman-sdd-propose`。

## 决策

**不把 Apache Fory 当作 scalim 的跨语言数据层。** 表数据的跨语言公共层若要做，对齐 **Apache Arrow**（及已对照的 polars），不是对象图 codec。IR / 观测 / viz 保持现有 JSON·JSONL·YAML。pickle 只作为 Python 进程内 IR `__getstate__` 兼容，YAML 解析器继续把 `pickle` 列在危险模块。

## scalim 侧事实

| 接缝 | 现行形状 |
|---|---|
| 产品 | Python 宽表编排：YAML/Python DSL → 不可变 IR → 批次流水线 → CSV/XLSX |
| 行 | loader / sink 走 `Iterator[Mapping[str, …]]`（dict 行），不是带共享指针的对象图 |
| 内存叙事 | 边算边放、`row_stream` / `column_buffered` / `column_chunked`；对照物是 pandas / polars 全表物化 |
| IR | dataclass 树，含 `__getstate__`（pickle 兼容的计划快照） |
| YAML 安全 | `SecurePythonReferenceResolver.DANGEROUS_MODULES` 含 `pickle` |
| 观测前端 | scalim-viz **只读** `.json` / `.jsonl`（README 写死） |
| ROADMAP | polars extra **延后**；无 Rust 执行后端立项 |

## Fory 是什么（对照本仓，不对照 xylitol 信封）

Fory ≈ **跨语言 pickle / Kryo**：搬的是对象图（共享引用、环、子类）。另有分析型 **row format**（部分反序列化），官方写可与 Arrow 集成。Thrift/Protobuf 是值树 DTO +（常配）RPC；Fory 本身是 codec，不管 RPC。

和 scalim **问题陈述**接近的一句是「宽表不要全量 inflate」。和 scalim **数据模型**不合的是：报表行是矩形、靠 key join，不是「二十条明细指向同一个 Customer 实例」。

## 按方向

| 方向 | Fory？ | 该用什么 |
|---|---|---|
| 别的语言写 loader / 读产出表 | **否** | **Arrow RecordBatch**（polars / pandas / DataFusion 的公共层）。Rust/C++ loader 出 Arrow，Python 侧再变成行迭代器或将来直接列式算子 |
| 替换 pickle 存 IR | 非首选 | IR 是树。YAML DSL / JSON 已能表达结构；Fory native 只在「必须保留 Python 对象身份且第二语言要读同一快照」时才比 pickle 强——本仓没有这个消费者 |
| scalim-viz | **否** | 已是 JSONL 回放；浏览器不是 Fory JS 主场 |
| 将来 Rust 执行后端 | **否（Fory）** | 批次/列式对齐 Arrow。Fory row 更像引擎内部行，不是生态交换格式 |
| 与 coding agent（xylitol）互调 | **否** | 文件（CSV/XLSX）或 `scalim-cli`；不共享运行时对象图。xylitol 已单独排除 Fory 作线协议 |

## 何时才值得再打开 Fory

同时出现再评估，不跳步：

1. 要把 **Python 领域对象图**（不是 dict 行）交给 JVM/Go 且必须保留指针身份；或
2. 官方 row format 在「不引入 Arrow、又要比自研行缓存更省」上有可复现的峰值 RSS 证据，且不破坏批次释放叙事。

未满足时：表走 Arrow/文件；计划走 YAML/JSON；观测走 JSONL。

## 指针

- 写出布局 SSOT：`docs/doc/getting-started/excel-column-residency.md`
- Perf ROI（内存优先、不乱加缓存）：`llmanspec/notplan/2026-08-11-perf-roi-judgment-chain.md`
- viz 只读 json/jsonl：`frontend/scalim-viz/README.md`
- pickle 危险模块：`src/scalim/dsl/yaml_dsl/runtime/references.py`
