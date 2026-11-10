/* OpenSweep 账本 UI —— 引擎接线层。所有数据来自本机引擎（127.0.0.1）。
   纪律：破坏性动作必经 <dialog> 确认，默认焦点落在「取消」；完成后盖「讫」印。 */
"use strict";

/* 令牌只存在于内存与 sessionStorage：地址栏里的 ?t= 读入后立刻抹掉，
   避免用户截图/转发地址时把令牌一起带出去。 */
let TOKEN = "";
try {
  TOKEN = new URLSearchParams(location.search).get("t") || sessionStorage.getItem("os-token") || "";
  if (TOKEN) sessionStorage.setItem("os-token", TOKEN);
  if (location.search) history.replaceState(null, "", location.pathname);
} catch (e) {
  TOKEN = new URLSearchParams(location.search).get("t") || "";
}
/* 在线演示（GitHub Pages）：demo.js 在非本机地址注入静态样本数据；
   本机 127.0.0.1 下该文件不生效，行为与真实引擎完全一致。 */
const DEMO = !!window.OPENSWEEP_DEMO;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const human = (n) => {
  if (n == null) return "—";
  for (const u of ["B", "KB", "MB", "GB"]) {
    if (n < 1024 || u === "GB") return u === "B" ? `${Math.round(n)} ${u}` : `${n.toFixed(1)} ${u}`;
    n /= 1024;
  }
};

async function api(name, opts) {
  if (DEMO) {
    if (opts && opts.method === "POST") {
      throw new Error("在线演示为只读样本：清理 / 加固 / 销账需在本机运行 python server.py");
    }
    const key = name.split("?")[0];
    if (!(key in window.OPENSWEEP_DEMO)) throw new Error(`演示数据未覆盖：${key}`);
    return JSON.parse(JSON.stringify(window.OPENSWEEP_DEMO[key]));
  }
  let r;
  try {
    r = await fetch(`/api/${name}`, {
      headers: {"X-Token": TOKEN}, ...opts,
      ...(opts && opts.body ? {headers: {"X-Token": TOKEN, "Content-Type": "application/json"}} : {}),
    });
  } catch (e) {
    throw new Error("引擎未响应，请确认 server.py 仍在运行");
  }
  if (!r.ok) {
    const j = await r.json().catch(() => ({}));
    throw new Error(j.error === "bad token" ? "令牌无效，请用 server.py 打印的完整地址重新打开" : (j.error || `HTTP ${r.status}`));
  }
  return r.json();
}

/* ---------- 对话框：默认焦点在安全项；Esc 也能收尾 ---------- */
let lastFocus = null;
function confirmBox(opt) {
  const d = $("confirm");
  return new Promise((resolve) => {
    lastFocus = document.activeElement;
    $("confirm-title").textContent = opt.title || "确认";
    $("confirm-body").textContent = opt.body || "";
    $("confirm-body").hidden = !opt.body;
    const warn = $("confirm-warn");
    warn.innerHTML = opt.warn || "";
    warn.hidden = !opt.warn;
    const list = $("confirm-list");
    list.innerHTML = "";
    if (opt.rows && opt.rows.length) {
      list.hidden = false;
      for (const row of opt.rows) {
        const li = document.createElement("li");
        li.innerHTML = `<span>${esc(row.label)}</span>` +
          `<span class="cl-n${row.danger ? " high" : ""}">${esc(row.value)}</span>`;
        list.appendChild(li);
      }
    } else {
      list.hidden = true;
    }
    $("confirm-foot").textContent = opt.foot || "";
    $("confirm-foot").hidden = !opt.foot;
    d.dataset.danger = opt.danger ? "1" : "0";
    $("confirm-yes").textContent = opt.okText || "用印确认";
    $("confirm-no").hidden = !!opt.info;
    /* 危险动作：必须先亲手勾选风险确认，确认键才可用（防误触） */
    const ack = $("confirm-ack");
    $("confirm-ack-wrap").hidden = !opt.ack;
    $("confirm-ack-text").textContent = opt.ack || "";
    ack.checked = false;
    $("confirm-yes").disabled = !!opt.ack;
    const onAck = () => { $("confirm-yes").disabled = !ack.checked; };
    if (opt.ack) ack.addEventListener("change", onAck);

    let settled = false;
    const done = (v) => {
      if (settled) return;
      settled = true;
      d.close();
      $("confirm-yes").onclick = $("confirm-no").onclick = null;
      ack.removeEventListener("change", onAck);
      $("confirm-yes").disabled = false;
      d.removeEventListener("cancel", onCancel);
      d.removeEventListener("close", onClose);
      if (lastFocus && lastFocus.focus) lastFocus.focus();
      resolve(v);
    };
    const onCancel = (e) => { e.preventDefault(); done(false); };
    const onClose = () => done(false);
    $("confirm-yes").onclick = () => done(true);
    $("confirm-no").onclick = () => done(false);
    d.addEventListener("cancel", onCancel);
    d.addEventListener("close", onClose);
    d.showModal();
    (opt.info ? $("confirm-yes") : $("confirm-no")).focus();
  });
}

