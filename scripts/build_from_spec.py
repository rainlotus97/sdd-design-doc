#!/usr/bin/env python3
"""Build a styled Word (.docx) Software Detailed Design Specification from declarative JSON specs."""
import argparse
import json
import os
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
    elif btype == "image":
        src = os.path.normpath(blk["file"])
        if not os.path.isabs(src):
            src = os.path.normpath(os.path.join(diagrams_dir, src))
        if not os.path.exists(src):
            raise FileNotFoundError(f"Missing diagram PNG: {src}")
        doc.add_image(src, blk.get("caption", ""), max_width_emu=int(blk.get("maxWidthEmu", 5852160)))
    else:
        raise ValueError(f"Unknown block type: {btype}")


def audit_docx(docx_path: str, expected_images: int):
    with zipfile.ZipFile(docx_path, "r") as z:
        bad_zip = z.testzip()
        if bad_zip is not None:
            raise RuntimeError(f"Corrupted zip member: {bad_zip}")
        doc_xml = z.read("word/document.xml")
        media_files = [n for n in z.namelist() if n.startswith("word/media/")]
    root = ET.fromstring(doc_xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    all_text = "".join(t.text or "" for t in root.findall(".//w:t", ns))
    leftovers = []
    for tok in ["【", "】", "（示例）", "填写要求", "常见错误", "模板）"]:
        cnt = all_text.count(tok)
        if cnt > 0:
            leftovers.append((tok, cnt))
    drawings = len(root.findall(".//w:drawing", ns))
    tables = len(root.findall(".//w:tbl", ns))
    print(f"[AUDIT] path={docx_path}")
    print(f"[AUDIT] tables={tables}, drawings={drawings}, media={len(media_files)}")
    if drawings != expected_images or len(media_files) != expected_images:
        raise RuntimeError(f"Image count mismatch: expected={expected_images}, drawings={drawings}, media={len(media_files)}")
    if leftovers:
        raise RuntimeError(f"Leftover template tokens found: {leftovers}")
    print("[AUDIT] PASSED (zip OK, XML OK, 0 leftover template placeholders)")


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description="Build Word SDD from JSON spec(s)")
    parser.add_argument("--spec", nargs="+", required=True, help="Ordered JSON spec file(s)")
    parser.add_argument("--diagrams-dir", default=".", help="Directory containing rendered diagram PNGs")
    parser.add_argument("--template", default="", help="Optional custom .docx template path")
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
    audit_docx(out_path, img_count)


if __name__ == "__main__":
    main()
