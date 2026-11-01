# OpenSweep × CCleaner 7.13 功能对照矩阵

依据：CCleaner 7.13.1573 逆向证据（二进制符号、statistics.db 子系统表、`ccleaner.ini` 769 规则节、config.def、GUI 资源、服务日志结构）。OpenSweep 为洁室复刻：不含 CCleaner 任何代码/资产/规则原文，规则位置均为公开取证事实。

## 状态图例
- ✅ 复刻（可用）
- ⚠️ 降级复刻（以更安全/更简单的方式实现核心价值）
- 🛣️ 路线图（设计已定，v1 未实现）
- ❌ 不复刻（附理由——其中"遥测/广告/云"为**刻意减法**）

## 功能对照

| # | CCleaner 功能 | 逆向证据 | OpenSweep | 说明 |
|---|---|---|---|---|
| 1 | Custom Clean（Windows/应用清理） | `ccleaner.ini` 769 节规则语法 `ID/Default/ActiveProcesses/FileKey/RegKey/OnFile处理器` | ✅ | 41 条自撰规则（v1.1 复查修订）；覆盖 §3.2 所列隐私面（MRU 全套含 Jump Lists/Cookie 行级删/历史/缓存/垃圾） |
| 2 | Cookie 选择性删除 + 站点白名单 | `CookiesSQLite3DB` 处理器、`#SelCookies/#DelCookies`、`CookiesAllowedList` | ✅ | `DELETE FROM cookies WHERE NOT (host LIKE …)` + `--keep-cookies` |
| 3 | 进程守卫（清理前等/关浏览器） | 规则字段 `ActiveProcesses=msedge.exe` | ✅ | `needs_close` + tasklist 检测，浏览器运行即跳过 |
| 4 | Health Check（清理/隐私/速度/安全四项） | `HealthCheckPrivacy.*` 代码模型 | ⚠️ | `scan` 命令= 只读扫描汇总（垃圾+追踪器+痕迹）；"速度/安全"依赖驱动/软件更新引擎，不复刻 |
| 5 | Cookie/历史/缓存/会话/表单清理 | 149 个隐私相关规则节 | ✅ | Edge/Chrome/Firefox；表单信息默认关、**密码清理根本不实现**（安全减法） |
| 6 | 操作回退 | 仅 Registry Cleaner 有备份（`data\RegistryBackup\`） | ✅ 超集 | **一切变更可撤销**：文件移入 undo 目录、注册表先 reg export、SQLite 先整库备份，`undo <journal>` 一键还原 |
| 7 | 默认安全位 | `Default=True/False` 字段 | ✅ | 复刻其 Default 语义且更保守：`session/autofill/recyclebin/streams/traynotify` 默认关 |
| 8 | Registry Cleaner（17 类"无效项"） | `winreg` 规则组（部分混淆存储） | ⚠️ 降级 | 只做**痕迹清理**（MRU），不做"无效共享DLL/文件扩展"等启发式删除——风险收益比差（与本审计报告 §7 结论一致） |
| 9 | 计划任务清理 | Scheduler/CTaskScheduler 符号 | ⚠️ | 用 Windows 自带 schtasks 注册 OpenSweep CLI 定时扫描（README 给出命令） |
| 10 | Startup Manager | `startup_manager_events/stats` 表 + `service_start_types` 清单 | 🔁 组合替代 | ~~v2 计划~~ → 交由 **Autoruns**（微软官方最全）；OpenSweep `tools` 命令负责检测与指引（ECOSYSTEM.md §四） |
| 11 | Software Updater | `su_adapter/su_controller` + OPSWAT/OESIS 引擎 + `driver-updater.svc.avast.com` | ❌ | 依赖商业版本库；只读替代：`winget upgrade` |
| 12 | Driver Updater | CCleanerDU.dll 16.7MB + 驱动后端 + 回滚状态机 | ❌ | 商业驱动数据库 + 高系统风险，不属于隐私范畴 |
| 13 | Performance Optimizer（程序休眠） | `program_deactivator_module` + `performance_optimizer_*` 表 | ❌ | 需 LocalSystem 服务挂起进程，风险高收益低 |
| 14 | Software Remover/卸载器 | `generic_uninstaller`/`SoftwareRemoverModule` | ❌ | Windows"设置→应用"已覆盖；v2 可做只读清单 |
| 15 | Duplicate Finder | `duplicate_finder_*` 表（7.x 新增） | 🔁 组合替代 | ~~v2 计划~~ → 交由 **dupeGuru**（BSD-3） |
| 16 | Drive Wiper/文件粉碎 | `data_shredder@asw` + **`DeferredTrimScheduler`（TRIM 感知）** | 🔁 组合替代 | ~~v2 计划~~ → 交由 **Eraser**（GPL）；SSD 上 naive 覆写本就低效 |
| 17 | 监控/Smart Cleaning/PC Health | `pc_health.json` 13 触发器（事件日志游标）+ LocalSystem 服务 | ❌ | 常驻监控是隐私与攻击面负债，不复刻 |
| 18 | 云清理/账号同步 | `cloud_cleaning` token 流程、`id.avast.com` SSO | ❌ | 零网络原则 |
| 19 | IPM 广告/交叉推广/升窗 | `IpmParamSolver@sdk@avast_ad`、`ClientParameters.GoogleAdvertisingId`、LIS 静默安装包、NotifyLimit 骚扰频控 | ❌ | **刻意减法——这是本项目存在的理由之一** |
| 20 | 遥测（心跳/设备详情/统计上报） | `[Analytics] lastHeartbeat`、statistics.db、burger_client、`submit.sb.avast.com` | ❌ | **零网络：无任何出站调用（可用 netstat 验证）** |
| 21 | 多语言 UI | 60 个 lang dll | ⚠️ | CLI 英文输出；无 UI 框架依赖是零依赖设计的一部分 |

## 与原版的安全设计差异（OpenSweep 增强项）

| 维度 | CCleaner 7.13 | OpenSweep v1 |
|---|---|---|
| 默认模式 | GUI 勾选即执行 | **dry-run 默认**，`--yes` 显式执行 |
| 可撤销性 | 仅注册表清理有备份 | **全操作日志化**（文件/注册表/SQLite 三类均可 `undo`） |
| 凭据安全 | 提供"保存的密码"清理项（默认关） | **不实现**该能力 |
| 权限面 | LocalSystem 服务常驻 + 保活器 | 单进程、当前用户权限、无常驻 |
| 网络 | 多通道遥测/配置/广告 | **0 出站连接** |
| 规则可信来源 | 远程 Shepherd 可动态改行为 | 规则本地静态，无远程修改通道 |

## 本机实测（2026-10-31，v1.1 回归扫描，只读）

- 检出 **18,752 项 / 1.0 GB**：临时文件 5,078 项 249.3MB；Chrome 缓存 612.9MB（运行中→正确守卫跳过）；Edge 缓存 2,483 项 158.1MB；Jump Lists 549 项 4.1MB；Cookie 70 条；ComDlg32 MRU 147 值；崩溃转储 14.1MB；缩略图缓存 20.1MB；Recent 快捷方式 2 项；PSReadLine 历史 18.2KB。
- 关键数字经**独立交叉验证**（不经 OpenSweep 直查）：Cookies 70/70、Autofill 133/133、ComDlg32 147/147、Jump Lists 549/549 全部精确一致（详见 REVIEW.md）。
- 与 CCleaner 自身 `statistics.db` 记录的清理类别（rule_name 粒度）同构，验证了规则覆盖面的对应关系。
- v1.0 复查发现并修复 9 处缺陷（含 2 处严重：undo 区自污染、dry-run 写打开数据库），全过程见 [REVIEW.md](REVIEW.md)。
