#!/usr/bin/env python3
"""Assemble multi-module SDD JSON specs with deduplicated 3.99 shared capabilities,
or inject a portable module spec directly into an existing master .docx with refreshed clickable TOC.
"""
import argparse
import copy
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from build_from_spec import apply_block, audit_docx, configure_stdio
from docx_builder import DocxBuilder


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

DEFAULT_STD_NS = {
    "w": W_NS,
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
}


def parse_spec_arg(raw: str, default_diagrams_dir: str):
    """Parse '<spec.json>' or '<spec.json>:<diagrams_dir>' cleanly."""
    # Support Windows drive letters (e.g. C:\foo.json:D:\figs) cleanly by rsplit when suffix exists
    if ":" in raw:
        left, right = raw.rsplit(":", 1)
        if len(left) > 1 and os.path.exists(left):
            return os.path.abspath(left), os.path.abspath(right)
    spec_path = os.path.abspath(raw)
    with open(spec_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    diag_dir = default_diagrams_dir
    if isinstance(data, dict) and data.get("diagramsDir"):
        cand = data["diagramsDir"]
        diag_dir = cand if os.path.isabs(cand) else os.path.normpath(os.path.join(os.path.dirname(spec_path), cand))
    return spec_path, os.path.abspath(diag_dir)


def load_spec_blocks(spec_path: str):
    with open(spec_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data, copy.deepcopy(data.get("blocks", []))
    if isinstance(data, list):
        return {}, copy.deepcopy(data)
    raise ValueError(f"Invalid spec JSON root in {spec_path}")


def normalize_cap_title(text: str) -> str:
    """Strip leading section numbering and punctuation for capability deduplication."""
    s = re.sub(r"^\s*\d+(?:\.\d+)*\s*", "", text.strip())
    s = re.sub(r"[\s\-—:：·、（）()]+", "", s).lower()
    return s


def _split_body_children(body_inner: str) -> list:
    """Split raw XML inside <w:body>...</w:body> into byte-exact top-level child chunks."""
    chunks = []
    n = len(body_inner)
    i = 0
    depth = 0
    start = None
    top_tag = ""

    while i < n:
        if body_inner.startswith("<!--", i):
            end = body_inner.find("-->", i + 4)
            i = n if end == -1 else end + 3
            continue
        if body_inner.startswith("<![CDATA[", i):
            end = body_inner.find("]]>", i + 9)
            i = n if end == -1 else end + 3
            continue
        lt = body_inner.find("<", i)
        if lt == -1:
            break
        # Find matching '>' honoring quoted attribute strings
        j = lt + 1
        quote = None
        while j < n:
            ch = body_inner[j]
            if quote:
                if ch == quote:
                    quote = None
            else:
                if ch in ('"', "'"):
                    quote = ch
                elif ch == ">":
                    break
            j += 1
        if j >= n:
            break
        tag_tok = body_inner[lt + 1 : j].strip()
        if not tag_tok or tag_tok.startswith("?") or tag_tok.startswith("!"):
            i = j + 1
            continue
        is_close = tag_tok.startswith("/")
        is_self = tag_tok.endswith("/")
        tag_name = tag_tok.lstrip("/").rstrip("/").split()[0]

        if not is_close:
            if depth == 0:
                start = lt
                top_tag = tag_name
            if not is_self:
                depth += 1
            elif depth == 0:
                chunks.append((top_tag, body_inner[start : j + 1]))
                start = None
        else:
            depth = max(0, depth - 1)
            if depth == 0 and start is not None:
                chunks.append((top_tag, body_inner[start : j + 1]))
                start = None
        i = j + 1
    return chunks


def _extract_plain_text(chunk_xml: str) -> str:
    return "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", chunk_xml, flags=re.DOTALL))


def _get_para_style(chunk_xml: str) -> str:
    m = re.search(r'<w:pStyle\s+w:val="([^"]+)"', chunk_xml)
    return m.group(1) if m else ""


