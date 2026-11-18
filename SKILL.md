---
name: sdd-design-doc
description: >-
  Generate standardized Software Detailed Design Specifications (.docx) and Story technical design docs (.md) grounded in real codebases.
  Enforces a structured "overview + flow/sequence-driven detailed design + UML class/interface design (functions and responsibilities only, no implementation code)" methodology,
  renders high-DPI SVG diagrams, and builds formatted Word documents from the team's default SDD template unless a custom .docx template is specified.
  Trigger phrases: 详细设计文档, 软件详细设计, 生成docx设计文档, Story设计文档, 按模板生成文档, SDD.
---

# 软件详细设计说明书与 Story 规划生成规范

本 Skill 提供 **三大核心文档生成能力**，用于基于真实代码仓、产品需求或已有 `.md` 草稿，输出可直接研发评审或移植进主模板的设计产物：
1. **能力一 · 完整模板文档生成（`--mode full`）**：生成符合固定模板规范（封面信息表、自动目录、`1 引言`、`2 设计概览`、`3 模块详细设计`、`附录 A`）的正式独立版 Word 详细设计说明书（`.docx`）。
2. **能力二 · 核心模块可迁移文档生成（`--mode module`）**：专注 **`3 模块详细设计`**（不含多余的第 1、2 章与目录），每个核心功能域按 `3.1`、`3.2` 清爽展开，供人工直接复制粘贴进主设计模板，或配合产出的 `spec*.json` / `diagrams.json` / `.md` 交由其他迁移工具自动提取装配。
3. **能力三 · `.md` 需求规划 → 确认后再生成文档（`plan-md -> confirm -> docx`）**：面向未落地需求、口头方案或已有 `.md` 文档，先整理生成结构清晰的 Markdown 设计规划稿（标明 `[拟定]` 与 `[待确认]` 事项），**经用户逐项审阅确认无误后**，再一键转换为完整模板文档（`--mode full`）或模块迁移文档（`--mode module`）。

---

## 一、核心原则（必须严格遵守）

1. **三类输入统一准则（实证核验 / 需求初设 / `.md` 转 `.docx`）**：
   - **已有代码仓逆向/整理**：用检索与读取工具核对真实存在的模块、核心类名、对外接口与关键规则；**禁止把内部布局像素/权重常量、私有临时变量、历史废弃开关或无关跨模块枝节写入设计正文与表格**。
   - **需求/初步方案设计或 `.md` 转 Story/Word**：若基于需求或已有 `.md` 文档设计，可先输出/整理为结构清晰的 `.md` Story 设计稿，再转成 `.docx`；尚未落地编码的新接口/新类必须显式标注 `[拟定]`；转 `.docx` 时将 `.md` 内容完整内化，不得残留“详见某某.md”。
2. **模板、版式与移植结构策略**：
   - 生成 `.docx` 时，**默认使用内置样式模板** [resources/default_sdd_template](./resources/default_sdd_template)（`#2E74B5` 蓝头表格、信息卡、`微软雅黑` 与 `Consolas` 字体体系），仅当用户明确指定其他 `.docx` 模板路径时传 `--template`。
   - **输出结构模式（按用户主文档结构选择）**：
     - **第 3 章可移植模块版（多模块分拆进主模板时的推荐默认）**：用户主文档已有 `1 引言` 与 `2 设计概览` 时，分文档仅输出极简顶部提示 + **`3 模块详细设计`**（例如一个大功能域收口为一个完整的 `3.1 <模块名称>` 含 `3.1.1~3.1.6`，不再将单功能拆碎成五六个微子章），便于直接复制移植进主模板第 3 章。
     - **完整独立说明书版**：需独立成册交付时，包含封面、目录、`1 引言`、`2 设计概览`、`3 模块详细设计` 与 `附录 A`。
   - **正式版版式与可读性防缺陷铁律**：
     - **杜绝“代码标识符轰炸”**：正文、流程节点、时序消息与常规表格一律使用**简洁流畅的工程中文**，不把长全大写常量（如 `HOME_LEFT_ROW_WEIGHT=2172`）或大量私有类名硬塞进窄表列导致换行撕裂；核心类名与关键对外方法集中在 **UML 类图** 与 `3.x.3` 简明职责列表展示。
     - **外部接口卡片化展示（重点突出不拥挤）**：面对无法避免的英文 HTTP 路径、参数、返回值或 MQTT 主题，优先使用 `api_card` 块——方法/路径高亮置顶，请求、核心字段（一字段一行、英文加粗配合中文含义）、界面展示与网络异常兜底分层排布，绝不把整段 JSON 塞进窄表格单元。
     - **左对齐与表格防跨页重绘**：全篇统一左对齐（`w:jc="left"`，严禁 `both`）；表格首行携带 `<w:keepNext w:val="1"/>`（`<= 3` 行短表整表绑定），并按 ECMA-376 先 `<w:cantSplit w:val="1"/>` 后 `<w:tblHeader w:val="1"/>` 避免跨页双表头。
   - 正式交付物必须彻底清理 `0 使用说明`、`填写约定`、`填写要求`、`常见错误` 及所有 `【】` 占位。