function notice(id, msg) {
  const n = $(id);
  if (!n) return;
  n.textContent = msg || "";
  n.hidden = !msg;
}

function busy(btn, on, text) {
  if (!btn) return;
  btn.setAttribute("aria-busy", on ? "true" : "false");
  if (on) { btn.dataset.label = btn.dataset.label || btn.textContent; btn.textContent = text || "处理中…"; }
  else if (btn.dataset.label) { btn.textContent = btn.dataset.label; delete btn.dataset.label; }
}

function stampFly(text) {
  const layer = $("stamp-layer");
  const s = $("stamp-fly");
  s.textContent = text || "讫";
  layer.classList.add("show");
  setTimeout(() => layer.classList.remove("show"), 950);
}

/* ---------- 台账 ---------- */
function loadHealth() {
  return api("health").then((h) => {
    $("k-harden").textContent = `${h.harden.hardened}/15`;
    $("k-harden").className = "n" + (h.harden.exposed ? " warn-text" : " ok-text");
    $("k-journals").textContent = h.journals;
    const st = h.admin ? "管理员会话" : "普通权限（管理员项将跳过）";
    $("health-note").textContent = `引擎规则 ${h.rules} 条，${st}`;
    $("edition").textContent = `No.${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-v3.2`;
    loadJournals();
  }).catch((e) => {
    $("health-note").textContent = `台账读取失败：${e.message}`;
  });
}

/* ---------- 清理 ---------- */
let scanData = [];
let picked = new Set();          // 选择跨筛选保留
let riskFilter = "all";
let ruleQuery = "";

/* 引擎规则名是英文（CLI 也用它），界面给非技术用户一份中文说法 */
const RULE_ZH = {
  "win.recentdocs": "最近打开的文档记录",
  "win.runmru": "「运行」对话框历史",
  "win.typedpaths": "资源管理器地址栏历史",
  "win.wordwheel": "资源管理器搜索历史",
  "win.userassist": "程序启动次数记录",
  "win.comdlg": "打开/另存为对话框记录",
  "win.mapdrive": "映射网络驱动器记录",
  "win.findcomputer": "「查找计算机」记录",
  "win.streams": "窗口布局缓存",
  "win.traynotify": "托盘通知历史",
  "win.pshistory": "PowerShell 命令历史",
  "win.recentitems": "「最近使用」快捷方式",
  "win.jumplists": "任务栏跳转列表",
  "junk.temp.user": "用户临时文件（%TEMP%）",
  "junk.temp.system": "系统临时文件（Windows\\Temp）",
  "junk.wer": "Windows 错误报告存档",
  "junk.crashdumps": "程序崩溃转储",
  "junk.thumbnails": "缩略图与图标缓存",
  "junk.shadercache": "DirectX 着色器缓存",
  "junk.widgets": "小组件网页缓存",
  "junk.dns": "刷新 DNS 解析缓存",
  "junk.recyclebin": "清空回收站（全部盘，不可撤销）",
  "app.winrar": "WinRAR 压缩包历史",
  "app.7zip": "7-Zip 路径与压缩历史",
  "app.office": "Office 最近文件",
  "app.acrobat": "Adobe Reader 最近文件",
  "app.mpchc": "MPC-HC 最近播放",
  "app.qq.stemp": "QQ / QQNT 临时文件",
  "app.wechat": "微信日志与缓存（不动聊天记录）",
  "app.tencent.logs": "腾讯组件安装/诊断日志",
  "app.doubao": "豆包客户端崩溃与指标缓存",
  "browser.edge.cache": "Edge 缓存",
  "browser.edge.history": "Edge 浏览历史",
  "browser.edge.cookies": "Edge Cookie（可留白名单）",
  "browser.edge.session": "Edge 会话恢复数据",
  "browser.edge.autofill": "Edge 已保存的表单信息",
  "browser.chrome.cache": "Chrome 缓存",
  "browser.chrome.history": "Chrome 浏览历史",
  "browser.chrome.cookies": "Chrome Cookie（可留白名单）",
  "browser.chrome.session": "Chrome 会话恢复数据",
  "browser.chrome.autofill": "Chrome 已保存的表单信息",
  "browser.firefox.cache": "Firefox 缓存",
  "browser.firefox.history": "Firefox 浏览历史",
  "browser.firefox.cookies": "Firefox Cookie（可留白名单）",
  "browser.firefox.autofill": "Firefox 已保存的表单内容",
};
const RISK_ORDER = ["high", "medium", "low"];
const RISK_LABEL = {high: "高风险", medium: "中风险", low: "低风险"};
const RISK_NOTE = {
  high: "递归清空整个目录，可能碰到正在运行的程序——默认不勾选",
  medium: "会改动使用记录或登录态，清完可能要重新登录/重填",
  low: "缓存与历史，清掉后系统会自行重建",
};
/* 高风险规则逐条说明，写在规则名下面，不靠用户猜 */
const RULE_WARN = {
  "junk.temp.user": "整目录递归：安装程序、编辑器未保存的临时副本都可能被清掉。清理前请关掉正在运行的程序。",
  "browser.edge.autofill": "会删掉已保存的地址/表单，之后需要重新填写。",
  "browser.chrome.autofill": "会删掉已保存的地址/表单，之后需要重新填写。",
  "browser.firefox.autofill": "会删掉已保存的表单内容，之后需要重新填写。",
};
/* 引擎备注是英文（CLI 也用它），账页里要读得懂：只翻译界面已知的几条 */
function noteZh(n) {
  const deep = n.match(/^(\w+)\.exe running - deep scan skipped$/);
  if (deep) return `${deep[1]} 正在运行，已跳过深度扫描`;
  const run = n.match(/^(\S+)\.exe running$/);
  if (run) return `${run[1]} 正在运行`;
  const lock = n.match(/^(.+): locked$/);
  if (lock) return `${lock[1]} 被占用，已跳过`;
  return {
    "must close browser before cleaning": "清理前请先关闭浏览器",
    "row counts n/a while browser running": "",
    "recyclebin special is Windows-only; skipped": "回收站清空仅在 Windows 可用",
    "needs administrator": "需要管理员权限",
  }[n] ?? n;
}

