---
name: sdd-design-doc-module
description: >-
  Generate portable Chapter-3-only modular Word (.docx) Software Detailed Design Specifications (`--mode module --strict-delivery`) ready for manual transplant or `sdd-design-doc-merge` master assembly.
  Focuses strictly on Chapter 3 (`3.x` modules + `3.99` deduplicated references), flow/sequence closed-loops, api_card external contracts, enum/model definitions, and grouped UML class diagrams.
  Trigger phrases: 模块详细设计, 生成第3章, 可移植模块文档, module SDD, sdd-design-doc-module.
---

# `sdd-design-doc-module` — 第 3 章可移植模块详细设计生成

专注输出 **`3 模块详细设计`**（不含多余的第 1、2 章与独立 TOC 目录），使研发可以直接复制第 3 章并入主设计模板，或把随同留存的 `spec_*.json` + `diagrams_out/` 交由 `sdd-design-doc-merge` 自动拼接、去重与目录更新。

---

## 执行工作流

1. **解析主 Skill 工具目录**：
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
   *(若合入现有主 `.docx`，可先执行 `merge_sdd.py inspect --docx <master.docx>` 确认当前最大模块号与已有的 `3.99` 公共能力清单。)*

2. **规划模块结构与 `3.99` 公共能力拆分**：
   - 将一个完整功能域收口为一个独立 `3.x <模块名称>`（含 `3.x.1 ~ 3.x.6`），禁止拆分过细。
   - **禁止跨模块重复造轮子**：若模块涉及通用的“统一认证登录与 401 令牌续期 / 共性 HTTP 超时退避与切页取消 / 全局共享资源池 / 跨页面公共面板”，将其收敛写入 **`3.99 公共基础能力设计`**（若仅作局部补充亦可产出一份可复用的 `shared_3_99.json`），而在业务 `3.x` 中只描述业务独有逻辑并明确引用 `3.99.x`。

3. **编写规范 `spec_*.json` 与 `diagrams.json`**：
   - **设计重流程与异常闭环 (`3.x.1` / `3.x.2` / `3.x.4`)**：
     - 全篇人话表达，严禁正文或常规表格出现像素/样式常量（如 `*WIDTH` / `*WEIGHT`）或代码标识符刷屏；
     - 常见网络异常（超时、重试、401、弱网降级、非法值显示 `--`）直接绘入全景流程图、时序图分支与 `api_card` 的 `"fallback"`；
     - **所有 `1/2/3`、`①/②/③` 列举必须一行一条**：正文用 `"steps"` / `"bullet"`，`api_card` 用字符串数组，表格多点用 `\n` 换行。
   - **代码设计重结构、枚举与类契约 (`3.x.3`)**：
     - **分组 UML 类图**：当类较多时拆为“ViewModel/Service 架构图 + Enum/Model 数据契约图”，用 `role: "enum"`（`«enum»` 紫头）与 `role: "model"` 清晰展示成员与字段；
     - **核心枚举与状态模型定义表**：列出模块内真实关键 `enum` 枚举名称、枚举值、业务语义与迁移条件；
     - **核心类与对外方法契约**：写出方法签名、入参、返回值与失败兜底（不写内部函数体）。
   - **外部接口与端点收敛 (`3.x.4`)**：HTTP/MQTT/UDP 接口一律用 `api_card` 卡片分层展示，英文接口字段一字段一行附带中文解释；具体 IP/端口统一收进本节末尾配置参考表（严禁散落正文）。
   - **零模板占位 / 零 `.md` 引用**。

4. **渲染图表 → `read_file` 逐张视觉检查 → 严格审计打包**：
   ```bash
   $PYTHON_BIN "$SKILL_DIR/scripts/diagram_dsl.py" diagrams.json ./diagrams_out
   node "$SKILL_DIR/scripts/snap_diagrams.cjs" ./diagrams_out
   # 使用 read_file 逐张检查 ./diagrams_out/*.png 无截断/重叠
   $PYTHON_BIN "$SKILL_DIR/scripts/build_from_spec.py" \
     --spec spec_module.json \
     --diagrams-dir ./diagrams_out \
     --mode module \
     --strict-delivery \
     --out "./模块软件详细设计说明书.docx"
   ```
   *(若此前由 WPS/Word 打开过同名输出文件，覆盖后提醒用户关闭旧标签再重新打开。)*
