"""对照组验证库 - 用于验证 Scalim 框架输出的正确性

这个模块提供纯 Python 实现的数据关联和计算逻辑,作为对照组验证 Scalim 输出.

功能:
1. 完整的纯 Python JOIN 引擎实现
2. 支持单级/多级/复合键关联验证
3. 派生字段计算验证
4. 详细的统计分析和诊断报告
5. 可作为集成测试使用

使用方法:

```python
from scalim_misc.demo_big_data_report.verification import DetailedVerification, verify_scalim_output

# 基础验证
result = verify_scalim_output(scalim_results, target_fields)
assert result.passed, result.summary

# 详细验证 (推荐用于集成测试)
detailed = DetailedVerification(scalim_results, target_fields)
report = detailed.run_full_verification()
assert report.all_passed, report.summary
```
"""

import csv
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Sequence, Tuple

from scalim.execution import ScalimEngine
from scalim.planning import PlanBuilder
from scalim.sinks.sink_memory import InMemoryColumnSink
from scalim.spec.ir.sources import SourceNormalizeIr
from scalim.typedefs import RowData

from .loaders import (
    calc_final_price,
    calc_order_amount,
    calc_profit,
    calc_tax_amount,
    load_categories,
    load_customers,
    load_logistics,
    load_orders,
    load_payment_methods,
    load_products,
    load_promotions,
    load_region_pricing,
    load_regions,
    load_warehouses,
)
from .shared import build_ecommerce_model


@dataclass
class FieldStats:
    """单字段统计信息"""

    field_name: str
    total_count: int = 0
    null_count: int = 0
    distinct_count: int = 0
    sample_values: List[Any] = field(default_factory=list)

    @property
    def null_rate(self) -> float:
        return self.null_count / self.total_count if self.total_count > 0 else 0.0


@dataclass
class ComparisonStats:
    """对比统计信息"""

    field_name: str
    match_count: int = 0
    mismatch_count: int = 0
    both_null_count: int = 0
    expected_null_count: int = 0
    actual_null_count: int = 0
    sample_mismatches: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def match_rate(self) -> float:
        total = self.match_count + self.mismatch_count
        return self.match_count / total if total > 0 else 1.0


@dataclass
class VerificationResult:
    """验证结果"""

    passed: bool
    total_rows: int
    checked_rows: int
    mismatches: List[Dict[str, Any]]
    summary: str
    field_stats: Dict[str, ComparisonStats] = field(default_factory=dict)

    def __str__(self) -> str:
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        return "{} - {}/{} rows, {} mismatches\n{}".format(status, self.checked_rows, self.total_rows, len(self.mismatches), self.summary)

    def __bool__(self) -> bool:
        return self.passed

    def raise_if_failed(self) -> None:
        if not self.passed:
            raise AssertionError(self.summary)

    def get_mismatch_summary(self) -> str:
        lines = []
        for fname, stats in self.field_stats.items():
            if stats.mismatch_count > 0:
                lines.append(
                    "  {}: {}/{} mismatches ({:.1f}% match rate)".format(
                        fname, stats.mismatch_count, stats.match_count + stats.mismatch_count, stats.match_rate * 100
                    )
                )
        return "\n".join(lines) if lines else "All fields matched"


@dataclass
class DetailedVerificationReport:
    """详细验证报告"""

    all_passed: bool
    row_count_match: bool
    expected_rows: int
    actual_rows: int
    field_results: Dict[str, VerificationResult]
    relation_checks: List[Dict[str, str]]
    performance_stats: Dict[str, float]
    summary: str

    def __str__(self) -> str:
        status = "✅ ALL PASSED" if self.all_passed else "❌ SOME FAILED"
        lines = [
            status,
            "Rows: expected={}, actual={}, match={}".format(self.expected_rows, self.actual_rows, self.row_count_match),
            "Fields checked: {}".format(len(self.field_results)),
        ]
        failed_fields = [f for f, r in self.field_results.items() if not r.passed]
        if failed_fields:
            lines.append("Failed fields: {}".format(", ".join(failed_fields)))
        return "\n".join(lines)