function matchRule(o) {
  if (riskFilter !== "all" && o.risk !== riskFilter) return false;
  const q = ruleQuery.trim().toLowerCase();
  if (!q) return true;
  const zh = RULE_ZH[o.id] || "";
  return (o.id + " " + o.name + " " + zh).toLowerCase().includes(q);
}

function stateRow(cls, text) {
  const tr = document.createElement("tr");
  tr.className = "state-row " + cls;
  tr.innerHTML = `<td colspan="5" class="empty">${esc(text)}</td>`;
  return tr;
}

function renderScan(results) {
  const tb = $("scan-body");
  tb.innerHTML = "";
  const visible = results.filter(matchRule);
  if (!visible.length) {
    const why = results.length ? "没有匹配的规则——换个关键词，或把风险筛选切回「全部」。"
      : "没有读取到清理规则。";
    tb.appendChild(stateRow("empty", why));
  }
  for (const risk of RISK_ORDER) {
    const group = visible.filter((o) => o.risk === risk);
    if (!group.length) continue;
    let items = 0, bytes = 0;
    for (const o of group) { items += o.items; bytes += o.bytes; }
    const gr = document.createElement("tr");
    gr.className = "group";
    gr.innerHTML = `<td colspan="5"><div class="g-wrap">
      <span class="g-title">${RISK_LABEL[risk]}<span class="rule-note"> · ${RISK_NOTE[risk]}</span></span>
      <span class="g-n">${group.length} 条 · ${items.toLocaleString()} 项${bytes ? " · " + human(bytes) : ""}</span>
    </div></td>`;
    tb.appendChild(gr);
    for (const o of group) {
      const tr = document.createElement("tr");
      const has = o.items > 0;
      tr.dataset.risk = o.risk;
      if (!has) tr.className = "zero-row";
      const badge = o.risk === "high" ? `<span class="badge high">高风险</span>`
        : (o.risk === "medium" ? `<span class="badge med">中风险</span>` : "");
      const warn = RULE_WARN[o.id] ? `<span class="rule-warn">${esc(RULE_WARN[o.id])}</span>` : "";
      const label = has
        ? `选择规则 ${o.id}（${RULE_ZH[o.id] || o.name}）`
        : `${o.id}，当前无条目`;
      tr.innerHTML = `<td><input type="checkbox" data-rule="${esc(o.id)}"${has ? "" : " disabled"}
          aria-label="${esc(label)}"></td>
        <td><span class="rule-name">${esc(RULE_ZH[o.id] || o.name)}</span>${badge}
          <br><span class="rule-id">${esc(o.id)}</span>${warn}</td>
        <td class="n" data-l="条目">${o.items.toLocaleString()}</td>
        <td class="n" data-l="体积">${o.bytes ? human(o.bytes) : "—"}</td>
        <td class="rule-note">${esc(o.notes.map(noteZh).filter(Boolean).join("；"))}</td>`;
      const cb = tr.querySelector("input");
      cb.checked = picked.has(o.id);
      if (cb.checked) tr.classList.add("selected");
      tr.addEventListener("click", (e) => {
        if (e.target.tagName === "INPUT" || cb.disabled) return;
        cb.checked = !cb.checked;
        cb.dispatchEvent(new Event("change"));
      });
      cb.addEventListener("change", () => {
        if (cb.checked) picked.add(o.id); else picked.delete(o.id);
        tr.classList.toggle("selected", cb.checked);
        syncClean();
      });
      tb.appendChild(tr);
    }
  }
  let items = 0, bytes = 0;
  for (const o of visible) { items += o.items; bytes += o.bytes; }
  $("sum-items").textContent = items.toLocaleString();
  $("sum-bytes").textContent = bytes ? human(bytes) : "—";
  $("scan-foot").hidden = visible.length === 0;

  const byRisk = {high: 0, medium: 0, low: 0};
  for (const o of results) if (byRisk[o.risk] != null) byRisk[o.risk] += 1;
  $("chip-n-high").textContent = byRisk.high;
  $("chip-n-med").textContent = byRisk.medium;
  $("chip-n-low").textContent = byRisk.low;
  $("scan-count").textContent = visible.length === results.length
    ? `${results.length} 条规则` : `${visible.length} / ${results.length} 条`;
  $("scanbar").hidden = results.length === 0;
  syncClean();
}

