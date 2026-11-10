# OpenSweep 对抗式复查记录（v1.0→v1.1→v3.2）+ 开发价值评估

复查日期：2026-10-31 ｜ 方法：全文重读推演 + 独立交叉验证（不经被测代码）+ 对照 ccleaner.ini 规则库原文

## 一、发现清单（v1.0 → v1.1 全部已修复）

| # | 严重度 | 问题 | 根因 | 修复 |
|---|---|---|---|---|
| B1 | **严重** | UNDO_ROOT 位于 `%TEMP%\OpenSweepUndo`，而 `junk.temp.user` 规则扫描/清理整个 `%TEMP%` —— **二次 apply 会迁移旧备份目录，破坏撤销链** | 撤销区选址与清理目标区重叠 | `iter_file_candidates()` 统一排除 UNDO_PREFIX |
| B2 | **严重** | dry-run 仍以读写模式打开真实 SQLite 并执行 DELETE（仅靠"不提交即回滚"兜底），短暂持锁 | dry 分支只跳过了 commit | dry 改为 `sqlite_count()` 只读估计（immutable=1），永不写打开 |
| B3 | 中 | `apply --rule X` 显式选择非默认规则时被 `default` 过滤器吞掉 | `sel2 = [r for r in sel if args.all or r["default"]]` 无显式优先 | 显式 `--rule` 时跳过默认过滤 |
| B4 | 中 | `browser.*.history` 与 `browser.*.session` 模式重叠（Current/Last Tabs 双计） | 规则拆分时遗留 | 从 history 移除，归属 session |
| B5 | 中（遗漏） | **Recent 快捷方式 `.lnk`（2 个）与 Taskbar Jump Lists（549 个文件）完全未覆盖**，对照 ccleaner.ini `[Recent Documents]`/`[Taskbar Jump Lists]` 确认属核心隐私面 | 初版规则集遗漏 | 新增 `win.recentitems`（默认开）、`win.jumplists`（默认关） |
| B6 | 中 | 文件型规则路径（path 本身是文件，如 PSReadLine history）扫描恒为 0 —— 实测该文件存在 18,642 字节但报 0 | `base.glob("*")` 对文件基路径返回空 | `iter_file_candidates()` 处理文件型基路径（fnmatch 匹配） |
| B7 | 小 | 死代码：`import ctypes`、`dir_size`、`chromium_profiles`、`firefox_profiles` 未使用 | 演进残留 | 删除 |
| B8 | 小 | Chrome 运行时 sqlite 项显示 0，易误读为"无 Cookie" | 守卫跳过时无说明 | notes 显式追加 "row counts n/a while browser running" |
| B9 | 中（潜伏） | Firefox Cookie 白名单会引用不存在的 `host_key` 列（moz_cookies 列名为 `host`），**启用白名单即 SQL 报错、整条删除失败** | KEEP 子句按 Chromium 列名硬编码 | 表级 `col` 字段 + `table_where()` 统一构造，域名参数消毒（防引号注入 SQL） |

## 二、扫描数字独立交叉验证（不经 opensweep.py）

| 指标 | OpenSweep v1.0 报告 | 独立直查 | 判定 |
|---|---|---|---|
| Edge cookies 行数 | 70 | 70 | ✅ 精确一致 |
| Edge autofill 行数 | 133 | 133 | ✅ 精确一致 |
| ComDlg32 注册表值 | 147 | 147 | ✅ 精确一致 |
| PSReadLine history | **0（bug）** | 存在，18,642 B | ❌ → v1.1 修复后报 1 项/18.2 KiB |
| Recent .lnk | **未覆盖（bug）** | 2 | ❌ → v1.1 新规则报 2 |
| Jump Lists | **未覆盖（bug）** | 65+484=549 | ❌ → v1.1 新规则报 549（4.1MB） |

## 三、v1.1 回归验证

