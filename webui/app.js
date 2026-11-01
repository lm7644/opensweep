/* OpenSweep 账本 UI —— 引擎接线层。所有数据来自本机引擎（127.0.0.1）。
   纪律：破坏性动作必经 <dialog> 确认；完成后盖「讫」印。 */
"use strict";

const TOKEN = new URLSearchParams(location.search).get("t") || "";
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g,
  (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const human = (n) => {
  if (n == null) return "—";
  for (const u of ["B","KB","MB","GB"]) {
    if (n < 1024 || u === "GB") return u === "B" ? `${Math.round(n)} ${u}` : `${n.toFixed(1)} ${u}`;
    n /= 1024;
  }
};

async function api(name, opts) {
  const r = await fetch(`/api/${name}`, {
    headers: {"X-Token": TOKEN}, ...opts,
    ...(opts && opts.body ? {headers:{"X-Token":TOKEN,"Content-Type":"application/json"}} : {}),
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.status);
  return r.json();
}

function confirmBox(title, body) {
  return new Promise((resolve) => {
    const d = $("confirm");
    $("confirm-title").textContent = title;
    $("confirm-body").textContent = body;
    const yes = $("confirm-yes"), no = $("confirm-no");
    const done = (v) => { d.close(); yes.onclick = no.onclick = null; resolve(v); };
    yes.onclick = () => done(true);
    no.onclick = () => done(false);
    d.showModal();
  });
}

function stampFly(text) {
  const layer = $("stamp-layer");
  const s = $("stamp-fly");
  s.textContent = text || "讫";
  layer.classList.add("show");
  setTimeout(() => layer.classList.remove("show"), 950);
}

/* ---------- 台账 ---------- */
async function loadHealth() {
  const h = await api("health");
  $("k-harden").textContent = `${h.harden.hardened}/15`;
  $("k-harden").className = "n" + (h.harden.exposed ? " warn-text" : " ok-text");
  $("k-journals").textContent = h.journals;
  $("k-startup").textContent = "—"; $("k-apps").textContent = "—";
  const st = h.admin ? "管理员会话" : "普通权限（管理员项将跳过）";
  $("health-note").textContent = `引擎规则 ${h.rules} 条，${st}`;
  $("edition").textContent = `No.${new Date().toISOString().slice(0, 10)}-v2.2`;
  loadJournals();
}

/* ---------- 清理 ---------- */
async function doScan() {
  $("btn-scan").disabled = true;
  $("scan-body").innerHTML = `<tr><td colspan="5" class="empty">扫描中……（临时目录较大时需几十秒）</td></tr>`;
  try {
    const {results} = await api("scan");
    const tb = $("scan-body");
    tb.innerHTML = "";
    let ti = 0, tb2 = 0;
    results.forEach((o, i) => {
      ti += o.items; tb2 += o.bytes;
      const tr = document.createElement("tr");
      tr.innerHTML = `<td><input type="checkbox" data-rule="${esc(o.id)}"></td>
        <td>${esc(o.id)}</td>
        <td class="n">${o.items.toLocaleString()}</td>
        <td class="n">${human(o.bytes)}</td>
        <td style="font-size:13px;color:var(--ink2)">${esc(o.notes.join("; "))}</td>`;
      tr.addEventListener("click", (e) => {
        if (e.target.tagName !== "INPUT") {
          const cb = tr.querySelector("input");
          cb.checked = !cb.checked;
        }
        syncCleanButton();
      });
      tr.querySelector("input").addEventListener("change", syncCleanButton);
      tb.appendChild(tr);
      if (i % 2) tr.style.background = "var(--paper2)";
    });
    $("k-scan-items").textContent = ti.toLocaleString();
    $("k-scan-size").textContent = human(tb2) + "（只读）";
    window.__scanTotals = {ti, tb2};
  } catch (e) {
    $("scan-body").innerHTML = `<tr><td colspan="5" class="empty">扫描失败：${esc(e.message)}</td></tr>`;
  }
  $("btn-scan").disabled = false;
  syncCleanButton();
}

function syncCleanButton() {
  const n = document.querySelectorAll("#scan-body input:checked").length;
  $("btn-clean").disabled = n === 0;
  $("btn-clean").textContent = n ? `清理选中（${n} 条）` : "清理选中";
}

async function doClean() {
  const ids = [...document.querySelectorAll("#scan-body input:checked")]
    .map((c) => c.dataset.rule);
  if (!ids.length) return;
  const keep = $("keep").value.split(",").map((s) => s.trim()).filter(Boolean);
  const ok = await confirmBox("清理确认",
    `将清理 ${ids.length} 条规则：\n${ids.join("、")}\n\n` +
    "文件移入撤销区、注册表先导出备份，全部可还原。\n浏览器相关规则在浏览器运行时自动跳过。\n\n确认执行？");
  if (!ok) return;
  const out = await api("clean", {method:"POST",
    body: JSON.stringify({rules: ids, keep, confirm: true})});
  stampFly("讫");
  const det = out.results.map((r) => `${r.id}: 文件${r.files} 注册表${r.deleted_values} 行${r.rows}`)
    .join("\n");
  await confirmBox("完成（可撤销）", `journal：${out.journal}\n\n${det || "（无变更）"}`);
  doScan(); loadHealth();
}

/* ---------- 加固 ---------- */
async function loadHarden() {
  const {rows} = await api("harden");
  const tb = $("harden-body");
  tb.innerHTML = "";
  rows.forEach((r) => {
    const cur = r.items.map((x) => `${x.value}=${x.current}`).join("; ");
    const tr = document.createElement("tr");
    const color = r.status === "hardened" ? "ok-text" :
                  (r.status === "exposed" ? "warn-text" : "");
    tr.innerHTML = `<td><span class="${color}">${esc(r.status)}</span></td>
      <td>${esc(r.id)}<br><span style="font-size:13px;color:var(--ink2)">${esc(r.name)}</span></td>
      <td style="font-family:Consolas,monospace;font-size:13px">${esc(cur.slice(0, 90))}</td>`;
    tb.appendChild(tr);
  });
}

async function doHardenApply() {
  const exposed = [...document.querySelectorAll("#harden-body tr td:first-child")]
    .filter((td) => td.textContent.trim() === "exposed")
    .map((td) => td.parentElement.children[1].textContent.split("\n")[0]);
  if (!exposed.length) { alert("没有 exposed 项。管理员项请在管理员终端运行 harden --yes。"); return; }
  const ok = await confirmBox("加固确认",
    `将加固 ${exposed.length} 项 Windows 隐私设置：\n${exposed.join("、")}\n\n` +
    "先备份注册表，可撤销。继续？");
  if (!ok) return;
  const out = await api("harden", {method:"POST", body: JSON.stringify({confirm: true})});
  stampFly("固");
  const changed = out.results.reduce((s, r) => s + r.changed, 0);
  await confirmBox("加固完成", `变更 ${changed} 个值。\njournal：${out.journal}`);
  loadHarden(); loadHealth();
}

/* ---------- 启动项 / 软件 / 更新 / 工具 ---------- */
async function loadStartup() {
  $("startup-body").innerHTML = `<tr><td colspan="3" class="empty">枚举中……</td></tr>`;
  const {items} = await api("startup");
  const tb = $("startup-body");
  tb.innerHTML = "";
  items.forEach((it, i) => {
    const tr = document.createElement("tr");
    if (i % 2) tr.style.background = "var(--paper2)";
    tr.innerHTML = `<td>${esc(it.kind)}</td><td>${esc(it.name)}</td>
      <td style="font-size:13px;color:var(--ink2)">${esc(it.cmd)}</td>`;
    tb.appendChild(tr);
  });
  $("k-startup").textContent = items.length.toLocaleString();
}

async function loadApps() {
  const q = ($("app-q").value || "").trim().toLowerCase();
  $("apps-body").innerHTML = `<tr><td colspan="3" class="empty">枚举中……</td></tr>`;
  const {apps} = await api("apps");
  const list = q ? apps.filter((a) =>
    a.name.toLowerCase().includes(q) || a.publisher.toLowerCase().includes(q)) : apps;
  const tb = $("apps-body");
  tb.innerHTML = "";
  list.forEach((a, i) => {
    const tr = document.createElement("tr");
    if (i % 2) tr.style.background = "var(--paper2)";
    tr.innerHTML = `<td>${esc(a.name)}</td><td class="n" style="font-size:13px">${esc(a.version)}</td>
      <td style="font-size:13px;color:var(--ink2)">${esc(a.publisher)}</td>`;
    tb.appendChild(tr);
  });
  if (!list.length) tb.innerHTML = `<tr><td colspan="3" class="empty">无匹配。</td></tr>`;
  $("k-apps").textContent = apps.length.toLocaleString();
}

async function loadUpdates() {
  $("updates-pre").textContent = "winget 查询中（可能需要十几秒）……";
  const {lines} = await api("updates");
  $("updates-pre").textContent = lines.join("\n");
}

async function loadTools() {
  const {rows} = await api("tools");
  const tb = $("tools-body");
  tb.innerHTML = "";
  rows.forEach((r, i) => {
    const tr = document.createElement("tr");
    if (i % 2) tr.style.background = "var(--paper2)";
    tr.innerHTML = `<td class="ok-text">${r.present ? "✓" : ""}</td>
      <td>${esc(r.tool)}</td><td>${esc(r.purpose)}</td>
      <td style="font-size:13px;color:var(--ink2)">${esc(r.usage)}</td>`;
    tb.appendChild(tr);
  });
}

/* ---------- 销账 ---------- */
let journalSel = null;
async function loadJournals() {
  const {journals} = await api("journals");
  const tb = $("undo-body");
  tb.innerHTML = "";
  journalSel = null;
  $("btn-undo").disabled = true;
  if (!journals.length) {
    tb.innerHTML = `<tr><td colspan="4" class="empty">无未销账 journal——账本干净。</td></tr>`;
    return;
  }
  journals.forEach((j, i) => {
    const tr = document.createElement("tr");
    if (i % 2) tr.style.background = "var(--paper2)";
    tr.innerHTML = `<td><input type="radio" name="jr"></td>
      <td>${esc(j.name)}</td>
      <td class="n" style="font-size:14px">${new Date(j.mtime * 1000)
        .toLocaleString("zh-CN", {hour12: false})}</td>
      <td class="n" style="font-size:14px">${human(j.size)}</td>`;
    tr.addEventListener("click", () => {
      tb.querySelectorAll("input").forEach((r) => (r.checked = false));
      tr.querySelector("input").checked = true;
      journalSel = j.name;
      $("btn-undo").disabled = false;
      $("undo-hint").textContent = "选中后可划销还原";
    });
    tb.appendChild(tr);
  });
}

async function doUndo() {
  if (!journalSel) return;
  const ok = await confirmBox("划销确认",
    `将按 journal 逆序还原全部操作：\n${journalSel}\n\n继续？`);
  if (!ok) return;
  await api("undo", {method:"POST",
    body: JSON.stringify({journal: journalSel, confirm: true})});
  stampFly("销");
  loadJournals(); loadHealth(); loadHarden();
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

/* 初始：一次编排式载入——台账、加固、销账自动到位，其余等用户点。
   file:// 直开时引擎不可达：给出诚实提示而不是静默报错。 */
if (location.protocol === "http:" && location.hostname === "127.0.0.1") {
  loadHealth();
  loadHarden();
} else {
  $("health-note").textContent =
    "当前以 file:// 直接打开——请通过 server.py 打印的 http://127.0.0.1 地址访问。";
  $("harden-body").innerHTML =
    `<tr><td colspan="3" class="empty">请经本地服务器访问（见上方提示）。</td></tr>`;
}