def inspect_docx_structure(docx_path: str) -> dict:
    """Inspect heading/table/TOC style IDs, existing 3.x / 3.99 sections, and max IDs in a .docx."""
    with zipfile.ZipFile(docx_path, "r") as z:
        doc_xml = z.read("word/document.xml").decode("utf-8", "ignore")
        styles_xml = z.read("word/styles.xml").decode("utf-8", "ignore") if "word/styles.xml" in z.namelist() else ""
        rels_xml = z.read("word/_rels/document.xml.rels").decode("utf-8", "ignore") if "word/_rels/document.xml.rels" in z.namelist() else ""
        media_names = [os.path.basename(n) for n in z.namelist() if n.startswith("word/media/")]

    style_map = {1: "000008", 2: "000009", 3: "00000a", 4: "00000b", 5: "00000c"}
    toc_style_map = {1: "000012", 2: "000013", 3: "00000f"}
    tbl_style = "000014"

    if styles_xml:
        st_root = ET.fromstring(styles_xml.encode("utf-8"))
        ns = {"w": W_NS}
        found_tbl_styles = []
        for st in st_root.findall("w:style", ns):
            stype = st.attrib.get(f"{{{W_NS}}}type", "")
            sid = st.attrib.get(f"{{{W_NS}}}styleId", "")
            name_el = st.find("w:name", ns)
            sname = (name_el.attrib.get(f"{{{W_NS}}}val", "") if name_el is not None else "").lower()
            ppr = st.find("w:pPr", ns)
            out_el = ppr.find("w:outlineLvl", ns) if ppr is not None else None
            out_lvl = out_el.attrib.get(f"{{{W_NS}}}val") if out_el is not None else None
            if stype == "paragraph":
                for lvl in (1, 2, 3, 4):
                    if sname in (f"heading {lvl}", f"标题 {lvl}", f"heading{lvl}") or out_lvl == str(lvl - 1):
                        style_map[lvl] = sid
                        break
                for lvl in (1, 2, 3):
                    if sname in (f"toc {lvl}", f"toc{lvl}", f"目录 {lvl}"):
                        toc_style_map[lvl] = sid
            elif stype == "table":
                found_tbl_styles.append((sid, sname))
        if found_tbl_styles:
            pref = next((sid for sid, sn in found_tbl_styles if sid == "000014" or "grid" in sn), found_tbl_styles[0][0])
            tbl_style = pref

    m_body = re.search(r"<w:body>(.*)<w:sectPr", doc_xml, flags=re.DOTALL)
    if not m_body:
        m_body = re.search(r"<w:body>(.*)</w:body>", doc_xml, flags=re.DOTALL)
    body_inner = m_body.group(1) if m_body else ""
    chunks = _split_body_children(body_inner)

    heading_sids = {style_map[1], style_map[2], style_map[3], style_map[4]}
    business_mods = []
    shared_caps = []
    has_3_99 = False
    max_ch3_fig = 0

    for tag, raw in chunks:
        if tag != "w:p":
            continue
        txt = _extract_plain_text(raw).strip()
        if not txt:
            continue
        sid = _get_para_style(raw)
        m_fig = re.match(r"^图\s*3-(\d+)\b", txt)
        if m_fig:
            max_ch3_fig = max(max_ch3_fig, int(m_fig.group(1)))
        is_h = sid in heading_sids or re.match(r"^(?:3\.\d+|3\.99(?:\.\d+)?)\s+\S", txt)
        if not is_h:
            continue
        if re.match(r"^3\.99(?:\s|$)", txt):
            has_3_99 = True
            continue
        m_sh = re.match(r"^3\.99\.(\d+)\s+(.+)$", txt)
        if m_sh:
            has_3_99 = True
            shared_caps.append({"num": f"3.99.{m_sh.group(1)}", "title": m_sh.group(2).strip(), "key": normalize_cap_title(txt)})
            continue
        m_bm = re.match(r"^3\.(\d+)\s+(.+)$", txt)
        if m_bm and int(m_bm.group(1)) not in (0, 99):
            num_int = int(m_bm.group(1))
            business_mods.append({"num": f"3.{num_int}", "idx": num_int, "title": m_bm.group(2).strip()})

    max_bm_id = max([int(x) for x in re.findall(r'<w:bookmarkStart[^>]+w:id="(\d+)"', doc_xml)] or [50])
    max_docpr_id = max([int(x) for x in re.findall(r'<wp:docPr[^>]+id="(\d+)"', doc_xml)] or [50])
    max_rid = max([int(x) for x in re.findall(r'Id="rId(\d+)"', rels_xml)] or [50])
    max_para_hex = max([int(x, 16) for x in re.findall(r'w14:paraId="([0-9A-Fa-f]+)"', doc_xml)] or [0x20000000])

    next_mod_idx = max([m["idx"] for m in business_mods] or [0]) + 1
    return {
        "style_map": style_map,
        "toc_style_map": toc_style_map,
        "tbl_style": tbl_style,
        "business_modules": business_mods,
        "has_3_99": has_3_99,
        "shared_capabilities": shared_caps,
        "next_module_idx": next_mod_idx,
        "next_module_num": f"3.{next_mod_idx}",
        "max_ch3_fig": max_ch3_fig,
        "has_toc": "目  录" in doc_xml or "TOC \\o" in doc_xml,
        "media_names": set(media_names),
        "max_ids": {
            "bm": max_bm_id + 10,
            "docpr": max_docpr_id + 10,
            "rid": max_rid + 10,
            "para_seq": max(1000, max_para_hex - 0x10000000 + 100),
        },
    }


def _rewrite_prefix_in_text(txt: str, src_prefix: str, dst_prefix: str, fig_map: dict) -> str:
    if not txt:
        return txt
    out = txt
    if src_prefix and dst_prefix and src_prefix != dst_prefix:
        out = re.sub(
            rf"(?<![\d\.Vv]){re.escape(src_prefix)}(?=\.\d+|[\s、，,。；;：:）)节条]|$)",
            dst_prefix,
            out,
        )
    for old_f, new_f in fig_map.items():
        out = re.sub(rf"图\s*{re.escape(old_f)}(?!\d)", f"图 {new_f}", out)
    return out


def _rewrite_block_prefixes(blk: dict, src_prefix: str, dst_prefix: str, fig_map: dict) -> dict:
    b = copy.deepcopy(blk)
    btype = b.get("type", "")
    if btype == "heading":
        b["text"] = _rewrite_prefix_in_text(b.get("text", ""), src_prefix, dst_prefix, fig_map)
    elif btype == "para":
        if "boldPrefix" in b:
            b["boldPrefix"] = _rewrite_prefix_in_text(b.get("boldPrefix", ""), src_prefix, dst_prefix, fig_map)
        t = b.get("text", "")
        if isinstance(t, list):
            b["text"] = [_rewrite_prefix_in_text(str(x), src_prefix, dst_prefix, fig_map) for x in t]
        else:
            b["text"] = _rewrite_prefix_in_text(str(t), src_prefix, dst_prefix, fig_map)
    elif btype == "bullet":
        b["boldPrefix"] = _rewrite_prefix_in_text(b.get("boldPrefix", ""), src_prefix, dst_prefix, fig_map)
        b["text"] = _rewrite_prefix_in_text(b.get("text", ""), src_prefix, dst_prefix, fig_map)
    elif btype == "step":
        b["text"] = _rewrite_prefix_in_text(b.get("text", ""), src_prefix, dst_prefix, fig_map)
    elif btype == "steps":
        b["items"] = [_rewrite_prefix_in_text(str(x), src_prefix, dst_prefix, fig_map) for x in b.get("items", [])]
    elif btype == "table":
        b["rows"] = [
            [_rewrite_prefix_in_text(str(c), src_prefix, dst_prefix, fig_map) if not isinstance(c, list) else [_rewrite_prefix_in_text(str(s), src_prefix, dst_prefix, fig_map) for s in c] for c in row]
            for row in b.get("rows", [])
        ]
    elif btype in ("api_card", "code_card"):
        for k in ("name", "signature", "summary", "tag", "direction", "trigger", "request", "display", "purpose", "params", "inputs", "returns", "outputs", "rules", "logic", "fallback"):
            if k in b and b[k]:
                v = b[k]
                if isinstance(v, list):
                    b[k] = [_rewrite_prefix_in_text(str(x), src_prefix, dst_prefix, fig_map) for x in v]
                else:
                    b[k] = _rewrite_prefix_in_text(str(v), src_prefix, dst_prefix, fig_map)
    elif btype == "image":
        b["caption"] = _rewrite_prefix_in_text(b.get("caption", ""), src_prefix, dst_prefix, fig_map)
    return b


