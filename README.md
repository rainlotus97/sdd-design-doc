# sdd-design-doc

跨平台（**Windows / macOS / Linux**）的软件详细设计说明书（`.docx`）与 Story 技术设计稿（`.md`）生成 Skill。

基于真实代码仓进行事实核验，强制采用 **“全景主干 + 关键环节拆解”总分结构** 与 **“重 UML 类图与接口职责、不贴实现源码”** 的设计规范；支持声明式 JSON 生成高清 2x DPI 流程图 / 时序图 / UML 类图 / 分层架构图，并一键构建符合团队默认模板规范（或自定义 `.docx` 模板）的 Word 详细设计说明书。

---

## 核心特性

- **三大核心交付能力**：
  1. **完整模板文档生成（`--mode full`）**：生成含封面、目录（TOC）、`1 引言`、`2 设计概览`、`3 模块详细设计` 与 `附录 A` 的完整 Word 详细设计说明书。
  2. **核心模块可迁移文档生成（`--mode module`）**：专注 **`3 模块详细设计`**（不含多余的第 1、2 章与目录），每个大功能域收口为清晰可读的 `3.x` 章节，方便人工直接复制移植进主模板或交由其他迁移工具处理。
  3. **`.md` 需求规划 → 确认后再生成文档**：针对新需求或已有 `.md` 草稿，先整理结构化 `.md` 设计规划（标明 `[拟定]` 与 `[待确认]`），经确认无误后再转为 `--mode full` 或 `--mode module` `.docx`。
- **代码实证优先**：基于已有代码仓设计时核对真实模块、关键类、接口参数与异常边界，杜绝凭空编造。
- **高清图表流水线**：声明式 `diagrams.json` → SVG/HTML → 2x DPI PNG（`diagram_dsl.py` + `snap_diagrams.cjs`）。
- **开箱即用跨平台支持（Windows 免装 Playwright）**：
  - `snap_diagrams.cjs` 自动检测本地 / 全局 / `npx` 缓存中的 `playwright` 或 `playwright-core`；
  - 若未安装 Playwright，**自动回退为零依赖原生 Chrome/Edge DevTools Protocol (CDP)**，在 Windows 上直接调用系统自带的 **Microsoft Edge** 或 **Google Chrome** 完成高清截图；
  - 支持读取 Windows UTF-8 with BOM（`utf-8-sig`）JSON、正确处理 Windows `file:///C:/...` 路径 URL、确保 `.docx` ZIP 内部使用 POSIX `/` 路径以及 UTF-8 控制台输出。
- **清爽排版与严格交付校验**：内置 `api_card` 卡片清晰分层展示英文接口路径/字段与网络异常兜底，告别长串代码标识符在窄表格里拥挤折行；默认左对齐、长签名自动独立成行、跨页表头 `keepNext` 与短表防拆；`build_from_spec.py --strict-delivery` 自动校验模式结构、零 `.md` 引用与端点集中归档。

---

## 快速安装

### 方式一：通过 `skills` CLI 一键安装（推荐）

```bash
npx skills add rainlotus97/sdd-design-doc
```

### 方式二：手动克隆到 Agent Skill 目录

根据你使用的 AI 编程工具，将仓库克隆到对应 `skills/sdd-design-doc` 目录（任选其一）：

**Windows (PowerShell)**：
```powershell
# Antigravity / 通用 Agent Skills
git clone https://github.com/rainlotus97/sdd-design-doc.git "$env:USERPROFILE\.agents\skills\sdd-design-doc"

# 若使用 Claude Code / Codex，按需放到对应目录：
# git clone https://github.com/rainlotus97/sdd-design-doc.git "$env:USERPROFILE\.claude\skills\sdd-design-doc"
# git clone https://github.com/rainlotus97/sdd-design-doc.git "$env:USERPROFILE\.codex\skills\sdd-design-doc"
```

**macOS / Linux (Bash/Zsh)**：
```bash
git clone https://github.com/rainlotus97/sdd-design-doc.git ~/.agents/skills/sdd-design-doc
```

---

## 环境要求与一键自检

- **Python 3.8+**（标准库即可，无需额外 `pip install`）
- **Node.js 16+**
- **浏览器（二选一）**：
  - 系统已安装 **Microsoft Edge**（Windows 10/11 自带）或 **Google Chrome / Chromium**（零 npm 依赖即可直接渲染）；
  - 或已安装 `playwright` / `playwright-core`（本地、`node_modules`、全局或 `npx` 缓存均可自动识别）。

运行内置自检脚本验证当前环境并执行端到端生成测试：

**Windows (PowerShell)**：
```powershell
cd "$env:USERPROFILE\.agents\skills\sdd-design-doc"
python scripts\check_env.py --smoke-test
```

**macOS / Linux (Bash/Zsh)**：
```bash
cd ~/.agents/skills/sdd-design-doc
python3 scripts/check_env.py --smoke-test
```

若一切正常，将输出 `[AUDIT] PASSED` 与 `[SMOKE] PASSED`。

---

## 独立命令行用法

如果你不通过 AI Agent，也可以直接调用脚本生成图表与 `.docx`：

### 1. 生成图表 HTML 并渲染为 2x PNG

```bash
python scripts/diagram_dsl.py diagrams.json ./diagrams_out
node scripts/snap_diagrams.cjs ./diagrams_out
```

> 可选参数：
> - `node scripts/snap_diagrams.cjs --check`：检查当前检测到的浏览器和渲染引擎（`playwright` / `cdp`）。
> - `node scripts/snap_diagrams.cjs --engine=cdp ./diagrams_out`：强制使用原生 CDP 模式。
> - 环境变量 `CHROME_PATH` / `EDGE_PATH`：手动指定浏览器可执行文件路径。

### 2. 构建并校验 `.docx`

```bash
# 生成核心模块可迁移文档（第 3 章）
python scripts/build_from_spec.py \
  --spec spec_module.json \
  --diagrams-dir ./diagrams_out \
  --mode module \
  --strict-delivery \
  --out ./module_output.docx

# 生成完整模板文档（含封面、TOC、1~3 章及附录 A）
python scripts/build_from_spec.py \
  --spec spec_part1.json spec_part2.json \
  --diagrams-dir ./diagrams_out \
  --mode full \
  --strict-delivery \
  --out ./full_output.docx
```

若需要使用自定义 Word 模板覆盖内置样式，传入 `--template /path/to/custom_template.docx`。

---

## 目录结构

```text
sdd-design-doc/
├── SKILL.md                          # Agent Skill 主规范文档
├── README.md                         # 安装、跨平台说明与使用指南
├── LICENSE                           # MIT 许可证
├── references/
│   ├── story_md_template.md          # Markdown Story 设计稿章节规范
│   ├── docx_spec_schema.md           # Word 说明书 JSON 规格与章节骨架
│   └── diagram_json_guide.md         # 4 类图表声明式 JSON 语法指南
├── resources/
│   └── default_sdd_template/         # 默认 SDD Word OOXML 样式模板
└── scripts/
    ├── diagram_dsl.py                # JSON -> SVG/HTML 图表生成器
    ├── snap_diagrams.cjs             # HTML -> 2x PNG 截图器（Playwright / 原生 CDP）
    ├── docx_builder.py               # OOXML .docx 打包与样式构建引擎
    ├── build_from_spec.py            # JSON 规格组装 + 交付审计脚本
    └── check_env.py                  # 跨平台环境检测与端到端冒烟测试
```