3. **内容聚焦双铁律（主功能 + 正常与异常闭环）**：
   - **详细设计**：聚焦当前模块真正的核心业务主功能，严格采用 **“全景主干 + 关键环节拆解”总分结构**；**将网络超时、断连重试、认证失效（401）、空值/越界降级等常见异常处理直接融入主流程图、时序图分支与接口兜底说明中**，删掉与主功能无关的扩展臆想或边缘噪音。
   - **代码设计**：**重 UML 类图与关键能力边界**，按职责分组绘制清晰的类图；**不贴函数内部实现体或伪代码**，仅说明核心类/关键接口 **“输入什么、做什么事、返回/呈现什么、失败怎么兜底”**。
4. **交付自足性、外部接口展开与 IP 集中收敛**：
   - **严禁在 `.docx` 中把未交付的 `.md` 作为基线出处**（封面/正文均禁止残留 `*.md` 文件名）。
   - **外部接口与 MQTT 必展开**：凡对接外部 HTTP/REST、WebSocket、UDP、MQTT，必须通过 `api_card` 或清晰契约写明触发时机、路径与请求参数、核心返回/载荷字段、界面消费效果与网络异常兜底。
   - **正文去 IP 化、端点集中放置**：具体 IP（`192.168.*` / `10.*` 等）不得散落在正文 prose 与图表中，统一以配置常量符号指代，并集中收进 **联调端点配置表**（独立版放在文末 `附录 A`，第 3 章可移植版放在 `3.x` 末尾的配置/端点小节）。

---

## 二、执行工作流（含三大能力路由）

### 第 1 步：确认输入形态、目标模式与是否先走 `.md` 规划确认
- **确认目标交付模式**：
  - ① **`--mode full`（完整模板文档）**：需要独立成册、含封面/目录/`1 引言`/`2 设计概览`/`3 模块详细设计`/`附录 A` 时选用；
  - ② **`--mode module`（核心模块可迁移文档）**：需要合入已有主模板的 `3 模块详细设计` 章节、或供其他工具解析迁移时选用（推荐：无多余 1~2 章与独立 TOC，直接复制即可）；
  - ③ **仅 `.md` 需求规划稿**。
- **是否启用“先 `.md` 规划确认，再生成 `.docx`”闭环**：
  - 若输入是**新需求、初步方案或待梳理的 `.md` 文档**：**必须先执行阶段 A → 输出规范的 `.md` 设计规划稿**（按 [references/story_md_template.md](./references/story_md_template.md) 写出规划范围、主流程与异常分支、拟定类图 `[拟定]`、接口字段及 `[待确认]` 清单），**暂停并向用户提交审阅**；**收到用户确认无误（或按反馈修订 `.md` 完结）后**，再进入第 3~5 步将确认后的 `.md` 转化为 `--mode full` 或 `--mode module` 的正式 `.docx`；
  - 若输入是**已有稳定代码仓**且用户明确直接产出 `.docx`：可直接核验源码后按指定模式生成 `.docx`。
- **模板与模块粒度**：未指定自定义模板时一律使用内置默认模板。**一个完整业务功能域对应一个大模块（如 `3.1 <模块名称>`）**，避免将单个功能过度拆成大量微子章增加迁移成本。

### 第 2 步：梳理核心功能与关键输入
1. 阅读用户提供的需求/Story/`.md` 文档或代码仓目录。
2. 聚焦**主要功能链路与常见异常闭环**收集关键信息：
   - 业务入口、交互状态、前后端/进程/MQTT 数据流；
   - **外部接口与协议要素**：方法、路径/主题、请求参数/Header、核心返回字段及界面消费效果；
   - **正常与异常闭环规则**：网络超时/断连重试、401 会话过期、空数据/非法值兜底显示，并把它们纳入主流程说明；
   - **核心类分工**：只抓模块骨架类与关键对外能力，跳过细碎辅助函数和 UI 排版像素权重常量。

### 第 3 步：生成文本内容（按目标产物选择）

- **若输出 `.md` Story 设计稿**：
  - 严格按 [references/story_md_template.md](./references/story_md_template.md) 编写：`1. 概述（专注核心能力）` → `2. 详细设计（2.1 全景主干含网络/异常闭环 + 2.2~2.n 关键环节）` → `3. 代码设计与接口契约（分组类图 + 核心类职责 + 清晰的接口与异常兜底表，不贴函数实现）`。

- **若输出 `.docx` 详细设计内容**：
  - 严格遵循 [references/docx_spec_schema.md](./references/docx_spec_schema.md) 的 JSON 规范编写 spec 文件（按模式选择“第 3 章可移植版”或“完整版”）。
  - 注意：`3.x.1.2` 与 `3.x.3` 坚持 **人话解释 + 图表主干/类图骨架**，严禁代码标识符刷屏；`3.x.4.1` 使用 `api_card` 清晰分点展示英文接口与核心返回字段及异常兜底；若含 TOC，每个 `level <= 3` 标题须填写单调非降 `estPage`。