def _split_module_and_shared_blocks(blocks: list):
    """Split out Chapter 3 wrappers (doc_title/toc/3/3.0), per-module 3.x blocks, and inline 3.99 shared blocks."""
    cleaned_biz = []
    inline_shared = []
    skip_until_next_h2 = False
    in_shared = False

    for blk in blocks:
        btype = blk.get("type", "")
        if btype in ("doc_title", "toc"):
            continue
        if btype == "heading":
            lvl = int(blk.get("level", 9))
            txt = blk.get("text", "").strip()
            if lvl == 1 and re.match(r"^3(?:\s|$)", txt):
                skip_until_next_h2 = False
                in_shared = False
                continue
            if lvl == 2 and re.match(r"^3\.0(?:\s|$)", txt):
                skip_until_next_h2 = True
                in_shared = False
                continue
            if lvl == 2 and re.match(r"^3\.99(?:\s|$)", txt):
                skip_until_next_h2 = False
                in_shared = True
                inline_shared.append(blk)
                continue
            if lvl <= 2:
                skip_until_next_h2 = False
                in_shared = False
        if skip_until_next_h2:
            continue
        if in_shared:
            inline_shared.append(blk)
        else:
            cleaned_biz.append(blk)
    return cleaned_biz, inline_shared


def _partition_business_modules(blocks: list) -> list:
    """Split a module block list if it contains multiple level-2 '3.x' modules."""
    groups = []
    cur = []
    cur_src = ""
    cur_title = ""
    seen_h2 = False
    for blk in blocks:
        if blk.get("type") == "heading" and int(blk.get("level", 9)) == 2:
            txt = blk.get("text", "").strip()
            if seen_h2 and cur:
                groups.append({"src_prefix": cur_src, "title": cur_title, "blocks": cur})
                cur = []
            seen_h2 = True
            m = re.match(r"^(3\.\d+)\s+(.+)$", txt)
            if m:
                cur_src = m.group(1)
                cur_title = m.group(2).strip()
            else:
                m_x = re.match(r"^(3\.[xX])\s+(.+)$", txt)
                cur_src = m_x.group(1) if m_x else ""
                cur_title = m_x.group(2).strip() if m_x else txt
        elif not seen_h2:
            # Skip loose wrapper notes before first 3.x heading when assembling/injecting
            continue
        cur.append(blk)
    if seen_h2 and cur:
        groups.append({"src_prefix": cur_src, "title": cur_title, "blocks": cur})
    elif cur and not seen_h2:
        groups.append({"src_prefix": "", "title": "", "blocks": cur})
    return groups


def _dedup_shared_subsections(shared_blocks: list, existing_shared_keys: set = None) -> tuple:
    """Parse 3.99.x subsections, deduplicate by normalized title, and number cleanly 3.99.1, 3.99.2..."""
    seen_keys = set(existing_shared_keys or set())
    intro_blocks = []
    sections = []
    cur_sec = None

    for blk in shared_blocks:
        if blk.get("type") == "heading" and int(blk.get("level", 9)) == 2:
            txt = blk.get("text", "").strip()
            if re.match(r"^3\.99(?:\s|$)", txt):
                continue
        if blk.get("type") == "heading" and int(blk.get("level", 9)) == 3:
            txt = blk.get("text", "").strip()
            m = re.match(r"^(3\.99\.\d+|3\.[xX]\.\d+)\s+(.+)$", txt)
            raw_prefix = m.group(1) if m else ""
            raw_title = m.group(2).strip() if m else txt
            key = normalize_cap_title(raw_title)
            if cur_sec is not None:
                sections.append(cur_sec)
            cur_sec = {"key": key, "src_prefix": raw_prefix, "title": raw_title, "blocks": [blk]}
            continue
        if cur_sec is None:
            intro_blocks.append(blk)
        else:
            cur_sec["blocks"].append(blk)
    if cur_sec is not None:
        sections.append(cur_sec)

    kept_sections = []
    skipped = []
    for sec in sections:
        if sec["key"] in seen_keys:
            skipped.append(sec["title"])
            continue
        seen_keys.add(sec["key"])
        kept_sections.append(sec)
    return intro_blocks, kept_sections, skipped


def _stage_and_renumber_module(blocks: list, diag_dir: str, staged_diag_dir: str, mod_tag: str, src_prefix: str, dst_prefix: str, next_fig_num: int) -> tuple:
    fig_map = {}
    ordered_labels = []
    for blk in blocks:
        if blk.get("type") == "image":
            m_cap = re.match(r"^图\s*(3-\d+)", blk.get("caption", "").strip())
            new_fig = f"3-{next_fig_num}"
            next_fig_num += 1
            ordered_labels.append(new_fig)
            if m_cap:
                fig_map[m_cap.group(1)] = new_fig

    out_blocks = []
    img_idx = 0
    for blk in blocks:
        nb = _rewrite_block_prefixes(blk, src_prefix, dst_prefix, fig_map)
        if nb.get("type") == "image":
            src = nb["file"]
            if not os.path.isabs(src):
                src = os.path.normpath(os.path.join(diag_dir, src))
            if not os.path.exists(src):
                raise FileNotFoundError(f"Missing diagram PNG during merge staging: {src}")
            f_label = ordered_labels[img_idx]
            img_idx += 1
            staged_name = f"{mod_tag}_{img_idx:02d}_{os.path.basename(src)}"
            shutil.copy2(src, os.path.join(staged_diag_dir, staged_name))
            nb["file"] = staged_name
            cap = nb.get("caption", "").strip()
            if not re.match(r"^图\s*3-\d+", cap):
                nb["caption"] = f"图 {f_label} {cap}".strip()
        out_blocks.append(nb)
    return out_blocks, next_fig_num


