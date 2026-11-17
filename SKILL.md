---
name: sdd-design-doc
description: >-
  Generate standardized Software Detailed Design Specifications (.docx) and Story technical design docs (.md) grounded in real codebases.
  Enforces a structured "overview + flow/sequence-driven detailed design + UML class/interface design (functions and responsibilities only, no implementation code)" methodology,
  renders high-DPI SVG diagrams, and builds formatted Word documents from the team's default SDD template unless a custom .docx template is specified.
  Trigger phrases: 详细设计文档, 软件详细设计, 生成docx设计文档, Story设计文档, 按模板生成文档, SDD.
---

# 软件详细设计说明书与 Story 设计稿生成规范

本 Skill 用于基于真实代码仓与需求/Story 输入，生成结构统一、图表清晰、可直接用于研发评审的 **Markdown Story 设计文档（`.md`）** 和/或 **正式版 Word 软件详细设计说明书（`.docx`）**。

---

## 一、核心原则（必须严格遵守）

1. **结合代码实证，禁止编造**：
   - 凡涉及已有代码仓的项目，必须先用 `rg`/`find`/`read_file` 核对真实存在的模块路径、类名、接口、方法签名、常量/默认值、枚举/错误码、配置文件与日志字段。
   - 若为先设计后编码的新模块，必须显式标注“拟定接口/待定标定值”，不得将推测写成已存在代码。
2. **模板与排版默认策略**：
   - 生成 `.docx` 时，**默认使用内置样式模板** [resources/default_sdd_template](./resources/default_sdd_template)（提取自固定 SDD 模板规范：封面信息表、自动目录、`1 引言`、`2 设计概览`、`3 模块详细设计 3.0~3.x.6`、`#2E74B5` 蓝头表格、`微软雅黑` 与 `Consolas` 字体体系）。
   - **仅当用户在输入中明确指定了其他 `.docx` 模板路径时**，才通过 `--template <custom.docx>` 动态覆盖；若未指定，一律使用默认模板。
   - **正式版版式防缺陷铁律**：
     - 全文正文、表格单元格与代码块统一使用**左对齐**（`w:jc="left"`），严禁两端对齐（`both`）导致中英混排换行时单词/汉字间距被强制拉宽；
     - 较长的 `3.x.3.k Class.method(...)` 前置签名由构建器自动拆分为独立深蓝加粗 `keepNext` 标题行，不与后续正文挤在同一段；
     - 所有跨页表格首行必须携带 `<w:keepNext w:val="1"/>`（`<= 3` 行短表对非末行全部绑定），且按 ECMA-376 顺序先 `<w:cantSplit w:val="1"/>` 后 `<w:tblHeader w:val="1"/>`，确保跨页时换到下一页绘制完整表头，绝不在上页底部遗留孤立表头造成“重复双表头”。
   - 正式交付物必须彻底清理 `0 使用说明`、`填写约定`、`填写要求`、`常见错误` 及所有 `【】` 占位。
3. **内容结构双铁律（来自 EMS HMI Story 实践范式）**：
   - **详细设计**：严格采用 **“全景主干 + 关键环节拆解”的总分结构**，禁止把全流程堆在一段文字或一张巨图里。重点围绕 **流程图（主干链路、决策分支）** 与 **时序图（跨模块异步交互、超时/断链容灾闭环）** 展开，文字只做精炼引导与边界说明。
   - **代码设计**：**重 UML 类图与接口契约设计**，按模块职责划分为多组独立类图；**不写函数内部具体实现代码或流水账伪代码**，仅列出核心 `class`/`interface`/`event` 的关键属性与**重要对外函数签名**，并用简洁条目概括每个类与重要函数 **“做什么事情（能力边界与协作关系）”**。
4. **交付自足性、外部接口展开与 IP 集中进附录**：
   - **严禁引用未随同交付的 `.md` 文档名**：当 `.docx` 作为独立交付件对外移交时，封面“设计输入”、`1.3 设计输入与基线` 及正文一律禁止将工程内部 `docs/*.md` / `*.md` 文件名作为基线出处；须替换为对应的真实源码模块、DTO 契约或协议规范名，并将 `.md` 中的接口字段、边界阈值与排查结论直接内嵌进 `.docx`。
   - **外部接口、请求返回值与 MQTT 必须在正文展开**：凡对接外部 REST HTTP、WebSocket、UDP、MQTT 或跨进程边界的模块，须在 `3.x.4.1 接口契约` 展开说明请求方法/路径、关键 Header、请求参数/Body、返回结构体字段、状态与伪 200 判定规则，以及 MQTT Topic、订阅方式（常驻/按需）、排队策略（`LATEST_ONLY`/`FULL_QUEUE`）与原始载荷字段（禁止只给一句话概述）。
   - **正文去 IP 化 + 附录 A 统一汇编**：具体环境 IP / Host / 端口原则上不散落在正文叙述与流程图标签中，正文中统一以配置常量符号名指代（如 `IntegrationEndpoints.*`、`LOOPBACK_HOST`）；全部外部接口清单、MQTT 全量字段与联调环境 IP/端口对照表统一汇编到文档末尾的 **`附录 A（外部接口契约、MQTT 主题与联调端点一览）`**。

