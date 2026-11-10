# 开源发布清单（RELEASE CHECKLIST）

目标仓库根目录 = 本 `opensweep/` 文件夹。发布前逐项勾选。

## ✅ 应包含（仓库内容）

- [x] `opensweep.py`（引擎+CLI）｜ `server.py`（本地 Web 服务）｜ `gui.py`（桌面 GUI）
- [x] `rules-windows.json`（45 条，Windows）｜ `rules-darwin.json`（11 条，macOS）
- [x] `harden.json`（15 项 Windows 隐私设置加固）
- [x] `webui/`（账本设计前端：index/styles/app）
- [x] `tests/`（test_suite.py 跨平台安全套件 + test_saturation.py 对抗饱和套件 + server_selftest.py）
- [x] `README.md`（双语）｜ `LICENSE`（MIT + 洁室声明）｜ `.gitignore` ｜ `.github/workflows/ci.yml`
- [x] 文档：`FEATURES.md` / `BENCHMARK.md` / `REVIEW.md` / `ECOSYSTEM.md` / `design-demos/`（含 direction-approved.md，体现流程可复用）

## ⛔ 绝不包含（排除项）

- [ ] `cc_re/` 整个目录 —— CCleaner 逆向证据语料（PE 样本、字符串转储、内存转储分析）是研究语料，不进公开仓库
- [ ] 任何商业产品的二进制、样本、规则文件原文（洁室红线）
- [ ] `cc_re/out/` 下的日志、URL 转储、注册表全表等本机隐私数据
- [ ] `huashu-design` 技能包本体（第三方作品，尊重其许可；文档中仅以链接引用其思想）
- [ ] 真实 journal（含本机文件路径）—— `.gitignore` 已含 sandbox/ 与 *.log

## 📋 发布步骤

1. `git init` 于 opensweep/ → 首次提交前 `git status` 逐文件核对上述排除项
2. 推送 GitHub → 确认 Actions 双平台（windows/macos × py3.10/3.12）全绿
3. 建立 v3.2.0 tag + Release Notes（引用 BENCHMARK 的诚实评分与安全测试矩阵）
4. README 顶部加 CI badge：`![ci](https://github.com/lm7644/opensweep/actions/workflows/ci.yml/badge.svg)`（v3.2 已加）
5. 首个外部 issue 模板建议：报告清理误伤时附 journal（脱敏后）

## 🧪 双平台验证状态（诚实声明）

- Windows 10/11 x64：本机全量实测（安全套件 41/41、饱和套件 41/41、server 自检 10/10、GUI、Web UI 浏览器实测、真机演练 5/5）
- macOS：代码路径完成（平台守卫 + darwin 规则集 + 跨平台套件），**验证依赖 CI 的 macos-latest 矩阵**——首次推送后务必查看 Actions 结果；真机 Safari/Edge 路径以 CI 为准
- Linux：可运行引擎核心（文件/SQLite 规则），无内置规则集，欢迎社区贡献 `rules-linux.json`

## 🔐 发布后维护约定

- 规则改动只进 rules-*.json（schema 见 README 扩展节），不碰引擎
- 每个 PR 必须通过沙箱套件；涉及清理语义的 PR 需附"保护文件清单不变"的测试输出
- 品味/行为反馈用 journal+issue 记录，拒绝遥测
