---
name: sdd-design-doc-merge
description: >-
  Merge multiple modular SDD JSON specs or inject new 3.x module specifications directly into an existing master .docx document via `scripts/merge_sdd.py`.
  Automatically detects existing modules & style IDs, deduplicates shared capabilities into fixed 3.99 sections, renumbers 3.1..3.n and 图 3-1..3-k, copies images cleanly, and refreshes clickable _Toc bookmarks.
  Trigger phrases: 合并设计文档, 合入主文档, 模块拼接, 文档去重与目录更新, merge SDD, sdd-design-doc-merge.
---

# `sdd-design-doc-merge` — 多模块装配、公共能力去重与主文档合入

用于解决**多人/分阶段编写多个模块详细设计后如何无错合并进同一份总文档**的问题，杜绝手工复制粘贴导致的样式错乱、章节编号/图号冲突、`3.99` 登录/网络底座重复编写，以及目录跳转失效。

---

## 三大核心指令 (`scripts/merge_sdd.py`)

先解析 `PYTHON_BIN` 与 `SKILL_DIR`（与主 Skill 相同）：

### 1. 探测已有总文档结构（`inspect`）
合入新模块前，先探测目标 `.docx` 中已占用的 `3.1 ~ 3.n` 编号、已包含的 `3.99` 公共基础能力、最大图号与样式 ID：
```bash
$PYTHON_BIN "$SKILL_DIR/scripts/merge_sdd.py" inspect \
  --docx "/path/to/master_sdd.docx"
```
根据返回的 `next_module_num` 与 `shared_capabilities` 清单编写新模块时，即可直接复用已有 `3.99.x` 条款，不再重复设计登录与重连机制。

### 2. 多份模块 JSON + `3.99` 去重组装为整份总文档（`assemble`）
将多份独立产出的 `spec_mod_*.json`（可自带各自的图表目录）与可选的 `--frontmatter` / `--shared` / `--appendix` 一键拼装为完整成册版（或第 3 章合集）：
```bash
$PYTHON_BIN "$SKILL_DIR/scripts/merge_sdd.py" assemble \
  --module mod_a/spec.json:mod_a/diagrams_out mod_b/spec.json:mod_b/diagrams_out \
  --shared shared/spec_3_99.json:shared/diagrams_out \
  --doc-title "XX系统软件详细设计说明书" \
  --mode full \
  --strict-delivery \
  --out "./汇总版软件详细设计说明书.docx"
```
**脚本自动完成以下工作**：
- **自动重编号**：按传入顺序自动重排业务模块号为 `3.1, 3.2, ...`，同步更新其下属 `3.x.1 ~ 3.x.6`、方法签名 `3.x.3.k` 与文内交叉引用（保护 `V3.1` 版本号不受误伤），统一生成 `3.0 模块清单` 表；
- **收敛与去重 `3.99`**：将各模块内联或独立传入的 `3.99` 公共基础能力汇总按标题语义去重后统一归入文末 **`3.99 公共基础能力设计`**，若业务模块仍误写同名通用能力则会告警提示；
- **图表防覆盖重排**：各模块图表加前缀隔离复制后全局连续编号 `图 3-1, 图 3-2, ...`；
- **可点击目录与严格审计**：重排所有 `_Toc20xx` 书签及超链接目录，并执行 `--strict-delivery` 全检。

### 3. 直接向已有主 `.docx` 追加/插入新模块（`inject`）
当目标是一份已经由研发/产品在 Word/WPS 中维护的现成 `.docx`（保留其封面、第 1~2 章、现有模块与页眉页脚不被破坏）时，使用 `inject` 直接往第 3 章尾部无损插入新模块与新增 `3.99` 条目：
```bash
$PYTHON_BIN "$SKILL_DIR/scripts/merge_sdd.py" inject \
  --target-docx "/path/to/existing_master.docx" \
  --module new_mod/spec.json:new_mod/diagrams_out \
  [--shared extra_shared/spec_3_99.json:extra_shared/diagrams_out] \
  --out "/path/to/existing_master_updated.docx"
```
**脚本自动完成以下工作**：
- 动态匹配目标 `.docx` 的 `styles.xml` 标题样式（兼容默认模板及标准 Word `Heading 1~4` / `标题 1~4`）；
- 无损保留原文封面、页眉页脚、第 1~2 章及已有 `3.x` 内容字节结构；
- 将新业务模块精准插入**已有最后一个 `3.x` 之后、`3.99` / 第 4 章 / 附录之前**，图号、书签 ID 与媒体 `rId` 自动顺延不冲突；
- 为缺失 `_Toc` 书签的标题补齐书签并刷新目录字段超链接（同时写入 `<w:updateFields w:val="true"/>` 提示 Word/WPS 打开时自动刷新页码）。

---

## 执行建议

- 若发现待合并的各模块各自重复写了登录或弱网重试，应先使用 AI 按 `3.99` 思想将共性内容提炼至 `shared_3_99.json`、将各业务模块改为引用 `3.99.x`，再运行 `assemble` 或 `inject`，从源头保证总文档清爽无冗余。
