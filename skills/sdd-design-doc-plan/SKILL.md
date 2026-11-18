---
name: sdd-design-doc-plan
description: >-
  Plan software detailed design specs as a structured Story Markdown blueprint (`plan-md -> user review -> confirm`) before generating Word (.docx) deliverables.
  Marks proposed designs as `[拟定]` and open questions as `[待确认]`, defines 3.99 shared infrastructure boundaries vs 3.x module scope, enum/model contracts, and normal/exception closed-loop flows.
  Trigger phrases: 设计规划, 需求规划, Story设计文档, 先出md规划, plan SDD, sdd-design-doc-plan.
---

# `sdd-design-doc-plan` — 需求规划与 `.md` Story 蓝图设计

用于**未落地需求、口头方案或待整合 `.md` 文档**的前置规划阶段。先输出人类高可读、结构已与第 3 章对齐的 Markdown 设计规划稿；**经用户确认或修订无误后**，再移交 `sdd-design-doc-module`、`sdd-design-doc-full` 或 `sdd-design-doc-merge` 转为正式 `.docx`。

---

## 执行步骤

1. **解析共享规则目录 `SKILL_DIR`**：按主目录查找 `references/story_md_template.md`（路径顺序：相对 `../..` -> `.agents/skills/sdd-design-doc` -> `~/.agents/skills/sdd-design-doc` -> `~/.gemini/config/skills/sdd-design-doc`）。
2. **输入盘点与模块边界切分**：
   - 将跨模块共用的认证登录、公共 HTTP 超时重试/切页取消、全局并发配额与公共 UI 面板识别并归类为 **`3.99` 公共基础能力复用边界**；
   - 按独立业务功能域划分 `3.1`, `3.2`... 拟定章节，避免拆碎。
   - 若同时关联已有代码仓库，检索核验现有类、枚举成员与已有 `3.99` 能力；尚未实现的接口/类/枚举一律标 **`[拟定]`**。
3. **严格按 `references/story_md_template.md` 撰写 `.md` 规划稿**：
   - `0. 需求规划摘要与待确认清单`：汇总所有需要产品/后端拍板的 **`[待确认]`** 项（字段、阈值、超时降级弹窗策略、联调约定等）。
   - `1. 模块代码架构与功能边界`：用架构分层图（明确本业务涉及工程内哪些模块、各块做什么及与 `3.99` 边界）配合交互表聚焦主功能与异常反馈。
   - `2. 业务主流程与正常/异常闭环`：用 Mermaid `flowchart TD` + `sequenceDiagram` 直接画入正常请求、超时重试、401 续期、空值/越界兜底。
   - `3. 重点函数、枚举与依赖设计`：**内部逻辑少而精、说重点**——给出 `3.99` 复用声明、分组类图（标 `[拟定]`），精选 2~4 个关键骨干函数（职责 + 输入 + 返回/影响 + 边界）与核心枚举/模型定义，禁止把私有计数器或五六个函数堆在一段里。
   - `4. 外部接口、MQTT Topic 与载荷契约`：HTTP 与 **MQTT** 同等展开（Topic、订阅/发布策略、**Payload JSON 结构**、一字段一行返回值与异常兜底），IP 集中放入文末配置参考表。
   - `5. 可靠性/安全与验收场景`：逐条列出正常与弱网/异常自愈验收闭环。
4. **格式铁律**：规划稿内所有多点列举（`1/2/3`、`①/②/③`）同样坚持一行一条，不在句中分号堆砌。
5. **停下来提交用户审阅**：明确询问用户确认以下事项后再转换 `.docx`：
   - `[待确认]` 清单中的拍板结论；
   - 拟分模块列表与 `3.99` 公共基础能力边界是否合理；
   - 目标出口选择：`sdd-design-doc-module`（仅第 3 章可移植版）、`sdd-design-doc-full`（完整成册版）或 `sdd-design-doc-merge`（合入已有总文档）。