function setRisk(risk) {
  riskFilter = risk;
  for (const b of document.querySelectorAll(".chips .chip")) {
    b.setAttribute("aria-pressed", b.dataset.risk === risk ? "true" : "false");
  }
  renderScan(scanData);
}

function syncClean() {
  const ids = [...picked];
  let items = 0, bytes = 0;
  const high = [];
  for (const id of ids) {
    const r = scanData.find((x) => x.id === id);
    if (!r) continue;
    items += r.items; bytes += r.bytes;
    if (r.risk === "high") high.push(id);
  }
  const b = $("btn-clean");
  b.disabled = !ids.length;
  b.textContent = ids.length ? `清理选中（${ids.length} 条）` : "清理选中";
  const s = $("clean-sum");
  if (!ids.length) {
    s.textContent = "尚未选择规则"; s.className = "sum";
  } else {
    s.textContent = `已选 ${ids.length} 条 · ${items.toLocaleString()} 项${bytes ? " · " + human(bytes) : ""}`;
    s.className = "sum has" + (high.length ? " danger" : "");
  }
  return {ids, items, bytes, high};
}

function selectVisible() {
  for (const o of scanData.filter(matchRule)) if (o.items > 0) picked.add(o.id);
  renderScan(scanData);
}

function clearPicked() {
  picked.clear();
  renderScan(scanData);
}

async function doScan() {
  const btn = $("btn-scan");
  const hero = $("btn-scan-hero");
  btn.disabled = hero.disabled = true;
  busy(btn, true, "扫描中… 0s");
  busy(hero, true, "扫描中…");
  const t0 = Date.now();
  const tick = setInterval(() => {
    btn.textContent = `扫描中… ${Math.floor((Date.now() - t0) / 1000)}s`;
  }, 1000);
  $("scan-body").innerHTML = "";
  $("scan-body").appendChild(stateRow("loading", "正在只读扫描本机临时文件与痕迹……（临时目录大时可能要好几分钟，可先去看别的）"));
  $("scan-foot").hidden = true;
  $("scanbar").hidden = true;
  $("scan-note").hidden = true;
  notice("scan-note", "");
  $("health-stamp").hidden = true;
  $("k-scan-items").textContent = "—";
  $("k-scan-size").textContent = "扫描中…";
  try {
    const {results} = await api("scan");
    scanData = results;
    for (const id of [...picked]) {
      const r = results.find((x) => x.id === id);
      if (!r || r.items === 0) picked.delete(id);
    }
    renderScan(results);
    let items = 0, bytes = 0;
    for (const r of results) { items += r.items; bytes += r.bytes; }
    $("k-scan-items").textContent = items.toLocaleString();
    $("k-scan-size").textContent = bytes ? human(bytes) : "0 B";
    $("health-stamp").hidden = false;
  } catch (e) {
    scanData = [];
    picked.clear();
    $("k-scan-size").textContent = "扫描失败";
    $("scan-body").innerHTML = "";
    $("scan-body").appendChild(stateRow("error", `扫描失败：${e.message}——点「只读扫描」可重试。`));
    notice("scan-note", `扫描失败：${e.message}`);
  }
  btn.disabled = hero.disabled = false;
  clearInterval(tick);
  busy(btn, false);
  busy(hero, false);
  syncClean();
}

/* 单条规则的结果分类：成功 / 部分 / 跳过 / 失败 */
function classify(r) {
  const did = r.files + r.deleted_values + r.deleted_keys + r.rows;
  const sk = r.skipped ? r.skipped.length : 0;
  if (sk && !did) return "skip";
  if (sk && did) return "part";
  if (!did) return "skip";
  return "ok";
}
const PILL = {ok: "成功", part: "部分", skip: "跳过", fail: "失败"};

function setTri(ok, skip, fail) {
  for (const [id, v] of [["res-ok", ok], ["res-skip", skip], ["res-fail", fail]]) {
    const el = $(id);
    el.textContent = v;
    el.parentElement.classList.toggle("is-zero", v === 0);
  }
}

