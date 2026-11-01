# 开源生态地图：OpenSweep vs 现有项目（2026-10-31 调查）

## 一、生态位澄清：三者不是同类工具

| 工具 | 生态位 | 与 OpenSweep 关系 |
|---|---|---|
| **BleachBit** | 文件/痕迹清理器（缓存、Cookie、历史、粉碎、空闲空间擦除） | **直接同类**（OpenSweep 的竞品） |
| **Windows 内置**（存储感知 / 磁盘清理 cleanmgr / 隐私设置面板） | 系统自带：垃圾清理窄覆盖 + 隐私设置开关 | 部分重叠（垃圾清理），不可扩展、无审计 |
| **Autoruns**（Sysinternals） | 自启动点全量枚举与管控（服务/驱动/计划任务/外壳扩展） | 相邻功能带 = CCleaner 的"启动项管理"，**不是清理器** |

结论：BleachBit 才是 OpenSweep 的同类；Windows 内置是弱竞品；Autoruns 属于另一个工具类。

## 二、GitHub 全景（按 OpenSweep/CCleaner 功能逐项映射）

| 功能带 | 项目 | 许可证 | 技术栈/状态 | 对 OpenSweep 的意义 |
|---|---|---|---|---|
| **痕迹清理** | [BleachBit](https://github.com/bleachbit/bleachbit) (~7.3k★) | GPL-3.0（含 CleanerML 规则定义） | Python/GTK，活跃 | **最强借鉴源**：CleanerML 声明式规则语法与 OpenSweep 的 JSON 规则化构想几乎同构 |
| 隐私设置加固 | [privacy.sexy](https://github.com/undergroundwires/privacy.sexy)（数千★） | 开源 | 生成 PowerShell 脚本，Win/macOS/Linux | 补 OpenSweep 不做的"设置项"维度（遥测开关等），思路可纳为引用脚本 |
| 隐私设置加固 | [Sophia Script](https://github.com/farag2/Sophia-Script-for-Windows) (~9.8k★) | **MIT** | PowerShell 模块，活跃 | 同上，粒度更细，MIT 可自由内嵌 |
| 综合调优 | [WinUtil](https://github.com/ChrisTitusTech/winutil) | **MIT** | PowerShell+GUI，活跃（2026 仍在更新） | 含启动项管理+tweaks，一站式参考 |
| 启动项管理 | [Autoruns](https://learn.microsoft.com/sysinternals/downloads/autoruns) | 闭源免费（微软官方） | v14.x | 枚举完整度天花板；**不值得自研替代** |
| 启动项管理 | AutoRunManager 等小型开源项目 | 开源 | 简单注册表启动管理 | 仅作参考 |
| 卸载器 | [Bulk-Crap-Uninstaller](https://github.com/BCUninstaller/Bulk-Crap-Uninstaller) | **Apache-2.0** | C#，寻找维护者中 | 现成方案，OpenSweep 无需做卸载器 |
| 重复文件 | [dupeGuru](https://github.com/arsenetar/dupeguru) | **BSD-3** | Python，维护较轻 | OpenSweep v2 砍掉该项的直接理由 |
| 文件粉碎 | [Eraser](https://github.com/gtrant/eraser)（eraser.heidi.ie） | GPL | Windows 经典粉碎器 | OpenSweep 粉碎器路线图的现成替代 |
| 软件更新 | winget（微软官方，MIT）+ [UniGetUI](https://github.com/marticliment/UniGetUI) | 开源 | 活跃 | Software Updater 功能的开源等价物 |
| 发现渠道 | awesome-privacy 等清单 | — | — | 后续找新工具的入口 |

## 三、许可证合规边界

**不受版权保护（随便借鉴）**：思路、算法、行为语义、**痕迹位置知识**（哪些注册表键/文件路径是隐私痕迹——公开取证事实）。OpenSweep 从第一天就是按这个原则做的。

**受版权约束（复制代码/规则文本时）**：
- **MIT / Apache-2.0 / BSD**（Sophia、WinUtil、BCU、dupeGuru、winget）：可自由复制进闭源项目，保留版权声明与许可文本即可
- **GPL-3.0**（BleachBit、Eraser）：复制其**代码或规则定义**会使整个衍生作品被传染为 GPL——仅在**分发**时触发义务
- **两种场景**：
  - 现状（私有自用，不分发）：连 GPL 代码都可以自由复用，无任何义务
  - 若将来开源发布 OpenSweep：抄 GPL 代码 ⇒ OpenSweep 必须以 GPL 发布；只抄 MIT/Apache 代码 ⇒ 保留声明即可保持自由
- 特别注意：BleachBit 的 CleanerML 规则文件属于其 GPL 范围，**不要整包复制规则文本**；按公开取证事实自行撰写（OpenSweep 现状即合规）

## 四、逐功能决策矩阵

| OpenSweep 功能项 | 决策 | 理由 |
|---|---|---|
| 核心痕迹清理（41 规则引擎） | **保留自研** | 已建成、已审计（v1.1）、零网络+全 undo 是真实差异化；维护成本≈0 |
| 规则外置 JSON 化 | **借鉴 BleachBit/CleanerML 思路**（非代码） | 声明式规则是正确方向，思路不受版权约束 |
| Windows 隐私设置加固 | **用 Sophia Script / privacy.sexy** | 成熟、MIT、OpenSweep 定位不含此项 |
| 启动项管理 | **用 Autoruns** | 微软官方最全，自研无价值 |
| 卸载器 | **用 BCU / 系统自带** | Apache-2.0 现成方案 |
| 重复文件查找 | **用 dupeGuru**，OpenSweep 砍掉 v2 计划 | BSD-3 现成 |
| 文件粉碎 | **用 Eraser**（或维持现状） | GPL 现成；SSD 上价值本就有限 |
| 软件更新 | **用 winget/UniGetUI** | 微软官方+开源 GUI |
| Driver Updater | 维持不复刻 | 商业驱动包生态（SDI 属例外但体量大） |

## 五、核心问题的最终回答

**"有必要自己开发吗，还是借鉴现有项目？"——正确答案不是二选一，而是组合**：

- 清理器：你**已经有了**（OpenSweep，成本已沉没、维护成本≈0）→ 保留；或日常直接用 BleachBit，二者取一
- 其余全部功能带：均有成熟开源/免费方案，**零自研必要**
- 借鉴姿势：思路/位置知识随便抄；代码按许可证（MIT 抄着方便，GPL 私有用无妨、开源发布要传染）
- OpenSweep 的剩余价值：**一份属于你、可审计、可随心扩展的个人基线**——建议投入方向是把规则库 JSON 外置化（借鉴 CleanerML 思路），而非开发新功能

一句话：**开发冲动应该停止，组合与借鉴应该开始。**
