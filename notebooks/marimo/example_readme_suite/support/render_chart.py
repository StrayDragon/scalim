"""从快照和测试数据生成 README 中的 SVG 图。"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from notebooks.marimo.example_readme_suite.support.compare import load_snapshot

ASSET_DIR_REL = Path("docs") / "assets" / "readme"
ASSET_COMPARE = ASSET_DIR_REL / "memory-compare.svg"
ASSET_SCENARIOS = ASSET_DIR_REL / "memory-compare-scenarios.svg"
ASSET_EB_SWEEP = ASSET_DIR_REL / "external-baseline-sweep.svg"
ASSET_EB_MATRIX = ASSET_DIR_REL / "external-baseline-matrix.svg"
ASSET_EB_SWEEP_TIME = ASSET_DIR_REL / "external-baseline-sweep-time.svg"
ASSET_EB_MATRIX_TIME = ASSET_DIR_REL / "external-baseline-matrix-time.svg"
_EB_DATA_REL = Path("docs") / "doc" / "assets" / "data" / "external-baseline-0.10.json"
_EB_PROBES_DATA_REL = Path("docs") / "doc" / "assets" / "data" / "external-baseline-0.10.probes.json"
_LEGACY_ASSETS = (
    ASSET_DIR_REL / "memory-savings.svg",
    ASSET_DIR_REL / "write-precompute-speedup.svg",
)

# 兼容旧名
ASSET_REL = ASSET_COMPARE

_EB_COLORS = {"pandas": "#b45309", "polars": "#7c3aed", "scalim": "#0f766e"}
_EB_SIDE_LABELS = {
    "pandas": "pandas（全量 DataFrame 惯用法）",
    "polars": "polars（全量 DataFrame · 多线程）",
    "scalim": "Scalim（批次流式）",
}


def load_external_baseline(repo_root: Optional[Path] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """读取版本锚定的外部基线数据（主矩阵 + 探针扫参；`SSOT` 见 `docs/doc/assets/data/`）。"""
    root = repo_root if repo_root is not None else _repo_root()
    main = json.loads((root / _EB_DATA_REL).read_text(encoding="utf-8"))
    probes = json.loads((root / _EB_PROBES_DATA_REL).read_text(encoding="utf-8"))
    return main, probes


def _eb_summary(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in data.get("summary", []) if isinstance(item, dict)]


def _eb_sweep_rows(probes: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [item for item in probes.get("sweeps", {}).get("rows", {}).get("points", []) if isinstance(item, dict)]


def _fmt_mib(v: float) -> str:
    if v >= 1000:
        return "{:.1f} GiB".format(v / 1024.0)
    return "{:.0f} MiB".format(v)


def _fmt_secs(v: float) -> str:
    if v >= 10:
        return "{:.0f}s".format(v)
    if v >= 1:
        return "{:.1f}s".format(v)
    return "{:.2f}s".format(v)


def _fmt_x_rows(v: int) -> str:
    if v >= 1e6:
        return "{:g}M".format(v / 1e6)
    if v >= 1e3:
        return "{:g}k".format(v / 1e3)
    return str(v)


def render_external_sweep_svg(probes: Dict[str, Any]) -> str:
    """行数扫参（固定 20 派生列 · csv）：峰值常驻内存 `RSS`，`log-log`。并排版式。"""
    points = _eb_sweep_rows(probes)
    if not points:
        raise ValueError("external-baseline probes 数据缺少 sweeps.rows")
    xs = sorted({int(p["x"]) for p in points})
    width, height = 640, 360
    left, right, top, bottom = 62, 128, 64, 58
    plot_w, plot_h = width - left - right, height - top - bottom

    def X(v: int) -> float:
        t = (math.log10(v) - math.log10(xs[0])) / (math.log10(xs[-1]) - math.log10(xs[0]))
        return left + t * plot_w

    y_lo, y_hi = 25.0, 900.0

    def Y(v: float) -> float:
        t = (math.log10(v) - math.log10(y_lo)) / (math.log10(y_hi) - math.log10(y_lo))
        return top + (1.0 - t) * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'.format(w=width, h=height),
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        '  <text x="18" y="30" font-family="DejaVu Sans, sans-serif" font-size="17" fill="#111">峰值内存（越低越好）</text>',
        '  <text x="18" y="46" font-family="DejaVu Sans, sans-serif" font-size="12.5" fill="#555">'
        "行数 1k → 1M · 20 派生列 · csv · 3 次取中位数</text>",
    ]
    for gv in (30, 100, 300, 900):
        y = Y(gv)
        lines.append('  <line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#e5e7eb"/>'.format(x1=left, x2=width - right, y=y))
        lines.append(
            '  <text x="{x}" y="{y}" text-anchor="end" font-family="DejaVu Sans, sans-serif" '
            'font-size="12.5" fill="#444">{t}</text>'.format(x=left - 9, y=y + 4, t=gv)
        )
    major = {xs[0], xs[len(xs) // 3], xs[2 * len(xs) // 3], xs[-1]}
    for xv in xs:
        x = X(xv)
        lines.append('  <line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#f3f4f6"/>'.format(x=x, y1=top, y2=height - bottom))
        if xv in major:
            lines.append(
                '  <line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#9ca3af"/>'.format(x=x, y1=height - bottom, y2=height - bottom + 5)
            )
            lines.append(
                '  <text x="{x}" y="{y}" text-anchor="middle" font-family="DejaVu Sans, sans-serif" '
                'font-size="12.5" fill="#444">{t}</text>'.format(x=x, y=height - bottom + 24, t=_fmt_x_rows(xv))
            )
    lines.append(
        '  <text x="{x}" y="{y}" text-anchor="middle" font-family="DejaVu Sans, sans-serif" '
        'font-size="12.5" fill="#333">行数（对数轴）</text>'.format(x=(left + width - right) / 2, y=height - 16)
    )
    lines.append(
        '  <text x="{x}" y="{y}" text-anchor="middle" transform="rotate(-90 {x} {y})" '
        'font-family="DejaVu Sans, sans-serif" font-size="12.5" fill="#333">峰值常驻内存 RSS（MiB）</text>'.format(
            x=16, y=(top + height - bottom) / 2
        )
    )
    for side in ("pandas", "polars", "scalim"):
        pts = sorted((p for p in points if p["side"] == side), key=lambda p: int(p["x"]))
        d = " ".join("{:.1f},{:.1f}".format(X(int(p["x"])), Y(float(p["rss_mib_median"]))) for p in pts)
        color = _EB_COLORS[side]
        lines.append('  <polyline points="{d}" fill="none" stroke="{c}" stroke-width="2.5"/>'.format(d=d, c=color))
        last = pts[-1]
        lx, ly = X(int(last["x"])), Y(float(last["rss_mib_median"]))
        lines.append('  <circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{c}"/>'.format(x=lx, y=ly, c=color))
        label = "Scalim" if side == "scalim" else side
        lines.append(
            '  <text x="{x:.1f}" y="{y:.1f}" font-family="DejaVu Sans, sans-serif" font-size="13" '
            'font-weight="bold" fill="{c}">{label} {_fmt}</text>'.format(
                x=lx + 7, y=ly + 4, c=color, label=label, _fmt=_fmt_mib(float(last["rss_mib_median"]))
            )
        )
    lines.append("</svg>")
    lines.append("")
    return "\n".join(lines)


def render_external_sweep_time_svg(probes: Dict[str, Any]) -> str:
    """行数扫参（固定 20 派生列 · csv）：总耗时，`log-log`。并排版式（诚实呈现时间取舍）。"""
    points = _eb_sweep_rows(probes)
    if not points:
        raise ValueError("external-baseline probes 数据缺少 sweeps.rows")
    xs = sorted({int(p["x"]) for p in points})
    width, height = 640, 360
    left, right, top, bottom = 62, 128, 64, 58
    plot_w, plot_h = width - left - right, height - top - bottom

    def X(v: int) -> float:
        t = (math.log10(v) - math.log10(xs[0])) / (math.log10(xs[-1]) - math.log10(xs[0]))
        return left + t * plot_w

    y_lo, y_hi = 0.01, 40.0

    def Y(v: float) -> float:
        t = (math.log10(v) - math.log10(y_lo)) / (math.log10(y_hi) - math.log10(y_lo))
        return top + (1.0 - t) * plot_h

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'.format(w=width, h=height),
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        '  <text x="18" y="30" font-family="DejaVu Sans, sans-serif" font-size="17" fill="#111">总耗时（越短越好）</text>',
        '  <text x="18" y="46" font-family="DejaVu Sans, sans-serif" font-size="12.5" fill="#555">'
        "同一组实验的时间轴：csv 场景 polars/pandas 快，Scalim 用时间换内存</text>",
    ]
    for gv in (0.02, 0.1, 1, 10):
        y = Y(gv)
        lines.append('  <line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#e5e7eb"/>'.format(x1=left, x2=width - right, y=y))
        lines.append(
            '  <text x="{x}" y="{y}" text-anchor="end" font-family="DejaVu Sans, sans-serif" '
            'font-size="12.5" fill="#444">{t}</text>'.format(x=left - 9, y=y + 4, t=_fmt_secs(gv))
        )
    major = {xs[0], xs[len(xs) // 3], xs[2 * len(xs) // 3], xs[-1]}
    for xv in xs:
        x = X(xv)
        lines.append('  <line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#f3f4f6"/>'.format(x=x, y1=top, y2=height - bottom))
        if xv in major:
            lines.append(
                '  <line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="#9ca3af"/>'.format(x=x, y1=height - bottom, y2=height - bottom + 5)
            )
            lines.append(
                '  <text x="{x}" y="{y}" text-anchor="middle" font-family="DejaVu Sans, sans-serif" '
                'font-size="12.5" fill="#444">{t}</text>'.format(x=x, y=height - bottom + 24, t=_fmt_x_rows(xv))
            )
    lines.append(
        '  <text x="{x}" y="{y}" text-anchor="middle" font-family="DejaVu Sans, sans-serif" '
        'font-size="12.5" fill="#333">行数（对数轴）</text>'.format(x=(left + width - right) / 2, y=height - 16)
    )
    lines.append(
        '  <text x="{x}" y="{y}" text-anchor="middle" transform="rotate(-90 {x} {y})" '
        'font-family="DejaVu Sans, sans-serif" font-size="12.5" fill="#333">总耗时（秒，对数轴）</text>'.format(
            x=16, y=(top + height - bottom) / 2
        )
    )
    for side in ("pandas", "polars", "scalim"):
        pts = sorted((p for p in points if p["side"] == side), key=lambda p: int(p["x"]))
        d = " ".join("{:.1f},{:.1f}".format(X(int(p["x"])), Y(float(p["time_s_median"]))) for p in pts)
        color = _EB_COLORS[side]
        lines.append('  <polyline points="{d}" fill="none" stroke="{c}" stroke-width="2.5"/>'.format(d=d, c=color))
        last = pts[-1]
        lx, ly = X(int(last["x"])), Y(float(last["time_s_median"]))
        lines.append('  <circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{c}"/>'.format(x=lx, y=ly, c=color))
        label = "Scalim" if side == "scalim" else side
        lines.append(
            '  <text x="{x:.1f}" y="{y:.1f}" font-family="DejaVu Sans, sans-serif" font-size="13" '
            'font-weight="bold" fill="{c}">{label} {_fmt}</text>'.format(
                x=lx + 7, y=ly + 4, c=color, label=label, _fmt=_fmt_secs(float(last["time_s_median"]))
            )
        )
    lines.append("</svg>")
    lines.append("")
    return "\n".join(lines)


_EB_SHAPE_LABELS = {
    "S1_report_wide_xlsx": "报表宽表 xlsx",
    "S2_wide_export_csv": "大宽表 csv",
    "S3_chain_boundary_xlsx": "链式边界 xlsx",
    "S4_long_rows_csv": "大长表 csv",
    "S5_wide_cols_csv": "超多列宽表 csv",
    "S6_wide_cols_xlsx": "超多列宽表 xlsx",
    "S7_relation_sqlite_csv": "多源关联 csv",
}


def _render_matrix_ratio_bars(
    data: Dict[str, Any], value_key: str, fmt: Any, x_hi: float, x_ticks: List[float], title: str, subtitle: str, y_axis_label: str
) -> str:
    """七种典型表：`polars`/`scalim` 相对 pandas 基线的倍数（线性轴 + 1.0× 基准虚线）.

    对数轴会把「`30 MiB` vs `1.9 GiB`」画得差不多长；改用倍数轴后差距一眼可见。
    条尾标注「倍数 · 绝对值」；行首附 pandas 绝对值作为锚点。
    """
    summary = _eb_summary(data)
    shapes = []
    for item in summary:
        sid = item.get("shape")
        if sid and sid not in shapes:
            shapes.append(sid)
    if not shapes:
        raise ValueError("external-baseline 数据缺少 summary")
    width, height = 640, 432
    top, bottom = 52, 58
    left, right = 206, 122
    plot_w = width - left - right

    def X(v: float) -> float:
        return left + (v / x_hi) * plot_w

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'.format(w=width, h=height),
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        '  <text x="18" y="28" font-family="DejaVu Sans, sans-serif" font-size="17" fill="#111">{t}</text>'.format(t=title),
        '  <text x="18" y="45" font-family="DejaVu Sans, sans-serif" font-size="12.5" fill="#555">{s}</text>'.format(s=subtitle),
    ]
    for gv in x_ticks:
        x = X(float(gv))
        major_base = abs(gv - 1.0) < 1e-9
        lines.append(
            '  <line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{c}" stroke-dasharray="{d}"/>'.format(
                x=x, y1=top - 4, y2=height - bottom + 4, c="#6b7280" if major_base else "#f3f4f6", d="5,4" if major_base else "1,0"
            )
        )
        lines.append(
            '  <text x="{x}" y="{y}" text-anchor="middle" font-family="DejaVu Sans, sans-serif" '
            'font-size="12" fill="{c}">{t}</text>'.format(
                x=x, y=height - bottom + 18, c="#374151" if major_base else "#666", t="{:g}×".format(gv)
            )
        )
    row_h = 44
    bar_h = 11
    gap = 5
    for idx, sid in enumerate(shapes):
        y0 = top + idx * row_h
        base = next((it for it in summary if it.get("shape") == sid and it.get("side") == "pandas"), None)
        base_abs = fmt(float(base[value_key])) if base and value_key in base else "?"
        lines.append(
            '  <text x="14" y="{y}" font-family="DejaVu Sans, sans-serif" font-size="12" fill="#222">{t}</text>'.format(
                y=y0 + 17, t=_EB_SHAPE_LABELS.get(sid, sid)
            )
        )
        lines.append(
            '  <text x="14" y="{y}" font-family="DejaVu Sans, sans-serif" font-size="10.5" fill="#888">pandas {t}</text>'.format(
                y=y0 + 33, t=base_abs
            )
        )
        for bi, side in enumerate(("polars", "scalim")):
            hit = next((it for it in summary if it.get("shape") == sid and it.get("side") == side), None)
            if not hit or value_key not in hit or not base or value_key not in base:
                continue
            v = float(hit[value_key])
            ratio = v / float(base[value_key])
            y = y0 + bi * (bar_h + gap)
            x2 = X(min(ratio, x_hi))
            lines.append(
                '  <rect x="{x1}" y="{y}" width="{w:.1f}" height="{h}" rx="2" fill="{c}"/>'.format(
                    x1=left, y=y, w=max(2.0, x2 - left), h=bar_h, c=_EB_COLORS[side]
                )
            )
            lines.append(
                '  <text x="{x:.1f}" y="{y}" font-family="DejaVu Sans, sans-serif" font-size="10.5" fill="#444">{t}</text>'.format(
                    x=x2 + 5, y=y + 9, t="{:.2f}× · {a}".format(ratio, a=fmt(v))
                )
            )
    lx = left
    for side in ("polars", "scalim"):
        lines.append('  <rect x="{x}" y="{y}" width="11" height="11" rx="2" fill="{c}"/>'.format(x=lx, y=height - 28, c=_EB_COLORS[side]))
        label = "Scalim（流式）" if side == "scalim" else side
        lines.append(
            '  <text x="{x}" y="{y}" font-family="DejaVu Sans, sans-serif" font-size="11.5" fill="#333">{t}</text>'.format(
                x=lx + 16, y=height - 18, t=label
            )
        )
        lx += 150
    lines.append(
        '  <text x="{x}" y="{y}" text-anchor="middle" font-family="DejaVu Sans, sans-serif" font-size="12" fill="#333">{t}</text>'.format(
            x=(left + width - right) / 2, y=height - 2, t=y_axis_label
        )
    )
    lines.append("</svg>")
    lines.append("")
    return "\n".join(lines)


def render_external_matrix_svg(data: Dict[str, Any]) -> str:
    """七种典型表：峰值内存相对 pandas 的倍数（线性轴）。并排版式。"""
    return _render_matrix_ratio_bars(
        data,
        "rss_hwm_mib_median",
        _fmt_mib,
        3.6,
        [0, 1, 2, 3],
        "峰值内存：相对 pandas 的倍数（越低越好）",
        "1.0× 虚线 = 与 pandas 持平 · 条尾含绝对值 · 3–5 次取中位数 · golden 全过",
        "相对 pandas 的峰值内存倍数（线性轴）",
    )


def render_external_matrix_time_svg(data: Dict[str, Any]) -> str:
    """七种典型表：总耗时相对 pandas 的倍数（线性轴）。并排版式（诚实呈现时间取舍）。"""
    return _render_matrix_ratio_bars(
        data,
        "total_s_median",
        _fmt_secs,
        8.0,
        [0, 2, 4, 6, 8],
        "总耗时：相对 pandas 的倍数（越短越好）",
        "1.0× 虚线 = 与 pandas 持平 · 大长表 csv 等 4 形状 scalim 为 2–7×（时间换内存）",
        "相对 pandas 的总耗时倍数（线性轴）",
    )


def expected_assets(snapshot: Optional[Dict[str, Any]] = None) -> List[Tuple[Path, str]]:
    data = snapshot if snapshot is not None else load_snapshot()
    eb_main, eb_probes = load_external_baseline()
    return [
        (ASSET_COMPARE, render_compare_svg(data)),
        (ASSET_SCENARIOS, render_scenarios_svg(data)),
        (ASSET_EB_SWEEP, render_external_sweep_svg(eb_probes)),
        (ASSET_EB_SWEEP_TIME, render_external_sweep_time_svg(eb_probes)),
        (ASSET_EB_MATRIX, render_external_matrix_svg(eb_main)),
        (ASSET_EB_MATRIX_TIME, render_external_matrix_time_svg(eb_main)),
    ]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _scenarios(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = snapshot.get("scenarios")
    if isinstance(raw, list) and raw:
        return [item for item in raw if isinstance(item, dict)]
    # 旧格式回退
    knobs = snapshot.get("knobs") or {}
    ratios = snapshot.get("ratios") or {"naive_rel": 1.0, "scalim_rel": 0.0}
    return [{"id": "baseline", "title": "默认", "knobs": knobs, "ratios": ratios}]


def _bar_pair_svg(*, title: str, subtitle: str, naive_rel: float, scalim_rel: float, width: int = 640, height: int = 220) -> str:
    if naive_rel <= 0:
        naive_rel = 1.0
    max_rel = max(naive_rel, scalim_rel, 0.01)
    left = 120
    bar_max = width - left - 40
    naive_w = int(bar_max * (naive_rel / max_rel))
    scalim_w = int(bar_max * (scalim_rel / max_rel))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'.format(w=width, h=height),
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        '  <text x="24" y="36" font-family="DejaVu Sans, sans-serif" font-size="18" fill="#111">{}</text>'.format(title),
        '  <text x="24" y="58" font-family="DejaVu Sans, sans-serif" font-size="12" fill="#555">{}</text>'.format(subtitle),
        '  <text x="24" y="110" font-family="DejaVu Sans, sans-serif" font-size="14" fill="#333">全量读取</text>',
        '  <rect x="{x}" y="90" width="{bw}" height="28" fill="#b45309"/>'.format(x=left, bw=max(1, naive_w)),
        '  <text x="{x}" y="110" font-family="DejaVu Sans, sans-serif" font-size="13" fill="#111">{:.2f}</text>'.format(
            naive_rel, x=left + max(1, naive_w) + 8
        ),
        '  <text x="24" y="160" font-family="DejaVu Sans, sans-serif" font-size="14" fill="#333">Scalim</text>',
        '  <rect x="{x}" y="140" width="{bw}" height="28" fill="#0f766e"/>'.format(x=left, bw=max(1, scalim_w)),
        '  <text x="{x}" y="160" font-family="DejaVu Sans, sans-serif" font-size="13" fill="#111">{:.2f}</text>'.format(
            scalim_rel, x=left + max(1, scalim_w) + 8
        ),
        '  <text x="24" y="200" font-family="DejaVu Sans, sans-serif" font-size="11" fill="#666">naive=1.0；这里只比较运行前后的 RSS，不是运行中的最高值，也不能比较不同机器。</text>',
        "</svg>",
        "",
    ]
    return "\n".join(lines)


def _knob_subtitle(knobs: Dict[str, Any]) -> str:
    return "N_ROWS={N_ROWS} N_FIELDS={N_FIELDS} BATCH_SIZE={BATCH_SIZE} PAYLOAD_CHARS={PAYLOAD_CHARS}".format(
        N_ROWS=knobs.get("N_ROWS", "?"),
        N_FIELDS=knobs.get("N_FIELDS", "?"),
        BATCH_SIZE=knobs.get("BATCH_SIZE", "?"),
        PAYLOAD_CHARS=knobs.get("PAYLOAD_CHARS", "?"),
    )


def render_compare_svg(snapshot: Dict[str, Any]) -> str:
    scenarios = _scenarios(snapshot)
    first = scenarios[0]
    ratios = first.get("ratios") or {}
    return _bar_pair_svg(
        title="本地内存变化（naive = 1.0）",
        subtitle=_knob_subtitle(first.get("knobs") or {}),
        naive_rel=float(ratios.get("naive_rel") or 1.0),
        scalim_rel=float(ratios.get("scalim_rel") or 0.0),
    )


def render_scenarios_svg(snapshot: Dict[str, Any]) -> str:
    scenarios = _scenarios(snapshot)
    width = 720
    row_h = 70
    top = 70
    height = top + row_h * len(scenarios) + 40
    left = 200
    bar_max = width - left - 80
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'.format(w=width, h=height),
        '  <rect width="100%" height="100%" fill="#ffffff"/>',
        '  <text x="24" y="32" font-family="DejaVu Sans, sans-serif" font-size="18" fill="#111">不同数据大小下的本地内存变化</text>',
        '  <text x="24" y="52" font-family="DejaVu Sans, sans-serif" font-size="12" fill="#555">每一行：橙色是全量读取（1.0），绿色是 Scalim</text>',
    ]
    for idx, item in enumerate(scenarios):
        y = top + idx * row_h
        ratios = item.get("ratios") or {}
        scalim_rel = float(ratios.get("scalim_rel") or 0.0)
        naive_w = bar_max
        scalim_w = int(bar_max * max(0.0, min(1.0, scalim_rel)))
        title = str(item.get("title") or item.get("id") or "scenario")
        knobs = item.get("knobs") or {}
        sub = "行数={}/字段={}".format(knobs.get("N_ROWS", "?"), knobs.get("N_FIELDS", "?"))
        lines.append(
            '  <text x="24" y="{y}" font-family="DejaVu Sans, sans-serif" font-size="13" fill="#222">{title}</text>'.format(
                y=y + 18, title=title
            )
        )
        lines.append(
            '  <text x="24" y="{y}" font-family="DejaVu Sans, sans-serif" font-size="11" fill="#666">{sub}</text>'.format(y=y + 34, sub=sub)
        )
        lines.append('  <rect x="{x}" y="{y}" width="{bw}" height="12" fill="#fbbf24"/>'.format(x=left, y=y + 8, bw=naive_w))
        lines.append('  <rect x="{x}" y="{y}" width="{bw}" height="12" fill="#0f766e"/>'.format(x=left, y=y + 24, bw=max(1, scalim_w)))
        lines.append(
            '  <text x="{x}" y="{y}" font-family="DejaVu Sans, sans-serif" font-size="12" fill="#111">{:.2f}</text>'.format(
                scalim_rel, x=left + max(1, scalim_w) + 8, y=y + 34
            )
        )
    lines.append("</svg>")
    lines.append("")
    return "\n".join(lines)


def expected_svg_text() -> str:
    """兼容旧调用：默认对比图。"""
    return render_compare_svg(load_snapshot())


def write_svg(repo_root: Path) -> Path:
    """写全部图表资产；返回主对比图路径。"""
    first = None  # type: Optional[Path]
    for rel, body in expected_assets():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        if first is None:
            first = path
    for rel in _LEGACY_ASSETS:
        legacy_asset = repo_root / rel
        if legacy_asset.is_file():
            legacy_asset.unlink()
    assert first is not None
    return first


if __name__ == "__main__":
    root = _repo_root()
    out = write_svg(root)
    print("wrote", out)