def _default_frontmatter_blocks(doc_title: str, module_rows: list) -> list:
    return [
        {"type": "doc_title", "text": doc_title},
        {"type": "toc"},
        {"type": "heading", "level": 1, "pageBreak": True, "text": "1 引言"},
        {"type": "heading", "level": 2, "text": "1.1 编写目的"},
        {"type": "para", "text": f"本文档为《{doc_title}》的汇总详细设计说明书，整合各业务功能模块与 3.99 公共基础能力规约，作为编码实现、接口联调与测试验收的统一技术基线。"},
        {"type": "heading", "level": 2, "text": "1.2 阅读对象"},
        {"type": "bullet", "boldPrefix": "前端 / 终端研发：", "text": "依据 3.x 与 3.99 节实现页面状态模型、接口调用、枚举约束与异常兜底闭环。"},
        {"type": "bullet", "boldPrefix": "测试与联调人员：", "text": "依据各模块主流程、错误兜底与附录联调接口清单设计正常与弱网测试用例。"},
        {"type": "heading", "level": 1, "pageBreak": True, "text": "2 设计概览"},
        {"type": "heading", "level": 2, "text": "2.1 分层与公共能力复用原则"},
        {"type": "para", "text": "系统采用“业务模块独立设计（3.1 ~ 3.n）+ 跨模块公共基础能力下沉（3.99）”的两层设计结构。所有跨模块复用的认证续期、弱网重试与取消、共享状态组件统一收敛至 3.99 公共基础能力设计，业务模块仅声明差异化业务逻辑并引用对应 3.99.x 条款，避免多文档拼接时的能力重复书写。"},
        {"type": "heading", "level": 2, "text": "2.2 模块总览"},
        {
            "type": "table",
            "headers": ["章节编号", "模块名称", "设计职责定位"],
            "colWidths": [1500, 3200, 4943],
            "centerCols": [0],
            "rows": module_rows,
        },
    ]


