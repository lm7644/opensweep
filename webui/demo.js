/* OpenSweep 在线演示（GitHub Pages）用的静态样本数据。
 *
 * 只在非本机地址生效：通过 server.py 打开 http://127.0.0.1 时本文件什么都不做，
 * 页面行为仍走真实引擎。演示页的所有数字都是样本，不代表任何真实设备。
 */
(function () {
  var host = location.hostname;
  if (host === "127.0.0.1" || host === "localhost" || location.protocol === "file:") return;

  var rows = [
    ["telemetry", "允许遥测数据", "hardened", "AllowTelemetry", "0"],
    ["advert-id", "广告 ID", "hardened", "Enabled", "0"],
    ["activity-history", "活动历史记录", "hardened", "PublishUserActivities", "0"],
    ["location", "定位服务", "hardened", "DisableLocation", "1"],
    ["diagnostics", "诊断数据（可选）", "hardened", "Disabled", "1"],
    ["tailored", "定制体验", "hardened", "Enabled", "0"],
    ["feedback", "反馈频率", "hardened", "DoNotShowFeedbackRequests", "1"],
    ["speech", "在线语音识别", "hardened", "HasAccepted", "0"],
    ["inking", "墨迹与输入个性化", "exposed", "Enabled", "1"],
    ["contacts", "联系人访问", "exposed", "Value", "Allow"],
    ["calendar", "日历访问", "hardened", "Value", "Deny"],
    ["messages", "消息访问", "hardened", "Value", "Deny"],
    ["app-launch", "应用启动跟踪", "exposed", "Start_TrackProgs", "1"],
    ["clipboard", "剪贴板跨设备同步", "admin-required", "EnableClipboardHistory", "1"],
    ["wifi-sense", "Wi-Fi Sense", "admin-required", "AutoConnectAllowedOEM", "1"]
  ];

  window.OPENSWEEP_DEMO = {
    health: {
      harden: {hardened: 11, exposed: 3, admin: 1},
      journals: 2, rules: 45, admin: false, platform: "win32"
    },
    harden: {
      rows: rows.map(function (r) {
        return {id: r[0], name: r[1], status: r[2], items: [{value: r[3], current: r[4]}]};
      })
    },
    scan: {
      results: [
        {id: "junk.temp.user", name: "junk.temp.user", risk: "high", items: 512, bytes: 1300234240, notes: []},
        {id: "browser.chrome.autofill", name: "browser.chrome.autofill", risk: "high", items: 34, bytes: 2202009, notes: []},
        {id: "app.wechat", name: "app.wechat", risk: "medium", items: 2100, bytes: 671088640, notes: []},
        {id: "app.qq.stemp", name: "app.qq.stemp", risk: "medium", items: 180, bytes: 99614720, notes: []},
        {id: "junk.wer", name: "junk.wer", risk: "medium", items: 3, bytes: 220200960, notes: []},
        {id: "browser.edge.cookies", name: "browser.edge.cookies", risk: "medium", items: 56, bytes: 1258291, notes: ["Edge.exe running - deep scan skipped"]},
        {id: "browser.edge.cache", name: "browser.edge.cache", risk: "low", items: 1832, bytes: 327680000, notes: []},
        {id: "browser.chrome.cache", name: "browser.chrome.cache", risk: "low", items: 940, bytes: 157286400, notes: []},
        {id: "browser.chrome.history", name: "browser.chrome.history", risk: "low", items: 640, bytes: 19503104, notes: []},
        {id: "junk.thumbnails", name: "junk.thumbnails", risk: "low", items: 4218, bytes: 88400000, notes: []},
        {id: "junk.shadercache", name: "junk.shadercache", risk: "low", items: 96, bytes: 12687770, notes: []},
        {id: "win.recentdocs", name: "win.recentdocs", risk: "low", items: 45, bytes: 314573, notes: []},
        {id: "win.runmru", name: "win.runmru", risk: "low", items: 12, bytes: 10240, notes: []},
        {id: "win.pshistory", name: "win.pshistory", risk: "low", items: 128, bytes: 20480, notes: []},
        {id: "junk.dns", name: "junk.dns", risk: "low", items: 0, bytes: 0, notes: []}
      ]
    },
    startup: {
      items: [
        {kind: "注册表·HKCU Run", name: "OneDrive", cmd: "C:\\Program Files\\Microsoft OneDrive\\OneDrive.exe /background"},
        {kind: "注册表·HKCU Run", name: "微信", cmd: "C:\\Program Files\\Tencent\\WeChat\\WeChat.exe"},
        {kind: "启动文件夹", name: "速览", cmd: "%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\quicklook.lnk"},
        {kind: "计划任务", name: "Adobe Acrobat Update", cmd: "AcrobatUpdateTask"},
        {kind: "服务", name: "Bonjour Service", cmd: "C:\\Program Files\\Bonjour\\mDNSResponder.exe"},
        {kind: "注册表·HKLM Run", name: "SecurityHealth", cmd: "%windir%\\system32\\SecurityHealthSystray.exe"}
      ]
    },
    apps: {
      apps: [
        {name: "7-Zip 24.08", version: "24.08", publisher: "Igor Pavlov"},
        {name: "Google Chrome", version: "130.0.6723.92", publisher: "Google LLC"},
        {name: "Microsoft Edge", version: "130.0.2849.68", publisher: "Microsoft Corporation"},
        {name: "Notepad++", version: "8.6.9", publisher: "Notepad++ Team"},
        {name: "PowerToys", version: "0.85.1", publisher: "Microsoft Corporation"},
        {name: "Visual Studio Code", version: "1.95.1", publisher: "Microsoft Corporation"},
        {name: "微信", version: "3.9.11", publisher: "Tencent"},
        {name: "WinRAR 7.01", version: "7.01", publisher: "win.rar GmbH"}
      ]
    },
    updates: {lines: [
      "名称                  ID                       当前版本      可用版本      源",
      "Google Chrome         Google.Chrome            130.0.6723.92 131.0.6778.86 winget",
      "PowerToys             Microsoft.PowerToys      0.85.1        0.86.0        winget",
      "Visual Studio Code    Microsoft.VisualStudioCode 1.95.1      1.96.0        winget"
    ]},
    tools: {rows: [
      {present: true, tool: "Autoruns", purpose: "启动项深度管控", usage: "单独下载，扫描登录项与计划任务"},
      {present: true, tool: "BCU (Bulk Crap Uninstaller)", purpose: "批量卸载与残留清理", usage: "卸载软件、清残留注册表"},
      {present: true, tool: "WizTree", purpose: "磁盘占用可视化", usage: "定位大目录，决定清理范围"},
      {present: false, tool: "dupeGuru", purpose: "重复文件去重", usage: "按内容哈希找重复，人工确认后删除"},
      {present: true, tool: "winget", purpose: "软件更新", usage: "winget upgrade 列出待升级"}
    ]},
    journals: {journals: [
      {name: "20261106-214203.json", mtime: 1794049323, size: 4812},
      {name: "20261105-101517.json", mtime: 1793950517, size: 12640}
    ]},
    purge: {root: "C:\\Users\\Demo\\AppData\\Local\\Temp\\OpenSweepUndo", journals: 2, files: 24, bytes: 4812000},
    rules: {rules: []},
    dupes: {groups: []}
  };

  function banner() {
    var app = document.querySelector(".app");
    var body = document.querySelector(".body");
    if (!app || !body) return;
    var d = document.createElement("div");
    d.className = "demo-strip";
    d.setAttribute("role", "status");
    d.textContent = "在线演示 · 页面数字为静态样本，不是本机扫描结果；" +
      "真实清理请在本机运行 python server.py（零外联、可撤销）。";
    app.insertBefore(d, body);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", banner);
  } else {
    banner();
  }
})();
