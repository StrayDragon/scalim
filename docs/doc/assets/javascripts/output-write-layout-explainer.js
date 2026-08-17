/*! Scalim docs: OutputWriteLayout interactive explainer. */
(function () {
  var ROWS = 6;
  var COLS = 4;
  var WINDOW = 2;
  var STYLE_ID = "owl-explainer-style";
  var LAYOUTS = [
    { id: "row_stream", label: "row_stream", gloss: "一行一行写" },
    { id: "column_buffered", label: "column_buffered", gloss: "整列先攒齐" },
    { id: "column_chunked", label: "column_chunked", gloss: "按窗刷列" },
  ];

  function pageHasExplainer() {
    return !!document.getElementById("owl-root");
  }

  function ensureStyle() {
    if (document.getElementById(STYLE_ID)) {
      return;
    }
    var css = [
      ".owl-root{display:grid;gap:1.25rem;margin:1rem 0 1.75rem;}",
      ".owl-card{border:1px solid var(--md-default-fg-color--lightest,#ddd);padding:14px 16px;}",
      ".owl-card h3{margin:0 0 8px;font-size:1rem;}",
      ".owl-muted{opacity:.72;font-size:.9rem;margin:0 0 10px;}",
      ".owl-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0;}",
      ".owl-btn{appearance:none;border:1px solid currentColor;background:transparent;color:inherit;padding:4px 10px;font:inherit;cursor:pointer;}",
      ".owl-btn[aria-pressed='true']{background:color-mix(in srgb, currentColor 12%, transparent);}",
      ".owl-btn:disabled{opacity:.45;cursor:not-allowed;}",
      ".owl-grid{display:grid;grid-template-columns:repeat(4,22px);gap:4px;margin:10px 0;}",
      ".owl-cell{width:22px;height:22px;border:1px solid color-mix(in srgb, currentColor 22%, transparent);box-sizing:border-box;}",
      ".owl-cell.is-ram{background:#b45309;}",
      ".owl-cell.is-flushed{background:#0f766e;}",
      ".owl-cell.is-write{outline:2px solid #0369a1;outline-offset:1px;}",
      ".owl-bar{height:14px;background:color-mix(in srgb, currentColor 10%, transparent);position:relative;flex:1;min-width:120px;}",
      ".owl-bar > span{display:block;height:100%;background:#b45309;width:0;}",
      ".owl-legend{display:flex;gap:14px;font-size:.85rem;margin:6px 0 0;}",
      ".owl-swatch{display:inline-block;width:10px;height:10px;margin-right:6px;vertical-align:middle;}",
      ".owl-choice{display:grid;gap:8px;}",
      ".owl-result{border-left:3px solid #0f766e;padding:8px 10px;margin-top:10px;}",
      ".owl-result.is-danger{border-left-color:#b42318;}",
      ".owl-peak-row{display:grid;grid-template-columns:140px 1fr 72px;gap:10px;align-items:center;margin:8px 0;}",
      ".owl-peak-fill{height:16px;background:#b45309;}",
      ".owl-peak-fill.ok{background:#0f766e;}",
      ".owl-factory-map{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px;}",
      ".owl-sink{border:1px solid color-mix(in srgb, currentColor 16%, transparent);padding:10px;}",
      ".owl-sink code{font-size:.85em;}",
      "@media (max-width:720px){.owl-factory-map,.owl-peak-row{grid-template-columns:1fr;}}",
    ].join("");
    var el = document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = css;
    document.head.appendChild(el);
  }

  function clear(el) {
    while (el && el.firstChild) {
      el.removeChild(el.firstChild);
    }
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text != null) {
      node.textContent = text;
    }
    return node;
  }

  function buildSteps(layout) {
    var steps = [];
    var r;
    var c;
    var w;
    var end;
    if (layout === "row_stream") {
      for (r = 0; r < ROWS; r++) {
        for (c = 0; c < COLS; c++) {
          steps.push({ kind: "write", r: r, c: c });
        }
        steps.push({ kind: "flush_row", r: r });
      }
    } else if (layout === "column_buffered") {
      for (c = 0; c < COLS; c++) {
        for (r = 0; r < ROWS; r++) {
          steps.push({ kind: "write", r: r, c: c });
        }
      }
      steps.push({ kind: "close" });
    } else {
      for (w = 0; w < ROWS; w += WINDOW) {
        end = Math.min(w + WINDOW, ROWS);
        for (c = 0; c < COLS; c++) {
          for (r = w; r < end; r++) {
            steps.push({ kind: "write", r: r, c: c });
          }
        }
        steps.push({ kind: "flush_window", from: w, to: end - 1 });
      }
    }
    return steps;
  }

  function emptyCells() {
    var cells = [];
    var i;
    for (i = 0; i < ROWS * COLS; i++) {
      cells.push("empty");
    }
    return cells;
  }

  function applyUntil(layout, n) {
    var steps = buildSteps(layout);
    var cells = emptyCells();
    var write = null;
    var i;
    var step;
    var r;
    var c;
    var limit = Math.max(0, Math.min(n, steps.length));
    for (i = 0; i < limit; i++) {
      step = steps[i];
      write = null;
      if (step.kind === "write") {
        cells[step.r * COLS + step.c] = "ram";
        write = { r: step.r, c: step.c };
      } else if (step.kind === "flush_row") {
        for (c = 0; c < COLS; c++) {
          cells[step.r * COLS + c] = "flushed";
        }
      } else if (step.kind === "flush_window") {
        for (r = step.from; r <= step.to; r++) {
          for (c = 0; c < COLS; c++) {
            cells[r * COLS + c] = "flushed";
          }
        }
      } else if (step.kind === "close") {
        for (r = 0; r < cells.length; r++) {
          if (cells[r] === "ram") {
            cells[r] = "flushed";
          }
        }
      }
    }
    var ram = 0;
    for (i = 0; i < cells.length; i++) {
      if (cells[i] === "ram") {
        ram++;
      }
    }
    return { cells: cells, write: write, ram: ram, total: steps.length, at: limit };
  }

  function mountTimeline(host) {
    var state = { layout: "column_buffered", at: 0, timer: null };
    var card = el("div", "owl-card");
    card.appendChild(el("h3", "", "写出时间线"));
    card.appendChild(
      el("p", "owl-muted", "小表 6×4。橙=仍在内存，青绿=已刷盘。看峰值何时起来、何时落下。"),
    );

    var tabs = el("div", "owl-row");
    LAYOUTS.forEach(function (item) {
      var btn = el("button", "owl-btn", item.label);
      btn.type = "button";
      btn.setAttribute("data-layout", item.id);
      btn.title = item.gloss;
      tabs.appendChild(btn);
    });
    card.appendChild(tabs);

    var gloss = el("p", "owl-muted", "");
    card.appendChild(gloss);

    var grid = el("div", "owl-grid");
    var cellNodes = [];
    var i;
    for (i = 0; i < ROWS * COLS; i++) {
      var cell = el("div", "owl-cell");
      grid.appendChild(cell);
      cellNodes.push(cell);
    }
    card.appendChild(grid);

    var memRow = el("div", "owl-row");
    memRow.appendChild(el("span", "", "内存中的格子"));
    var bar = el("div", "owl-bar");
    var fill = el("span");
    bar.appendChild(fill);
    memRow.appendChild(bar);
    var memLabel = el("span", "", "0");
    memRow.appendChild(memLabel);
    card.appendChild(memRow);

    var legend = el("div", "owl-legend");
    legend.innerHTML =
      '<span><i class="owl-swatch" style="background:#b45309"></i>内存</span>' +
      '<span><i class="owl-swatch" style="background:#0f766e"></i>已落盘</span>' +
      '<span><i class="owl-swatch" style="outline:2px solid #0369a1;outline-offset:-2px"></i>当前写入</span>';
    card.appendChild(legend);

    var controls = el("div", "owl-row");
    var play = el("button", "owl-btn", "播放");
    var stepBtn = el("button", "owl-btn", "下一步");
    var reset = el("button", "owl-btn", "重置");
    play.type = stepBtn.type = reset.type = "button";
    controls.appendChild(play);
    controls.appendChild(stepBtn);
    controls.appendChild(reset);
    card.appendChild(controls);

    function stop() {
      if (state.timer) {
        window.clearInterval(state.timer);
        state.timer = null;
      }
      play.textContent = "播放";
    }
    window.__owlStop = stop;

    function paint() {
      var snap = applyUntil(state.layout, state.at);
      var layoutMeta = LAYOUTS.filter(function (x) {
        return x.id === state.layout;
      })[0];
      gloss.textContent =
        layoutMeta.gloss +
        " · 步 " +
        snap.at +
        "/" +
        snap.total +
        " · 峰值只看橙格数量";
      cellNodes.forEach(function (node, idx) {
        node.className = "owl-cell";
        if (snap.cells[idx] === "ram") {
          node.classList.add("is-ram");
        } else if (snap.cells[idx] === "flushed") {
          node.classList.add("is-flushed");
        }
        if (snap.write && snap.write.r * COLS + snap.write.c === idx) {
          node.classList.add("is-write");
        }
      });
      fill.style.width = (100 * snap.ram) / (ROWS * COLS) + "%";
      memLabel.textContent = String(snap.ram);
      Array.prototype.forEach.call(tabs.querySelectorAll("button"), function (btn) {
        btn.setAttribute("aria-pressed", btn.getAttribute("data-layout") === state.layout ? "true" : "false");
      });
    }

    tabs.addEventListener("click", function (ev) {
      var target = ev.target;
      if (!target || !target.getAttribute) {
        return;
      }
      var id = target.getAttribute("data-layout");
      if (!id) {
        return;
      }
      stop();
      state.layout = id;
      state.at = 0;
      paint();
    });
    stepBtn.addEventListener("click", function () {
      var snap = applyUntil(state.layout, state.at);
      if (state.at < snap.total) {
        state.at += 1;
      }
      paint();
    });
    reset.addEventListener("click", function () {
      stop();
      state.at = 0;
      paint();
    });
    play.addEventListener("click", function () {
      if (state.timer) {
        stop();
        return;
      }
      play.textContent = "暂停";
      state.timer = window.setInterval(function () {
        var snap = applyUntil(state.layout, state.at);
        if (state.at >= snap.total) {
          stop();
          return;
        }
        state.at += 1;
        paint();
      }, 160);
    });

    host._owlStop = stop;
    paint();
    host.appendChild(card);
  }

  var DECISION = {
    start: {
      q: "是 YAML books / output_composition 多表组合吗？",
      options: [
        { label: "是", next: "books" },
        { label: "否，纯 IR 文件 sink", next: "format" },
      ],
    },
    books: {
      result: "row_stream",
      note: "组合层只能行写出。设 column_buffered / column_chunked 会 fail-fast，不是假开关。",
      danger: false,
    },
    format: {
      q: "输出 format？",
      options: [
        { label: "excel", next: "excel_orient" },
        { label: "csv", next: "csv_orient" },
      ],
    },
    csv_orient: {
      q: "CSV 要按行流式，还是按列攒完再写？",
      options: [
        { label: "按行", next: "csv_row" },
        { label: "按列", next: "csv_col" },
        { label: "想像 Excel 那样按窗刷列", next: "csv_chunk_illegal" },
      ],
    },
    csv_row: { result: "row_stream", note: "工厂 → CSVSink。", danger: false },
    csv_col: { result: "column_buffered", note: "工厂 → ColumnCSVSink。CSV 没有 column_chunked 实现。", danger: false },
    csv_chunk_illegal: {
      result: "fail-fast",
      note: "显式 column_chunked + csv 会拒绝。请改 column_buffered / row_stream，或改用 excel。",
      danger: true,
    },
    excel_orient: {
      q: "Excel 是行式写出（streaming=True），还是列式 IR（streaming=False）？",
      options: [
        { label: "行式", next: "excel_row" },
        { label: "列式", next: "excel_peak" },
      ],
    },
    excel_row: { result: "row_stream", note: "工厂 → ExcelSink。", danger: false },
    excel_peak: {
      q: "宽表 / 高行数让 pre_close 峰值不可接受？",
      options: [
        { label: "峰可接受，要历史列缓存语义", next: "excel_buf" },
        { label: "要砍峰值（按行窗刷列）", next: "excel_chunk" },
      ],
    },
    excel_buf: {
      result: "column_buffered",
      note: "默认列式路径。工厂 → ColumnExcelSink。未设 layout 时也是这条。",
      danger: false,
    },
    excel_chunk: {
      result: "column_chunked",
      note: "显式 OutputWriteLayout.COLUMN_CHUNKED。工厂 → StreamingColumnExcelSink。无自动切换。",
      danger: false,
    },
  };

  function mountDecision(host) {
    var card = el("div", "owl-card");
    card.appendChild(el("h3", "", "选型树"));
    card.appendChild(el("p", "owl-muted", "点选项往下走。这是人工选型，不是运行时自动改 layout。"));
    var body = el("div", "owl-choice");
    card.appendChild(body);
    var trail = [];

    function render(id) {
      clear(body);
      var node = DECISION[id];
      if (node.result) {
        var box = el("div", "owl-result" + (node.danger ? " is-danger" : ""));
        box.appendChild(el("strong", "", node.result));
        box.appendChild(el("p", "owl-muted", node.note));
        body.appendChild(box);
      } else {
        body.appendChild(el("p", "", node.q));
        node.options.forEach(function (opt) {
          var btn = el("button", "owl-btn", opt.label);
          btn.type = "button";
          btn.addEventListener("click", function () {
            trail.push(id);
            render(opt.next);
          });
          body.appendChild(btn);
        });
      }
      var nav = el("div", "owl-row");
      var back = el("button", "owl-btn", "上一步");
      var restart = el("button", "owl-btn", "从头");
      back.type = restart.type = "button";
      back.disabled = trail.length === 0;
      back.addEventListener("click", function () {
        var prev = trail.pop();
        if (prev) {
          render(prev);
        }
      });
      restart.addEventListener("click", function () {
        trail = [];
        render("start");
      });
      nav.appendChild(back);
      nav.appendChild(restart);
      body.appendChild(nav);
    }

    render("start");
    host.appendChild(card);
  }

  function mountPeak(host) {
    var card = el("div", "owl-card");
    card.appendChild(el("h3", "", "峰值对照（证据）"));
    card.appendChild(
      el(
        "p",
        "owl-muted",
        "100k×300 列式 Excel：column_buffered ≈ 3.59GB，column_chunked ≈ 0.12GB（约 97%）。墙钟往往差不多。",
      ),
    );
    [
      { name: "column_buffered", gb: 3.59, cls: "owl-peak-fill" },
      { name: "column_chunked", gb: 0.12, cls: "owl-peak-fill ok" },
    ].forEach(function (row) {
      var line = el("div", "owl-peak-row");
      line.appendChild(el("code", "", row.name));
      var track = el("div", "owl-bar");
      var fill = el("span", row.cls);
      fill.style.width = (100 * row.gb) / 3.59 + "%";
      track.appendChild(fill);
      line.appendChild(track);
      line.appendChild(el("span", "", row.gb.toFixed(2) + " GB"));
      card.appendChild(line);
    });
    card.appendChild(
      el("p", "owl-muted", "来源：scripts/bench_output_write_layout_dual_run.py；业务格子等价，不是 xlsx 字节相等。"),
    );
    host.appendChild(card);
  }

  var FACTORY = {
    row_stream: {
      csv: "CSVSink",
      excel: "ExcelSink",
      note: "YAML books / composition 强制走这条。",
    },
    column_buffered: {
      csv: "ColumnCSVSink",
      excel: "ColumnExcelSink",
      note: "未设 layout 时的列式默认。CSV 忽略 ExcelColumnResidency.CHUNKED。",
    },
    column_chunked: {
      csv: "fail-fast（无实现）",
      excel: "StreamingColumnExcelSink",
      note: "仅 excel + 无 composition。与 books 同开会拒绝。",
    },
  };

  function mountFactory(host) {
    var state = "column_buffered";
    var card = el("div", "owl-card");
    card.appendChild(el("h3", "", "工厂映射"));
    card.appendChild(el("p", "owl-muted", "点 layout，看 csv / excel 分别落到哪个 sink。"));
    var tabs = el("div", "owl-row");
    LAYOUTS.forEach(function (item) {
      var btn = el("button", "owl-btn", item.label);
      btn.type = "button";
      btn.setAttribute("data-layout", item.id);
      tabs.appendChild(btn);
    });
    card.appendChild(tabs);
    var map = el("div", "owl-factory-map");
    var csvBox = el("div", "owl-sink");
    var excelBox = el("div", "owl-sink");
    map.appendChild(csvBox);
    map.appendChild(excelBox);
    card.appendChild(map);
    var note = el("p", "owl-muted", "");
    card.appendChild(note);

    function paint() {
      var info = FACTORY[state];
      clear(csvBox);
      clear(excelBox);
      csvBox.appendChild(el("div", "owl-muted", "format=csv"));
      csvBox.appendChild(el("code", "", info.csv));
      excelBox.appendChild(el("div", "owl-muted", "format=excel"));
      excelBox.appendChild(el("code", "", info.excel));
      note.textContent = info.note;
      Array.prototype.forEach.call(tabs.querySelectorAll("button"), function (btn) {
        btn.setAttribute("aria-pressed", btn.getAttribute("data-layout") === state ? "true" : "false");
      });
    }

    tabs.addEventListener("click", function (ev) {
      var target = ev.target;
      if (!target || !target.getAttribute) {
        return;
      }
      var id = target.getAttribute("data-layout");
      if (!id) {
        return;
      }
      state = id;
      paint();
    });
    paint();
    host.appendChild(card);
  }

  function mount() {
    var root = document.getElementById("owl-root");
    if (!root) {
      return;
    }
    if (root.getAttribute("data-owl-ready") === "true") {
      return;
    }
    ensureStyle();
    if (typeof root._owlStop === "function") {
      root._owlStop();
    }
    clear(root);
    mountTimeline(root);
    mountDecision(root);
    mountPeak(root);
    mountFactory(root);
    root.setAttribute("data-owl-ready", "true");
  }

  function init() {
    if (typeof window.__owlStop === "function") {
      window.__owlStop();
      window.__owlStop = null;
    }
    if (!pageHasExplainer()) {
      return;
    }
    var root = document.getElementById("owl-root");
    if (root) {
      root.removeAttribute("data-owl-ready");
    }
    mount();
  }

  document.addEventListener("DOMContentLoaded", init);
  window.addEventListener("load", init);

  var subscribed = false;
  function trySubscribe() {
    if (subscribed) {
      return true;
    }
    if (typeof document$ !== "undefined" && document$ && typeof document$.subscribe === "function") {
      document$.subscribe(init);
      subscribed = true;
      return true;
    }
    return false;
  }
  if (!trySubscribe()) {
    var attempts = 0;
    var timer = window.setInterval(function () {
      attempts += 1;
      if (trySubscribe() || attempts > 40) {
        window.clearInterval(timer);
      }
    }, 250);
  }
  init();
})();
