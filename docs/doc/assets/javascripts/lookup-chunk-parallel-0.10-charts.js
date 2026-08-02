/*! Scalim docs: lookup chunk parallelism 0.10.0 interactive charts (d3). */
(function () {
  var DATA_URLS = [
    "assets/data/lookup-chunk-parallel-0.10.json",
    "../assets/data/lookup-chunk-parallel-0.10.json",
    "../../assets/data/lookup-chunk-parallel-0.10.json",
  ];
  var FALLBACK = null;

  function pageHasCharts() {
    return !!document.getElementById("lcp10-chart-speedup");
  }

  function clear(el) {
    while (el && el.firstChild) {
      el.removeChild(el.firstChild);
    }
  }

  function themeColors() {
    var style = window.getComputedStyle(document.body);
    var fg = style.color || "#1a1a1a";
    return {
      fg: fg,
      muted: "color-mix(in srgb, " + fg + " 55%, transparent)",
      serial: "#b45309",
      parallel: "#0f766e",
      accent: "#0369a1",
      grid: "color-mix(in srgb, " + fg + " 12%, transparent)",
    };
  }

  function ensureD3(cb) {
    if (typeof d3 !== "undefined") {
      cb();
      return;
    }
    var s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js";
    s.onload = function () {
      cb();
    };
    document.head.appendChild(s);
  }

  function fetchData(cb) {
    var i = 0;
    function next() {
      if (i >= DATA_URLS.length) {
        if (FALLBACK) cb(FALLBACK);
        return;
      }
      var url = DATA_URLS[i++];
      fetch(url)
        .then(function (r) {
          if (!r.ok) throw new Error("status " + r.status);
          return r.json();
        })
        .then(function (data) {
          FALLBACK = data;
          cb(data);
        })
        .catch(next);
    }
    next();
  }

  function sizeOf(sel, fallbackW, fallbackH) {
    var node = document.querySelector(sel);
    var w = (node && node.clientWidth) || fallbackW;
    return { width: Math.max(280, w), height: fallbackH };
  }

  function renderSpeedup(data) {
    var host = document.getElementById("lcp10-chart-speedup");
    if (!host || typeof d3 === "undefined") return;
    clear(host);
    var rows = data.workload.slice().sort(function (a, b) {
      return b.speedup - a.speedup;
    });
    var colors = themeColors();
    var margin = { top: 16, right: 56, bottom: 28, left: 148 };
    var dim = sizeOf("#lcp10-chart-speedup", 720, 28 * rows.length + 60);
    var width = dim.width - margin.left - margin.right;
    var height = dim.height - margin.top - margin.bottom;
    var svg = d3
      .select(host)
      .append("svg")
      .attr("viewBox", "0 0 " + dim.width + " " + dim.height)
      .attr("role", "img")
      .attr("aria-label", "Lookup chunk parallelism speedup");
    var g = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");
    var y = d3
      .scaleBand()
      .domain(
        rows.map(function (d) {
          return d.label;
        }),
      )
      .range([0, height])
      .padding(0.2);
    var x = d3
      .scaleLinear()
      .domain([
        0,
        d3.max(rows, function (d) {
          return d.speedup;
        }) * 1.12,
      ])
      .nice()
      .range([0, width]);
    g.append("g")
      .attr("transform", "translate(0," + height + ")")
      .call(d3.axisBottom(x).ticks(6))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.muted);
        sel.selectAll("line,path").attr("stroke", colors.grid);
      });
    g.append("g")
      .call(d3.axisLeft(y).tickSize(0))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.fg).attr("font-size", 12);
        sel.select(".domain").attr("stroke", "none");
      });
    g.append("line")
      .attr("x1", x(1))
      .attr("x2", x(1))
      .attr("y1", 0)
      .attr("y2", height)
      .attr("stroke", colors.muted)
      .attr("stroke-dasharray", "4 4");
    g.selectAll("rect")
      .data(rows)
      .enter()
      .append("rect")
      .attr("y", function (d) {
        return y(d.label);
      })
      .attr("height", y.bandwidth())
      .attr("x", 0)
      .attr("width", function (d) {
        return x(d.speedup);
      })
      .attr("fill", colors.parallel)
      .attr("rx", 3);
    g.selectAll("text.val")
      .data(rows)
      .enter()
      .append("text")
      .attr("x", function (d) {
        return x(d.speedup) + 6;
      })
      .attr("y", function (d) {
        return y(d.label) + y.bandwidth() / 2;
      })
      .attr("dy", "0.35em")
      .attr("fill", colors.fg)
      .attr("font-size", 12)
      .attr("font-weight", 600)
      .text(function (d) {
        return d.speedup.toFixed(2) + "×";
      });
  }

  function renderWall(data) {
    var host = document.getElementById("lcp10-chart-wall");
    if (!host || typeof d3 === "undefined") return;
    clear(host);
    var rows = data.workload;
    var colors = themeColors();
    var margin = { top: 24, right: 20, bottom: 72, left: 52 };
    var dim = sizeOf("#lcp10-chart-wall", 720, 320);
    var width = dim.width - margin.left - margin.right;
    var height = dim.height - margin.top - margin.bottom;
    var svg = d3
      .select(host)
      .append("svg")
      .attr("viewBox", "0 0 " + dim.width + " " + dim.height)
      .attr("role", "img")
      .attr("aria-label", "Serial vs chunk-parallel wall time");
    var g = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");
    var x0 = d3
      .scaleBand()
      .domain(
        rows.map(function (d) {
          return d.id;
        }),
      )
      .range([0, width])
      .padding(0.25);
    var x1 = d3.scaleBand().domain(["serial", "parallel"]).range([0, x0.bandwidth()]).padding(0.15);
    var y = d3
      .scaleLinear()
      .domain([
        0,
        d3.max(rows, function (d) {
          return Math.max(d.serial_s, d.parallel_s);
        }) * 1.15,
      ])
      .nice()
      .range([height, 0]);
    g.append("g")
      .attr("transform", "translate(0," + height + ")")
      .call(
        d3.axisBottom(x0).tickFormat(function (id) {
          var found = rows.filter(function (r) {
            return r.id === id;
          })[0];
          return found ? found.label : id;
        }),
      )
      .selectAll("text")
      .attr("transform", "rotate(-28)")
      .attr("text-anchor", "end")
      .attr("fill", colors.fg)
      .attr("font-size", 11);
    g.append("g")
      .call(d3.axisLeft(y).ticks(6))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.muted);
        sel.selectAll("line,path").attr("stroke", colors.grid);
      });
    var groups = g
      .selectAll("g.grp")
      .data(rows)
      .enter()
      .append("g")
      .attr("transform", function (d) {
        return "translate(" + x0(d.id) + ",0)";
      });
    groups
      .append("rect")
      .attr("x", x1("serial"))
      .attr("y", function (d) {
        return y(d.serial_s);
      })
      .attr("width", x1.bandwidth())
      .attr("height", function (d) {
        return height - y(d.serial_s);
      })
      .attr("fill", colors.serial)
      .attr("rx", 2);
    groups
      .append("rect")
      .attr("x", x1("parallel"))
      .attr("y", function (d) {
        return y(d.parallel_s);
      })
      .attr("width", x1.bandwidth())
      .attr("height", function (d) {
        return height - y(d.parallel_s);
      })
      .attr("fill", colors.parallel)
      .attr("rx", 2);
    var legend = svg.append("g").attr("transform", "translate(" + (margin.left + 8) + ",8)");
    [
      ["串行分片（对照）", colors.serial],
      ["opt-in 分片并行（0.10）", colors.parallel],
    ].forEach(function (item, i) {
      var lg = legend.append("g").attr("transform", "translate(" + i * 220 + ",0)");
      lg.append("rect").attr("width", 12).attr("height", 12).attr("fill", item[1]).attr("rx", 2);
      lg.append("text").attr("x", 18).attr("y", 10).attr("fill", colors.fg).attr("font-size", 12).text(item[0]);
    });
  }

  function renderRss(data) {
    var host = document.getElementById("lcp10-chart-rss");
    if (!host || typeof d3 === "undefined") return;
    clear(host);
    var rows = data.workload.slice().sort(function (a, b) {
      return a.rss_delta_pct - b.rss_delta_pct;
    });
    var colors = themeColors();
    var margin = { top: 16, right: 56, bottom: 28, left: 148 };
    var dim = sizeOf("#lcp10-chart-rss", 720, 28 * rows.length + 60);
    var width = dim.width - margin.left - margin.right;
    var height = dim.height - margin.top - margin.bottom;
    var svg = d3
      .select(host)
      .append("svg")
      .attr("viewBox", "0 0 " + dim.width + " " + dim.height)
      .attr("role", "img")
      .attr("aria-label", "Peak RSS delta percent");
    var g = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");
    var y = d3
      .scaleBand()
      .domain(
        rows.map(function (d) {
          return d.label;
        }),
      )
      .range([0, height])
      .padding(0.2);
    var xMax = Math.max(
      12,
      d3.max(rows, function (d) {
        return Math.abs(d.rss_delta_pct);
      }) * 1.2,
    );
    var x = d3.scaleLinear().domain([0, xMax]).nice().range([0, width]);
    g.append("g")
      .attr("transform", "translate(0," + height + ")")
      .call(d3.axisBottom(x).ticks(6).tickFormat(function (v) {
        return v + "%";
      }))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.muted);
        sel.selectAll("line,path").attr("stroke", colors.grid);
      });
    g.append("g")
      .call(d3.axisLeft(y).tickSize(0))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.fg).attr("font-size", 12);
        sel.select(".domain").attr("stroke", "none");
      });
    g.append("line")
      .attr("x1", x(10))
      .attr("x2", x(10))
      .attr("y1", 0)
      .attr("y2", height)
      .attr("stroke", colors.accent)
      .attr("stroke-dasharray", "4 4");
    g.selectAll("rect")
      .data(rows)
      .enter()
      .append("rect")
      .attr("y", function (d) {
        return y(d.label);
      })
      .attr("height", y.bandwidth())
      .attr("x", 0)
      .attr("width", function (d) {
        return x(Math.abs(d.rss_delta_pct));
      })
      .attr("fill", function (d) {
        return d.rss_delta_pct <= 10 ? colors.parallel : colors.serial;
      })
      .attr("rx", 3);
    g.selectAll("text.val")
      .data(rows)
      .enter()
      .append("text")
      .attr("x", function (d) {
        return x(Math.abs(d.rss_delta_pct)) + 6;
      })
      .attr("y", function (d) {
        return y(d.label) + y.bandwidth() / 2;
      })
      .attr("dy", "0.35em")
      .attr("fill", colors.fg)
      .attr("font-size", 12)
      .attr("font-weight", 600)
      .text(function (d) {
        var sign = d.rss_delta_pct >= 0 ? "+" : "";
        return sign + d.rss_delta_pct.toFixed(2) + "%";
      });
  }

  function fillMeta(data) {
    var el = document.getElementById("lcp10-measured-at");
    if (el) el.textContent = data.measured_at || "";
    var note = document.getElementById("lcp10-host-note");
    if (note) note.textContent = data.host_note || "";
  }

  function renderAll(data) {
    if (!pageHasCharts()) return;
    fillMeta(data);
    renderSpeedup(data);
    renderWall(data);
    renderRss(data);
  }

  function boot() {
    if (!pageHasCharts()) return;
    ensureD3(function () {
      fetchData(renderAll);
    });
  }

  document.addEventListener("DOMContentLoaded", boot);
  window.addEventListener("load", boot);
  if (typeof document$ !== "undefined" && document$ && typeof document$.subscribe === "function") {
    document$.subscribe(boot);
  }
  setTimeout(boot, 300);
})();