function showResult(sel, out) {
  const list = $("result-list");
  list.innerHTML = "";
  let ok = 0, skip = 0, fail = 0;
  for (const id of sel.ids) {
    const r = out.results.find((x) => x.id === id);
    const li = document.createElement("li");
    if (!r) {
      fail += 1;
      li.innerHTML = `<span class="pill fail">失败</span>
        <span class="rl-name">${esc(RULE_ZH[id] || id)}<span class="rl-id">${esc(id)}</span></span>
        <span class="rl-val">引擎未返回该规则</span>`;
    } else {
      const k = classify(r);
      if (k === "ok" || k === "part") ok += 1; else if (k === "skip") skip += 1; else fail += 1;
      const bits = [];
      if (r.files) bits.push(`文件 ${r.files}`);
      if (r.deleted_values) bits.push(`注册表 ${r.deleted_values} 值`);
      if (r.rows) bits.push(`记录 ${r.rows} 行`);
      if (r.bytes) bits.push(human(r.bytes));
      const why = r.skipped && r.skipped.length
        ? `<span class="rule-warn">${esc(r.skipped.map(noteZh).filter(Boolean).join("；"))}</span>` : "";
      li.innerHTML = `<span class="pill ${k}">${PILL[k]}</span>
        <span class="rl-name">${esc(RULE_ZH[id] || id)}<span class="rl-id">${esc(id)}</span>${why}</span>
        <span class="rl-val">${bits.length ? esc(bits.join(" · ")) : "无条目"}</span>`;
    }
    list.appendChild(li);
  }
  setTri(ok, skip, fail);
  $("result-journal").textContent = out.journal ? `journal：${out.journal}` : "";
  $("clean-result").hidden = false;
  $("clean-result").scrollIntoView({block: "nearest", behavior: "smooth"});
}

async function doClean() {
  const sel = syncClean();
  if (!sel.ids.length) return;
  const rows = sel.ids.map((id) => {
    const r = scanData.find((x) => x.id === id) || {items: 0, bytes: 0, risk: "low"};
    return {label: RULE_ZH[id] || id, value: `${r.items.toLocaleString()} 项 · ${r.bytes ? human(r.bytes) : "—"}`, danger: r.risk === "high"};
  });
  const warn = sel.high.length
    ? `高风险规则 <b>${sel.high.map((i) => esc(RULE_ZH[i] || i)).join("、")}</b> 用 <b>*</b> 递归匹配整个目录，会连其他程序正在使用的临时文件一起清掉。确认前请关闭安装程序与正在运行的应用。`
    : "";
  const ok = await confirmBox({
    title: "清理确认",
    body: `将清理 ${sel.ids.length} 条规则，合计 ${sel.items.toLocaleString()} 个条目${sel.bytes ? " / " + human(sel.bytes) : ""}。`,
    warn,
    rows,
    foot: "文件移入撤销区、注册表先导出备份，可在「销账」里整笔还原。浏览器相关规则在浏览器运行时自动跳过。",
    danger: sel.high.length > 0,
    ack: sel.high.length ? "我知道高风险规则会清空整个目录，已关闭正在运行的程序。" : "",
    okText: "用印清理",
  });
  if (!ok) return;
  const keep = $("keep").value.split(",").map((s) => s.trim()).filter(Boolean);
  const wantRp = $("rp-check") && $("rp-check").checked;
  const btn = $("btn-clean");
  btn.disabled = true;
  busy(btn, true, "清理中…");
  try {
    const out = await api("clean", {
      method: "POST",
      body: JSON.stringify({rules: sel.ids, keep, confirm: true, restore_point: wantRp}),
    });
    stampFly("讫");
    picked.clear();
    showResult(sel, out);
    doScan(); loadHealth();
  } catch (e) {
    const list = $("result-list");
    list.innerHTML = "";
    for (const id of sel.ids) {
      const li = document.createElement("li");
      li.innerHTML = `<span class="pill fail">失败</span>
        <span class="rl-name">${esc(RULE_ZH[id] || id)}<span class="rl-id">${esc(id)}</span></span>
        <span class="rl-val">${esc(e.message)}</span>`;
      list.appendChild(li);
    }
    setTri(0, 0, sel.ids.length);
    $("result-journal").textContent = "本次未写入 journal";
    $("clean-result").hidden = false;
    notice("scan-note", `清理失败：${e.message}`);
  }
  btn.disabled = false;
  busy(btn, false);
  syncClean();
}