---

## 二、执行工作流

### 第 1 步：确认输出形态与范围
- **输出形态**：确认用户需要 ① Markdown Story 设计稿（`.md`）、② Word 详细设计说明书（`.docx`），还是 ③ 先沉淀 `.md` 再生成 `.docx`。
- **模板确认**：若用户未指定自定义模板，使用默认内置模板；若指定了自定义 `.docx`，后续传 `--template <路径>`。
- **模块切分**：
  - 小范围单 Story（≤5 个模块）：可一次按序构建完整设计；
  - 大项目多模块（>5 个模块，如整套系统说明书）：建议先确定 `第 1 章 + 第 2 章 + 3.0 模块清单`，再按 2~4 个模块分批编写 JSON 规格文件，最后合并传给 `build_from_spec.py` 生成同一份 `.docx`，避免细节缩水。

### 第 2 步：调研代码仓与设计输入
1. 阅读用户提供的 Story/需求/接口文档（若有）。
2. 并行检索代码仓，收集并核实：
   - 工程模块划分（`HAP`/`HAR`/子包与目录结构）与依赖关系；
   - 关键配置文件（XML/JSON/YAML/构建脚本）及其校验与映射规则；
   - 核心类的**公开函数签名**、状态枚举、定时器/超时参数、持久化键、事件类型、错误码、告警码与日志 TAG；
   - UI 消费层如何订阅与处理异常状态（如无效值展示、防抖、生命周期注销）。

### 第 3 步：生成文本内容（按目标产物选择）

- **若输出 `.md` Story 设计稿**：
  - 严格按 [references/story_md_template.md](./references/story_md_template.md) 编写：`1. 概述` → `2. 详细设计（2.1 全景主干流程图 + 2.2~2.n 关键环节拆解流程图/时序图）` → `3. 代码设计（3.1~3.n 分组 Mermaid classDiagram + 重要函数职责清单，不贴函数实现）`。

- **若输出 `.docx` 详细设计说明书**：
  - 严格遵循 [references/docx_spec_schema.md](./references/docx_spec_schema.md) 的章节与 JSON 结构编写 spec 文件（`doc_title`、`table`、`toc`、第 1~3 章、各 `3.x.1 ~ 3.x.6` 小节及 `附录 A`）。
  - 注意：`3.x.1.2` 与 `3.x.3` 必须体现“总分结构 + 流程/时序/类图优先 + 只列重要函数做什么事情”，不要退化成大段纯文字或代码粘贴；`3.x.4.1` 须展开外部 HTTP/MQTT/UDP 请求与返回字段；每个 `level <= 3` 的标题（含 `附录 A` 及其子节）均须填写单调非降的 `estPage`，避免目录出现默认值 `1`。

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

### 第 5 步：打包生成 `.docx` 并验证交付
运行构建脚本（内置 ZIP 完整性、XML 良构、图片数匹配、模板占位符残留、左对齐/`keepNext` 版式及交付自足性检查；正式对外交付建议附加 `--strict-delivery` 开启零 `.md` 引用与附录前零裸 IP 强校验）：

**macOS / Linux (Bash/Zsh)**：
```bash
$PYTHON_BIN "$SKILL_DIR/scripts/build_from_spec.py" \
  --spec spec_part1.json [spec_part2.json ...] \
  --diagrams-dir ./diagrams_out \
  [--template /path/to/custom_template.docx] \
  --strict-delivery \
  --out "/path/to/output.docx"
```

**Windows (PowerShell)**：
```powershell
& $PythonBin @PyArgs "$SkillDir\scripts\build_from_spec.py" `
  --spec spec_part1.json `
  --diagrams-dir .\diagrams_out `
  --strict-delivery `
  --out ".\output.docx"
```

版式抽检：在 macOS 上可用 `qlmanage -t -s 1400 -o ./preview "/path/to/output.docx"` 生成首页缩略图并用 `read_file` 确认封面与目录版式无异常；在 Windows / Linux 上可直接用 Word / WPS 打开核验，或通过 LibreOffice（`soffice --headless --convert-to pdf output.docx`）转 PDF 后渲染预览。**注意**：若用户已在 WPS / Word 中打开同名 `.docx`，覆盖重建后务必提醒关闭旧标签页（不要保存覆盖）再重新打开，否则客户端可能继续展示内存缓存的旧版。最终向用户报告时，仅陈述本次实际读取或脚本核验过的文件路径、图表数量、模块清单与校验结果。