class _PythonJoinEngine:
    """纯 Python 实现的 `Join` 引擎(对照组)

    完整实现了 Scalim 框架的关联逻辑,作为对照组验证:
    - 单级关联 (FK -> PK)
    - 多级关联 (FK -> PK -> FK -> PK)
    - 复合键关联 ((FK1, FK2) -> (PK1, PK2))
    - 派生字段计算
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Any] = {}
        self._load_stats: Dict[str, int] = {}

    def _load(self, key: str, loader: Callable[[], Any]) -> Any:
        if key not in self._cache:
            value = loader()
            # 示例说明: `payment_methods` `loader` 返回 `list[row]`,Scalim 执行期会按 `key_field` 做 `normalize`.
            if key == "payment_methods":
                value = SourceNormalizeIr(kind="index_by_key", key_field="payment_method_id").apply(value, source_id=key)
            self._cache[key] = value
            self._load_stats[key] = len(self._cache[key]) if hasattr(self._cache[key], "__len__") else 0
        return self._cache[key]

    def _lookup(self, row: Dict[str, Any], fk: str, table: Dict[Any, Dict[str, Any]], field: str) -> Any:
        fk_val = row.get(fk)
        if fk_val is None:
            return None
        target = table.get(fk_val)
        return target.get(field) if target else None

    def _lookup_multi(self, row: Dict[str, Any], path: List[Tuple[str, Dict[Any, Dict[str, Any]]]], field: str) -> Any:
        cur: Optional[Dict[str, Any]] = row
        for fk, table in path:
            if cur is None:
                return None
            fk_val = cur.get(fk)
            if fk_val is None:
                return None
            cur = table.get(fk_val)
        return cur.get(field) if cur else None

    def _lookup_composite(self, row: Dict[str, Any], fks: Tuple[str, ...], table: Dict[Tuple[Any, ...], Dict[str, Any]], field: str) -> Any:
        vals = []
        for fk in fks:
            v = row.get(fk)
            if v is None:
                return None
            vals.append(v)
        target = table.get(tuple(vals))
        return target.get(field) if target else None

    def get_load_stats(self) -> Dict[str, int]:
        return dict(self._load_stats)

    def build_expected(self, order: Dict[str, Any]) -> Dict[str, Any]:
        customers = self._load("customers", load_customers)
        products = self._load("products", load_products)
        categories = self._load("categories", load_categories)
        warehouses = self._load("warehouses", load_warehouses)
        regions = self._load("regions", load_regions)
        region_pricing = self._load("region_pricing", load_region_pricing)
        promotions = self._load("promotions", load_promotions)
        payment_methods = self._load("payment_methods", load_payment_methods)
        logistics = self._load("logistics", load_logistics)

        r: Dict[str, Any] = {}

        # 基础字段 (主表直接字段)
        for f in ["order_id", "quantity", "unit_price", "discount_rate", "order_date"]:
            r[f] = order.get(f)

        # 单级关联 - 客户
        r["customer_name"] = self._lookup(order, "customer_id", customers, "customer_name")
        r["customer_level"] = self._lookup(order, "customer_id", customers, "customer_level")
        r["customer_phone"] = self._lookup(order, "customer_id", customers, "customer_phone")
        r["registration_date"] = self._lookup(order, "customer_id", customers, "registration_date")

        # 单级关联 - 产品
        r["product_name"] = self._lookup(order, "product_id", products, "product_name")
        r["product_brand"] = self._lookup(order, "product_id", products, "product_brand")
        r["product_cost"] = self._lookup(order, "product_id", products, "product_cost")
        r["product_category_id"] = self._lookup(order, "product_id", products, "category_id")

        # 单级关联 - 促销 (可为空)
        r["promotion_name"] = self._lookup(order, "promotion_id", promotions, "promotion_name")
        r["promotion_discount"] = self._lookup(order, "promotion_id", promotions, "promotion_discount")
        r["no_promotion"] = not r["promotion_name"]

        # 单级关联 - 支付方式
        r["payment_method_name"] = self._lookup(order, "payment_method_id", payment_methods, "payment_method_name")

        # 单级关联 - 物流
        r["logistics_name"] = self._lookup(order, "logistics_id", logistics, "logistics_name")
        r["logistics_speed"] = self._lookup(order, "logistics_id", logistics, "logistics_speed")

        # 单级关联 - 仓库
        r["warehouse_name"] = self._lookup(order, "warehouse_id", warehouses, "warehouse_name")

        # 多级关联 - 分类 (`orders` -> `products` -> `categories`)
        r["category_name"] = self._lookup_multi(order, [("product_id", products), ("category_id", categories)], "category_name")

        # 多级关联 - 区域 (`orders` -> `warehouses` -> `regions`)
        r["region_name"] = self._lookup_multi(order, [("warehouse_id", warehouses), ("region_id", regions)], "region_name")
        r["region_name_display"] = r["region_name"]
        r["region_manager"] = self._lookup_multi(order, [("warehouse_id", warehouses), ("region_id", regions)], "region_manager")

        # 复合键关联 - 区域定价 (region_id, product_category_id)
        r["price_adjustment"] = self._lookup_composite(order, ("region_id", "product_category_id"), region_pricing, "price_adjustment")
        r["shipping_fee"] = self._lookup_composite(order, ("region_id", "product_category_id"), region_pricing, "shipping_fee")
        r["tax_rate"] = self._lookup_composite(order, ("region_id", "product_category_id"), region_pricing, "tax_rate")

        # 派生字段计算
        r["order_amount"] = calc_order_amount(quantity=r["quantity"], unit_price=r["unit_price"], discount_rate=r["discount_rate"])
        r["profit"] = calc_profit(order_amount=r["order_amount"], product_cost=r["product_cost"], quantity=r["quantity"])
        r["tax_amount"] = calc_tax_amount(order_amount=r["order_amount"], tax_rate=r["tax_rate"])
        r["final_price"] = calc_final_price(
            order_amount=r["order_amount"], price_adjustment=r["price_adjustment"], shipping_fee=r["shipping_fee"]
        )

        return r

    def build_all_expected(self) -> List[Dict[str, Any]]:
        orders = self._load("orders", load_orders)
        return [self.build_expected(o) for o in orders]

    def get_expected_stats(self) -> Dict[str, FieldStats]:
        all_expected = self.build_all_expected()

        stats: Dict[str, FieldStats] = {}
        if not all_expected:
            return stats

        for field_name in all_expected[0]:
            fs = FieldStats(field_name=field_name)
            values: List[Any] = []
            for row in all_expected:
                val = row.get(field_name)
                fs.total_count += 1
                if val is None:
                    fs.null_count += 1
                else:
                    values.append(val)
            fs.distinct_count = len({str(v) for v in values})
            fs.sample_values = values[:5]
            stats[field_name] = fs

        return stats


def _values_equal(expected: Any, actual: Any, tolerance: float = 0.01) -> bool:
    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False
    if isinstance(expected, float) or isinstance(actual, float):
        try:
            return abs(float(expected) - float(actual)) < tolerance
        except (TypeError, ValueError):
            return False
    return expected == actual


def verify_scalim_output(
    scalim_output: Sequence[RowData],
    fields_to_check: Optional[Sequence[str]] = None,
    tolerance: float = 0.01,
    max_mismatches: int = 10,
    *,
    collect_field_stats: bool = True,
) -> VerificationResult:
    """验证 Scalim 输出结果

    Args:
        scalim_output: Scalim 框架输出的结果列表
        fields_to_check: 要检查的字段列表(None 表示检查所有可验证字段)
        tolerance: 浮点数比较容差
        max_mismatches: 最大记录的不匹配数量
        collect_field_stats: 是否收集字段级统计信息

    Returns:
        VerificationResult 对象
    """
    engine = _PythonJoinEngine()
    expected_results = engine.build_all_expected()

    expected_by_pk = {r["order_id"]: r for r in expected_results}
    actual_by_pk = {r["order_id"]: r for r in scalim_output if "order_id" in r}

    mismatches: List[Dict[str, Any]] = []
    field_stats: Dict[str, ComparisonStats] = {}
    checked = 0

    for pk, actual in actual_by_pk.items():
        expected = expected_by_pk.get(pk)
        if expected is None:
            continue

        checked += 1
        check_fields = fields_to_check or list(expected.keys())

        for fname in check_fields:
            if fname not in expected:
                continue

            if collect_field_stats and fname not in field_stats:
                field_stats[fname] = ComparisonStats(field_name=fname)

            exp_val = expected.get(fname)
            act_val = actual.get(fname)

            if _values_equal(exp_val, act_val, tolerance):
                if collect_field_stats:
                    if exp_val is None and act_val is None:
                        field_stats[fname].both_null_count += 1
                    field_stats[fname].match_count += 1
            else:
                if collect_field_stats:
                    field_stats[fname].mismatch_count += 1
                    if exp_val is None:
                        field_stats[fname].expected_null_count += 1
                    if act_val is None:
                        field_stats[fname].actual_null_count += 1
                    if len(field_stats[fname].sample_mismatches) < _SAMPLE_MISMATCH_LIMIT:
                        field_stats[fname].sample_mismatches.append({"pk": pk, "expected": exp_val, "actual": act_val})

                if len(mismatches) < max_mismatches:
                    mismatches.append({"pk": pk, "field": fname, "expected": exp_val, "actual": act_val})

    passed = len(mismatches) == 0
    if passed:
        summary = "All {} rows validated successfully.".format(checked)
    else:
        lines = ["{} mismatches found:".format(len(mismatches))]
        for m in mismatches[:_SUMMARY_MISMATCH_LIMIT]:
            lines.append("  PK={}, {}: {} != {}".format(m["pk"], m["field"], m["expected"], m["actual"]))
        if len(mismatches) > _SUMMARY_MISMATCH_LIMIT:
            lines.append("  ... and {} more".format(len(mismatches) - _SUMMARY_MISMATCH_LIMIT))
        summary = "\n".join(lines)

    total_rows = len(scalim_output)
    return VerificationResult(
        passed=passed, total_rows=total_rows, checked_rows=checked, mismatches=mismatches, summary=summary, field_stats=field_stats
    )


_DEFAULT_OUTPUT_CSV_INT_FIELDS: FrozenSet[str] = frozenset(
    [
        "order_id",
        "quantity",
        "product_category_id",
        "logistics_speed",
    ]
)

_DEFAULT_OUTPUT_CSV_FLOAT_FIELDS: FrozenSet[str] = frozenset(
    [
        "unit_price",
        "discount_rate",
        "promotion_discount",
        "product_cost",
        "price_adjustment",
        "shipping_fee",
        "tax_rate",
        "order_amount",
        "profit",
        "tax_amount",
        "final_price",
    ]
)


def _coerce_output_csv_value(
    field_id: str,
    raw: object,
    *,
    int_fields: FrozenSet[str],
    float_fields: FrozenSet[str],
) -> Any:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    value: Any = text
    if field_id in int_fields:
        try:
            value = int(text)
        except ValueError:
            value = None
    elif field_id in float_fields:
        try:
            value = float(text)
        except ValueError:
            value = None
    return value


def read_output_csv_rows(
    path: object,
    *,
    int_fields: Optional[Sequence[str]] = None,
    float_fields: Optional[Sequence[str]] = None,
) -> List[RowData]:
    """读取 scalim 输出的 CSV rows,并做最小类型还原.

    说明:
    - 输出 CSV 的值是字符串;纯 Python 对照组对拍需要把 `order_id` 等字段恢复成 int/float.
    - 未声明类型的字段保持为字符串;空字符串 -> None.
    """
    int_fields_set = frozenset(int_fields) if int_fields is not None else _DEFAULT_OUTPUT_CSV_INT_FIELDS
    float_fields_set = frozenset(float_fields) if float_fields is not None else _DEFAULT_OUTPUT_CSV_FLOAT_FIELDS

    p = Path(str(path))
    if not p.exists():
        msg = "Missing output CSV: {!r}".format(str(p))
        raise FileNotFoundError(msg)

    rows: List[RowData] = []
    with p.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            out: Dict[str, Any] = {}
            for k, v in (row or {}).items():
                key = str(k or "").strip()
                if not key:
                    continue
                out[key] = _coerce_output_csv_value(
                    key,
                    v,
                    int_fields=int_fields_set,
                    float_fields=float_fields_set,
                )
            rows.append(out)
    return rows


def verify_scalim_output_csv(
    output_csv_path: object,
    *,
    fields_to_check: Optional[Sequence[str]] = None,
    tolerance: float = 0.01,
) -> VerificationResult:
    """对拍验证: 从 CSV 输出读取 rows 并用纯 Python 对照组验证."""
    rows = read_output_csv_rows(output_csv_path)
    result = verify_scalim_output(rows, fields_to_check=fields_to_check, tolerance=tolerance)
    if rows and result.checked_rows != len(rows):
        summary = "PK mismatch: checked_rows={} != total_rows={} (did you forget to coerce order_id to int?)".format(
            result.checked_rows,
            len(rows),
        )
        return VerificationResult(
            passed=False,
            total_rows=len(rows),
            checked_rows=result.checked_rows,
            mismatches=result.mismatches,
            summary=summary,
            field_stats=result.field_stats,
        )
    return result


class DetailedVerification:
    """详细验证类 - 用于集成测试

    提供更全面的验证功能:
    - 行数对比
    - 字段级统计
    - 关联类型检查
    - 性能统计
    """

    def __init__(self, scalim_output: Sequence[RowData], fields_to_check: Optional[Sequence[str]] = None, tolerance: float = 0.01) -> None:
        self.scalim_output = scalim_output
        self.fields_to_check = fields_to_check
        self.tolerance = tolerance
        self._engine = _PythonJoinEngine()
        self._expected_results: Optional[List[Dict[str, Any]]] = None

    def _get_expected(self) -> List[Dict[str, Any]]:
        if self._expected_results is None:
            self._expected_results = self._engine.build_all_expected()
        return self._expected_results

    def verify_row_count(self) -> Tuple[bool, int, int]:
        expected = self._get_expected()
        return len(expected) == len(self.scalim_output), len(expected), len(self.scalim_output)

    def verify_field(self, field_name: str) -> VerificationResult:
        return verify_scalim_output(self.scalim_output, fields_to_check=[field_name], tolerance=self.tolerance, max_mismatches=20)

    def verify_relation_type(self, relation_type: str) -> VerificationResult:
        # 使用 RELATION_TYPE_GROUPS 常量,避免重复定义
        type_mapping = {
            "single_level": "单级关联",
            "multi_level": "多级关联",
            "composite_key": "复合键关联",
            "derived": "派生字段",
            "basic": "基础字段",
        }
        group_name = type_mapping.get(relation_type)
        fields = RELATION_TYPE_GROUPS.get(group_name, []) if group_name else []
        if self.fields_to_check:
            fields = [f for f in fields if f in self.fields_to_check]
        return verify_scalim_output(self.scalim_output, fields_to_check=fields, tolerance=self.tolerance, max_mismatches=20)

    def run_full_verification(self) -> DetailedVerificationReport:
        start_time = time.time()

        row_match, expected_rows, actual_rows = self.verify_row_count()

        # 一次性验证所有字段(避免重复构建预期结果)
        check_fields = self.fields_to_check or (list(self._get_expected()[0].keys()) if self._get_expected() else [])
        full_result = verify_scalim_output(self.scalim_output, fields_to_check=check_fields, tolerance=self.tolerance, max_mismatches=100)

        # 从完整结果中提取每个字段的状态
        field_results: Dict[str, VerificationResult] = {}
        mismatched_fields = {str(m.get("field")) for m in full_result.mismatches if m.get("field")}
        for fname in check_fields:
            field_passed = fname not in mismatched_fields
            field_results[fname] = VerificationResult(
                passed=field_passed,
                total_rows=full_result.total_rows,
                checked_rows=full_result.checked_rows,
                mismatches=[m for m in full_result.mismatches if m.get("field") == fname],
                summary="OK" if field_passed else "Field {} has mismatches".format(fname),
            )

        # 按关联类型汇总
        relation_checks: List[Dict[str, str]] = []
        type_mapping = {
            "basic": "基础字段",
            "single_level": "单级关联",
            "multi_level": "多级关联",
            "composite_key": "复合键关联",
            "derived": "派生字段",
        }
        for rtype, group_name in type_mapping.items():
            fields = RELATION_TYPE_GROUPS.get(group_name, [])
            if self.fields_to_check:
                fields = [f for f in fields if f in self.fields_to_check]
            failed = [f for f in fields if f in mismatched_fields]
            status = "✅ PASS" if not failed else "❌ FAIL ({} mismatches)".format(len(failed))
            relation_checks.append({"关联类型": rtype, "状态": status})

        all_passed = row_match and full_result.passed

        elapsed = time.time() - start_time
        performance_stats = {"verification_time": elapsed, "rows_per_second": actual_rows / elapsed if elapsed > 0 else 0}

        summary_lines = []
        if not row_match:
            summary_lines.append("Row count mismatch: expected={}, actual={}".format(expected_rows, actual_rows))
        if mismatched_fields:
            summary_lines.append("Failed fields: {}".format(", ".join(sorted(mismatched_fields))))
        if not summary_lines:
            summary_lines.append("All {} fields verified successfully".format(len(field_results)))

        return DetailedVerificationReport(
            all_passed=all_passed,
            row_count_match=row_match,
            expected_rows=expected_rows,
            actual_rows=actual_rows,
            field_results=field_results,
            relation_checks=relation_checks,
            performance_stats=performance_stats,
            summary="\n".join(summary_lines),
        )


# 关联类型检查列表 - 覆盖所有关联类型
RELATION_CHECKS = [
    # 基础字段
    ("基础字段-订单ID", "order_id"),
    ("基础字段-数量", "quantity"),
    ("基础字段-单价", "unit_price"),
    ("基础字段-折扣率", "discount_rate"),
    ("基础字段-日期", "order_date"),
    # 单级关联 - 客户
    ("单级关联-客户姓名", "customer_name"),
    ("单级关联-会员等级", "customer_level"),
    ("单级关联-客户电话", "customer_phone"),
    # 单级关联 - 产品
    ("单级关联-产品名称", "product_name"),
    ("单级关联-产品品牌", "product_brand"),
    ("单级关联-产品成本", "product_cost"),
    ("单级关联-产品分类ID", "product_category_id"),
    # 单级关联 - 其他
    ("单级关联-促销活动", "promotion_name"),
    ("单级关联-促销折扣", "promotion_discount"),
    ("单级关联-支付方式", "payment_method_name"),
    ("单级关联-物流公司", "logistics_name"),
    ("单级关联-配送时效", "logistics_speed"),
    ("单级关联-仓库名称", "warehouse_name"),
    # 多级关联
    ("多级关联-产品分类", "category_name"),
    ("多级关联-区域名称", "region_name"),
    ("多级关联-区域名称展示", "region_name_display"),
    ("多级关联-区域经理", "region_manager"),
    # 复合键关联
    ("复合键关联-价格调整", "price_adjustment"),
    ("复合键关联-运费", "shipping_fee"),
    ("复合键关联-税率", "tax_rate"),
    # 派生字段
    ("派生字段-订单金额", "order_amount"),
    ("派生字段-利润", "profit"),
    ("派生字段-税费", "tax_amount"),
    ("派生字段-最终价格", "final_price"),
]

# 按关联类型分组的字段
RELATION_TYPE_GROUPS: Dict[str, List[str]] = {
    "基础字段": ["order_id", "quantity", "unit_price", "discount_rate", "order_date"],
    "单级关联": [
        "customer_name",
        "customer_level",
        "customer_phone",
        "product_name",
        "product_brand",
        "product_cost",
        "product_category_id",
        "promotion_name",
        "promotion_discount",
        "payment_method_name",
        "logistics_name",
        "logistics_speed",
        "warehouse_name",
    ],
    "多级关联": ["category_name", "region_name", "region_name_display", "region_manager"],
    "复合键关联": ["price_adjustment", "shipping_fee", "tax_rate"],
    "派生字段": ["order_amount", "profit", "tax_amount", "final_price"],
}


def get_relation_check_results(result: VerificationResult) -> List[Dict[str, str]]:
    mismatched = {m.get("field") for m in result.mismatches if "field" in m}
    return [{"关联类型": name, "字段": field, "状态": "❌ FAIL" if field in mismatched else "✅ PASS"} for name, field in RELATION_CHECKS]


def get_relation_type_summary(result: VerificationResult) -> List[Dict[str, str]]:
    """按关联类型分组的验证结果汇总"""
    mismatched = {m.get("field") for m in result.mismatches if "field" in m}
    summary = []
    for group_name, fields in RELATION_TYPE_GROUPS.items():
        failed = [f for f in fields if f in mismatched]
        total = len(fields)
        passed = total - len(failed)
        status = "✅ {}/{} PASS".format(passed, total) if not failed else "❌ {}/{} FAIL: {}".format(passed, total, ", ".join(failed))
        summary.append({"关联类型": group_name, "状态": status})
    return summary


def quick_verify(scalim_output: Sequence[RowData], fields: Optional[Sequence[str]] = None) -> bool:
    """快速验证 - 返回布尔值,适合断言使用"""
    result = verify_scalim_output(scalim_output, fields_to_check=fields)
    return result.passed


def assert_scalim_correct(scalim_output: Sequence[RowData], fields: Optional[Sequence[str]] = None, msg: str = "") -> None:
    """断言 Scalim 输出正确 - 失败时抛出详细异常"""
    result = verify_scalim_output(scalim_output, fields_to_check=fields, max_mismatches=20)
    if not result.passed:
        error_msg = msg + "\n" if msg else ""
        error_msg += str(result)
        if result.field_stats:
            error_msg += "\n\nField-level stats:\n" + result.get_mismatch_summary()
        raise AssertionError(error_msg)


# ============================================================================
# 纯 Python 实现 - 用于对照测试
# ============================================================================


def python_build_order_report(target_fields: List[str]) -> List[Dict[str, Any]]:
    """纯 Python 实现订单报表构建

    这个函数用纯 Python 代码实现与 Scalim 相同的数据关联和计算逻辑.
    可以用于对照验证 Scalim 输出的正确性.

    Args:
        target_fields: 目标字段列表

    Returns:
        报表数据列表
    """
    engine = _PythonJoinEngine()
    all_results = engine.build_all_expected()

    # 只保留目标字段
    return [{k: v for k, v in row.items() if k in target_fields} for row in all_results]


_CSV_FLOAT_TOLERANCE = 0.01
_SAMPLE_MISMATCH_LIMIT = 3
_SUMMARY_MISMATCH_LIMIT = 5


def export_to_csv(data: Sequence[RowData], filepath: str, fields: Sequence[str]) -> None:
    """导出数据到 CSV 文件"""
    output_path = Path(filepath)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        writer.writerows([dict(row) for row in data])


def compare_csv_files(file1: str, file2: str) -> Tuple[bool, str]:
    """对比两个 CSV 文件

    Returns:
        (是否相同, 差异描述)
    """
    file1_path = Path(file1)
    file2_path = Path(file2)
    with file1_path.open("r", encoding="utf-8") as f1, file2_path.open("r", encoding="utf-8") as f2:
        reader1 = list(csv.DictReader(f1))
        reader2 = list(csv.DictReader(f2))

    if len(reader1) != len(reader2):
        return False, "行数不同: {} vs {}".format(len(reader1), len(reader2))

    differences = []
    for i, (row1, row2) in enumerate(zip(reader1, reader2)):
        for key in row1:
            v1, v2 = row1.get(key), row2.get(key)
            # 浮点数比较
            try:
                f1, f2 = float(v1 or 0), float(v2 or 0)
                if abs(f1 - f2) > _CSV_FLOAT_TOLERANCE:
                    differences.append("行{} 字段{}: {} vs {}".format(i, key, v1, v2))
            except (ValueError, TypeError):
                if v1 != v2:
                    differences.append("行{} 字段{}: {} vs {}".format(i, key, v1, v2))

    if differences:
        return False, "发现 {} 处差异:\n{}".format(len(differences), "\n".join(differences[:10]))

    return True, "完全匹配"


class _ReverseSortValue:
    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def __lt__(self, other: "_ReverseSortValue") -> bool:
        return other.value < self.value


@dataclass
class OrderByVerificationResult:
    passed: bool
    order_by: Tuple[str, ...]
    message: str


def verify_order_by(scalim_output: Sequence[RowData], order_by: Sequence[str]) -> OrderByVerificationResult:
    """验证输出顺序是否满足 order_by."""
    if not order_by:
        return OrderByVerificationResult(passed=True, order_by=tuple(order_by), message="order_by is empty")
    indices = list(range(len(scalim_output)))
    for raw_key in reversed(order_by):
        key = raw_key.strip()
        if not key:
            continue
        descending = key.startswith("-")
        field_key = key[1:] if descending else key

        def _sort_key(idx: int, *, _field_key: str = field_key, _descending: bool = descending) -> Tuple[int, Any]:
            value = scalim_output[idx].get(_field_key)
            if value is None:
                return (1, 0)
            if _descending:
                return (0, _ReverseSortValue(value))
            return (0, value)

        indices.sort(key=_sort_key)
    expected = indices
    actual = list(range(len(scalim_output)))
    if expected == actual:
        return OrderByVerificationResult(passed=True, order_by=tuple(order_by), message="order_by matched")

    mismatch_at = next((idx for idx, expected_idx in enumerate(expected) if expected_idx != idx), -1)
    message = "order_by mismatch at position {}".format(mismatch_at)
    return OrderByVerificationResult(passed=False, order_by=tuple(order_by), message=message)


@dataclass
class FileComparisonResult:
    """文件对比结果"""

    matched: bool
    scalim_file: str
    python_file: str
    row_count: int
    diff_summary: str

    def __str__(self) -> str:
        status = "✅ MATCHED" if self.matched else "❌ DIFFERENT"
        return "{}: {} 行\n{}".format(status, self.row_count, self.diff_summary)


def run_parallel_comparison(target_fields: List[str], output_dir: Optional[str] = None) -> FileComparisonResult:
    """运行并行对比测试

    同时用 Scalim 框架和纯 Python 实现处理相同数据,
    将结果导出为 CSV 文件,然后对比两个文件.

    Args:
        target_fields: 目标字段列表
        output_dir: 输出目录

    Returns:
        FileComparisonResult 对象
    """
    if output_dir is None:
        output_dir = tempfile.gettempdir()

    # 1. Scalim 框架执行
    model = build_ecommerce_model()
    plan = PlanBuilder(model).build(targets=target_fields)
    engine = ScalimEngine(demand=model, plan=plan, batch_size=100)

    with InMemoryColumnSink(field_names=target_fields) as sink:
        _ = engine.run(main_rows=load_orders(), sink=sink)
        scalim_results = sink.get_rows()

    # 2. 纯 Python 执行
    python_results = python_build_order_report(target_fields)

    # 3. 导出 CSV
    output_dir_path = Path(output_dir)
    scalim_csv = output_dir_path / "scalim_output.csv"
    python_csv = output_dir_path / "python_output.csv"

    export_to_csv(scalim_results, str(scalim_csv), target_fields)
    export_to_csv(python_results, str(python_csv), target_fields)

    # 4. 对比文件
    matched, diff_summary = compare_csv_files(str(scalim_csv), str(python_csv))

    return FileComparisonResult(
        matched=matched,
        scalim_file=str(scalim_csv),
        python_file=str(python_csv),
        row_count=len(scalim_results),
        diff_summary=diff_summary,
    )