### 第 4 步：渲染图表并强制视觉自检（`.docx` 必需步骤）
参考 [references/diagram_json_guide.md](./references/diagram_json_guide.md) 编写图表定义文件 `diagrams.json`（涵盖上下文/分层图、主干与分支流程图、时序图、按职责分组的 UML 类图）。

执行渲染前，请按当前 Skill 实际所在目录解析 `SKILL_DIR`（常见路径：`~/.agents/skills/sdd-design-doc`、`~/.gemini/config/skills/sdd-design-doc`、`~/.claude/skills/sdd-design-doc`、`~/.codex/skills/sdd-design-doc` 或项目内 `.agents/skills/sdd-design-doc`）。`snap_diagrams.cjs` 会优先使用 `playwright` / `playwright-core`，若未安装则自动通过内置零依赖 CDP 回退调用系统 **Microsoft Edge** 或 **Google Chrome**。

**macOS / Linux (Bash/Zsh)**：
```bash
# macOS 下若默认 python3 存在 pyexpat 异常，优先使用系统 /usr/bin/python3
PYTHON_BIN=$(/usr/bin/python3 -c "import xml.etree.ElementTree" 2>/dev/null && echo /usr/bin/python3 || echo python3)
SKILL_DIR=$(for d in "$PWD/.agents/skills/sdd-design-doc" "$HOME/.agents/skills/sdd-design-doc" "$HOME/.gemini/config/skills/sdd-design-doc" "$HOME/.claude/skills/sdd-design-doc" "$HOME/.codex/skills/sdd-design-doc"; do [ -d "$d" ] && echo "$d" && break; done)

$PYTHON_BIN "$SKILL_DIR/scripts/diagram_dsl.py" diagrams.json ./diagrams_out
node "$SKILL_DIR/scripts/snap_diagrams.cjs" ./diagrams_out
```

**Windows (PowerShell)**：
```powershell
$PythonBin = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { "py" }
$PyArgs = if ($PythonBin -eq "py") { @("-3") } else { @() }
$SkillDir = @(
  "$PWD\.agents\skills\sdd-design-doc",
  "$env:USERPROFILE\.agents\skills\sdd-design-doc",
  "$env:USERPROFILE\.gemini\config\skills\sdd-design-doc",
  "$env:USERPROFILE\.claude\skills\sdd-design-doc",
  "$env:USERPROFILE\.codex\skills\sdd-design-doc"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

& $PythonBin @PyArgs "$SkillDir\scripts\diagram_dsl.py" diagrams.json .\diagrams_out
node "$SkillDir\scripts\snap_diagrams.cjs" .\diagrams_out
```

**强制视觉验收**：使用 `read_file` 逐张查看 `./diagrams_out/*.png`，确认无文字截断、无边框溢出、无箭头穿过文本；若有瑕疵，调整 `diagrams.json` 坐标/尺寸后重新渲染直到全部清晰无误。

### 第 5 步：打包生成 `.docx` 并按模式强制审计交付
根据第 1 步选定的目标传入 `--mode full`（完整模板文档）或 `--mode module`（核心模块迁移文档），推荐附加 `--strict-delivery` 开启完整/模块模式约束、零 `.md` 引用、正文零裸 IP、左对齐与表头 `keepNext` 强校验：

**macOS / Linux (Bash/Zsh)**：
```bash
$PYTHON_BIN "$SKILL_DIR/scripts/build_from_spec.py" \
  --spec spec_part1.json [spec_part2.json ...] \
  --diagrams-dir ./diagrams_out \
  [--template /path/to/custom_template.docx] \
  --mode module \
  --strict-delivery \
  --out "/path/to/output.docx"
```

**Windows (PowerShell)**：
```powershell
& $PythonBin @PyArgs "$SkillDir\scripts\build_from_spec.py" `
  --spec spec_part1.json `
  --diagrams-dir .\diagrams_out `
  --mode module `
  --strict-delivery `
  --out ".\output.docx"
```

> 若同时需要供其他工具/脚本二次迁移，可保留产出目录下的 `spec*.json`、`diagrams.json` 与经确认的规划 `.md` 作为结构化中间产物。

版式抽检：在 macOS 上可用 `qlmanage -t -s 1400 -o ./preview "/path/to/output.docx"` 生成首页缩略图并用 `read_file` 确认封面与目录版式无异常；在 Windows / Linux 上可直接用 Word / WPS 打开核验，或通过 LibreOffice（`soffice --headless --convert-to pdf output.docx`）转 PDF 后渲染预览。**注意**：若用户已在 WPS / Word 中打开同名 `.docx`，覆盖重建后务必提醒关闭旧标签页（不要保存覆盖）再重新打开，否则客户端可能继续展示内存缓存的旧版。最终向用户报告时，仅陈述本次实际读取或脚本核验过的文件路径、图表数量、模块清单与校验结果。