def cmd_assemble(args):
    module_inputs = [parse_spec_arg(raw, args.diagrams_dir) for raw in args.module]
    shared_inputs = [parse_spec_arg(raw, args.diagrams_dir) for raw in (args.shared or [])]

    first_meta, _ = load_spec_blocks(module_inputs[0][0])
    doc_title = args.doc_title or first_meta.get("docTitle", "软件详细设计说明书（汇总版）")
    header_title = args.header_title or first_meta.get("headerTitle", f"{doc_title} V1.0")
    creator = args.creator or first_meta.get("creator", "研发团队")

    with tempfile.TemporaryDirectory() as stage_dir:
        biz_entries = []
        raw_shared_pool = []

        # Collect business module groups & any inline 3.99 shared blocks
        for sp_path, diag_dir in module_inputs:
            _, blocks = load_spec_blocks(sp_path)
            biz_blocks, inline_shared = _split_module_and_shared_blocks(blocks)
            if inline_shared:
                raw_shared_pool.append((inline_shared, diag_dir))
            for grp in _partition_business_modules(biz_blocks):
                biz_entries.append((grp["src_prefix"], grp["title"], grp["blocks"], diag_dir))

        # Collect explicit --shared files
        for sp_path, diag_dir in shared_inputs:
            _, blocks = load_spec_blocks(sp_path)
            _, explicit_shared = _split_module_and_shared_blocks(blocks)
            target_blocks = explicit_shared if explicit_shared else blocks
            raw_shared_pool.append((target_blocks, diag_dir))

        next_fig = 1
        next_mod_idx = 1
        staged_biz_blocks = []
        manifest_rows = []
        est_page = 4 if args.mode == "full" else 1

        for idx, (src_prefix, title, blocks, diag_dir) in enumerate(biz_entries, 1):
            dst_prefix = f"3.{next_mod_idx}"
            next_mod_idx += 1
            manifest_rows.append([dst_prefix, title or f"业务模块 {idx}", f"详见 {dst_prefix} 节主流程、状态枚举、接口卡片与类契约"])
            renumbered, next_fig = _stage_and_renumber_module(
                blocks, diag_dir, stage_dir, f"mod{idx:02d}", src_prefix, dst_prefix, next_fig
            )
            for b in renumbered:
                if b.get("type") == "heading":
                    lvl = int(b.get("level", 9))
                    if lvl <= 3 and "estPage" not in b:
                        b["estPage"] = est_page
                        est_page += 1
            staged_biz_blocks.extend(renumbered)

        # Assemble & deduplicate 3.99 shared capabilities
        shared_intro_all = []
        staged_shared_blocks = []
        seen_shared_keys = set()
        shared_sub_idx = 1

        for s_idx, (s_blocks, s_diag) in enumerate(raw_shared_pool, 1):
            intro, kept_secs, skipped = _dedup_shared_subsections(s_blocks, seen_shared_keys)
            for t in skipped:
                print(f"[MERGE DEDUP] Skipped duplicated shared capability '{t}' in shared input #{s_idx}")
            if intro and not shared_intro_all:
                renum_intro, next_fig = _stage_and_renumber_module(
                    intro, s_diag, stage_dir, f"sh_intro_{s_idx:02d}", "3.99", "3.99", next_fig
                )
                shared_intro_all.extend(renum_intro)
            for sec in kept_secs:
                seen_shared_keys.add(sec["key"])
                dst_sub = f"3.99.{shared_sub_idx}"
                shared_sub_idx += 1
                renum_sec, next_fig = _stage_and_renumber_module(
                    sec["blocks"], s_diag, stage_dir, f"sh{shared_sub_idx:02d}", sec["src_prefix"], dst_sub, next_fig
                )
                for b in renum_sec:
                    if b.get("type") == "heading" and int(b.get("level", 9)) <= 3 and "estPage" not in b:
                        b["estPage"] = est_page
                        est_page += 1
                staged_shared_blocks.extend(renum_sec)

        # Warn if any business module heading repeats a normalized 3.99 shared capability
        if seen_shared_keys:
            for b in staged_biz_blocks:
                if b.get("type") == "heading" and int(b.get("level", 9)) >= 3:
                    k = normalize_cap_title(b.get("text", ""))
                    if k and k in seen_shared_keys:
                        print(f"[MERGE DEDUP WARN] Business heading '{b.get('text', '')}' overlaps with 3.99 shared capability; verify reference-only pointer.")

        ch3_header_blocks = [
            {"type": "heading", "level": 1, "pageBreak": args.mode == "full", "estPage": 3 if args.mode == "full" else 1, "center": args.mode == "module", "text": "3 模块详细设计"},
            {"type": "heading", "level": 2, "estPage": 3 if args.mode == "full" else 1, "text": "3.0 模块清单"},
        ]
        all_manifest_rows = list(manifest_rows)
        if staged_shared_blocks:
            all_manifest_rows.append(["3.99", "公共基础能力设计", "跨模块复用的统一认证续期、弱网重试取消、共享状态组件与底层配额规约（固定尾节，避免重复书写）"])
        ch3_header_blocks.append(
            {
                "type": "table",
                "headers": ["模块编号", "模块名称", "核心设计范围与复用关系"],
                "colWidths": [1450, 3200, 4993],
                "centerCols": [0],
                "rows": all_manifest_rows,
            }
        )

        final_blocks = []
        if args.mode == "module" and args.doc_title:
            final_blocks.append({"type": "doc_title", "text": doc_title})
            final_blocks.append({
                "type": "para",
                "boldPrefix": "可移植结构说明：",
                "text": "本文档专注《3 模块详细设计》，业务模块（3.1 ~ 3.n）与跨模块公共基础能力（3.99）已严格分离；人工按章复制或交由自动化合入工具装配进主总文档均可零冲突复用。",
            })
        elif args.mode == "full":
            if args.frontmatter:
                fm_meta, fm_blocks = load_spec_blocks(os.path.abspath(args.frontmatter))
                if fm_meta.get("docTitle") and not args.doc_title:
                    doc_title = fm_meta["docTitle"]
                if fm_meta.get("headerTitle") and not args.header_title:
                    header_title = fm_meta["headerTitle"]
                fm_diag = args.frontmatter_diagrams_dir or os.path.dirname(os.path.abspath(args.frontmatter))
                fm_img_i = 0
                for b in fm_blocks:
                    nb = copy.deepcopy(b)
                    if nb.get("type") == "image":
                        src = nb["file"] if os.path.isabs(nb["file"]) else os.path.join(fm_diag, nb["file"])
                        fm_img_i += 1
                        sname = f"fm_{fm_img_i:02d}_{os.path.basename(src)}"
                        shutil.copy2(src, os.path.join(stage_dir, sname))
                        nb["file"] = sname
                    final_blocks.append(nb)
            else:
                final_blocks.extend(_default_frontmatter_blocks(doc_title, all_manifest_rows))

        final_blocks.extend(ch3_header_blocks)
        final_blocks.extend(staged_biz_blocks)

        if staged_shared_blocks:
            final_blocks.append({"type": "heading", "level": 2, "estPage": est_page, "text": "3.99 公共基础能力设计"})
            if shared_intro_all:
                final_blocks.extend(shared_intro_all)
            else:
                final_blocks.append({"type": "para", "text": "本节汇总各业务模块共同依赖的基础能力设计。业务模块 3.1 ~ 3.n 中不再展开重复实现，统一引用本节对应小节。"})
            final_blocks.extend(staged_shared_blocks)

        if args.appendix:
            _, app_blocks = load_spec_blocks(os.path.abspath(args.appendix))
            final_blocks.extend(app_blocks)

        doc = DocxBuilder(
            header_title=header_title,
            doc_title=doc_title,
            creator=creator,
            template_docx=args.template,
        )
        img_count = 0
        for blk in final_blocks:
            apply_block(doc, blk, stage_dir)
            if blk.get("type") == "image":
                img_count += 1
        doc.build(args.out)
        audit_docx(args.out, img_count, custom_template=bool(args.template), strict_delivery=args.strict_delivery, mode=args.mode)
        print(f"[MERGE ASSEMBLE] Successfully built {args.out} ({len(manifest_rows)} business module(s), {len(seen_shared_keys)} 3.99 shared item(s), {img_count} diagram(s))")


