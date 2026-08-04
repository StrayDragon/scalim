"""从快照和测试数据生成 README 中的 SVG 图。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from notebooks.marimo.example_readme_suite.support.compare import load_snapshot

ASSET_DIR_REL = Path("docs") / "assets" / "readme"
ASSET_COMPARE = ASSET_DIR_REL / "memory-compare.svg"
ASSET_SCENARIOS = ASSET_DIR_REL / "memory-compare-scenarios.svg"
_LEGACY_ASSETS = (
    ASSET_DIR_REL / "memory-savings.svg",
    ASSET_DIR_REL / "write-precompute-speedup.svg",
)

# 兼容旧名
ASSET_REL = ASSET_COMPARE


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


def expected_assets(snapshot: Optional[Dict[str, Any]] = None) -> List[Tuple[Path, str]]:
    data = snapshot if snapshot is not None else load_snapshot()
    return [
        (ASSET_COMPARE, render_compare_svg(data)),
        (ASSET_SCENARIOS, render_scenarios_svg(data)),
    ]


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