/* ---------- 加固 ---------- */
function loadHarden() {
  return api("harden").then(({rows}) => {
    const tb = $("harden-body");
    tb.innerHTML = "";
    for (const r of rows) {
      const cur = r.items.map((x) => `${x.value}=${x.current}`).join("; ");
      const curShort = cur.length > 44 ? cur.slice(0, 44) + "…" : cur;
      const tr = document.createElement("tr");
      const cls = r.status === "hardened" ? "ok-text" : (r.status === "exposed" ? "warn-text" : "");
      const st = r.status === "hardened" ? "已加固" : (r.status === "exposed" ? "未加固" : r.status);
      tr.innerHTML = `<td data-status="${esc(r.status)}"><span class="${cls}">${esc(st)}</span></td>
        <td><span class="rule-name">${esc(r.id)}</span><br>
        <span class="rule-note">${esc(r.name)}</span></td>
        <td class="rule-note" data-l="当前" title="${esc(cur)}">${esc(curShort)}</td>`;
      tb.appendChild(tr);
    }
  }).catch((e) => {
    $("harden-body").innerHTML = `<tr><td colspan="3" class="empty">读取失败：${esc(e.message)}</td></tr>`;
  });
}

async function doHardenApply() {
  const exposed = [...document.querySelectorAll("#harden-body td[data-status='exposed']")]
    .map((td) => td.parentElement.children[1].querySelector(".rule-name").textContent.trim());
  if (!exposed.length) {
    await confirmBox({
      title: "没有可加固项",
      body: "当前没有未加固（exposed）项。管理员项请在管理员终端运行 harden --yes。",
      info: true, okText: "知道了",
    });
    return;
  }
  const ok = await confirmBox({
    title: "加固确认",
    body: `将加固 ${exposed.length} 项 Windows 隐私设置。`,
    rows: exposed.map((id) => ({label: id, value: "exposed → hardened"})),
    foot: "先备份注册表，可在「销账」里整笔还原。",
    okText: "用印加固",
  });
  if (!ok) return;
  const btn = $("btn-harden");
  btn.disabled = true;
  busy(btn, true, "加固中…");
  try {
    const out = await api("harden", {method: "POST", body: JSON.stringify({confirm: true})});
    stampFly("固");
    const changed = out.results.reduce((s, r) => s + r.changed, 0);
    await confirmBox({
      title: "加固完成", body: `变更 ${changed} 个值。\njournal：${out.journal}`,
      info: true, okText: "知道了",
    });
    loadHarden(); loadHealth();
  } catch (e) {
    await confirmBox({title: "加固失败", body: e.message, info: true, okText: "知道了", danger: true});
  }
  btn.disabled = false;
  busy(btn, false);
}

/* ---------- 启动项 / 软件 / 更新 / 工具 ---------- */
async function loadStartup() {
  $("startup-body").innerHTML = `<tr><td colspan="3" class="empty">枚举中……</td></tr>`;
  let items;
  try {
    ({items} = await api("startup"));
  } catch (e) {
    $("startup-body").innerHTML = `<tr><td colspan="3" class="empty">读取失败：${esc(e.message)}</td></tr>`;
    return;
  }
  const tb = $("startup-body");
  tb.innerHTML = "";
  for (const it of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td data-l="类型">${esc(it.kind)}</td>
      <td><span class="rule-name">${esc(it.name)}</span></td>
      <td class="rule-note" data-l="命令">${esc(it.cmd)}</td>`;
    tb.appendChild(tr);
  }
  if (!items.length) tb.innerHTML = `<tr><td colspan="3" class="empty">没有读取到自启动项。</td></tr>`;
  $("k-startup").textContent = items.length.toLocaleString();
}

async function loadApps() {
  const q = ($("app-q").value || "").trim().toLowerCase();
  $("apps-body").innerHTML = `<tr><td colspan="3" class="empty">枚举中……</td></tr>`;
  let apps;
  try {
    ({apps} = await api("apps"));
  } catch (e) {
    $("apps-body").innerHTML = `<tr><td colspan="3" class="empty">读取失败：${esc(e.message)}</td></tr>`;
    return;
  }
  const list = q ? apps.filter((a) =>
    a.name.toLowerCase().includes(q) || a.publisher.toLowerCase().includes(q)) : apps;
  const tb = $("apps-body");
  tb.innerHTML = "";
  for (const a of list) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><span class="rule-name">${esc(a.name)}</span></td>
      <td class="rule-note" data-l="版本">${esc(a.version)}</td>
      <td class="rule-note" data-l="发布者">${esc(a.publisher)}</td>`;
    tb.appendChild(tr);
  }
  if (!list.length) tb.innerHTML = `<tr><td colspan="3" class="empty">无匹配。</td></tr>`;
  $("k-apps").textContent = apps.length.toLocaleString();
}

async function loadUpdates() {
  $("updates-pre").textContent = "winget 查询中（可能需要十几秒）……";
  try {
    const {lines} = await api("updates");
    $("updates-pre").textContent = lines.length ? lines.join("\n") : "没有待升级的软件。";
  } catch (e) {
    $("updates-pre").textContent = "查询失败：" + e.message;
  }
}