def _rebuild_toc_paragraphs(doc_xml: str, info: dict) -> str:
    """Assign missing _Toc bookmarks to level 1..3 headings and rebuild TOC hyperlink list cleanly."""
    h1, h2, h3 = info["style_map"][1], info["style_map"][2], info["style_map"][3]
    lvl_by_sid = {h1: 1, h2: 2, h3: 3}
    bm_seq = info["max_ids"]["bm"] + 500
    para_seq = info["max_ids"]["para_seq"] + 500

    m_body = re.search(r"(<w:body>)(.*)(<w:sectPr.*</w:body>)", doc_xml, flags=re.DOTALL)
    if not m_body:
        m_body = re.search(r"(<w:body>)(.*)(</w:body>)", doc_xml, flags=re.DOTALL)
    if not m_body:
        return doc_xml

    chunks = _split_body_children(m_body.group(2))
    toc_start = None
    toc_end = None
    for idx, (tag, raw) in enumerate(chunks):
        if tag == "w:p" and ("TOC \\o" in raw or 'TOC \\o' in raw):
            toc_start = idx
        if toc_start is not None and idx > toc_start and tag == "w:p":
            if '<w:fldChar w:fldCharType="end"/>' in raw and 'PAGEREF' not in raw and not _extract_plain_text(raw).strip():
                toc_end = idx
                break
            if _get_para_style(raw) not in info["toc_style_map"].values() and idx > toc_start + 1:
                toc_end = idx - 1
                break

    # Collect heading entries and ensure every level 1..3 heading has a _Toc bookmark
    toc_entries = []
    updated_chunks = []
    for idx, (tag, raw) in enumerate(chunks):
        if tag == "w:p" and (toc_start is None or idx < toc_start or idx > (toc_end or toc_start)):
            sid = _get_para_style(raw)
            if sid in lvl_by_sid:
                txt = _extract_plain_text(raw).strip()
                if txt and txt != "目  录":
                    m_bm = re.search(r'<w:bookmarkStart[^>]+w:name="(_Toc[^"]+)"', raw)
                    if m_bm:
                        bm_name = m_bm.group(1)
                    else:
                        bm_seq += 1
                        bm_name = f"_Toc{2000 + bm_seq}"
                        first_r = raw.find("<w:r")
                        end_p = raw.rfind("</w:p>")
                        if first_r != -1 and end_p != -1:
                            raw = (
                                raw[:first_r]
                                + f'<w:bookmarkStart w:id="{bm_seq}" w:name="{bm_name}"/>'
                                + raw[first_r:end_p]
                                + f'<w:bookmarkEnd w:id="{bm_seq}"/></w:p>'
                            )
                    toc_entries.append((lvl_by_sid[sid], bm_name, txt))
        updated_chunks.append((tag, raw))

    if toc_start is None or toc_end is None or not toc_entries:
        new_body = "".join(r for _, r in updated_chunks)
        return doc_xml[: m_body.start(2)] + new_body + doc_xml[m_body.end(2) :]

    # Rebuild TOC field paragraphs preserving target document TOC styles
    toc_p_xmls = []
    tst = info["toc_style_map"]
    for t_idx, (lvl, bm, title) in enumerate(toc_entries):
        para_seq += 1
        pid = f"{0x10000000 + para_seq:08X}"
        st = tst.get(lvl, tst[3])
        outer_begin = (
            '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        ) if t_idx == 0 else ""
        toc_p_xmls.append(
            f'<w:p w14:paraId="{pid}"><w:pPr><w:pStyle w:val="{st}"/>'
            f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9626"/></w:tabs></w:pPr>'
            f'{outer_begin}'
            f'<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> HYPERLINK \\l {bm} </w:instrText></w:r>'
            f'<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:lang w:eastAsia="zh-CN"/></w:rPr><w:t xml:space="preserve">{escape(title)}</w:t></w:r>'
            f'<w:r><w:tab/></w:r>'
            f'<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r><w:instrText xml:space="preserve"> PAGEREF {bm} \\h </w:instrText></w:r>'
            f'<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            f'<w:r><w:t>1</w:t></w:r>'
            f'<w:r><w:fldChar w:fldCharType="end"/></w:r>'
            f'<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
        )
    para_seq += 1
    pid_end = f"{0x10000000 + para_seq:08X}"
    toc_p_xmls.append(f'<w:p w14:paraId="{pid_end}"><w:pPr/><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')

    final_chunks = updated_chunks[:toc_start] + [("w:p", x) for x in toc_p_xmls] + updated_chunks[toc_end + 1 :]
    new_body = "".join(r for _, r in final_chunks)
    return doc_xml[: m_body.start(2)] + new_body + doc_xml[m_body.end(2) :]


def cmd_inject(args):
    target_abs = os.path.abspath(args.target_docx)
    out_abs = os.path.abspath(args.out)
    info = inspect_docx_structure(target_abs)

    module_inputs = [parse_spec_arg(raw, args.diagrams_dir) for raw in (args.module or [])]
    shared_inputs = [parse_spec_arg(raw, args.diagrams_dir) for raw in (args.shared or [])]
    if not module_inputs and not shared_inputs:
        raise ValueError("inject requires at least one --module or --shared input")

    with tempfile.TemporaryDirectory() as tmp:
        stage_dir = os.path.join(tmp, "diag_stage")
        work_dir = os.path.join(tmp, "docx_stage")
        os.makedirs(stage_dir, exist_ok=True)
        with zipfile.ZipFile(target_abs, "r") as z:
            z.extractall(work_dir)

        next_mod_idx = info["next_module_idx"]
        next_fig = info["max_ch3_fig"] + 1
        seen_shared_keys = {c["key"] for c in info["shared_capabilities"]}

        # Build business module OOXML chunks using target document styles & collision-free IDs
        biz_builder = DocxBuilder(
            header_title="", doc_title="", style_map=info["style_map"], tbl_style=info["tbl_style"]
        )
        biz_builder._bm_seq = info["max_ids"]["bm"]
        biz_builder._docpr_seq = info["max_ids"]["docpr"]
        biz_builder._rid_seq = info["max_ids"]["rid"]
        biz_builder._para_seq = info["max_ids"]["para_seq"]

        raw_shared_pool = []
        injected_mods = []
        for idx, (sp_path, diag_dir) in enumerate(module_inputs, 1):
            _, blocks = load_spec_blocks(sp_path)
            biz_blocks, inline_shared = _split_module_and_shared_blocks(blocks)
            if inline_shared:
                raw_shared_pool.append((inline_shared, diag_dir))
            for grp in _partition_business_modules(biz_blocks):
                dst_prefix = f"3.{next_mod_idx}"
                next_mod_idx += 1
                injected_mods.append((dst_prefix, grp["title"]))
                renum, next_fig = _stage_and_renumber_module(
                    grp["blocks"], diag_dir, stage_dir, f"inj{idx:02d}_{next_mod_idx}", grp["src_prefix"], dst_prefix, next_fig
                )
                for b in renum:
                    apply_block(biz_builder, b, stage_dir)

        for sp_path, diag_dir in shared_inputs:
            _, blocks = load_spec_blocks(sp_path)
            _, exp_shared = _split_module_and_shared_blocks(blocks)
            raw_shared_pool.append((exp_shared if exp_shared else blocks, diag_dir))

        shared_builder = DocxBuilder(
            header_title="", doc_title="", style_map=info["style_map"], tbl_style=info["tbl_style"]
        )
        shared_builder._bm_seq = biz_builder._bm_seq + 100
        shared_builder._docpr_seq = biz_builder._docpr_seq + 100
        shared_builder._rid_seq = biz_builder._rid_seq + 100
        shared_builder._para_seq = biz_builder._para_seq + 200

        sh_idx = len(info["shared_capabilities"]) + 1
        shared_added = []
        pending_shared_blocks = []
        for s_blocks, s_diag in raw_shared_pool:
            intro, kept_secs, skipped = _dedup_shared_subsections(s_blocks, seen_shared_keys)
            for t in skipped:
                print(f"[MERGE DEDUP] Target already covers shared capability '{t}'; skipping duplicate.")
            if not info["has_3_99"] and not pending_shared_blocks and kept_secs:
                pending_shared_blocks.append({"type": "heading", "level": 2, "text": "3.99 公共基础能力设计"})
                if intro:
                    renum_intro, next_fig = _stage_and_renumber_module(
                        intro, s_diag, stage_dir, f"injsh_intro_{sh_idx:02d}", "3.99", "3.99", next_fig
                    )
                    pending_shared_blocks.extend(renum_intro)
                else:
                    pending_shared_blocks.append({"type": "para", "text": "本节统一收敛跨业务模块复用的公共基础能力，避免在各 3.x 模块中重复描述。"})
            for sec in kept_secs:
                seen_shared_keys.add(sec["key"])
                dst_sub = f"3.99.{sh_idx}"
                sh_idx += 1
                shared_added.append(dst_sub)
                renum, next_fig = _stage_and_renumber_module(
                    sec["blocks"], s_diag, stage_dir, f"injsh_{sh_idx:02d}", sec["src_prefix"], dst_sub, next_fig
                )
                pending_shared_blocks.extend(renum)

        for b in pending_shared_blocks:
            apply_block(shared_builder, b, stage_dir)

        # Copy staged PNG images cleanly into word/media/ and register rels without collisions
        all_images = list(biz_builder.images) + list(shared_builder.images)
        media_dir = os.path.join(work_dir, "word", "media")
        os.makedirs(media_dir, exist_ok=True)
        rels_path = os.path.join(work_dir, "word", "_rels", "document.xml.rels")
        rels_root = ET.parse(rels_path).getroot()
        img_tag_idx = len(info["media_names"]) + 1

        biz_xml_str = "".join(biz_builder.elements)
        shared_xml_str = "".join(shared_builder.elements)

        for rid, _, src_path in all_images:
            while f"merged_fig_{img_tag_idx:03d}.png" in info["media_names"]:
                img_tag_idx += 1
            new_media_name = f"merged_fig_{img_tag_idx:03d}.png"
            info["media_names"].add(new_media_name)
            shutil.copy2(src_path, os.path.join(media_dir, new_media_name))
            el = ET.SubElement(rels_root, f"{{{REL_NS}}}Relationship")
            el.set("Id", rid)
            el.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
            el.set("Target", f"media/{new_media_name}")

        ET.register_namespace("", REL_NS)
        ET.ElementTree(rels_root).write(rels_path, encoding="utf-8", xml_declaration=True)

        # Ensure PNG ContentType exists
        ct_path = os.path.join(work_dir, "[Content_Types].xml")
        if all_images and os.path.exists(ct_path):
            ct_root = ET.parse(ct_path).getroot()
            if not any(el.attrib.get("Extension", "").lower() == "png" for el in ct_root.findall(f"{{{CT_NS}}}Default")):
                el = ET.SubElement(ct_root, f"{{{CT_NS}}}Default")
                el.set("Extension", "png")
                el.set("ContentType", "image/png")
                ET.register_namespace("", CT_NS)
                ET.ElementTree(ct_root).write(ct_path, encoding="utf-8", xml_declaration=True)

        # Splice into target word/document.xml preserving untouched sections byte-for-byte
        doc_path = os.path.join(work_dir, "word", "document.xml")
        with open(doc_path, "r", encoding="utf-8") as f:
            doc_xml = f.read()

        # Ensure root <w:document> declares standard drawing/w14 namespaces used by injected fragments
        m_root = re.match(r"^(<\?xml[^>]*\?>\s*)?(<w:document\b[^>]*)(>)", doc_xml, flags=re.DOTALL)
        if m_root:
            root_head = m_root.group(2)
            for pfx, uri in DEFAULT_STD_NS.items():
                if f"xmlns:{pfx}=" not in root_head:
                    root_head += f' xmlns:{pfx}="{uri}"'
            doc_xml = (m_root.group(1) or "") + root_head + ">" + doc_xml[m_root.end(3) :]

        m_body = re.search(r"(<w:body>)(.*)(<w:sectPr.*</w:body>)", doc_xml, flags=re.DOTALL)
        if not m_body:
            m_body = re.search(r"(<w:body>)(.*)(</w:body>)", doc_xml, flags=re.DOTALL)
        chunks = _split_body_children(m_body.group(2))

        # Locate anchors: start of 3.99, start of Ch4/Appendix
        pos_3_99 = None
        pos_ch4_or_app = len(chunks)
        for c_i, (tag, raw) in enumerate(chunks):
            if tag != "w:p":
                continue
            txt = _extract_plain_text(raw).strip()
            if pos_3_99 is None and re.match(r"^3\.99(?:\s|$)", txt):
                pos_3_99 = c_i
            if re.match(r"^(?:4\s+\S|第\s*4\s*章|附录)", txt):
                pos_ch4_or_app = c_i
                break

        biz_insert_idx = pos_3_99 if pos_3_99 is not None else pos_ch4_or_app
        new_chunks = []
        for c_i, ch in enumerate(chunks):
            if c_i == biz_insert_idx and biz_xml_str:
                new_chunks.append(("w:p", biz_xml_str))
            if c_i == pos_ch4_or_app and shared_xml_str:
                new_chunks.append(("w:p", shared_xml_str))
            new_chunks.append(ch)
        if biz_insert_idx == len(chunks) and biz_xml_str:
            new_chunks.append(("w:p", biz_xml_str))
        if pos_ch4_or_app == len(chunks) and shared_xml_str:
            new_chunks.append(("w:p", shared_xml_str))

        doc_xml = doc_xml[: m_body.start(2)] + "".join(r for _, r in new_chunks) + doc_xml[m_body.end(2) :]

        # Rebuild clickable TOC entries if target has a TOC block
        info_after = dict(info)
        info_after["max_ids"]["bm"] = shared_builder._bm_seq + 10
        info_after["max_ids"]["para_seq"] = shared_builder._para_seq + 10
        doc_xml = _rebuild_toc_paragraphs(doc_xml, info_after)
        ET.fromstring(doc_xml.encode("utf-8"))

        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(doc_xml)

        # Ensure fields (page numbers & TOC) auto-update when opened in Word/WPS
        settings_path = os.path.join(work_dir, "word", "settings.xml")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                s_xml = f.read()
            if "<w:updateFields" not in s_xml:
                s_xml = s_xml.replace("</w:settings>", '<w:updateFields w:val="true"/></w:settings>')
                with open(settings_path, "w", encoding="utf-8") as f:
                    f.write(s_xml)

        os.makedirs(os.path.dirname(out_abs), exist_ok=True)
        with zipfile.ZipFile(out_abs, "w", zipfile.ZIP_DEFLATED) as zout:
            for rdir, _, files in os.walk(work_dir):
                for fn in sorted(files):
                    full = os.path.join(rdir, fn)
                    arc = os.path.relpath(full, work_dir).replace(os.sep, "/")
                    if os.altsep:
                        arc = arc.replace(os.altsep, "/")
                    zout.write(full, arc)

    # Validate output archive + XML integrity
    with zipfile.ZipFile(out_abs, "r") as zv:
        bad = zv.testzip()
        if bad is not None:
            raise RuntimeError(f"Corrupted merged docx member: {bad}")
        ET.fromstring(zv.read("word/document.xml"))
    print(f"[MERGE INJECT] Updated {out_abs}: added modules={injected_mods}, shared={shared_added}, images={len(all_images)}")


def cmd_inspect(args):
    info = inspect_docx_structure(os.path.abspath(args.docx))
    printable = {k: (sorted(v) if isinstance(v, set) else v) for k, v in info.items()}
    print(json.dumps(printable, ensure_ascii=False, indent=2))


def main():
    configure_stdio()
    ap = argparse.ArgumentParser(description="Merge modular SDD specs with 3.99 deduplication or inject into master .docx")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_insp = sub.add_parser("inspect", help="Inspect existing Chapter 3 modules, 3.99 shared capabilities, and styles in a .docx")
    p_insp.add_argument("--docx", required=True, help="Existing .docx path")

    p_asm = sub.add_parser("assemble", help="Assemble multiple module JSON specs + shared 3.99 spec into a unified .docx")
    p_asm.add_argument("--frontmatter", default="", help="Optional cover/Ch1/Ch2 JSON spec")
    p_asm.add_argument("--frontmatter-diagrams-dir", default="", help="Optional diagrams dir for frontmatter")
    p_asm.add_argument("--module", nargs="+", required=True, help="Ordered '<mod.json>' or '<mod.json>:<diagrams_dir>' inputs")
    p_asm.add_argument("--shared", nargs="*", default=[], help="Optional '<shared_3_99.json>[:diagrams_dir]' inputs")
    p_asm.add_argument("--appendix", default="", help="Optional Appendix JSON spec")
    p_asm.add_argument("--diagrams-dir", default=".", help="Fallback diagrams directory")
    p_asm.add_argument("--mode", default="full", choices=["full", "module"], help="Output mode ('full' with TOC or 'module' Chapter-3 bundle)")
    p_asm.add_argument("--doc-title", default="", help="Document title override")
    p_asm.add_argument("--header-title", default="", help="Running header override")
    p_asm.add_argument("--creator", default="", help="Document author")
    p_asm.add_argument("--template", default="", help="Optional custom .docx template")
    p_asm.add_argument("--strict-delivery", action="store_true", help="Enable strict delivery audit checks")
    p_asm.add_argument("--out", required=True, help="Output merged .docx path")

    p_inj = sub.add_parser("inject", help="Inject new module/3.99 specs into an existing master .docx and refresh clickable TOC")
    p_inj.add_argument("--target-docx", required=True, help="Existing master .docx path")
    p_inj.add_argument("--module", nargs="*", default=[], help="'<mod.json>' or '<mod.json>:<diagrams_dir>' inputs to append")
    p_inj.add_argument("--shared", nargs="*", default=[], help="Optional '<shared_3_99.json>[:diagrams_dir]' inputs to add under 3.99")
    p_inj.add_argument("--diagrams-dir", default=".", help="Fallback diagrams directory")
    p_inj.add_argument("--out", required=True, help="Output updated master .docx path")

    args = ap.parse_args()
    if args.cmd == "inspect":
        cmd_inspect(args)
    elif args.cmd == "assemble":
        cmd_assemble(args)
    elif args.cmd == "inject":
        cmd_inject(args)


if __name__ == "__main__":
    main()
