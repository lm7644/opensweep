# OpenSweep

[中文](#中文) | [English](#english)

<a id="中文"></a>
## 中文

Windows / macOS 隐私痕迹清理工具（洁室实现）。**零依赖**（仅 Python 3.10+ 标准库）、**零网络**（无任何出站连接；winget 仅在更新页显式调用）、**默认只读**、**全操作可撤销**（journal 机制）、**凭据库全规则不可见**。

三种前端：CLI（`opensweep.py`）/ 暗色桌面 GUI（`gui.py`）/ 账本风本地 Web UI（`server.py` → http://127.0.0.1）。规则库为声明式 JSON（`rules-windows.json` / `rules-darwin.json` / `harden.json`），按平台加载。

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
python server.py                   # 账本 Web UI（打印带 token 的本地地址）
python gui.py                      # 桌面 GUI
python tests/test_suite.py         # 沙箱安全测试（清单哈希 + 多轮 apply/undo）
```

### 安全设计

1. dry-run 默认，破坏性动作需 `--yes` / 对话框确认 / API `confirm:true`
2. 一切变更入 journal：文件移入撤销区、注册表先导出、SQLite 先整库备份；`undo` 逆序还原
3. 凭据/书签库（Login Data、Bookmarks 等）对**所有**规则不可见
4. 浏览器运行时其规则自动跳过；Cookie 支持站点白名单
5. 不提供"保存的密码清理"；回收站清空默认关闭且不可撤销（故默认关）

<a id="english"></a>
## English

A privacy trace cleaner for Windows & macOS (clean-room implementation). **Zero dependencies** (Python 3.10+ stdlib only), **zero network** (no outbound connections; winget only on the explicit updates page), **read-only by default**, and **everything reversible** via journals. Credential stores (Login Data / Bookmarks) are invisible to every rule.

Front-ends: CLI (`opensweep.py`), dark desktop GUI (`gui.py`), and a ledger-style local web UI (`server.py` → http://127.0.0.1, token-gated). Rules are declarative JSON loaded per platform (`rules-windows.json` / `rules-darwin.json` / `harden.json`).

```bash
python opensweep.py scan    # read-only scan
python opensweep.py apply   # dry-run by default; add --yes, undo anytime
python opensweep.py harden  # Windows privacy-settings hardening (report first)
python server.py            # local web UI (prints tokenized URL)
python tests/test_suite.py  # sandboxed safety suite (manifest-hashed, multi-round)
```

CI runs the sandboxed safety suite on **windows-latest + macos-latest** (Python 3.10/3.12) on every push.

### Docs
`FEATURES.md`（功能对照）/ `BENCHMARK.md`（竞品评分，算式透明）/ `REVIEW.md`（对抗式复查）/ `ECOSYSTEM.md`（组合与借鉴生态）/ `tests/`（安全测试套件）

### License
MIT — see [LICENSE](LICENSE). Clean-room notice included therein.