async function loadTools() {
  let rows;
  try {
    ({rows} = await api("tools"));
  } catch (e) {
    $("tools-body").innerHTML = `<tr><td colspan="4" class="empty">检测失败：${esc(e.message)}</td></tr>`;
    return;
  }
  const tb = $("tools-body");
  tb.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td data-l="在">${r.present ? '<span class="ok-text">已装</span>' : '<span class="rule-note">未装</span>'}</td>
      <td><span class="rule-name">${esc(r.tool)}</span></td>
      <td class="rule-note">${esc(r.purpose)}</td>
      <td class="rule-note" data-l="用法">${esc(r.usage)}</td>`;
    tb.appendChild(tr);
  }
}

/* ---------- 销账 ---------- */
let journalSel = null;
async function loadJournals() {
  let journals;
  try {
    ({journals} = await api("journals"));
  } catch (e) {
    $("undo-body").innerHTML = `<tr><td colspan="4" class="empty">读取失败：${esc(e.message)}</td></tr>`;
    return;
  }
  const tb = $("undo-body");
  tb.innerHTML = "";
  journalSel = null;
  $("btn-undo").disabled = true;
  $("undo-hint").textContent = "";
  if (!journals.length) {
    tb.innerHTML = `<tr><td colspan="4" class="empty">无未销账 journal——账本干净。</td></tr>`;
    return;
  }
  for (const j of journals) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td><input type="radio" name="jr" aria-label="选择 journal ${esc(j.name)}"></td>
      <td><span class="rule-name">${esc(j.name)}</span></td>
      <td class="n" data-l="写入" style="font-size:14px">${new Date(j.mtime * 1000)
        .toLocaleString("zh-CN", {hour12: false})}</td>
      <td class="n" data-l="大小" style="font-size:14px">${human(j.size)}</td>`;
    tr.addEventListener("click", () => {
      tb.querySelectorAll("input").forEach((r) => { r.checked = false; r.closest("tr").classList.remove("selected"); });
      tr.querySelector("input").checked = true;
      tr.classList.add("selected");
      journalSel = j.name;
      $("btn-undo").disabled = false;
      $("undo-hint").textContent = "选中后可划销还原";
    });
    tb.appendChild(tr);
  }
}

async function doUndo() {
  if (!journalSel) return;
  const ok = await confirmBox({
    title: "划销确认",
    body: `将按 journal 逆序还原这一笔的全部操作：\n${journalSel}`,
    foot: "还原过程中断可重新执行同一份 journal。",
    okText: "划销还原",
  });
  if (!ok) return;
  const btn = $("btn-undo");
  btn.disabled = true;
  busy(btn, true, "还原中…");
  try {
    await api("undo", {method: "POST", body: JSON.stringify({journal: journalSel, confirm: true})});
    stampFly("销");
  } catch (e) {
    await confirmBox({title: "划销失败", body: e.message, info: true, okText: "知道了", danger: true});
  }
  busy(btn, false);
  btn.disabled = true;
  loadJournals(); loadHealth(); loadHarden();
}

async function doPurge() {
  const btn = $("btn-purge");
  let s;
  try {
    s = await api("purge");
  } catch (e) {
    await confirmBox({title: "读取撤销区失败", body: e.message, info: true, okText: "知道了", danger: true});
    return;
  }
  if (!s.journals && !s.files) {
    await confirmBox({title: "撤销区已空", body: "没有可清空的备份。", info: true, okText: "知道了"});
    return;
  }
  const ok = await confirmBox({
    title: "清空撤销区",
    body: `撤销区存有 ${s.journals} 份 journal、${s.files} 个文件（${human(s.bytes)}）。`,
    warn: "撤销区里是<b>已清理痕迹的明文副本</b>。清空会永久删除这些备份，之后任何清理都<b>无法再撤销</b>。只有确定不再需要还原时才清空。",
    foot: `位置：${s.root}`,
    danger: true,
    ack: "我知道清空后无法再撤销任何清理，仍要永久删除这些备份。",
    okText: "永久清空",
  });
  if (!ok) return;
  btn.disabled = true;
  busy(btn, true, "清空中…");
  try {
    const r = await api("purge", {method: "POST", body: JSON.stringify({confirm: true})});
    stampFly("焚");
    let msg = `已清空 ${r.journals} 份 journal、${r.files} 个文件（${human(r.bytes)}）。`;
    if (r.failed) msg += `\n${r.failed} 项被占用未能删除，请关闭相关程序后重试。`;
    await confirmBox({title: "清空完成", body: msg, info: true, okText: "知道了"});
    loadJournals(); loadHealth();
  } catch (e) {
    await confirmBox({title: "清空失败", body: e.message, info: true, okText: "知道了", danger: true});
  }
  btn.disabled = false;
  busy(btn, false);
}

