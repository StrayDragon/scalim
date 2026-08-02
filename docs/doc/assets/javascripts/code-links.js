(() => {
  const STORAGE_REPO_ROOT = "scalim_docs.repo_root";
  const STORAGE_GIT_WEB_BASE = "scalim_docs.git.web_base";
  const STORAGE_GIT_PATH_PREFIX = "scalim_docs.git.path_prefix";
  const STORAGE_VSCODE_SCHEME = "scalim_docs.editor.vscode_scheme";
  const STORAGE_CURSOR_SCHEME = "scalim_docs.editor.cursor_scheme";
  const STORAGE_ZED_SCHEME = "scalim_docs.editor.zed_scheme";

  const DEFAULT_VSCODE_SCHEME = "vscode://file/";
  const DEFAULT_CURSOR_SCHEME = "cursor://file/";
  const DEFAULT_ZED_SCHEME = "zed://file/";

  function getLocalStorage(key) {
    try {
      return window.localStorage.getItem(key) || "";
    } catch {
      return "";
    }
  }

  function setLocalStorage(key, value) {
    try {
      window.localStorage.setItem(key, String(value || ""));
    } catch {
      // ignore
    }
  }

  function normalizeRepoRoot(root) {
    let trimmed = String(root || "").trim();
    if (!trimmed) return "";
    trimmed = trimmed.replace(/\\/g, "/");
    return trimmed.replace(/\/+$/, "");
  }

  function normalizeRelPath(relPath) {
    let p = String(relPath || "").trim();
    if (!p) return "";
    // Keep repo-relative paths; drop leading "./" or "/".
    p = p.replace(/^[./]+/, "");
    return p;
  }

  function normalizeWebBase(base) {
    const trimmed = String(base || "").trim();
    if (!trimmed) return "";
    return trimmed.endsWith("/") ? trimmed : trimmed + "/";
  }

  function normalizePathPrefix(prefix) {
    let p = String(prefix || "").trim();
    if (!p) return "";
    p = p.replace(/\\/g, "/");
    p = p.replace(/^[./]+/, "");
    p = p.replace(/^\/+/, "");
    p = p.replace(/\/+$/, "");
    return p ? p + "/" : "";
  }

  function joinAbs(repoRoot, relPath) {
    const root = normalizeRepoRoot(repoRoot);
    const rel = normalizeRelPath(relPath);
    if (!root || !rel) return "";
    return root + "/" + rel;
  }

  function encodePathForUrl(absPath) {
    // encodeURI does not encode '#'/'?' which would break the URL.
    return encodeURI(absPath).replace(/#/g, "%23").replace(/\?/g, "%3F");
  }

  function guessGitBases(base) {
    const b = normalizeWebBase(base);
    if (!b) return { blobBase: "", treeBase: "" };
    if (b.includes("/-/blob/")) return { blobBase: b, treeBase: b.replace("/-/blob/", "/-/tree/") };
    if (b.includes("/-/tree/")) return { treeBase: b, blobBase: b.replace("/-/tree/", "/-/blob/") };
    if (b.includes("/blob/")) return { blobBase: b, treeBase: b.replace("/blob/", "/tree/") };
    if (b.includes("/tree/")) return { treeBase: b, blobBase: b.replace("/tree/", "/blob/") };
    return { blobBase: b, treeBase: b };
  }

  function toFileUrl(absPath) {
    const p = String(absPath || "").trim();
    if (!p) return "";
    // If already looks like file://, keep it.
    if (p.startsWith("file://")) return p;
    // Windows drive path: C:/... or C:\...
    if (/^[A-Za-z]:[\\/]/.test(p)) {
      const norm = p.replace(/\\/g, "/");
      return "file:///" + encodePathForUrl(norm);
    }
    // POSIX: /...
    if (p.startsWith("/")) return "file://" + encodePathForUrl(p);
    // Fallback: treat as absolute-ish.
    return "file://" + encodePathForUrl(p);
  }

  function parseCodeRef(rawRef) {
    const raw = String(rawRef || "").trim();
    if (!raw) return { raw: "", path: "", suffix: "" };
    const parts = raw.split("::");
    const path = parts[0];
    const suffix = parts.slice(1).join("::");
    return { raw, path, suffix };
  }

  function copyToClipboard(text) {
    const value = String(text || "");
    if (!value) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(value).catch(() => {
        window.prompt("复制以下内容:", value);
      });
      return;
    }
    window.prompt("复制以下内容:", value);
  }

  function openExternal(url) {
    if (!url) return;
    // Some schemes (vscode://) work best via location.href.
    window.location.href = url;
  }

  function openWeb(url) {
    if (!url) return;
    window.open(url, "_blank", "noopener");
  }

  function promptRepoRoot(current) {
    const next = window.prompt("请输入仓库根目录的绝对路径(用于打开本地文件):", current || "");
    if (next === null) return "";
    const normalized = normalizeRepoRoot(next);
    setLocalStorage(STORAGE_REPO_ROOT, normalized);
    return normalized;
  }

  function promptGitWebBase(current) {
    const next = window.prompt(
      "请输入 Git Web Base(例: GitHub: https://github.com/org/repo/blob/main/ ):",
      current || "",
    );
    if (next === null) return "";
    const normalized = normalizeWebBase(next);
    setLocalStorage(STORAGE_GIT_WEB_BASE, normalized);
    return normalized;
  }

  function promptGitPathPrefix(current) {
    const next = window.prompt("请输入 Git 仓库内路径前缀(可选,用于单仓/子目录映射):", current || "");
    if (next === null) return "";
    const normalized = normalizePathPrefix(next);
    setLocalStorage(STORAGE_GIT_PATH_PREFIX, normalized);
    return normalized;
  }

  function ensureMenu() {
    let menu = document.getElementById("scalim-code-link-menu");
    if (menu) return menu;

    menu = document.createElement("div");
    menu.id = "scalim-code-link-menu";
    menu.style.position = "fixed";
    menu.style.zIndex = "9999";
    menu.style.minWidth = "260px";
    menu.style.maxWidth = "420px";
    menu.style.display = "none";
    menu.style.padding = "10px";
    menu.style.border = "1px solid rgba(0,0,0,.15)";
    menu.style.borderRadius = "10px";
    menu.style.boxShadow = "0 8px 24px rgba(0,0,0,.18)";
    menu.style.background = "var(--md-default-bg-color, #fff)";
    menu.style.color = "var(--md-default-fg-color, #111)";
    menu.style.fontSize = "14px";
    menu.style.lineHeight = "1.4";

    document.body.appendChild(menu);

    // Hide menu on outside click (bubble phase), so the capture-phase opener can
    // call `stopPropagation()` without immediately closing itself.
    document.addEventListener("click", (ev) => {
      if (menu.style.display === "none") return;
      if (ev.target && menu.contains(ev.target)) return;
      menu.style.display = "none";
    });

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape") menu.style.display = "none";
    });

    return menu;
  }

  function renderMenu(menu, x, y, codeRef) {
    const { raw, path, suffix } = codeRef;
    const repoRoot = normalizeRepoRoot(getLocalStorage(STORAGE_REPO_ROOT));
    const gitWebBase = normalizeWebBase(getLocalStorage(STORAGE_GIT_WEB_BASE));
    const gitPathPrefix = normalizePathPrefix(getLocalStorage(STORAGE_GIT_PATH_PREFIX));
    const vscodeScheme = (getLocalStorage(STORAGE_VSCODE_SCHEME) || DEFAULT_VSCODE_SCHEME).trim() || DEFAULT_VSCODE_SCHEME;
    const cursorScheme = (getLocalStorage(STORAGE_CURSOR_SCHEME) || DEFAULT_CURSOR_SCHEME).trim() || DEFAULT_CURSOR_SCHEME;
    const zedScheme = (getLocalStorage(STORAGE_ZED_SCHEME) || DEFAULT_ZED_SCHEME).trim() || DEFAULT_ZED_SCHEME;

    const relPath = normalizeRelPath(path);
    const hasRepoRoot = Boolean(repoRoot);
    const hasGitWebBase = Boolean(gitWebBase);

    const title = document.createElement("div");
    title.style.fontWeight = "600";
    title.style.marginBottom = "8px";
    title.textContent = raw;

    const hint = document.createElement("div");
    hint.style.opacity = "0.8";
    hint.style.marginBottom = "10px";
    hint.textContent = suffix ? `定位: ${suffix}` : "定位: 文件/目录";

    const actions = document.createElement("div");
    actions.style.display = "grid";
    actions.style.gridTemplateColumns = "1fr";
    actions.style.gap = "6px";

    function addButton(label, onClick, { disabled = false } = {}) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      btn.disabled = disabled;
      btn.style.textAlign = "left";
      btn.style.padding = "8px 10px";
      btn.style.borderRadius = "8px";
      btn.style.border = "1px solid rgba(0,0,0,.12)";
      btn.style.background = "transparent";
      btn.style.cursor = disabled ? "not-allowed" : "pointer";
      btn.style.opacity = disabled ? "0.5" : "1";
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        if (disabled) return;
        menu.style.display = "none";
        onClick();
      });
      actions.appendChild(btn);
    }

    addButton("复制路径", () => copyToClipboard(raw));
    addButton("用 VS Code 打开", () => {
      const root = hasRepoRoot ? repoRoot : promptRepoRoot(repoRoot);
      if (!root) return;
      const abs = joinAbs(root, relPath);
      openExternal(vscodeScheme + encodePathForUrl(abs));
    });
    addButton("用 Cursor 打开", () => {
      const root = hasRepoRoot ? repoRoot : promptRepoRoot(repoRoot);
      if (!root) return;
      const abs = joinAbs(root, relPath);
      openExternal(cursorScheme + encodePathForUrl(abs));
    });
    addButton("用 Zed 打开", () => {
      const root = hasRepoRoot ? repoRoot : promptRepoRoot(repoRoot);
      if (!root) return;
      const abs = joinAbs(root, relPath);
      openExternal(zedScheme + encodePathForUrl(abs));
    });
    addButton("用浏览器打开(file://)", () => {
      const root = hasRepoRoot ? repoRoot : promptRepoRoot(repoRoot);
      if (!root) return;
      const abs = joinAbs(root, relPath);
      openWeb(toFileUrl(abs));
    });
    addButton("用 Git 网页打开", () => {
      const base = hasGitWebBase ? gitWebBase : promptGitWebBase(gitWebBase);
      if (!base) return;
      const { blobBase, treeBase } = guessGitBases(base);
      const isDir = String(path || "").trim().endsWith("/");
      const chosen = isDir ? (treeBase || blobBase) : (blobBase || treeBase);
      if (!chosen) return;
      const prefix = gitPathPrefix || normalizePathPrefix(getLocalStorage(STORAGE_GIT_PATH_PREFIX));
      const pathInRepo = prefix + relPath;
      openWeb(chosen + encodePathForUrl(pathInRepo));
    });

    const settings = document.createElement("div");
    settings.style.marginTop = "10px";
    settings.style.paddingTop = "10px";
    settings.style.borderTop = "1px solid rgba(0,0,0,.12)";
    settings.style.display = "grid";
    settings.style.gridTemplateColumns = "1fr";
    settings.style.gap = "6px";

    function addSettingButton(label, onClick) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      btn.style.textAlign = "left";
      btn.style.padding = "6px 10px";
      btn.style.borderRadius = "8px";
      btn.style.border = "1px dashed rgba(0,0,0,.22)";
      btn.style.background = "transparent";
      btn.style.cursor = "pointer";
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        onClick();
      });
      settings.appendChild(btn);
    }

    addSettingButton(`设置 repo_root(当前: ${repoRoot || "未设置"})`, () => {
      promptRepoRoot(repoRoot);
      menu.style.display = "none";
    });
    addSettingButton(`设置 Git Web Base(当前: ${gitWebBase || "未设置"})`, () => {
      promptGitWebBase(gitWebBase);
      menu.style.display = "none";
    });
    addSettingButton(`设置 Git 路径前缀(当前: ${gitPathPrefix || "未设置"})`, () => {
      promptGitPathPrefix(gitPathPrefix);
      menu.style.display = "none";
    });

    const advanced = document.createElement("details");
    advanced.style.marginTop = "4px";
    const summary = document.createElement("summary");
    summary.textContent = "更多设置";
    summary.style.cursor = "pointer";
    summary.style.opacity = "0.85";
    summary.style.userSelect = "none";

    const advancedBox = document.createElement("div");
    advancedBox.style.marginTop = "8px";
    advancedBox.style.display = "grid";
    advancedBox.style.gridTemplateColumns = "1fr";
    advancedBox.style.gap = "6px";

    function addAdvancedButton(label, onClick) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = label;
      btn.style.textAlign = "left";
      btn.style.padding = "6px 10px";
      btn.style.borderRadius = "8px";
      btn.style.border = "1px dashed rgba(0,0,0,.22)";
      btn.style.background = "transparent";
      btn.style.cursor = "pointer";
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        onClick();
      });
      advancedBox.appendChild(btn);
    }

    addAdvancedButton(`设置 VS Code Scheme(当前: ${vscodeScheme})`, () => {
      const next = window.prompt("请输入 VS Code 的 URL scheme 前缀:", vscodeScheme);
      if (next === null) return;
      setLocalStorage(STORAGE_VSCODE_SCHEME, String(next || "").trim() || DEFAULT_VSCODE_SCHEME);
      menu.style.display = "none";
    });

    addAdvancedButton(`设置 Cursor Scheme(当前: ${cursorScheme})`, () => {
      const next = window.prompt("请输入 Cursor 的 URL scheme 前缀:", cursorScheme);
      if (next === null) return;
      setLocalStorage(STORAGE_CURSOR_SCHEME, String(next || "").trim() || DEFAULT_CURSOR_SCHEME);
      menu.style.display = "none";
    });

    addAdvancedButton(`设置 Zed Scheme(当前: ${zedScheme})`, () => {
      const next = window.prompt("请输入 Zed 的 URL scheme 前缀:", zedScheme);
      if (next === null) return;
      setLocalStorage(STORAGE_ZED_SCHEME, String(next || "").trim() || DEFAULT_ZED_SCHEME);
      menu.style.display = "none";
    });

    advanced.appendChild(summary);
    advanced.appendChild(advancedBox);
    settings.appendChild(advanced);

    // Build final content
    menu.replaceChildren(title, hint, actions, settings);

    // Position with basic viewport clamping
    const margin = 10;
    menu.style.left = "0px";
    menu.style.top = "0px";
    menu.style.display = "block";
    const rect = menu.getBoundingClientRect();
    const left = Math.min(Math.max(margin, x), window.innerWidth - rect.width - margin);
    const top = Math.min(Math.max(margin, y), window.innerHeight - rect.height - margin);
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
  }

  document.addEventListener(
    "click",
    (ev) => {
    const target = ev.target;
    if (!(target instanceof Element)) return;

    const a = target.closest("a[href]");
    if (!a) return;

    const href = a.getAttribute("href") || "";
    // 仓库文件链接约定: `repo:<repo-relative-path>`（正文显示路径，打开动作由注解菜单完成）。
    const marker = "repo:";
    const idx = href.indexOf(marker);
    if (idx < 0) return;

    const rawRef = decodeURIComponent(href.slice(idx + marker.length)).replace(/\?ref$/, "");
    const codeRef = parseCodeRef(rawRef);
    if (!codeRef.raw) return;

    ev.preventDefault();
    ev.stopPropagation();

    const menu = ensureMenu();
    renderMenu(menu, ev.clientX, ev.clientY, codeRef);
    },
    // Use capture to run before mkdocs-material's instant-navigation click handler.
    true,
  );
})();
