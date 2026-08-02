/*! Scalim docs: write-precompute 0.10.0 interactive charts (d3). */
(function () {
  var DATA_URLS = [
    "assets/data/write-precompute-0.10.json",
    "../assets/data/write-precompute-0.10.json",
    "../../assets/data/write-precompute-0.10.json",
  ];

  var FALLBACK = null; // filled after first successful fetch; optional inline later

  function pageHasCharts() {
    return !!document.getElementById("wp10-chart-speedup");
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
      eager: "#b45309",
      late: "#0f766e",
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
    s.onerror = function () {
      console.warn("write-precompute charts: d3 failed to load");
    };
    document.head.appendChild(s);
  }

  function fetchData(cb) {
    var i = 0;
    function next() {
      if (i >= DATA_URLS.length) {
        if (FALLBACK) {
          cb(FALLBACK);
        } else {
          console.warn("write-precompute charts: data json not found");
        }
        return;
      }
      var url = DATA_URLS[i++];
      fetch(url)
        .then(function (r) {
          if (!r.ok) {
            throw new Error("status " + r.status);
          }
          return r.json();
        })
        .then(function (data) {
          FALLBACK = data;
          cb(data);
        })
        .catch(function () {
          next();
        });
    }
    next();
  }

  function sizeOf(sel, fallbackW, fallbackH) {
    var node = document.querySelector(sel);
    if (!node) {
      return { width: fallbackW, height: fallbackH };
    }
    var w = node.clientWidth || fallbackW;
    return { width: Math.max(280, w), height: fallbackH };
  }

  function renderSpeedup(data) {
    var host = document.getElementById("wp10-chart-speedup");
    if (!host || typeof d3 === "undefined") {
      return;
    }
    clear(host);
    var rows = data.workload.slice().sort(function (a, b) {
      return b.speedup - a.speedup;
    });
    var colors = themeColors();
    var margin = { top: 16, right: 48, bottom: 28, left: 148 };
    var dim = sizeOf("#wp10-chart-speedup", 720, 28 * rows.length + 60);
    var width = dim.width - margin.left - margin.right;
    var height = dim.height - margin.top - margin.bottom;

    var svg = d3
      .select(host)
      .append("svg")
      .attr("viewBox", "0 0 " + dim.width + " " + dim.height)
      .attr("role", "img")
      .attr("aria-label", "Workload speedup bar chart");

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

    g.selectAll("rect.bar")
      .data(rows)
      .enter()
      .append("rect")
      .attr("class", "bar")
      .attr("y", function (d) {
        return y(d.label);
      })
      .attr("height", y.bandwidth())
      .attr("x", 0)
      .attr("width", function (d) {
        return x(d.speedup);
      })
      .attr("fill", function (d) {
        return d.sink === "row" ? colors.late : colors.accent;
      })
      .attr("rx", 3);

    g.selectAll("text.val")
      .data(rows)
      .enter()
      .append("text")
      .attr("class", "val")
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
    var host = document.getElementById("wp10-chart-wall");
    if (!host || typeof d3 === "undefined") {
      return;
    }
    clear(host);
    var rows = data.workload.filter(function (d) {
      return d.sink === "row";
    });
    var colors = themeColors();
    var margin = { top: 20, right: 20, bottom: 64, left: 48 };
    var dim = sizeOf("#wp10-chart-wall", 720, 320);
    var width = dim.width - margin.left - margin.right;
    var height = dim.height - margin.top - margin.bottom;
    var svg = d3
      .select(host)
      .append("svg")
      .attr("viewBox", "0 0 " + dim.width + " " + dim.height)
      .attr("role", "img")
      .attr("aria-label", "Eager vs late wall time");

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
    var x1 = d3.scaleBand().domain(["eager", "late"]).range([0, x0.bandwidth()]).padding(0.15);
    var y = d3
      .scaleLinear()
      .domain([
        0,
        d3.max(rows, function (d) {
          return Math.max(d.eager_s, d.late_s);
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
          return found ? found.label.replace("·行写出", "").replace("·行", "") : id;
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
      .attr("x", x1("eager"))
      .attr("y", function (d) {
        return y(d.eager_s);
      })
      .attr("width", x1.bandwidth())
      .attr("height", function (d) {
        return height - y(d.eager_s);
      })
      .attr("fill", colors.eager)
      .attr("rx", 2);

    groups
      .append("rect")
      .attr("x", x1("late"))
      .attr("y", function (d) {
        return y(d.late_s);
      })
      .attr("width", x1.bandwidth())
      .attr("height", function (d) {
        return height - y(d.late_s);
      })
      .attr("fill", colors.late)
      .attr("rx", 2);

    var legend = svg.append("g").attr("transform", "translate(" + (margin.left + 8) + ",8)");
    [
      ["早算 (eager)", colors.eager],
      ["晚算 (0.10 write-precompute)", colors.late],
    ].forEach(function (item, i) {
      var lg = legend.append("g").attr("transform", "translate(" + i * 210 + ",0)");
      lg.append("rect").attr("width", 12).attr("height", 12).attr("fill", item[1]).attr("rx", 2);
      lg.append("text")
        .attr("x", 18)
        .attr("y", 10)
        .attr("fill", colors.fg)
        .attr("font-size", 12)
        .text(item[0]);
    });
  }

  function renderMicro(data) {
    var host = document.getElementById("wp10-chart-micro");
    if (!host || typeof d3 === "undefined") {
      return;
    }
    clear(host);
    var rows = data.micro_m_sweep;
    var colors = themeColors();
    var margin = { top: 20, right: 24, bottom: 40, left: 48 };
    var dim = sizeOf("#wp10-chart-micro", 520, 260);
    var width = dim.width - margin.left - margin.right;
    var height = dim.height - margin.top - margin.bottom;

    var svg = d3
      .select(host)
      .append("svg")
      .attr("viewBox", "0 0 " + dim.width + " " + dim.height)
      .attr("role", "img")
      .attr("aria-label", "Speedup vs derived field count M");

    var g = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");
    var x = d3
      .scaleLinear()
      .domain([
        0,
        d3.max(rows, function (d) {
          return d.m;
        }),
      ])
      .nice()
      .range([0, width]);
    var y = d3
      .scaleLinear()
      .domain([
        1,
        d3.max(rows, function (d) {
          return d.row_speedup;
        }) * 1.1,
      ])
      .nice()
      .range([height, 0]);

    g.append("g")
      .attr("transform", "translate(0," + height + ")")
      .call(d3.axisBottom(x).ticks(5))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.muted);
        sel.selectAll("line,path").attr("stroke", colors.grid);
      });
    g.append("g")
      .call(d3.axisLeft(y).ticks(5))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.muted);
        sel.selectAll("line,path").attr("stroke", colors.grid);
      });

    g.append("text")
      .attr("x", width / 2)
      .attr("y", height + 32)
      .attr("text-anchor", "middle")
      .attr("fill", colors.muted)
      .attr("font-size", 12)
      .text("仅写出派生字段数 M（N=4000）");

    var line = d3
      .line()
      .x(function (d) {
        return x(d.m);
      })
      .y(function (d) {
        return y(d.row_speedup);
      })
      .curve(d3.curveMonotoneX);

    g.append("path").datum(rows).attr("fill", "none").attr("stroke", colors.late).attr("stroke-width", 2.5).attr("d", line);

    g.selectAll("circle")
      .data(rows)
      .enter()
      .append("circle")
      .attr("cx", function (d) {
        return x(d.m);
      })
      .attr("cy", function (d) {
        return y(d.row_speedup);
      })
      .attr("r", 5)
      .attr("fill", colors.late);

    g.selectAll("text.pt")
      .data(rows)
      .enter()
      .append("text")
      .attr("x", function (d) {
        return x(d.m) + 8;
      })
      .attr("y", function (d) {
        return y(d.row_speedup) - 8;
      })
      .attr("fill", colors.fg)
      .attr("font-size", 12)
      .attr("font-weight", 600)
      .text(function (d) {
        return d.row_speedup.toFixed(2) + "×";
      });
  }

  function renderResidency(data) {
    var host = document.getElementById("wp10-chart-residency");
    if (!host || typeof d3 === "undefined") {
      return;
    }
    clear(host);
    // focus flat/mixed (honest narrative); log peak ratio
    var rows = data.residency_matrix.filter(function (d) {
      return d.topology !== "chain" || d.sink === "row";
    });
    var colors = themeColors();
    var margin = { top: 16, right: 24, bottom: 48, left: 56 };
    var dim = sizeOf("#wp10-chart-residency", 720, 340);
    var width = dim.width - margin.left - margin.right;
    var height = dim.height - margin.top - margin.bottom;

    var svg = d3
      .select(host)
      .append("svg")
      .attr("viewBox", "0 0 " + dim.width + " " + dim.height)
      .attr("role", "img")
      .attr("aria-label", "Residency peak ratio scatter");

    var g = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");
    var x = d3
      .scaleLinear()
      .domain([
        0,
        d3.max(rows, function (d) {
          return d.est_eager_gib;
        }) * 1.05,
      ])
      .nice()
      .range([0, width]);
    var y = d3
      .scaleLog()
      .domain([
        1,
        d3.max(rows, function (d) {
          return d.peak_ratio;
        }) * 1.2,
      ])
      .range([height, 0]);

    g.append("g")
      .attr("transform", "translate(0," + height + ")")
      .call(d3.axisBottom(x).ticks(6))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.muted);
        sel.selectAll("line,path").attr("stroke", colors.grid);
      });
    g.append("g")
      .call(d3.axisLeft(y).ticks(6, "~s"))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.muted);
        sel.selectAll("line,path").attr("stroke", colors.grid);
      });

    g.append("text")
      .attr("x", width / 2)
      .attr("y", height + 36)
      .attr("text-anchor", "middle")
      .attr("fill", colors.muted)
      .attr("font-size", 12)
      .text("估 eager 全驻留 (GiB，~64 B/cell)");

    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("x", -height / 2)
      .attr("y", -42)
      .attr("text-anchor", "middle")
      .attr("fill", colors.muted)
      .attr("font-size", 12)
      .text("峰值派生格比 (eager / late，log)");

    g.selectAll("circle")
      .data(rows)
      .enter()
      .append("circle")
      .attr("cx", function (d) {
        return x(d.est_eager_gib);
      })
      .attr("cy", function (d) {
        return y(Math.max(d.peak_ratio, 1.01));
      })
      .attr("r", function (d) {
        return d.sink === "row" ? 7 : 5;
      })
      .attr("fill", function (d) {
        if (d.topology === "flat") {
          return colors.late;
        }
        if (d.topology === "mixed") {
          return colors.accent;
        }
        return colors.eager;
      })
      .attr("opacity", 0.85)
      .append("title")
      .text(function (d) {
        return (
          d.scale +
          " " +
          d.topology +
          " " +
          d.sink +
          " | ratio=" +
          d.peak_ratio +
          " | eager≈" +
          d.est_eager_gib +
          "GiB"
        );
      });
  }

  function renderEngineRss(data) {
    var host = document.getElementById("wp10-chart-engine-rss");
    if (!host || typeof d3 === "undefined" || !data.engine_small_5gib) {
      return;
    }
    clear(host);
    var rows = data.engine_small_5gib;
    var colors = themeColors();
    var margin = { top: 16, right: 24, bottom: 56, left: 48 };
    var dim = sizeOf("#wp10-chart-engine-rss", 720, 280);
    var width = dim.width - margin.left - margin.right;
    var height = dim.height - margin.top - margin.bottom;

    var svg = d3
      .select(host)
      .append("svg")
      .attr("viewBox", "0 0 " + dim.width + " " + dim.height)
      .attr("role", "img")
      .attr("aria-label", "Engine peak RSS vs estimated eager hold");

    var g = svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")");
    var x = d3
      .scaleBand()
      .domain(
        rows.map(function (d) {
          return d.case_id;
        }),
      )
      .range([0, width])
      .padding(0.3);
    var y = d3
      .scaleLinear()
      .domain([
        0,
        d3.max(rows, function (d) {
          return d.rss_peak_mib;
        }) * 1.15,
      ])
      .nice()
      .range([height, 0]);

    g.append("g")
      .attr("transform", "translate(0," + height + ")")
      .call(
        d3.axisBottom(x).tickFormat(function (id) {
          return id.replace("small_", "");
        }),
      )
      .selectAll("text")
      .attr("transform", "rotate(-30)")
      .attr("text-anchor", "end")
      .attr("fill", colors.fg)
      .attr("font-size", 11);

    g.append("g")
      .call(d3.axisLeft(y).ticks(6))
      .call(function (sel) {
        sel.selectAll("text").attr("fill", colors.muted);
        sel.selectAll("line,path").attr("stroke", colors.grid);
      });

    g.selectAll("rect")
      .data(rows)
      .enter()
      .append("rect")
      .attr("x", function (d) {
        return x(d.case_id);
      })
      .attr("y", function (d) {
        return y(d.rss_peak_mib);
      })
      .attr("width", x.bandwidth())
      .attr("height", function (d) {
        return height - y(d.rss_peak_mib);
      })
      .attr("fill", colors.accent)
      .attr("rx", 3)
      .append("title")
      .text(function (d) {
        return d.case_id + ": peak RSS " + d.rss_peak_mib + " MiB (est eager hold " + d.est_eager_gib + " GiB)";
      });

    g.append("text")
      .attr("x", width / 2)
      .attr("y", -2)
      .attr("text-anchor", "middle")
      .attr("fill", colors.muted)
      .attr("font-size", 12)
      .text("~5 GiB 估档 · 真跑引擎峰值 RSS（MiB，discard sink + late）");
  }

  function fillMeta(data) {
    var el = document.getElementById("wp10-measured-at");
    if (el) {
      el.textContent = data.measured_at || "";
    }
    var note = document.getElementById("wp10-host-note");
    if (note) {
      note.textContent = data.host_note || "";
    }
  }

  function renderAll(data) {
    if (!pageHasCharts()) {
      return;
    }
    fillMeta(data);
    renderSpeedup(data);
    renderWall(data);
    renderMicro(data);
    renderResidency(data);
    renderEngineRss(data);
  }

  function boot() {
    if (!pageHasCharts()) {
      return;
    }
    ensureD3(function () {
      fetchData(function (data) {
        renderAll(data);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", boot);
  window.addEventListener("load", boot);
  if (typeof document$ !== "undefined" && document$ && typeof document$.subscribe === "function") {
    document$.subscribe(boot);
  }
  setTimeout(boot, 300);
})();