/* ---------- 重复快查 ---------- */
async function loadDupes() {
  const dir = $("dupes-dir").value.trim();
  if (!dir) { notice("dupes-note", "先填要扫描的目录。"); $("dupes-dir").focus(); return; }
  notice("dupes-note", "");
  const min = parseFloat($("dupes-min").value || "10");
  const btn = $("btn-dupes");
  btn.disabled = true;
  busy(btn, true, "比对中…");
  $("dupes-body").innerHTML = `<tr><td colspan="4" class="empty">哈希比对中……（目录大时较慢）</td></tr>`;
  try {
    const {groups} = await api(`dupes?dir=${encodeURIComponent(dir)}&min=${min}`);
    const tb = $("dupes-body");
    tb.innerHTML = "";
    if (!groups.length) {
      tb.innerHTML = `<tr><td colspan="4" class="empty">该体积阈值下未发现重复文件。</td></tr>`;
    }
    for (const g of groups) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td class="n" data-l="份数">${g.count}</td><td class="n" data-l="单份">${human(g.size)}</td>
        <td class="n ok-text" data-l="浪费">${human(g.wasted)}</td>
        <td class="rule-note" style="word-break:break-all">${g.files.map(esc).join("<br>")}</td>`;
      tb.appendChild(tr);
    }
  } catch (e) {
    $("dupes-body").innerHTML = `<tr><td colspan="4" class="empty">${esc(e.message)}</td></tr>`;
  }
  btn.disabled = false;
  busy(btn, false);
}

/* ---------- 账页索引：当前章节高亮 ---------- */
function initSpy() {
  const links = [...document.querySelectorAll("#nav a")];
  const byId = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      for (const a of links) a.removeAttribute("aria-current");
      const a = byId.get(e.target.id);
      if (!a) continue;
      a.setAttribute("aria-current", "true");
      const nav = $("nav");
      if (nav && nav.scrollWidth > nav.clientWidth) {
        nav.scrollTo({left: a.offsetLeft - 12, behavior: "smooth"});
      }
    }
  }, {rootMargin: "-35% 0px -60% 0px", threshold: 0});
  for (const id of byId.keys()) {
    const s = document.getElementById(id);
    if (s) io.observe(s);
  }
}

/* ---------- 接线 ---------- */
$("btn-health").onclick = () => { loadHealth(); loadHarden(); };
$("btn-scan").onclick = doScan;
$("btn-clean").onclick = doClean;
$("btn-harden-scan").onclick = loadHarden;
$("btn-harden").onclick = doHardenApply;
$("btn-startup").onclick = loadStartup;
$("btn-apps").onclick = loadApps;
$("app-q").addEventListener("keydown", (e) => { if (e.key === "Enter") loadApps(); });
$("btn-updates").onclick = loadUpdates;
$("btn-tools").onclick = loadTools;
$("btn-undo").onclick = doUndo;
$("btn-purge").onclick = doPurge;
$("btn-dupes").onclick = loadDupes;

/* 首屏主操作：滚到清理区再开扫，让用户立刻看到加载态与结果 */
$("btn-scan-hero").onclick = () => {
  $("sec-clean").scrollIntoView({block: "start"});
  doScan();
};
$("btn-select-visible").onclick = selectVisible;
$("btn-clear-sel").onclick = clearPicked;
$("btn-result-close").onclick = () => { $("clean-result").hidden = true; };
for (const chip of document.querySelectorAll(".chips .chip")) {
  chip.addEventListener("click", () => setRisk(chip.dataset.risk));
}
let qTimer = null;
$("rule-q").addEventListener("input", (e) => {
  const v = e.target.value;
  clearTimeout(qTimer);
  qTimer = setTimeout(() => { ruleQuery = v; renderScan(scanData); }, 120);
});
$("rule-q").addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  e.target.value = ""; ruleQuery = ""; renderScan(scanData);
});

/* 初始：一次编排式载入——台账、加固、销账自动到位，其余等用户点。
   file:// 直开时引擎不可达：给出诚实提示而不是静默报错。 */
let PLATFORM = "unknown";
async function boot() {
  initSpy();
  if (DEMO) {
    $("health-note").textContent = "在线演示：以下为静态样本数据，不是本机扫描结果。";
    $("rp-label").hidden = false;
    loadHealth();
    loadHarden();
    return;
  }
  if (!(location.protocol === "http:" && location.hostname === "127.0.0.1")) {
    $("health-note").textContent =
      "当前以 file:// 直接打开——请通过 server.py 打印的 http://127.0.0.1 地址访问。";
    $("harden-body").innerHTML =
      `<tr><td colspan="3" class="empty">请经本地服务器访问（见上方提示）。</td></tr>`;
    return;
  }
  if (!TOKEN) {
    $("health-note").textContent =
      "缺少访问令牌——请使用 server.py 打印的完整地址（含 ?t=…）打开本页。";
    $("harden-body").innerHTML =
      `<tr><td colspan="3" class="empty">地址不完整，未加载数据。</td></tr>`;
    return;
  }
  try {
    const h = await api("health");
    PLATFORM = h.platform || "unknown";
  } catch (e) {}
  if (PLATFORM === "win32") $("rp-label").hidden = false;
  loadHealth();
  loadHarden();
}
boot();
