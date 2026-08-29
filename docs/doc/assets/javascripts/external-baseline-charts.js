/*! Scalim docs: external baseline probe charts (d3) — 扫参曲线 / 函数复杂度 / 慢源分片并行 / py36 边界. */
(function () {
  var DATA_URLS = [
    "assets/data/external-baseline-0.10.probes.json",
    "../assets/data/external-baseline-0.10.probes.json",
    "../../assets/data/external-baseline-0.10.probes.json",
  ];

  var SIDE_COLORS = {
    pandas: "#b45309",
    polars: "#7c3aed",
    scalim: "#0f766e",
  };
  var SIDE_LABELS = {
    pandas: "pandas（惯用法：全量 DataFrame）",
    polars: "polars（惯用法：全量 DataFrame，多线程）",
    scalim: "Scalim（批次流式）",
  };

  function pageHasCharts() {
    return !!document.getElementById("eb-chart-sweep-rows-rss");
  }

  function clear(el) {
    while (el && el.firstChild) el.removeChild(el.firstChild);
  }

  function themeColors() {
    var style = window.getComputedStyle(document.body);
    var fg = style.color || "#1a1a1a";
    return {
      fg: fg,
      muted: "color-mix(in srgb, " + fg + " 55%, transparent)",
      grid: "color-mix(in srgb, " + fg + " 12%, transparent)",
    };
  }

  function ensureD3(cb) {
    if (typeof d3 !== "undefined") { cb(); return; }
    var s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js";
    s.onload = cb;
    s.onerror = function () { console.warn("external-baseline charts: d3 failed to load"); };
    document.head.appendChild(s);
  }

  function fetchData(cb) {
    var i = 0;
    function next() {
      if (i >= DATA_URLS.length) { console.warn("external-baseline charts: data json not found"); return; }
      d3.json(DATA_URLS[i]).then(function (d) { cb(d); }).catch(function () { i += 1; next(); });
    }
    next();
  }

  function note(el, text) {
    clear(el);
    el.append("div").attr("class", "eb-note").text(text);
  }

  /* 通用图例 */
  function legend(svg, items, x, y) {
    var g = svg.append("g").attr("transform", "translate(" + x + "," + y + ")");
    items.forEach(function (it, i) {
      var row = g.append("g").attr("transform", "translate(" + (i % 2) * 190 + "," + Math.floor(i / 2) * 18 + ")");
      row.append("rect").attr("width", 11).attr("height", 11).attr("rx", 2)
        .attr("fill", it.color).attr("opacity", it.opacity == null ? 1 : it.opacity);
      row.append("text").attr("x", 16).attr("y", 9.5).attr("font-size", 10.5).attr("fill", "currentColor")
        .text(it.label);
    });
  }

  /* 折线图（扫参）：x 等距点位 + y 对数 */
  function renderSweep(data, chartId, metric, yLabel, xLabel) {
    var host = document.getElementById(chartId);
    if (!host) return;
    var sec = chartId.indexOf("cols") >= 0 ? data.sweeps.cols : data.sweeps.rows;
    var key = metric === "rss" ? "rss_mib_median" : "time_s_median";
    var points = sec.points;
    if (!points || !points.length) { note(host, "暂无数据"); return; }
    clear(host);

    var xVals = [];
    points.forEach(function (p) { if (xVals.indexOf(p.x) < 0) xVals.push(p.x); });
    xVals.sort(function (a, b) { return a - b; });
    var sides = ["pandas", "polars", "scalim"];

    var width = host.clientWidth || 720;
    var height = 300;
    var m = { top: 42, right: 16, bottom: 46, left: 74 };
    var svg = d3.select(host).append("svg")
      .attr("viewBox", "0 0 " + width + " " + height)
      .attr("width", "100%").attr("role", "img")
      .attr("aria-label", xLabel + "与" + yLabel + "关系折线图");

    var x = d3.scalePoint().domain(xVals).range([m.left, width - m.right]).padding(0.35);
    var yMin = d3.min(points, function (p) { return p[key]; });
    var yMax = d3.max(points, function (p) { return p[key]; });
    var y = d3.scaleLog().domain([Math.max(yMin / 1.6, yMax / 400), yMax * 1.5]).range([height - m.bottom, m.top]);

    svg.append("g").selectAll("line").data(y.ticks(5)).join("line")
      .attr("x1", m.left).attr("x2", width - m.right).attr("y1", y).attr("y2", y)
      .attr("stroke", themeColors().grid);
    svg.append("g").selectAll("text").data(y.ticks(5)).join("text")
      .attr("x", m.left - 8).attr("y", function (d) { return y(d) + 4; })
      .attr("text-anchor", "end").attr("font-size", 10.5).attr("fill", "currentColor")
      .text(function (d) { return d >= 1000 ? (d / 1000) + "k" : d3.format(".1f")(d); });

    svg.append("g").selectAll("text").data(xVals).join("text")
      .attr("x", x).attr("y", height - m.bottom + 18)
      .attr("text-anchor", "middle").attr("font-size", 10.5).attr("fill", "currentColor")
      .text(function (d) { return d >= 1000 ? (d / 1000) + "k" : d; });

    svg.append("text").attr("x", (m.left + width - m.right) / 2).attr("y", height - 6)
      .attr("text-anchor", "middle").attr("font-size", 11).attr("fill", "currentColor").text(xLabel);
    svg.append("text").attr("transform", "rotate(-90)").attr("x", -(m.top + height - m.bottom) / 2)
      .attr("y", 16).attr("text-anchor", "middle").attr("font-size", 11).attr("fill", "currentColor")
      .text(yLabel);

    sides.forEach(function (side) {
      var pts = xVals.map(function (xv) {
        var hit = points.find(function (p) { return p.x === xv && p.side === side; });
        return hit ? { x: xv, v: hit[key] } : null;
      });
      var line = d3.line().defined(function (d) { return d; })
        .x(function (d) { return x(d.x); }).y(function (d) { return y(d.v); });
      svg.append("path").datum(pts.filter(function (d) { return d; }))
        .attr("fill", "none").attr("stroke", SIDE_COLORS[side]).attr("stroke-width", 2)
        .attr("d", line);
      svg.selectAll(null).data(pts.filter(function (d) { return d; })).join("circle")
        .attr("cx", function (d) { return x(d.x); }).attr("cy", function (d) { return y(d.v); })
        .attr("r", 3).attr("fill", SIDE_COLORS[side]);
    });

    legend(svg, sides.map(function (s) { return { color: SIDE_COLORS[s], label: SIDE_LABELS[s] }; }),
      m.left + 4, 12);
  }

  /* 分组柱状图（通用） */
  function renderGroupedBars(chartId, groups, series, yLabel, unitFormat) {
    var host = document.getElementById(chartId);
    if (!host) return;
    if (!groups.length) { note(host, "暂无数据"); return; }
    clear(host);

    var width = host.clientWidth || 720;
    var height = 300;
    var m = { top: 44, right: 12, bottom: 58, left: 66 };
    var svg = d3.select(host).append("svg")
      .attr("viewBox", "0 0 " + width + " " + height)
      .attr("width", "100%").attr("role", "img")
      .attr("aria-label", yLabel + "分组柱状图");

    var yMax = d3.max(groups, function (g) {
      return d3.max(g.bars, function (b) { return b.value; });
    });
    var y = d3.scaleLinear().domain([0, yMax * 1.15]).range([height - m.bottom, m.top]);
    var x0 = d3.scaleBand().domain(groups.map(function (g) { return g.label; }))
      .range([m.left, width - m.right]).paddingInner(0.24).paddingOuter(0.08);
    var x1 = d3.scaleBand().domain(series.map(function (s) { return s.key; }))
      .range([0, x0.bandwidth()]).padding(0.06);

    svg.append("g").selectAll("line").data(y.ticks(4)).join("line")
      .attr("x1", m.left).attr("x2", width - m.right).attr("y1", y).attr("y2", y)
      .attr("stroke", themeColors().grid);
    svg.append("g").selectAll("text").data(y.ticks(4)).join("text")
      .attr("x", m.left - 8).attr("y", function (d) { return y(d) + 4; })
      .attr("text-anchor", "end").attr("font-size", 10.5).attr("fill", "currentColor")
      .text(function (d) { return unitFormat ? unitFormat(d) : d; });

    var g = svg.selectAll(null).data(groups).join("g")
      .attr("transform", function (d) { return "translate(" + x0(d.label) + ",0)"; });
    g.selectAll(null).data(function (d) { return d.bars; }).join("rect")
      .attr("x", function (d) { return x1(d.key); })
      .attr("width", x1.bandwidth())
      .attr("y", function (d) { return y(d.value); })
      .attr("height", function (d) { return height - m.bottom - y(d.value); })
      .attr("rx", 2)
      .attr("fill", function (d) { return d.color; });
    g.selectAll(null).data(function (d) { return d.bars; }).join("text")
      .attr("x", function (d) { return x1(d.key) + x1.bandwidth() / 2; })
      .attr("y", function (d) { return y(d.value) - 5; })
      .attr("text-anchor", "middle").attr("font-size", 9.5).attr("fill", "currentColor")
      .text(function (d) { return d.label == null ? "" : d.label; });

    g.append("text")
      .attr("x", x0.bandwidth() / 2).attr("y", height - m.bottom + 16)
      .attr("text-anchor", "middle").attr("font-size", 10.5).attr("fill", "currentColor")
      .text(function (d) { return d.label; });

    svg.append("text").attr("x", m.left).attr("y", height - 6)
      .attr("font-size", 11).attr("fill", "currentColor").text(yLabel);

    legend(svg, series.map(function (s) { return { color: s.color, label: s.label }; }),
      m.left + 4, 12);
  }

  function renderAll(data) {
    if (!pageHasCharts()) return;
    renderSweep(data, "eb-chart-sweep-rows-rss", "rss", "峰值常驻内存 RSS（MiB，对数轴）", "行数（行）");
    renderSweep(data, "eb-chart-sweep-rows-time", "time", "总耗时（秒，对数轴）", "行数（行）");
    renderSweep(data, "eb-chart-sweep-cols-rss", "rss", "峰值常驻内存 RSS（MiB，对数轴）", "派生列数（列）");
    renderSweep(data, "eb-chart-sweep-cols-time", "time", "总耗时（秒，对数轴）", "派生列数（列）");

    if (data.calc_weight) {
      var levels = ["L0(算术)", "L1(十次循环)", "L2(百次循环)"];
      var groups = levels.map(function (lv) {
        return {
          label: lv,
          bars: ["pandas", "polars", "scalim"].map(function (side) {
            var hit = data.calc_weight.points.find(function (p) { return p.level_label === lv && p.side === side; });
            return hit ? { key: side, value: hit.time_s_median, color: SIDE_COLORS[side],
                           label: hit.time_s_median.toFixed(2) } : null;
          }).filter(function (b) { return b; }),
        };
      });
      renderGroupedBars("eb-chart-calc-weight", groups,
        ["pandas", "polars", "scalim"].map(function (s) {
          return { key: s, color: SIDE_COLORS[s], label: SIDE_LABELS[s] };
        }),
        "总耗时（秒）· 10k 行 × 20 派生列 · csv", function (d) { return d + "s"; });
    }

    if (data.relation_rtt) {
      var rttPoints = data.relation_rtt.points;
      var cfgLabels = {
        full_single: "全量单次拉取",
        chunk100_serial: "分片 100 · 串行",
        chunk100_parW4: "分片 100 · 并行 W=4",
        chunk250_parW4: "分片 250 · 并行 W=4",
      };
      var cfgColors = { full_single: "#64748b", chunk100_serial: "#b45309", chunk100_parW4: "#0f766e", chunk250_parW4: "#0369a1" };
      var rttGroups = [5, 20, 50].map(function (ms) {
        return {
          label: "RTT=" + ms + "ms",
          bars: Object.keys(cfgLabels).map(function (ck) {
            var hit = rttPoints.find(function (p) { return p.rtt_ms === ms && p.config === ck; });
            return hit ? { key: ck, value: hit.time_s_median, color: cfgColors[ck],
                           label: hit.time_s_median.toFixed(2) } : null;
          }).filter(function (b) { return b; }),
        };
      });
      renderGroupedBars("eb-chart-rtt", rttGroups,
        Object.keys(cfgLabels).map(function (ck) { return { key: ck, color: cfgColors[ck], label: cfgLabels[ck] }; }),
        "总耗时（秒）· 2 万个关联键 · sleep 模拟单次往返", function (d) { return d + "s"; });
    }

    if (data.py36_boundary) {
      var shapes = [];
      data.py36_boundary.points.forEach(function (p) {
        if (shapes.indexOf(p.shape) < 0) shapes.push(p.shape);
      });
      var shapeLabels = {
        P_S2_csv_50k: "宽表 csv · 5 万行",
        P_S4_long_500k: "长表 csv · 50 万行",
        P_S7_relation_30k: "关联 csv · 3 万行",
      };
      var pyGroups = shapes.map(function (sh) {
        return {
          label: shapeLabels[sh] || sh,
          bars: [
            { key: "py310", value: (data.py36_boundary.points.find(function (p) { return p.shape === sh && p.python === "py310"; }) || {}).rss_mib_median, color: "#0369a1" },
            { key: "py36", value: (data.py36_boundary.points.find(function (p) { return p.shape === sh && p.python === "py36"; }) || {}).rss_mib_median, color: "#b45309" },
          ].map(function (b) {
            if (b.value == null) return null;
            return { key: b.key, value: b.value, color: b.color, label: b.value.toFixed(1) };
          }).filter(function (b) { return b; }),
        };
      });
      renderGroupedBars("eb-chart-py36-rss", pyGroups,
        [{ key: "py310", color: "#0369a1", label: "Python 3.10（官方测量环境）" },
         { key: "py36", color: "#b45309", label: "Python 3.6.15（最低兼容边界）" }],
        "峰值常驻内存 RSS（MiB）· scalim 串行模式", function (d) { return d; });
    }
  }

  function init() {
    if (!pageHasCharts()) return;
    ensureD3(function () {
      fetchData(renderAll);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
