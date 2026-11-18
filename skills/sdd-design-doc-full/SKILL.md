---
name: sdd-design-doc-full
description: >-
  Generate standalone formal Word (.docx) Software Detailed Design Specifications (`--mode full --strict-delivery`) compliant with the full template structure:
  Cover, clickable _Toc hyperlinks, Chapter 1 Introduction, Chapter 2 Design Overview, Chapter 3 Module Detailed Design (3.1..3.n + 3.99 shared infra), and Appendix A.
  Trigger phrases: 完整详细设计, 完整版docx, 按模板生成文档, full SDD, sdd-design-doc-full.
---

# `sdd-design-doc-full` — 完整模板版详细设计说明书生成

用于**独立成册交付或系统级架构总览归档**，一次性产出符合正式模板结构的完整 `.docx`（封面、自动可点击目录、`1 引言`、`2 设计概览`、`3 模块详细设计`、`附录 A`）。

---

## 执行工作流

1. **解析共享工具根目录 `SKILL_DIR`**：
   ```bash
   PYTHON_BIN=$(/usr/bin/python3 -c "import xml.etree.ElementTree" 2>/dev/null && echo /usr/bin/python3 || echo python3)
   SCRIPT_DIR_CUR=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)
   SKILL_DIR=$(for d in \
     "$(cd "$SCRIPT_DIR_CUR/../.." 2>/dev/null && pwd)" \
     "$PWD/.agents/skills/sdd-design-doc" \
     "$HOME/.agents/skills/sdd-design-doc" \
     "$HOME/.gemini/config/skills/sdd-design-doc" \
     "$HOME/.claude/skills/sdd-design-doc" \
     "$HOME/.codex/skills/sdd-design-doc"; do
     [ -f "$d/scripts/build_from_spec.py" ] && echo "$d" && break
   done)
   ```

2. **规划完整成册章节架构**：
   - **封面与可点击目录**：`doc_title` + 封面信息表 + `toc` 占位块；所有 `level <= 3` 标题须填写单调非降 `estPage` 供目录页码占位，脚本自动生成 `_Toc20xx` 书签与超链接跳转并开启 Word/WPS 打开时域刷新。
   - **`1 引言` & `2 设计概览`**：系统上下文图、分层依赖架构图、关键跨模块边界与非功能基线。
   - **`3 模块详细设计`（核心设计区）**：
     - **`3.0 模块清单`**：总览表清晰区分业务模块 **`3.1 ~ 3.n`** 与固定收尾基础节 **`3.99`**；
     - **`3.1 ~ 3.n` 各业务模块**：每模块开篇先附 **`layers` 模块代码架构图**（说明涉及工程中哪些代码模块、各自做什么）；随后聚焦主流程 + 网络/异常闭环（`3.x.1~3.x.2`）、分组 UML 类图与精选 **`code_card`（重点函数 + 核心枚举/模型，少而精不堆变量）**（`3.x.3`）、HTTP 与 **MQTT（含 Topic/direction/Payload）** 同等展开的 `api_card`（`3.x.4`）、可靠性与验证（`3.x.5~3.x.6`）；
     - **`3.99 公共基础能力设计`**：统一承载跨模块共用的认证与令牌续期、HTTP 超时重试与切页取消、共享解码配额池与公共组件协调，业务章节直接引用，严禁重复拷贝。
   - **`附录 A`**：集中放置全部外部联调 IP、端口、环境切换约束与 Mock 调试说明，确保正文与图表零裸 IP。

3. **强格式自查（`--mode full --strict-delivery`）**：
   - 多点列举（`1/2/3`、`①/②/③`）一律一行一条；
   - `api_card` 分点清晰；
   - 全篇零 `.md` 文件引用、零模板占位词、统一左对齐与表头 `keepNext`。

4. **渲染图表 → `read_file` 验收 → 构建并抽检封面与目录页**：
   ```bash
   $PYTHON_BIN "$SKILL_DIR/scripts/diagram_dsl.py" diagrams.json ./diagrams_out
   node "$SKILL_DIR/scripts/snap_diagrams.cjs" ./diagrams_out
   # 使用 read_file 逐张核验 ./diagrams_out/*.png
   $PYTHON_BIN "$SKILL_DIR/scripts/build_from_spec.py" \
     --spec spec_full.json \
     [--template /path/to/custom.docx] \
     --diagrams-dir ./diagrams_out \
     --mode full \
     --strict-delivery \
     --out "./软件详细设计说明书.docx"
   ```
   *(若由多组/多模块并行产出再组装，推荐先各自产出模块 JSON spec，再交由 `sdd-design-doc-merge` 执行去重拼接。)*
