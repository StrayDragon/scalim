## Why

当前 `default` cases 支持通过 `call_by: ^defaults/default()`（或 `^defaults/default_of_value_cast()`）在 relation miss 时回填“零/空”缺省值，以消除业务侧 `_safe_*` 中间字段膨胀。

但 `^defaults/default()` / `^defaults/default_of_value_cast()` 的语义依赖“被写回字段”的 `value_cast`：

- 当字段显式声明 `value_cast` 时，它可以稳定推导出缺省值（例如 `int -> 0`、`str -> ""`）。
- 当字段未声明 `value_cast` 时，系统无法可靠推断“默认值的目标类型”，若静默回退为 `None`，非常容易被误用：
  - YAML 作者以为“已经强制补 0”，但实际没有（仍为 `None`）。
  - 下游 compute/聚合可能将 `None` 当作异常或被动兜底，导致错误被隐藏或诊断困难。

因此需要一个更贴近 Rust `Default::default()` 的 builtin，并配套更严格的 compile-time 校验，确保缺省值推导是“显式类型边界”下的确定行为。

## What Changes

### 1) 新增 builtin：`^defaults/default_of_value_cast()`（并提供别名 `^defaults/default()`）

提供一个推荐的 builtin，用于 `default[*].call_by` 场景，行为类似“按类型返回默认值”：

- 其返回值由字段 `value_cast` 决定（示例）：
  - `value_cast: int` → `0`
  - `value_cast: decimal` → `0`（后续仍会经过 `value_cast` 转换，得到 `Decimal(0)`）
  - `value_cast: str` → `""`
  - `value_cast: auto` → `""`（v1 先保持与当前 `auto` 转换语义一致；是否将 `auto` 视为可用类型边界可在后续评估）
- 该 builtin 仅用于“relation miss 缺省值”语义，不改变 relation hit 行为。

> 备注：该 builtin 是“按 `value_cast` 推导默认值”的语义命名，避免 `zero_*` 在 `str` 场景下带来的歧义，更接近 Rust 的 `Default` 心智模型。

### 2) 更严格的校验：缺省值推导必须有显式 `value_cast`

当某字段的 `default[*].call_by` 引用了 `^defaults/default_of_value_cast()` 时：

- 系统 MUST 在编译/校验阶段 fail-fast：该字段必须显式声明 `value_cast`
- 错误必须可定位到 `fields.<field_id>.default[<idx>].call_by`
- 诊断信息必须包含可行动建议：
  - “为该字段补 `value_cast: int/decimal/str/...`”
  - 或 “改用 `literal` 显式指定缺省值（例如 `literal: 0`）”

> NOTE: 该校验规则刻意只约束“需要类型推导”的 builtin；`literal` 不受此约束（因为作者已显式指定目标值）。

### 3) 迁移建议（不做兼容层）

后续若将该 proposal 转正为 active change（或在未发布阶段一步到位重命名）：

- 推荐将既有配置中的 `^defaults/zero_of_value_cast()` 统一升级为 `^defaults/default()`（或 `^defaults/default_of_value_cast()`）
- 并对使用该 builtin 的字段补齐 `value_cast`，否则直接报错
- 若业务确实希望“无条件补 0”（不依赖类型推导），使用 `literal: 0`

## Example

```yaml
sources:
  rating_stats:
    loader: myapp.loaders:load_ratings
    key: employee_id
    fields:
      total_reviews:
        relation: metrics_to_ratings
        value_cast: int
        default:
          - when: relation_miss
            call_by: ^defaults/default_of_value_cast()

      comment:
        relation: metrics_to_ratings
        value_cast: str
        default:
          - when: relation_miss
            call_by: ^defaults/default_of_value_cast()

      amount_sum:
        relation: metrics_to_ratings
        # 若不写 value_cast，这里应直接编译失败（避免误以为补 0）
        default:
          - when: relation_miss
            call_by: ^defaults/default_of_value_cast()
```

## Impact

- YAML authoring surface：
  - 新增 builtin callable id：`defaults/default_of_value_cast`
  - 不新增新字段；复用现有 `default[*].call_by`
- 解析/校验：
  - strict validator + LSP diagnostics 需新增一条规则：当引用该 builtin 时必须显式声明 `value_cast`
- 运行期：
  - miss 分支按 `value_cast` 推导并写回缺省值；仍沿用 `value_cast` 作为最终类型边界
