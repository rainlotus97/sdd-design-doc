#!/usr/bin/env python3
"""Build a styled Word (.docx) Software Detailed Design Specification from declarative JSON specs."""
import argparse
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from docx_builder import DocxBuilder


def configure_stdio():
    """Ensure UTF-8 console output on Windows legacy codepages."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def apply_block(doc: DocxBuilder, blk: dict, diagrams_dir: str):
    btype = blk["type"]
    if btype == "doc_title":
        doc.add_doc_title(blk["text"])
    elif btype == "toc":
        doc.insert_toc_placeholder()
    elif btype == "blank":
        doc.add_blank(blk.get("size", 8))
    elif btype == "heading":
        doc.add_heading(
            int(blk["level"]),
            blk["text"],
            page_break=bool(blk.get("pageBreak", False)),
            est_page=int(blk.get("estPage", 1)),
            center=bool(blk.get("center", False)),
        )
    elif btype == "para":
        doc.add_para(blk.get("text", ""), bold_prefix=blk.get("boldPrefix", ""), space_after=int(blk.get("spaceAfter", 80)))
    elif btype == "bullet":
        doc.add_bullet(blk.get("boldPrefix", ""), blk.get("text", ""))
    elif btype == "step":
        doc.add_numbered_step(int(blk["num"]), blk["text"])
    elif btype == "steps":
        for idx, item in enumerate(blk.get("items", []), 1):
            doc.add_numbered_step(idx, item)
    elif btype == "code":
        doc.add_code_block(blk.get("lines", []))
    elif btype == "table":
        doc.add_table(
            blk["headers"],
            blk["rows"],
            col_widths=blk.get("colWidths"),
            center_cols=blk.get("centerCols"),
        )
    elif btype == "api_card":
        doc.add_api_card(blk)
    elif btype == "image":
        src = os.path.normpath(blk["file"])
        if not os.path.isabs(src):
            src = os.path.normpath(os.path.join(diagrams_dir, src))
        if not os.path.exists(src):
            raise FileNotFoundError(f"Missing diagram PNG: {src}")
        doc.add_image(src, blk.get("caption", ""), max_width_emu=int(blk.get("maxWidthEmu", 5852160)))
    else:
        raise ValueError(f"Unknown block type: {btype}")


def audit_docx(docx_path: str, expected_images: int, custom_template: bool = False, strict_delivery: bool = False, mode: str = "auto"):
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    md_pat = re.compile(r"[A-Za-z0-9_\u4e00-\u9fff-]+\.md")
    ip_pat = re.compile(r"(?:10|127|172|192|0)\.\d{1,3}\.\d{1,3}\.\d{1,3}(?::\d+)?")
    inline_enum_pats = [
        re.compile(r"①[^①\n]{2,}②"),
        re.compile(r"(?<![\d\.])1）[^）\n]{2,}[；;，,]?\s*2）"),
        re.compile(r"(?:(?<=^)|(?<=[：:；;\s]))1\)\s*[^;\n]{2,}[；;]\s*2\)"),
        re.compile(r"（1）[^（\n]{2,}[；;]?\s*（2）"),
        re.compile(r"(?:(?<=^)|(?<=[：:；;\s]))1\.\s+[^\n]{3,}[；;]\s*2\.\s+"),
    ]

    with zipfile.ZipFile(docx_path, "r") as z:
        bad_zip = z.testzip()
        if bad_zip is not None:
            raise RuntimeError(f"Corrupted zip member: {bad_zip}")
        doc_xml = z.read("word/document.xml")
        styles_xml = z.read("word/styles.xml").decode("utf-8", "ignore") if "word/styles.xml" in z.namelist() else ""
        media_files = [n for n in z.namelist() if n.startswith("word/media/")]

    doc_text_xml = doc_xml.decode("utf-8", "ignore")
    root = ET.fromstring(doc_xml)
    ns = {"w": w_ns}
    all_text = "".join(t.text or "" for t in root.findall(".//w:t", ns))
    leftovers = []
    for tok in ["【", "】", "（示例）", "填写要求", "常见错误", "模板）"]:
        cnt = all_text.count(tok)
        if cnt > 0:
            leftovers.append((tok, cnt))
    drawings = len(root.findall(".//w:drawing", ns))
    tables = len(root.findall(".//w:tbl", ns))

    both_styles = styles_xml.count('w:val="both"')
    both_doc = doc_text_xml.count('w:val="both"')
    body = root.find(f"{{{w_ns}}}body")
    missing_hdr_kn = 0
    for tbl in root.findall(".//w:tbl", ns):
        trs = tbl.findall(f"{{{w_ns}}}tr")
        if len(trs) > 1:
            tr_pr = trs[0].find(f"{{{w_ns}}}trPr")
            if tr_pr is not None and tr_pr.find(f"{{{w_ns}}}tblHeader") is not None:
                if any(
                    (p.find(f"{{{w_ns}}}pPr") is None or p.find(f"{{{w_ns}}}pPr").find(f"{{{w_ns}}}keepNext") is None)
                    for p in trs[0].iter(f"{{{w_ns}}}p")
                ):
                    missing_hdr_kn += 1

    body_blocks = ["".join(el.itertext()) for el in body] if body is not None else []
    endpoint_tbl_texts = set()
    for tbl in root.findall(".//w:tbl", ns):
        txt_t = "".join(tbl.itertext())
        if any(k in txt_t for k in ("联调端点", "Endpoint", "Mock", "本地服务端点", "环境配置")):
            endpoint_tbl_texts.add(txt_t)
    app_idx = next(
        (i for i, txt in enumerate(body_blocks) if "附录 A" in txt or "附录A" in txt or txt.strip().startswith("附录")),
        len(body_blocks),
    )
    pre_blocks_filtered = [txt for txt in body_blocks[:app_idx] if txt not in endpoint_tbl_texts]
    pre_app_text = "\n".join(pre_blocks_filtered)
    md_hits = md_pat.findall("\n".join(body_blocks))
    ip_pre_hits = ip_pat.findall(pre_app_text)

    inline_enum_hits = []
    for p_el in root.findall(".//w:body//w:p", ns):
        pt = "".join(t.text or "" for t in p_el.findall(".//w:t", ns)).strip()
        if not pt:
            continue
        if any(pat.search(pt) for pat in inline_enum_pats):
            inline_enum_hits.append(pt[:48] + ("..." if len(pt) > 48 else ""))

    has_toc = "目  录" in doc_text_xml
    p_texts = ["".join(p.itertext()).strip() for p in body.findall(f"{{{w_ns}}}p")] if body is not None else []
    has_ch3 = any(t.startswith("3 模块详细设计") or t.startswith("3.1 ") or t.startswith("3.99 ") for t in p_texts)
    has_ch1_or_2 = any(t.startswith("1 引言") or t.startswith("2 设计概览") for t in p_texts)

    print(f"[AUDIT] path={docx_path}")
    print(f"[AUDIT] mode={mode}, tables={tables}, drawings={drawings}, media={len(media_files)}, jc_both=({both_styles},{both_doc}), hdr_missing_keepNext={missing_hdr_kn}")
    if md_hits:
        print(f"[AUDIT WARN] Internal .md file reference(s) detected: {md_hits[:8]}")
    if ip_pre_hits:
        print(f"[AUDIT WARN] Raw IP literal(s) detected before Appendix: {ip_pre_hits[:8]}")
    if inline_enum_hits:
        print(f"[AUDIT WARN] Inline bunched enumeration(s) detected (split into one-per-line items): {inline_enum_hits[:6]}")

    if drawings != expected_images or len(media_files) != expected_images:
        raise RuntimeError(f"Image count mismatch: expected={expected_images}, drawings={drawings}, media={len(media_files)}")
    if leftovers:
        raise RuntimeError(f"Leftover template tokens found: {leftovers}")
    if mode == "full" and not has_toc:
        raise RuntimeError("Mode 'full' requires a 'toc' block in the document spec")
    if mode == "module":
        if has_toc:
            raise RuntimeError("Mode 'module' must not include a standalone TOC block ('目  录')")
        if not has_ch3:
            raise RuntimeError("Mode 'module' requires '3 模块详细设计' or '3.1 ...' module sections")
        if strict_delivery and has_ch1_or_2:
            raise RuntimeError("Mode 'module' with --strict-delivery must focus only on Chapter 3 without '1 引言' / '2 设计概览'")
    if (not custom_template or strict_delivery) and (both_styles > 0 or both_doc > 0 or missing_hdr_kn > 0):
        raise RuntimeError(f"OOXML layout check failed: jc_both=({both_styles},{both_doc}), hdr_missing_keepNext={missing_hdr_kn}")
    if strict_delivery and (md_hits or ip_pre_hits or inline_enum_hits):
        raise RuntimeError(
            f"Strict delivery check failed: md_refs={md_hits[:5]}, pre_appendix_ips={ip_pre_hits[:5]}, inline_enums={inline_enum_hits[:4]}"
        )
    print("[AUDIT] PASSED (zip OK, XML OK, 0 leftover template placeholders)")


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description="Build Word SDD from JSON spec(s)")
    parser.add_argument("--spec", nargs="+", required=True, help="Ordered JSON spec file(s)")
    parser.add_argument("--diagrams-dir", default=".", help="Directory containing rendered diagram PNGs")
    parser.add_argument("--template", default="", help="Optional custom .docx template path")
    parser.add_argument("--mode", default="auto", choices=["auto", "full", "module"], help="Document mode: 'full' (full template SDD), 'module' (portable Chapter-3-only module doc), or 'auto'")
    parser.add_argument("--strict-delivery", action="store_true", help="Fail if internal .md refs, pre-appendix bare IPs, jc='both', or orphaned table headers exist")
    parser.add_argument("--out", required=True, help="Output .docx file path")
    args = parser.parse_args()

    meta = {}
    blocks = []
    for sp_path in args.spec:
        with open(sp_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            for k in ("docTitle", "headerTitle", "creator"):
                if k in data:
                    meta[k] = data[k]
            blocks.extend(data.get("blocks", []))
        elif isinstance(data, list):
            blocks.extend(data)
        else:
            raise ValueError(f"Invalid spec JSON root in {sp_path}")

    resolved_mode = args.mode
    if resolved_mode == "auto":
        resolved_mode = "full" if any(b.get("type") == "toc" for b in blocks) else "module"

    if resolved_mode == "full" and any(b.get("type") == "toc" for b in blocks):
        toc_default_ones = sum(1 for b in blocks if b.get("type") == "heading" and int(b.get("level", 9)) <= 3 and "estPage" not in b)
        if toc_default_ones > 0:
            print(f"[AUDIT WARN] {toc_default_ones} TOC heading(s) missing 'estPage' (will default to page 1 in TOC)")

    doc = DocxBuilder(
        header_title=meta.get("headerTitle", meta.get("docTitle", "软件开发详细设计说明书")),
        doc_title=meta.get("docTitle", "软件开发详细设计说明书"),
        creator=meta.get("creator", "研发团队"),
        template_docx=args.template,
    )
    img_count = 0
    for blk in blocks:
        if blk.get("type") == "image":
            img_count += 1
        apply_block(doc, blk, args.diagrams_dir)

    out_path = doc.build(args.out)
    audit_docx(out_path, img_count, custom_template=bool(args.template), strict_delivery=bool(args.strict_delivery), mode=resolved_mode)


if __name__ == "__main__":
    main()