- 规则总数 41（11 traces + 9 junk + 5 apps + 16 browsers）
- 全量扫描：18,752 项 / 1.0 GB；三处修复项（pshistory/recentitems/jumplists）与独立直查数字逐一吻合
- dry-run apply：分类过滤、显式 `--rule` 覆盖、零写入均符合预期
- 文档勘误：v1.0 宣称"38 条规则"实为 39（off-by-one），v1.1 修订后为 41，FEATURES.md 已更正

**遗留已知限制**（非缺陷，已在 README 声明）：`C:\Windows\Temp` 需管理员；浏览器打开时行计数 n/a；Registry"无效项"启发式清理刻意不做；undo 不覆盖 recyclebin/flushdns。

---

## 四、复刻开发价值评估

### 结论先行
**作为个人隐私工具链组件：值得维护性投入（v1.1 即合理交付点）。作为产品：不建议继续投入。**

### 1. 用户价值（对你）—— 高
- 本机装有 CCleaner 7（LocalSystem 服务常驻 + 遥测/广告多通道 + 远程配置可改行为）。OpenSweep 提供了**零网络、规则本地静态、全操作可撤销、可审计**的对位替代，且干净解决"清理器自身是隐私负债"的悖论。
- 复刻过程沉淀的注册表/文件痕迹位置知识（41 条规则即知识库）独立于工具本身有价值。

### 2. 技术价值 —— 已兑现
- 验证了一条完整方法论：逆向取证 → 语义还原（规则语法/守卫/白名单/备份语义）→ 洁室重实现 → 安全语义超集（dry-run 默认 + 全 journal undo，原版仅注册表有备份）。
- 本次复查证明该产物经得起对抗式审计（9 处发现全部可归因、可修复、可回归）。

### 3. 产品化 —— 否（成本/竞争分析）
| 维度 | 判断 |
|---|---|
| 市场 | 拥挤：BleachBit（开源免费）、Windows 11 内置存储感知+隐私仪表盘、O&O ShutUp、Autoruns 各占生态位 |
| 形态 | CLI 无大众竞争力；补 GUI 是数周级投入且要长期维护 |
| 维护负担 | 浏览器 profile 路径/SQLite schema 漂移是持续性负债（Chrome App-Bound 加密等前例） |
| 差异化 | "零遥测+可撤销"是真实卖点但小众，撑不起产品；作为开源小工具发布则与 BleachBit 重叠 |

### 4. 分级建议
- **已完成（本次）**：v1.1 加固——必要且回报立现。
- **可选低成本项**（每项 ≤ 半天）：单文件粉碎器（TRIM 诚实文档化）；启动项 Run 键禁用（备份语义现成）；`--json` 报告落盘作审计留痕。
- **不建议**：Driver Updater/软件更新器/性能优化器复刻——商业数据库依赖，无差异化；GUI 化。
- **长期形态**：把规则库抽为独立 JSON + 语法文档，作为"Windows 隐私痕迹位置知识库"留存，比继续堆功能更有价值。

---

## 五、v3.2 安全审计与修订记录（2026-11-09）

方法：全文重读 + 沙箱套件回归 + 本机引擎实测 + Web UI 浏览器端到端验证。上文 v1.0/v1.1 章节为历史快照（其中「41 规则」是 v1.1 当时的真实数字，未改写）；本节记录当前 45 规则引擎的审计与修复。

### 已修复

