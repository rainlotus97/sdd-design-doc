#!/usr/bin/env python3
"""Generic OOXML .docx builder cloning styles, theme, numbering, header & footer from a template."""
import os
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TEMPLATE_DIR = os.path.join(SKILL_ROOT, "resources", "default_sdd_template")


import re

def read_png_size(path: str):
    with open(path, "rb") as f:
        data = f.read(24)
    w = int.from_bytes(data[16:20], "big")
    h = int.from_bytes(data[20:24], "big")
    return w, h


class DocxBuilder:
    def __init__(self, header_title: str, doc_title: str, creator: str = "研发团队", template_docx: str = ""):
        self.header_title = header_title
        self.doc_title = doc_title
        self.creator = creator
        self.template_docx = template_docx
        self._para_seq = 1
        self._bm_seq = 10
        self._docpr_seq = 1
        self._rid_seq = 10
        self.elements = []
        self.toc_entries = []  # (level 1..3, bookmark_name, title, est_page)
        self.images = []       # (rid, target_name, src_path)

    def _next_para_id(self) -> str:
        val = f"{0x10000000 + self._para_seq:08X}"
        self._para_seq += 1
        return val

    def _next_bm_id(self) -> int:
        val = self._bm_seq
        self._bm_seq += 1
        return val

    def _next_docpr_id(self) -> int:
        val = self._docpr_seq
        self._docpr_seq += 1
        return val

    def _t(self, text: str) -> str:
        space_attr = ' xml:space="preserve"' if (text.startswith(" ") or text.endswith(" ") or "  " in text) else ""
        return f"<w:t{space_attr}>{escape(text)}</w:t>"

    def add_blank(self, sz: int = 8):
        pid = self._next_para_id()
        self.elements.append(
            f'<w:p w14:paraId="{pid}"><w:pPr><w:spacing w:after="0"/>'
            f'<w:rPr><w:rFonts w:hint="eastAsia" w:eastAsia="微软雅黑"/><w:sz w:val="{sz}"/><w:lang w:eastAsia="zh-CN"/></w:rPr>'
            f'</w:pPr></w:p>'
        )

    def add_doc_title(self, text: str):
        pid = self._next_para_id()
        self.elements.append(
            f'<w:p w14:paraId="{pid}"><w:pPr><w:spacing w:before="240" w:after="280"/><w:bidi w:val="0"/><w:jc w:val="center"/>'
            f'<w:rPr><w:rFonts w:hint="eastAsia" w:ascii="微软雅黑" w:hAnsi="微软雅黑" w:eastAsia="微软雅黑"/><w:b w:val="1"/><w:sz w:val="40"/><w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:hint="eastAsia" w:ascii="微软雅黑" w:hAnsi="微软雅黑" w:eastAsia="微软雅黑"/><w:b w:val="1"/><w:sz w:val="40"/><w:color w:val="000000"/><w:lang w:eastAsia="zh-CN"/></w:rPr>{self._t(text)}</w:r></w:p>'
        )

    def add_heading(self, level: int, text: str, page_break: bool = False, est_page: int = 1, center: bool = False):
        style_map = {1: "000008", 2: "000009", 3: "00000a", 4: "00000b", 5: "00000c"}
        style_id = style_map[level]
        pid = self._next_para_id()
        ppr_extra = '<w:pageBreakBefore w:val="1"/>' if page_break else ''
        jc_xml = '<w:jc w:val="center"/>' if center else '<w:jc w:val="left"/>'
        rpr_override = '<w:b w:val="1"/><w:sz w:val="21"/>' if level == 5 else ''
        run_rpr = f'<w:rPr><w:rFonts w:hint="eastAsia"/>{rpr_override}<w:lang w:eastAsia="zh-CN"/></w:rPr>'

        if level <= 3:
            bm_id = self._next_bm_id()
            bm_name = f"_Toc{2000 + bm_id}"
            self.toc_entries.append((level, bm_name, text, est_page))
            self.elements.append(
                f'<w:p w14:paraId="{pid}"><w:pPr><w:pStyle w:val="{style_id}"/>{ppr_extra}<w:keepNext w:val="1"/><w:bidi w:val="0"/>{jc_xml}'
                f'<w:rPr><w:rFonts w:hint="eastAsia"/>{rpr_override}<w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>'
                f'<w:bookmarkStart w:id="{bm_id}" w:name="{bm_name}"/>'
                f'<w:r>{run_rpr}{self._t(text)}</w:r>'
                f'<w:bookmarkEnd w:id="{bm_id}"/></w:p>'
            )
        else:
            self.elements.append(
                f'<w:p w14:paraId="{pid}"><w:pPr><w:pStyle w:val="{style_id}"/>{ppr_extra}<w:keepNext w:val="1"/><w:bidi w:val="0"/>{jc_xml}'
                f'<w:rPr><w:rFonts w:hint="eastAsia"/>{rpr_override}<w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>'
                f'<w:r>{run_rpr}{self._t(text)}</w:r></w:p>'
            )

    def add_para(self, text: str, bold_prefix: str = "", space_after: int = 80):
        # Long sub-interface signature prefixes (e.g. "3.2.3.1 Class.method(...)：") read much cleaner
        # on their own bold keepNext title line above the body paragraph instead of wrapping inline.
        split_prefix = bool(
            bold_prefix and re.match(r"^\d+\.\d+\.\d+\.\d+\s", bold_prefix) and len(bold_prefix) > 32
        )
        if split_prefix:
            hdr_title = bold_prefix.rstrip("：: ")
            pid_hdr = self._next_para_id()
            self.elements.append(
                f'<w:p w14:paraId="{pid_hdr}"><w:pPr><w:keepNext w:val="1"/><w:spacing w:before="100" w:after="40" w:line="276" w:lineRule="auto"/>'
                f'<w:jc w:val="left"/><w:rPr><w:rFonts w:hint="eastAsia"/><w:b w:val="1"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
                f'<w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>'
                f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:b w:val="1"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
                f'<w:color w:val="1E3A5F"/><w:lang w:eastAsia="zh-CN"/></w:rPr>{self._t(hdr_title)}</w:r></w:p>'
            )
            bold_prefix = ""

        lines = str(text).split("\n")
        for idx, line in enumerate(lines):
            pid = self._next_para_id()
            runs = []
            if idx == 0 and bold_prefix:
                runs.append(
                    f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:b w:val="1"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
                    f'<w:lang w:eastAsia="zh-CN"/></w:rPr>{self._t(bold_prefix)}</w:r>'
                )
            if line:
                runs.append(
                    f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
                    f'<w:lang w:eastAsia="zh-CN"/></w:rPr>{self._t(line)}</w:r>'
                )
            after = space_after if idx == len(lines) - 1 else 40
            self.elements.append(
                f'<w:p w14:paraId="{pid}"><w:pPr><w:spacing w:after="{after}" w:line="280" w:lineRule="auto"/>'
                f'<w:jc w:val="left"/><w:rPr><w:rFonts w:hint="eastAsia"/><w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>{"".join(runs)}</w:p>'
            )

    def add_bullet(self, bold_prefix: str, text: str):
        pid = self._next_para_id()
        runs = [
            f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
            f'<w:lang w:eastAsia="zh-CN"/></w:rPr>{self._t("• ")}</w:r>'
        ]
        if bold_prefix:
            runs.append(
                f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:b w:val="1"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
                f'<w:lang w:eastAsia="zh-CN"/></w:rPr>{self._t(bold_prefix)}</w:r>'
            )
        if text:
            runs.append(
                f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:sz w:val="21"/><w:szCs w:val="21"/>'
                f'<w:lang w:eastAsia="zh-CN"/></w:rPr>{self._t(text)}</w:r>'
            )
        self.elements.append(
            f'<w:p w14:paraId="{pid}"><w:pPr><w:spacing w:before="20" w:after="40" w:line="260" w:lineRule="auto"/>'
            f'<w:jc w:val="left"/><w:ind w:left="360" w:hanging="200"/>'
            f'<w:rPr><w:rFonts w:hint="eastAsia"/><w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>{"".join(runs)}</w:p>'
        )

    def add_numbered_step(self, step_num: int, text: str):
        pid = self._next_para_id()
        self.elements.append(
            f'<w:p w14:paraId="{pid}"><w:pPr><w:spacing w:before="20" w:after="40" w:line="260" w:lineRule="auto"/>'
            f'<w:jc w:val="left"/><w:ind w:left="420" w:hanging="280"/>'
            f'<w:rPr><w:rFonts w:hint="eastAsia"/><w:sz w:val="21"/><w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:eastAsia="zh-CN"/></w:rPr>'
            f'{self._t(f"{step_num}. {text}")}</w:r></w:p>'
        )

    def add_code_block(self, lines):
        for idx, line in enumerate(lines):
            pid = self._next_para_id()
            after = 80 if idx == len(lines) - 1 else 0
            before = 40 if idx == 0 else 0
            self.elements.append(
                f'<w:p w14:paraId="{pid}"><w:pPr>'
                f'<w:pBdr><w:left w:val="single" w:sz="12" w:space="8" w:color="2E74B5"/></w:pBdr>'
                f'<w:shd w:val="clear" w:color="auto" w:fill="F6F8FA"/>'
                f'<w:spacing w:before="{before}" w:after="{after}" w:line="240" w:lineRule="auto"/>'
                f'<w:jc w:val="left"/><w:ind w:left="240" w:right="120"/>'
                f'<w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="微软雅黑" w:cs="Consolas"/><w:sz w:val="17"/></w:rPr></w:pPr>'
                f'<w:r><w:rPr><w:rFonts w:hint="eastAsia" w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="微软雅黑" w:cs="Consolas"/>'
                f'<w:sz w:val="17"/><w:szCs w:val="17"/><w:color w:val="1F2937"/></w:rPr>{self._t(line)}</w:r></w:p>'
            )

    def add_table(self, headers, rows, col_widths=None, center_cols=None):
        total_w = 9643
        ncols = len(headers)
        if col_widths is None or len(col_widths) != ncols:
            base = total_w // ncols
            col_widths = [base] * ncols
            col_widths[-1] += total_w - sum(col_widths)
        else:
            col_widths = list(col_widths)
            diff = total_w - sum(col_widths)
            if diff != 0:
                col_widths[-1] += diff
        center_cols = set(center_cols or [])

        grid_cols = "".join(f'<w:gridCol w:w="{w}"/>' for w in col_widths)
        tr_list = []

        # Header row MUST keepNext so it is NEVER left orphaned at the bottom of a page without Row 1,
        # avoiding duplicate lonely header + repeated next-page header.
        hdr_keep_next = '<w:keepNext w:val="1"/>' if rows else ''
        hdr_cells = []
        for c_idx, htext in enumerate(headers):
            cw = col_widths[c_idx]
            pid = self._next_para_id()
            hdr_cells.append(
                f'<w:tc><w:tcPr><w:tcW w:w="{cw}" w:type="dxa"/>'
                f'<w:shd w:val="clear" w:color="auto" w:fill="2E74B5"/><w:vAlign w:val="center"/></w:tcPr>'
                f'<w:p w14:paraId="{pid}"><w:pPr>{hdr_keep_next}<w:spacing w:before="30" w:after="30" w:line="240" w:lineRule="auto"/>'
                f'<w:jc w:val="center"/><w:rPr><w:rFonts w:ascii="微软雅黑" w:hAnsi="微软雅黑" w:eastAsia="微软雅黑"/>'
                f'<w:b w:val="1"/><w:color w:val="FFFFFF"/><w:sz w:val="18"/></w:rPr></w:pPr>'
                f'<w:r><w:rPr><w:rFonts w:hint="eastAsia" w:ascii="微软雅黑" w:hAnsi="微软雅黑" w:eastAsia="微软雅黑"/>'
                f'<w:b w:val="1"/><w:color w:val="FFFFFF"/><w:sz w:val="18"/><w:szCs w:val="18"/><w:lang w:eastAsia="zh-CN"/></w:rPr>'
                f'{self._t(str(htext))}</w:r></w:p></w:tc>'
            )
        tr_list.append(f'<w:tr><w:trPr><w:tblHeader w:val="1"/><w:cantSplit/></w:trPr>{"".join(hdr_cells)}</w:tr>')

        for row in rows:
            row_cells = []
            for c_idx in range(ncols):
                val = row[c_idx] if c_idx < len(row) else ""
                cw = col_widths[c_idx]
                jc = '<w:jc w:val="center"/>' if c_idx in center_cols else '<w:jc w:val="left"/>'
                lines = str(val).split("\n")
                p_list = []
                for line in lines:
                    lpid = self._next_para_id()
                    p_list.append(
                        f'<w:p w14:paraId="{lpid}"><w:pPr><w:spacing w:before="25" w:after="25" w:line="240" w:lineRule="auto"/>{jc}'
                        f'<w:rPr><w:rFonts w:ascii="微软雅黑" w:hAnsi="微软雅黑" w:eastAsia="微软雅黑"/><w:sz w:val="18"/></w:rPr></w:pPr>'
                        f'<w:r><w:rPr><w:rFonts w:hint="eastAsia" w:ascii="微软雅黑" w:hAnsi="微软雅黑" w:eastAsia="微软雅黑"/>'
                        f'<w:sz w:val="18"/><w:szCs w:val="18"/><w:lang w:eastAsia="zh-CN"/></w:rPr>'
                        f'{self._t(line)}</w:r></w:p>'
                    )
                row_cells.append(
                    f'<w:tc><w:tcPr><w:tcW w:w="{cw}" w:type="dxa"/><w:vAlign w:val="center"/></w:tcPr>{"".join(p_list)}</w:tc>'
                )
            tr_list.append(f'<w:tr><w:trPr><w:cantSplit/></w:trPr>{"".join(row_cells)}</w:tr>')

        self.elements.append(
            f'<w:tbl><w:tblPr><w:tblStyle w:val="000014"/><w:tblW w:w="0" w:type="auto"/><w:tblInd w:w="0" w:type="dxa"/>'
            f'<w:tblBorders><w:top w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
            f'<w:left w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
            f'<w:bottom w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
            f'<w:right w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
            f'<w:insideH w:val="single" w:color="auto" w:sz="4" w:space="0"/>'
            f'<w:insideV w:val="single" w:color="auto" w:sz="4" w:space="0"/></w:tblBorders>'
            f'<w:tblLayout w:type="fixed"/>'
            f'<w:tblCellMar><w:top w:w="30" w:type="dxa"/><w:left w:w="108" w:type="dxa"/><w:bottom w:w="30" w:type="dxa"/><w:right w:w="108" w:type="dxa"/></w:tblCellMar>'
            f'</w:tblPr><w:tblGrid>{grid_cols}</w:tblGrid>{"".join(tr_list)}</w:tbl>'
        )

    def add_image(self, png_path: str, caption: str, max_width_emu: int = 5852160):
        rid = f"rId{self._rid_seq}"
        self._rid_seq += 1
        img_name = f"fig_{len(self.images) + 1:02d}.png"
        self.images.append((rid, img_name, png_path))

        pw, ph = read_png_size(png_path)
        cx = max_width_emu
        cy = int(max_width_emu * ph / max(1, pw))
        max_h = 6200000
        if cy > max_h:
            cx = int(max_h * pw / max(1, ph))
            cy = max_h

        docpr_id = self._next_docpr_id()
        pic_id = self._next_docpr_id()
        pid_img = self._next_para_id()
        pid_cap = self._next_para_id()

        self.elements.append(
            f'<w:p w14:paraId="{pid_img}"><w:pPr><w:keepNext w:val="1"/><w:spacing w:before="80" w:after="40"/><w:jc w:val="center"/>'
            f'<w:rPr><w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:lang w:eastAsia="zh-CN"/></w:rPr>'
            f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
            f'<wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:effectExtent l="0" t="0" r="0" b="0"/>'
            f'<wp:docPr id="{docpr_id}" name="{img_name}"/>'
            f'<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic><pic:nvPicPr><pic:cNvPr id="{pic_id}" name="{img_name}"/>'
            f'<pic:cNvPicPr><a:picLocks noChangeAspect="1"/></pic:cNvPicPr></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            f'</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
        )
        self.elements.append(
            f'<w:p w14:paraId="{pid_cap}"><w:pPr><w:spacing w:before="20" w:after="100"/><w:jc w:val="center"/>'
            f'<w:rPr><w:rFonts w:hint="eastAsia"/><w:b w:val="1"/><w:sz w:val="18"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:b w:val="1"/><w:sz w:val="18"/><w:szCs w:val="18"/><w:lang w:eastAsia="zh-CN"/></w:rPr>'
            f'{self._t(caption)}</w:r></w:p>'
        )

    def insert_toc_placeholder(self):
        self.toc_insert_index = len(self.elements)

    def _build_toc_elements(self):
        toc_els = []
        pid_hdr = self._next_para_id()
        toc_els.append(
            f'<w:p w14:paraId="{pid_hdr}"><w:pPr><w:pageBreakBefore w:val="1"/><w:bidi w:val="0"/>'
            f'<w:spacing w:after="200"/><w:rPr><w:rFonts w:hint="eastAsia"/><w:b w:val="1"/><w:sz w:val="32"/>'
            f'<w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:b w:val="1"/><w:sz w:val="32"/>'
            f'<w:lang w:eastAsia="zh-CN"/></w:rPr><w:t xml:space="preserve">目  录</w:t></w:r></w:p>'
        )
        style_map = {1: "000012", 2: "000013", 3: "00000f"}
        for idx, (lvl, bm, title, pg) in enumerate(self.toc_entries):
            pid = self._next_para_id()
            st = style_map.get(lvl, "00000f")
            outer_begin = (
                '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                '<w:r><w:instrText>TOC \\o "1-3" \\h \\z</w:instrText></w:r>'
                '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            ) if idx == 0 else ""
            toc_els.append(
                f'<w:p w14:paraId="{pid}"><w:pPr><w:pStyle w:val="{st}"/>'
                f'<w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9626"/></w:tabs></w:pPr>'
                f'{outer_begin}'
                f'<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                f'<w:r><w:instrText xml:space="preserve"> HYPERLINK \\l {bm} </w:instrText></w:r>'
                f'<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
                f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:lang w:eastAsia="zh-CN"/></w:rPr>{self._t(title)}</w:r>'
                f'<w:r><w:tab/></w:r>'
                f'<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                f'<w:r><w:instrText xml:space="preserve"> PAGEREF {bm} \\h </w:instrText></w:r>'
                f'<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
                f'<w:r><w:t>{pg}</w:t></w:r>'
                f'<w:r><w:fldChar w:fldCharType="end"/></w:r>'
                f'<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
            )
        pid_end = self._next_para_id()
        toc_els.append(
            f'<w:p w14:paraId="{pid_end}"><w:pPr/><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
        )
        return toc_els

    def build(self, output_path: str):
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = os.path.join(tmp, "stage")
            if self.template_docx:
                with zipfile.ZipFile(self.template_docx, "r") as z:
                    z.extractall(work_dir)
            else:
                shutil.copytree(
                    DEFAULT_TEMPLATE_DIR,
                    work_dir,
                    ignore=shutil.ignore_patterns(".DS_Store", "Thumbs.db", "__MACOSX"),
                )

            media_dir = os.path.join(work_dir, "word", "media")
            os.makedirs(media_dir, exist_ok=True)
            for f in os.listdir(media_dir):
                fpath = os.path.join(media_dir, f)
                if os.path.isdir(fpath) and not os.path.islink(fpath):
                    shutil.rmtree(fpath)
                else:
                    os.remove(fpath)
            for _, img_name, src_path in self.images:
                shutil.copy2(src_path, os.path.join(media_dir, img_name))

            # Ensure PNG content type is declared when custom templates omit it
            ct_path = os.path.join(work_dir, "[Content_Types].xml")
            if self.images and os.path.exists(ct_path):
                ct_ns = "http://schemas.openxmlformats.org/package/2006/content-types"
                ct_root = ET.parse(ct_path).getroot()
                has_png = any(
                    el.attrib.get("Extension", "").lower() == "png"
                    for el in ct_root.findall(f"{{{ct_ns}}}Default")
                )
                if not has_png:
                    el = ET.SubElement(ct_root, f"{{{ct_ns}}}Default")
                    el.set("Extension", "png")
                    el.set("ContentType", "image/png")
                    ET.register_namespace("", ct_ns)
                    ET.ElementTree(ct_root).write(ct_path, encoding="utf-8", xml_declaration=True)

            # Update document.xml.rels cleanly while preserving existing non-image rels
            rels_path = os.path.join(work_dir, "word", "_rels", "document.xml.rels")
            rels_root = ET.parse(rels_path).getroot()
            rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
            kept = []
            for rel in list(rels_root):
                if rel.attrib.get("Type", "").endswith("/image"):
                    rels_root.remove(rel)
                else:
                    kept.append(rel)
            for rid, img_name, _ in self.images:
                el = ET.SubElement(rels_root, f"{{{rel_ns}}}Relationship")
                el.set("Id", rid)
                el.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
                el.set("Target", f"media/{img_name}")
            ET.register_namespace("", rel_ns)
            ET.ElementTree(rels_root).write(rels_path, encoding="utf-8", xml_declaration=True)

            # Update header1.xml if present
            hdr_path = os.path.join(work_dir, "word", "header1.xml")
            if os.path.exists(hdr_path) and self.header_title:
                hdr_xml = (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<w:hdr xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
                    'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                    'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="w14">'
                    '<w:p w14:paraId="2B878536"><w:pPr><w:pStyle w:val="000011"/><w:jc w:val="left"/>'
                    '<w:rPr><w:rFonts w:hint="eastAsia" w:ascii="微软雅黑" w:hAnsi="微软雅黑" w:eastAsia="微软雅黑" w:cs="微软雅黑"/>'
                    '<w:color w:val="808080"/><w:sz w:val="17"/><w:lang w:eastAsia="zh-CN"/></w:rPr></w:pPr>'
                    f'<w:r><w:rPr><w:rFonts w:hint="eastAsia"/><w:lang w:eastAsia="zh-CN"/></w:rPr><w:t>{escape(self.header_title)}</w:t></w:r>'
                    '</w:p></w:hdr>'
                )
                with open(hdr_path, "w", encoding="utf-8") as f:
                    f.write(hdr_xml)

            settings_path = os.path.join(work_dir, "word", "settings.xml")
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    s_xml = f.read()
                if "<w:updateFields" not in s_xml:
                    s_xml = s_xml.replace("</w:settings>", '<w:updateFields w:val="true"/></w:settings>')
                with open(settings_path, "w", encoding="utf-8") as f:
                    f.write(s_xml)

            core_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
                'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                f'<dc:title>{escape(self.doc_title)}</dc:title>'
                f'<dc:creator>{escape(self.creator)}</dc:creator>'
                '</cp:coreProperties>'
            )
            os.makedirs(os.path.join(work_dir, "docProps"), exist_ok=True)
            with open(os.path.join(work_dir, "docProps", "core.xml"), "w", encoding="utf-8") as f:
                f.write(core_xml)

            toc_els = self._build_toc_elements() if self.toc_entries else []
            idx = getattr(self, "toc_insert_index", len(self.elements))
            full_elements = self.elements[:idx] + toc_els + self.elements[idx:]

            # Preserve custom template sectPr if custom template used, else use default
            sect_pr = (
                '<w:sectPr><w:headerReference r:id="rId7" w:type="default"/>'
                '<w:footerReference r:id="rId8" w:type="default"/>'
                '<w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1240" w:right="1140" w:bottom="1240" w:left="1140" w:header="851" w:footer="992" w:gutter="0"/>'
                '<w:cols w:space="425" w:num="1"/>'
                '<w:titlePg w:val="1"/>'
                '<w:docGrid w:type="lines" w:linePitch="312" w:charSpace="0"/></w:sectPr>'
            )
            doc_path = os.path.join(work_dir, "word", "document.xml")
            if self.template_docx and os.path.exists(doc_path):
                orig_root = ET.parse(doc_path).getroot()
                w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                orig_sect = orig_root.find(f"{{{w_ns}}}body/{{{w_ns}}}sectPr")
                if orig_sect is not None:
                    sect_pr = ET.tostring(orig_sect, encoding="unicode")

            doc_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document '
                'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
                'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
                'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
                'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
                'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="w14">'
                f'<w:body>{"".join(full_elements)}{sect_pr}</w:body></w:document>'
            )
            ET.fromstring(doc_xml)

            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(doc_xml)

            output_abs = os.path.abspath(output_path)
            os.makedirs(os.path.dirname(output_abs), exist_ok=True)
            with zipfile.ZipFile(output_abs, "w", zipfile.ZIP_DEFLATED) as zout:
                for root_dir, _, files in os.walk(work_dir):
                    for fn in sorted(files):
                        full = os.path.join(root_dir, fn)
                        # OOXML archives require POSIX forward slashes regardless of host OS
                        arc = os.path.relpath(full, work_dir).replace(os.sep, "/")
                        if os.altsep:
                            arc = arc.replace(os.altsep, "/")
                        zout.write(full, arc)
        return output_path
