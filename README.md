# sdd-design-doc (Software Detailed Design Spec & Story Family)

标准化软件详细设计说明书（`.docx`）与 Story 技术规划文档（`.md`）技能家族——覆盖**需求规划确认、单模块可移植第 3 章生成、完整成册交付、多模块去重拼接与已有主文档无损合入**。

## 技能家族分化

| Skill | 职责定位 | 典型输出 |
| :--- | :--- | :--- |
| **`sdd-design-doc`** | 主调度路由与通用设计/排版基线 | 根据任务意图路由至下方 4 项专用能力 |
| **`sdd-design-doc-plan`** | `plan-md -> user review -> confirm` 前置设计蓝图 | 标明 `[拟定]`、`[待确认]`、枚举结构与异常闭环的规划 `.md` |
| **`sdd-design-doc-module`** | 专注第 3 章的可移植模块详细设计（`--mode module`） | 仅含 `3 模块详细设计` + 引用 `3.99` 的模块 `.docx` 与 JSON 资产 |
| **`sdd-design-doc-full`** | 完整成册模板文档（`--mode full`） | 封面、可点击目录、第 1~3 章（含 `3.99` 公共基础能力）与 `附录 A` |
| **`sdd-design-doc-merge`** | 多模块去重装配 & 主 `.docx` 第 3 章无损合入 | 自动重排 `3.x`/`图 3-k`、去重 `3.99`、刷新 `_Toc` 可点击目录 |

---

## 核心特性

- **设计重流程 + 代码重架构、枚举与类契约**：
  - `3.x.1~3.x.2` 聚焦主业务流程与正常/异常闭环（网络超时、重试、401 续期、非法值降级），拒绝私有布局像素常量刷屏；
  - `3.x.3` 配备按职责分组的 UML 类图（含紫色 `«enum»` 与天蓝 `«Model»` 色带）、核心枚举（Enum）定义表及完整方法签名契约（不贴函数实现体）。
- **`3.99 公共基础能力设计` 防跨模块重复**：
  - 统一认证登录与令牌静默续期、共性 HTTP 重试与切页取消、全局资源配额池、跨模块共享组件集中收敛到 `3.99`，各业务章节只写业务增量并声明引用。
- **外部接口 `api_card` + 一行一条清爽排版**：
  - HTTP/MQTT/UDP/WS 外部接口用独立卡片展示，任何 `1/2/3`、`①/②/③` 多点列举均分行呈现（`--strict-delivery` 自动拦截分号句堆砌、`.md` 残留引用、正文中散落 IP、表格 `both` 对齐与孤立表头）。
- **零外部 Python-docx 依赖渲染**：基于声明式 SVG → Chromium/Playwright/CDP 高分渲染 PNG + 原生 OOXML 构建与无损 XML 合入。

---

## 安装

```bash
# 全局安装（推荐，同时安装 sdd-design-doc 与 4 个子命令）
npx skills add rainlotus97/sdd-design-doc
```

也可直接克隆到项目的 `.agents/skills/sdd-design-doc/`（或 `~/.agents/skills/`），并将 `skills/sdd-design-doc-*` 平铺复制到同级目录。

---

## 快速自检（含完整模式、模块模式与多模块 Merge 端到端测试）

```bash
# macOS / Linux（若默认 python3 存在 pyexpat 异常，自动选用 /usr/bin/python3）
PYTHON_BIN=$(/usr/bin/python3 -c "import xml.etree.ElementTree" 2>/dev/null && echo /usr/bin/python3 || echo python3)
$PYTHON_BIN scripts/check_env.py --smoke-test
```

```powershell
# Windows PowerShell
py -3 scripts/check_env.py --smoke-test
```

---

## 目录说明

- [SKILL.md](./SKILL.md) — 主入口路由与通用工程规范
- [skills/](./skills) — `sdd-design-doc-plan` / `-module` / `-full` / `-merge` 四大专用子 Skill
- [scripts/diagram_dsl.py](./scripts/diagram_dsl.py) — 流程图、时序图、分层图、UML 类图（含 `enum`/`model`）生成器
- [scripts/snap_diagrams.cjs](./scripts/snap_diagrams.cjs) — Playwright / 零依赖 CDP 浏览器高分辨率 PNG 截图器
- [scripts/docx_builder.py](./scripts/docx_builder.py) — 原生 OOXML 生成引擎（左对齐、`keepNext` 防双表头、`api_card` 分行列表）
- [scripts/build_from_spec.py](./scripts/build_from_spec.py) — `--mode full|module` 构建与 `--strict-delivery` 审计器
- [scripts/merge_sdd.py](./scripts/merge_sdd.py) — 多模块去重组装（`assemble`）、主文档探测（`inspect`）与无损合入更新目录（`inject`）
- [references/](./references) — Story 规划模板、JSON Schema 与图表编写手册
- [resources/default_sdd_template/](./resources/default_sdd_template) — 内置默认样式母版
