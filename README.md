# OpenSweep

[![ci](https://github.com/lm7644/opensweep/actions/workflows/ci.yml/badge.svg)](https://github.com/lm7644/opensweep/actions/workflows/ci.yml)

[中文](#中文) | [English](#english)

<a id="中文"></a>
## 中文

Windows / macOS 隐私痕迹与垃圾清理工具（**v3.2**，洁室实现）。**零依赖**（仅 Python 3.10+ 标准库）、**主程序零外联**（`updates` 页仅在你点击时调用 winget；维护者发布脚本 `upload_to_github.py` 会访问 GitHub API，不属于运行时功能）、**默认只读**、**全操作可撤销**（journal 机制）、**凭据库全规则不可见**。

项目起初只做隐私痕迹清理，现已扩展为「痕迹 + 垃圾」清理器，并附带只读盘点（启动项 / 已装软件 / 待升级 / 重复文件快查）与组合工具指引——清理交给本工具，其余交给生态（见 [ECOSYSTEM.md](ECOSYSTEM.md)）。

v3.2 新增：**`purge` 撤销区清空**（CLI / GUI / Web UI 三端，确认后可永久删除备份，CLI 支持 `--shred` 覆写）；安全加固（令牌常量时间比较、Host 头校验防 DNS 重绑定、`dupes` 参数校验、SQLite 清理后 best-effort `VACUUM`、注册表导出失败即中止）；跨平台撤销区路径修复（macOS `$TMPDIR`）；GUI 撤销按钮失效修复。
v3.1 新增：`report`（自包含 HTML 审计报告）、`dupes`（重复文件只读快查）、`apply --restore-point`（清理前系统还原点）、macOS `$TMPDIR` 按年龄清理规则（≥3 天）。

> **重要（默认值变更）**：`junk.temp.user`（`%TEMP%`）已改为 **`risk: high` / `default: false`**，默认 `apply` 不再包含它。该规则用 `patterns: "*"` + `recurse: true` **递归清空整个用户临时目录**（含其他程序正在使用的临时文件），可撤销但会打断运行中的安装程序/应用。需要时请显式点名执行：`python opensweep.py apply --all --rule junk.temp.user --yes`，并先确认没有安装程序在跑。Web UI 会把该规则标为「高风险」并在确认框里单独提示。

三种前端：CLI（`opensweep.py`）/ 暗色桌面 GUI（`gui.py`）/ 深色应用式本地 Web UI（`server.py` → http://127.0.0.1，标题栏＋侧栏＋状态栏布局，对齐桌面 GUI）。规则库为声明式 JSON（`rules-windows.json` / `rules-darwin.json` / `harden.json`），按平台加载。

> **在线演示**：[https://lm7644.github.io/opensweep/](https://lm7644.github.io/opensweep/) —— GitHub Pages 上的深色应用式 Web UI 静态样本页；页面数字为演示数据，不是本机扫描结果，真实清理仍需本机运行 `python server.py`。

> OpenSweep 为洁室实现：不含任何商业产品的代码、资产或规则文本；清理目标位置均为公开取证事实。与任何商业清理器无关。

### 快速开始

```bash
python opensweep.py rules          # 规则清单
python opensweep.py scan           # 只读扫描
python opensweep.py apply          # 干跑（默认）；--yes 执行；--undo 可还原
python opensweep.py apply --restore-point --yes   # 清理前先建系统还原点（Windows，需管理员）
python opensweep.py harden         # Windows 隐私设置加固报告（--yes 应用）
python opensweep.py startup|apps   # 只读清单（启动项 / 已装软件）
python opensweep.py updates        # winget 待升级列表（Windows）
python opensweep.py dupes <dir>    # 重复文件快查（只读，≥10MB 内容哈希）
python opensweep.py report         # 自包含 HTML 审计报告（账本风格）
python opensweep.py undo <journal> # 按 journal 逆序还原一整笔清理
python opensweep.py purge          # 撤销区盘点（只读预览）；--yes 永久清空；--shred 先覆写
python server.py                   # 深色应用 Web UI（打印带 token 的本地地址）
python gui.py                      # 桌面 GUI
python tests/test_suite.py         # 沙箱安全测试（清单哈希 + 多轮 apply/undo）
```

### 安全设计

1. dry-run 默认，破坏性动作需 `--yes` / 对话框确认 / API `confirm:true`
2. 一切变更入 journal：文件移入撤销区、注册表先导出、SQLite 先整库备份；`undo` 逆序还原
3. 凭据/书签库（Login Data、Bookmarks 等）对**所有**规则不可见
4. 浏览器运行时其规则自动跳过；Cookie 支持站点白名单
5. 不提供"保存的密码清理"；回收站清空默认关闭且不可撤销（故默认关）
6. 本地 Web 服务仅绑定 `127.0.0.1`，令牌常量时间比较 + Host 头校验（防 DNS 重绑定），破坏性 API 必带 `confirm:true`

### 隐私边界与已知限制（诚实声明）

- **撤销区是明文副本**：清理只是把文件/数据库/注册表备份移入撤销区（`%TEMP%\OpenSweepUndo` 或 macOS `$TMPDIR/OpenSweepUndo`），痕迹并未真正消失，而是换了个地方明文存放，以便 `undo`。确认不再需要还原后，用 `purge` 永久清空撤销区；`purge --shred` 会先覆写再删除（best-effort，**非取证级安全擦除**——SSD 磨损均衡/日志文件系统下覆写不等于彻底不可恢复）。
- **整库备份的连带面**：SQLite 规则为保证可撤销，备份的是**整个数据库文件**，因此备份里会连带同库的其它表（如清理 Cookie 时备份含同库的历史/ autofill 等）。这是「整笔可还原」设计的代价；`purge` 会一并销毁这些备份。
- **凭据保护按文件名**：`Login Data`、`Bookmarks` 等凭据/书签库靠**文件名**对所有规则不可见；若某程序把凭据存成非常规文件名，不在保护之列。规则只覆盖公开取证事实里的标准位置。
- **注册表导出失败即中止**：任一注册表项备份（`reg export`）失败时，该项跳过不动，绝不无备份删除。
- **浏览器运行时**：相关规则自动跳过（行计数显示 n/a）；Cookie 白名单按站点保留。

### 平台支持

| 平台 | 状态 |
|---|---|
| Windows 10/11 x64 | 本机全量实测（安全套件 41/41、饱和套件 41/41、server 自检 10/10、GUI、Web UI） |
| macOS | 代码路径完成（平台守卫 + `rules-darwin.json` + 跨平台套件），以 CI `macos-latest` 矩阵为准 |
| Linux | 可运行引擎核心（文件/SQLite 规则），无内置规则集，欢迎贡献 `rules-linux.json` |

<a id="english"></a>
## English

> **Live demo**: [https://lm7644.github.io/opensweep/](https://lm7644.github.io/opensweep/) — static sample of the dark, desktop-app-style Web UI on GitHub Pages. Numbers are demo data, not a scan of your machine; run `python server.py` locally for real cleaning.

A privacy-trace **and junk** cleaner for Windows & macOS (clean-room implementation, **v3.2**). **Zero dependencies** (Python 3.10+ stdlib only), **no outbound traffic from the app** (winget runs only when you open the updates page; the maintainer-only `upload_to_github.py` talks to the GitHub API), **read-only by default**, and **everything reversible** via journals. Credential stores (Login Data / Bookmarks) are invisible to every rule. Beyond cleaning, it offers read-only inventories (startup / installed apps / pending updates / duplicate quick-scan) and a composition layer that defers the rest to the ecosystem.

**Privacy boundary:** cleaning moves plaintext copies into the undo area so they stay reversible — the traces are not gone until you `purge` the undo area (`--shred` overwrites first, best-effort, not forensic-grade). See the Chinese section above for the full honest limitations.

Front-ends: CLI (`opensweep.py`), dark desktop GUI (`gui.py`), and a dark, desktop-app-style local web UI (`server.py` → http://127.0.0.1, token-gated). Rules are declarative JSON loaded per platform (`rules-windows.json` / `rules-darwin.json` / `harden.json`).

```bash
python opensweep.py scan    # read-only scan
python opensweep.py apply   # dry-run by default; add --yes, undo anytime
python opensweep.py harden  # Windows privacy-settings hardening (report first)
python opensweep.py purge   # preview undo area; --yes destroys backups, --shred overwrites
python server.py            # local web UI (prints tokenized URL)
python tests/test_suite.py  # sandboxed safety suite (manifest-hashed, multi-round)
```

CI runs the sandboxed safety suite on **windows-latest + macos-latest** (Python 3.10/3.12) on every push.

### Docs
`FEATURES.md`（功能对照）/ `BENCHMARK.md`（竞品评分，算式透明）/ `REVIEW.md`（对抗式复查）/ `ECOSYSTEM.md`（组合与借鉴生态）/ `tests/`（安全测试套件）

### License
MIT — see [LICENSE](LICENSE). Clean-room notice in [NOTICE](NOTICE).
