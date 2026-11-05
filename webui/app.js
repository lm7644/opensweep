/* OpenSweep 账本 UI —— 引擎接线层。所有数据来自本机引擎（127.0.0.1）。
   纪律：破坏性动作必经 <dialog> 确认，默认焦点落在「取消」；完成后盖「讫」印。 */
"use strict";

const TOKEN = new URLSearchParams(location.search).get("t") || "";
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

    let settled = false;
    const done = (v) => {
      if (settled) return;
      settled = true;
      d.close();
      $("confirm-yes").onclick = $("confirm-no").onclick = null;
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
    $("edition").textContent = `No.${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-v3.1`;
    loadJournals();
  }).catch((e) => {
    $("health-note").textContent = `台账读取失败：${e.message}`;
  });
}

/* ---------- 清理 ---------- */
let scanData = [];
function renderScan(results) {
  const tb = $("scan-body");
  tb.innerHTML = "";
  for (const o of results) {
    const tr = document.createElement("tr");
    const has = o.items > 0;
    if (!has) tr.className = "zero-row";
    const badge = o.risk === "high" ? `<span class="badge high">高风险</span>`
      : (o.risk === "medium" ? `<span class="badge med">中风险</span>` : "");
    const label = has ? `选择规则 ${o.id}` : `${o.id}，当前无条目`;
    tr.innerHTML = `<td><input type="checkbox" data-rule="${esc(o.id)}"${has ? "" : " disabled"}
        aria-label="${esc(label)}"></td>
      <td><span class="rule-name">${esc(o.id)}</span>${badge}</td>
      <td class="n" data-l="条目">${o.items.toLocaleString()}</td>
      <td class="n" data-l="体积">${o.bytes ? human(o.bytes) : "—"}</td>
      <td class="rule-note">${esc(o.notes.join("; "))}</td>`;
    const cb = tr.querySelector("input");
    tr.addEventListener("click", (e) => {
      if (e.target.tagName === "INPUT" || cb.disabled) return;
      cb.checked = !cb.checked;
      tr.classList.toggle("selected", cb.checked);
      syncClean();
    });
    cb.addEventListener("change", () => {
      tr.classList.toggle("selected", cb.checked);
      syncClean();
    });
    tb.appendChild(tr);
  }
  let items = 0, bytes = 0;
  for (const o of results) { items += o.items; bytes += o.bytes; }
  $("sum-items").textContent = items.toLocaleString();
  $("sum-bytes").textContent = bytes ? human(bytes) : "—";
  $("scan-foot").hidden = results.length === 0;
}

function selectedIds() {
  return [...document.querySelectorAll("#scan-body input:checked")].map((c) => c.dataset.rule);
}

function syncClean() {
  const ids = selectedIds();
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

async function doScan() {
  const btn = $("btn-scan");
  btn.disabled = true;
  busy(btn, true, "扫描中… 0s");
  const t0 = Date.now();
  const tick = setInterval(() => {
    btn.textContent = `扫描中… ${Math.floor((Date.now() - t0) / 1000)}s`;
  }, 1000);
  $("scan-body").innerHTML = `<tr><td colspan="5" class="empty">扫描中……（临时目录较大时需一两分钟）</td></tr>`;
  $("scan-foot").hidden = true;
  notice("scan-note", "");
  $("health-stamp").hidden = true;
  $("k-scan-items").textContent = "—";
  $("k-scan-size").textContent = "扫描中…";
  try {
    const {results} = await api("scan");
    scanData = results;
    renderScan(results);
    let items = 0, bytes = 0;
    for (const r of results) { items += r.items; bytes += r.bytes; }
    $("k-scan-items").textContent = items.toLocaleString();
    $("k-scan-size").textContent = bytes ? human(bytes) : "0 B";
    $("health-stamp").hidden = false;
  } catch (e) {
    scanData = [];
    $("k-scan-size").textContent = "扫描失败";
    $("scan-body").innerHTML = `<tr><td colspan="5" class="empty">扫描失败：${esc(e.message)}</td></tr>`;
  }
  btn.disabled = false;
  clearInterval(tick);
  busy(btn, false);
  syncClean();
}

async function doClean() {
  const sel = syncClean();
  if (!sel.ids.length) return;
  const rows = sel.ids.map((id) => {
    const r = scanData.find((x) => x.id === id) || {items: 0, bytes: 0, risk: "low"};
    return {label: id, value: `${r.items.toLocaleString()} 项 · ${r.bytes ? human(r.bytes) : "—"}`, danger: r.risk === "high"};
  });
  const warn = sel.high.length
    ? `高风险规则 <b>${sel.high.map(esc).join("、")}</b> 用 <b>*</b> 递归匹配整个目录，会连其他程序正在使用的临时文件一起清掉。确认前请关闭安装程序与正在运行的应用。`
    : "";
  const ok = await confirmBox({
    title: "清理确认",
    body: `将清理 ${sel.ids.length} 条规则，合计 ${sel.items.toLocaleString()} 个条目${sel.bytes ? " / " + human(sel.bytes) : ""}。`,
    warn,
    rows,
    foot: "文件移入撤销区、注册表先导出备份，可在「销账」里整笔还原。浏览器相关规则在浏览器运行时自动跳过。",
    danger: sel.high.length > 0,
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
    const det = out.results.map((r) => `${r.id}：文件 ${r.files} · 注册表 ${r.deleted_values} 行 ${r.rows}`).join("\n");
    await confirmBox({
      title: "记账完成（可撤销）",
      body: `journal：${out.journal}\n\n${det || "（无变更）"}`,
      foot: "如需反悔，到「销账」选中该 journal 划销。",
      info: true,
      okText: "知道了",
    });
    doScan(); loadHealth();
  } catch (e) {
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
$("btn-dupes").onclick = loadDupes;

/* 初始：一次编排式载入——台账、加固、销账自动到位，其余等用户点。
   file:// 直开时引擎不可达：给出诚实提示而不是静默报错。 */
let PLATFORM = "unknown";
async function boot() {
  initSpy();
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