| # | 严重度 | 问题 | 修复 | 验证 |
|---|---|---|---|---|
| P1 | **高** | 撤销区明文留存全部「已清理」痕迹，且无清空手段——清理后痕迹只是换地方存放 | 新增 `undo_area_summary`/`purge_undo`/`_shred_file` + CLI `purge`（`--yes`/`--shred`）+ server `/api/purge`（confirm 门控）+ GUI/Web UI 按钮 | 沙箱 purge 实测清空；浏览器端到端（预览→勾选风险确认→清空→列表归零→磁盘为空） |
| D1 | **高** | `UNDO_ROOT` 仅读 `TEMP`，macOS（设 `TMPDIR` 而非 `TEMP`）会落到错误的相对路径 | 依次取 `TEMP`/`TMP`/`TMPDIR`/`tempfile.gettempdir()` | 沙箱注入仍生效，安全套件 41/41 |
| P4 | **高** | 注册表项可能在备份未验证时就被删除（不可逆） | `reg_export` 失败或备份不存在即跳过该项，绝不无备份删除 | 安全套件回归 |
| GUI-undo | **高**（本轮新发现） | `gui.py do_undo` 定义了 work/done 却从未调用 `_run`——「撤销选中」确认后静默无动作 | 补上 `self._run(work, done, …)`，完成后刷新列表 | GUI selftest；与其余 handler 同构 |
| P2 | 中 | SQLite 行删除后数据仍在 freelist，可被恢复 | commit 后 best-effort `VACUUM`（持锁失败不影响行删除） | 饱和套件 S9 活锁 WAL 仍 41/41 |
| purge-ro | **高**（本轮新发现） | Windows 只读属性使 `purge` 无法删除只读备份（实测 failed=3，痕迹残留），且 `_shred_file` 先 unlink 再覆写会落空 | 新增 `_force_writable`（删前 `chmod`）；`_shred_file` 改为原地覆写+`fsync` 不 unlink；`purge_undo` 对每个条目先去只读再 rmtree/unlink | 饱和套件 S19 八项全过、failed=0；只读探针文件确从磁盘消失 |
| P8 | 中 | `create_restore_point` 描述串接进 PowerShell `-Command`，未来调用方可注入 | 描述消毒（仅留 `A-Za-z0-9 _.-`，截断 120） | 编译 + 套件 |
| D2 | 中 | server `dupes` 的 `min` 接受 NaN/负数/inf/非数字 | 校验有限且 ≥0，非法返回 400 | 实测 nan/-5/abc/inf 均 400 |
| 令牌 | 中 | server 令牌用 `==` 比较（非常量时间）；无 Host 校验（DNS 重绑定面） | `hmac.compare_digest`（bytes）+ Host 头仅许 loopback | selftest 10/10；rebind Host→403 |
| P5 | 中 | 发布脚本令牌进 curl argv（进程列表可见）；不排除密钥文件 | 令牌经 `--config -` 走 stdin（不落盘不进 argv），payload 走临时文件；排除 `.env*`/`*.pem`/`*.key`/`*.token`/`credentials.json`/`secrets.json` 等 | 假令牌 401 证传输正确；排除测试；临时文件清理测试 |
| D3 | 低 | GUI 加固确认文案暗示「仅加固所列项」，实际引擎实时读取并加固全部 exposed | 文案改为「所有当前未加固项，以应用时实时读取为准」 | 文案核对 |
| 性能 | 低 | `startup_report` 服务计数 O(n²) | 计数器上限 200 | 套件回归 |
| 死代码 | 低 | `gui._row` 全未使用（含 no-op 循环） | 整体删除 | GUI selftest |
| 文档 | 低 | 版本/计数/评分陈旧（BENCHMARK 结论 5.6/9.0 与自身算式 6.7/8.7 矛盾等） | 全量勘误 + 版本统一 v3.2 + README 重新定位（痕迹+垃圾）+ 隐私边界节 | 人工核对 |

### 未处理（及原因）

- **P3 整库备份连带敏感表**：SQLite 为「整笔可还原」备份整库，必然连带同库其它表。改为表级备份会破坏 undo 契约；已在 README 隐私边界声明，`purge` 会销毁这些备份。
- **P7 凭据保护按文件名**：覆盖任意文件名需内容识别（误报风险、超出零依赖定位）；已声明为标准位置+文件名保护。
- **D4 undo 可能覆盖清理后新建的同名文件**：低风险；改动 move/copy 语义反而可能破坏还原可靠性，维持现状并文档化。
- **`reg_tree_values` 双开键**：性能影响可忽略，重构风险大于收益，不动。

### 回归结果（Windows 10 / Python 3.13）

安全套件 **41/41** · 饱和套件 **41/41**（本轮新增 S19 purge 八项）· server 自检 **10/10** · GUI `--selftest` **OK** · Web UI 浏览器实测 purge 全流程无控制台错误。macOS 以 CI `macos-latest` 矩阵为准。
