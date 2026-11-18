---
name: sdd-design-doc
description: >-
  Standardized Software Detailed Design Specification (.docx) & Story design (.md) family hub.
  Coordinates 4 specialized capabilities: planning Markdown blueprints (`sdd-design-doc-plan`), portable Chapter-3 modules (`sdd-design-doc-module`),
  standalone full specifications (`sdd-design-doc-full`), and deduplicated multi-module merging with 3.99 shared infrastructure & clickable TOC (`sdd-design-doc-merge`).
  Trigger phrases: 详细设计文档, 软件详细设计, 生成docx设计文档, Story设计文档, 按模板生成文档, SDD.
---

# 软件详细设计说明书与模块化交付家族（`sdd-design-doc`）

本主 Skill 是 `sdd-design-doc` 工具家族的统一调度入口与共享质量基线（脚本、模板与规范均内置在本目录）。请根据当前任务阶段直接选用或路由至对应的专用子命令：

| 子命令 / Skill | 核心定位与触发场景 | 典型命令 / 产出 |
| :--- | :--- | :--- |
| **`sdd-design-doc-plan`** | **先规划、后成文**：针对新需求、口头方案或已有 `.md` 草稿，输出含 `[拟定]` 与 `[待确认]` 清单的 `.md` 规划稿，等待用户拍板确认。 | 输出确认态 Story 规划 `.md` |
| **`sdd-design-doc-module`** | **单模块可移植第 3 章**：仅输出 `3 模块详细设计`（`3.x`），去掉多余封面前序与目录，引用 `3.99` 公共基础能力；随附 JSON spec 与 PNG 图表。 | `build_from_spec.py --mode module --strict-delivery` |
| **`sdd-design-doc-full`** | **完整独立模板文档**：输出含封面、可点击目录、`1 引言`、`2 设计概览`、`3 模块详细设计（含 3.99）` 与 `附录 A` 的成册版 `.docx`。 | `build_from_spec.py --mode full --strict-delivery` |
| **`sdd-design-doc-merge`** | **多模块拼装、去重与合入主 `.docx`**：将多个模块 JSON 或增量模块合入整份总文档；自动重排 `3.1..3.n` 与 `图 3-k`、去重收敛 `3.99`、刷新可点击 `_Toc` 目录。 | `merge_sdd.py inspect \| assemble \| inject` |

---

## 全家族通用六大工程铁律

1. **三类输入统一实证原则（代码库 / 需求初设 / `.md` 转 `.docx`）**：
   - 基于源码时须核对真实类名、方法签名、枚举与协议字段；禁止编造接口，禁止将私有布局像素常量（如 `*WIDTH` / `*WEIGHT`）或废枝写入正文与表格。
   - 基于需求/初设时对新类、新接口标 **`[拟定]`**；转 `.docx` 时将 `.md` 内容完整内化，严禁出现“详见某某.md”。
2. **结构分工：每模块开篇必配架构图 + 流程重闭环 + 代码少而精（`code_card`）**：
   - **模块开篇架构图**：每个 `3.x` 模块在 `3.x.1` 开头须先给出一张 `layers` 模块架构图，一目了然讲清**自身业务横跨哪些工程代码模块、各层分别做什么、依赖哪些 `3.99` 与外部服务**。
   - **流程与异常闭环**：`3.x.1~3.x.2` 使用简洁工程中文，将网络超时、断连重试、401 令牌过期、空值/越界兜底直接融进全景主干流程图与时序分支中。
   - **代码设计（`3.x.3`）少而精**：不把三五个方法塞进一个标题、不把内部私有计数器/缓存变量写进正文、不用窄列三列表硬塞长类名造成断词撕裂；配合分组 UML 类图（`<<enum>>` / `<<Model>>` / `ViewModel`），仅精选 **2~4 个最核心重点函数**与 **1~2 个关键枚举/状态模型**，使用全宽 `code_card` 分点写清职责、输入、输出与边界（仍不贴函数实现体）。
3. **禁止文字堆砌，多点列举一律分行**：
   - 任何 `1/2/3`、`①/②/③` 或 `1）/2）` 多项说明**必须拆成一行一条**（使用 `"steps"`、多条 `"bullet"`、`api_card`/`code_card` 数组列表或表格 cell `\n` 分行），严禁在单一分号句内挤入多点列举。`build_from_spec.py --strict-delivery` 会自动扫描并拦截此类堆砌。
4. **公共基础能力收敛至 `3.99`，拒绝跨模块重复**：
   - 认证登录与令牌静默续期、共性 HTTP 超时退避重试与切页取消、全局资源配额池、跨页面公共组件统一写入 **`3.99 公共基础能力设计`**（`3.99.1`, `3.99.2`...）。
   - 业务模块 `3.1 ~ 3.n` 只说明自身的业务差异与触发调用边界，并明确标注“遵循 `3.99.x` 规约”。
5. **外部接口与 MQTT Topic/Payload 同等卡片化 + 正文去 IP 化**：
   - HTTP/REST、UDP/WS 与 **MQTT Topic** 一律使用 `api_card` 卡片分层呈现；对接 MQTT 时必须写明 Topic、订阅/发布方向与策略（`direction`/`qos`）、**完整 JSON Payload 载荷结构**（`payload`）、一字段一行的中文核心字段说明、界面消费与断链/空载荷兜底。
   - 具体 IP/端口不得散落正文与图表，统一以配置常量符号指代并集中收敛至联调端点配置表（`--mode full` 放文末 `附录 A`，`--mode module` 放 `3.x` 末尾配置节）。
6. **正式版版式与 OOXML 零缺陷门槛**：
   - 统一左对齐（`w:jc="left"`），表格首行强制 `<w:keepNext w:val="1"/>` 且先 `<w:cantSplit w:val="1"/>` 后 `<w:tblHeader w:val="1"/>` 防止翻页双表头，`<= 3` 行短表整体绑定。
   - 图表须用 `diagram_dsl.py` + `snap_diagrams.cjs` 渲染并通过 `read_file` 逐张验收无截断/重叠后再执行打包。

---

## 环境解析与通用验证指令

> 所有子 Skill 共用主目录 `sdd-design-doc` 下的 `scripts/` 与 `resources/default_sdd_template`（支持从当前子 Skill 上两级、项目 `.agents/skills/sdd-design-doc` 或用户全局目录自动解析）。

**macOS / Linux (Bash/Zsh)**：
```bash
PYTHON_BIN=$(/usr/bin/python3 -c "import xml.etree.ElementTree" 2>/dev/null && echo /usr/bin/python3 || echo python3)
SKILL_DIR=$(for d in \
  "$PWD/.agents/skills/sdd-design-doc" \
  "$HOME/.agents/skills/sdd-design-doc" \
  "$HOME/.gemini/config/skills/sdd-design-doc" \
  "$HOME/.claude/skills/sdd-design-doc" \
  "$HOME/.codex/skills/sdd-design-doc"; do
  [ -f "$d/scripts/build_from_spec.py" ] && echo "$d" && break
done)
$PYTHON_BIN "$SKILL_DIR/scripts/check_env.py" --smoke-test
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
) | Where-Object { Test-Path "$_\scripts\build_from_spec.py" } | Select-Object -First 1
& $PythonBin @PyArgs "$SkillDir\scripts\check_env.py" --smoke-test
```

更多规范细节参见：
- [references/story_md_template.md](./references/story_md_template.md)
- [references/docx_spec_schema.md](./references/docx_spec_schema.md)
- [references/diagram_json_guide.md](./references/diagram_json_guide.md)
