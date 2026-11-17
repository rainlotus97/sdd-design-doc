#!/usr/bin/env python3
"""Generic declarative JSON -> clean SVG/HTML diagram renderer for SDD documents."""
import argparse
import html
import json
import os
import sys


def configure_stdio():
    """Ensure UTF-8 console output on Windows legacy codepages."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def text_width_px(s: str, font_size: float = 13.0) -> float:
    w = 0.0
    for ch in s:
        if ord(ch) > 127:
            w += font_size * 1.02
        elif ch in "WM@#%&":
            w += font_size * 0.78
        elif ch in "iljtI.,:;!|()[] ":
            w += font_size * 0.38
        else:
            w += font_size * 0.61
    return w


def esc(s: str) -> str:
    return html.escape(str(s))


def svg_wrap(width: int, height: int, title: str, body: str) -> str:
    title_el = (
        f'<text x="{width/2}" y="26" text-anchor="middle" font-size="16" font-weight="700" fill="#1E3A5F">{esc(title)}</text>'
        if title else ''
    )
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #FFFFFF;
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Helvetica Neue", Arial, sans-serif;
    display: inline-block;
  }}
  svg {{ display: block; background: #FFFFFF; }}
</style>
</head>
<body>
<svg id="diagram" xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#3B4D63"/>
    </marker>
    <marker id="arrow-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#2E74B5"/>
    </marker>
    <marker id="arrow-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#C62828"/>
    </marker>
    <marker id="arrow-amber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#D97706"/>
    </marker>
    <marker id="arrow-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#059669"/>
    </marker>
    <marker id="open-arrow" viewBox="0 0 12 10" refX="11" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <path d="M 1 1 L 11 5 L 1 9" fill="none" stroke="#0F766E" stroke-width="1.6"/>
    </marker>
    <marker id="tri-empty" viewBox="0 0 12 12" refX="11" refY="6" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
      <path d="M 1 1 L 11 6 L 1 11 z" fill="#FFFFFF" stroke="#2E74B5" stroke-width="1.5"/>
    </marker>
    <marker id="diamond-fill" viewBox="0 0 14 10" refX="1" refY="5" markerWidth="10" markerHeight="8" orient="auto">
      <path d="M 1 5 L 7 1 L 13 5 L 7 9 z" fill="#2E74B5" stroke="#2E74B5" stroke-width="1.4"/>
    </marker>
    <marker id="diamond-open" viewBox="0 0 14 10" refX="1" refY="5" markerWidth="10" markerHeight="8" orient="auto">
      <path d="M 1 5 L 7 1 L 13 5 L 7 9 z" fill="#FFFFFF" stroke="#2E74B5" stroke-width="1.4"/>
    </marker>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#1E293B" flood-opacity="0.08"/>
    </filter>
  </defs>
  <rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>
  {title_el}
  {body}
</svg>
</body>
</html>"""


THEME_STYLES = {
    "start": ("#E8F5E9", "#2E7D32", "#1B5E20", 22),
    "end": ("#E8F5E9", "#2E7D32", "#1B5E20", 22),
    "process": ("#E3F2FD", "#1976D2", "#1E3A5F", 6),
    "decision": ("#FFF7ED", "#D97706", "#7C2D12", 0),
    "warn": ("#FFF7ED", "#D97706", "#7C2D12", 6),
    "error": ("#FFEBEE", "#C62828", "#7F1D1D", 6),
    "muted": ("#F1F5F9", "#475569", "#1E293B", 6),
    "purple": ("#F5F3FF", "#7C3AED", "#4C1D95", 6),
    "green": ("#ECFDF5", "#059669", "#064E3B", 6),
}


def draw_box(x, y, w, h, lines, fill="#E3F2FD", stroke="#1976D2", text_color="#1E3A5F",
             rx=6, font_size=12.5, bold_first=True, dash=""):
    dash_attr = f'stroke-dasharray="{dash}"' if dash else ''
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5" {dash_attr} filter="url(#shadow)"/>']
    line_h = font_size + 5
    total_h = len(lines) * line_h
    start_y = y + (h - total_h) / 2 + font_size * 0.85
    for idx, line in enumerate(lines):
        fw = "700" if (bold_first and idx == 0) else "500"
        col = text_color if (idx == 0 or not bold_first) else "#475569"
        fs = font_size if (idx == 0 or not bold_first) else max(11.0, font_size - 1.0)
        parts.append(f'<text x="{x + w/2}" y="{start_y + idx*line_h:.1f}" text-anchor="middle" font-size="{fs}" font-weight="{fw}" fill="{col}">{esc(line)}</text>')
    return "\n".join(parts)


def draw_diamond(cx, cy, w, h, lines, fill="#FFF7ED", stroke="#D97706", text_color="#7C2D12", font_size=12.0):
    pts = f"{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}"
    parts = [f'<polygon points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="1.6" filter="url(#shadow)"/>']
    line_h = font_size + 4
    total_h = len(lines) * line_h
    start_y = cy - total_h / 2 + font_size * 0.85
    for idx, line in enumerate(lines):
        parts.append(f'<text x="{cx}" y="{start_y + idx*line_h:.1f}" text-anchor="middle" font-size="{font_size}" font-weight="600" fill="{text_color}">{esc(line)}</text>')
    return "\n".join(parts)


def draw_arrow(pts, label="", label_pos=None, stroke="#3B4D63", marker="url(#arrow)", dash="", font_size=11.5):
    d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    dash_attr = f'stroke-dasharray="{dash}"' if dash else ''
    out = [f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="1.6" {dash_attr} marker-end="{marker}"/>']
    if label:
        if label_pos is None:
            mid = pts[len(pts)//2]
            prev = pts[max(0, len(pts)//2 - 1)]
            lx, ly = (mid[0] + prev[0]) / 2, (mid[1] + prev[1]) / 2
        else:
            lx, ly = label_pos
        tw = text_width_px(label, font_size) + 10
        out.append(f'<rect x="{lx - tw/2:.1f}" y="{ly - 10:.1f}" width="{tw:.1f}" height="18" rx="3" fill="#FFFFFF" fill-opacity="0.94"/>')
        out.append(f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="middle" font-size="{font_size}" font-weight="500" fill="{stroke}">{esc(label)}</text>')
    return "\n".join(out)


def render_flowchart(spec: dict) -> str:
    width = int(spec.get("width", 1000))
    height = int(spec.get("height", 620))
    title = spec.get("title", "")
    p = []

    for grp in spec.get("groups", []):
        gx, gy, gw, gh = grp["x"], grp["y"], grp["w"], grp["h"]
        bg = grp.get("fill", "#F8FAFC")
        bd = grp.get("stroke", "#2E74B5")
        dash = grp.get("dash", "5,3")
        p.append(f'<rect x="{gx}" y="{gy}" width="{gw}" height="{gh}" rx="8" fill="{bg}" stroke="{bd}" stroke-width="1.5" stroke-dasharray="{dash}"/>')
        if grp.get("label"):
            p.append(f'<text x="{gx + 16}" y="{gy + 22}" font-size="13" font-weight="700" fill="{bd}">{esc(grp["label"])}</text>')

    anchors = {}
    for nd in spec.get("nodes", []):
        nid = nd["id"]
        kind = nd.get("kind", "process")
        lines = nd.get("lines", [nd.get("label", nid)])
        fill, stroke, tcol, default_rx = THEME_STYLES.get(kind, THEME_STYLES["process"])
        fill = nd.get("fill", fill)
        stroke = nd.get("stroke", stroke)
        tcol = nd.get("textColor", tcol)
        fs = float(nd.get("fontSize", 12))

        if kind == "decision":
            cx, cy = nd["cx"], nd["cy"]
            min_w = max(text_width_px(l, fs) for l in lines) * 1.45 + 48
            w = max(nd.get("w", 200), min_w)
            h = max(nd.get("h", 64), len(lines) * (fs + 5) + 30)
            p.append(draw_diamond(cx, cy, w, h, lines, fill, stroke, tcol, fs))
            anchors[nid] = {
                "top": (cx, cy - h/2), "bottom": (cx, cy + h/2),
                "left": (cx - w/2, cy), "right": (cx + w/2, cy), "center": (cx, cy),
            }
        else:
            x, y = nd["x"], nd["y"]
            min_w = max(text_width_px(l, fs) for l in lines) + 28
            w = max(nd.get("w", 200), min_w)
            h = max(nd.get("h", 52), len(lines) * (fs + 5) + 20)
            rx = nd.get("rx", default_rx)
            p.append(draw_box(x, y, w, h, lines, fill, stroke, tcol, rx=rx, font_size=fs))
            anchors[nid] = {
                "top": (x + w/2, y), "bottom": (x + w/2, y + h),
                "left": (x, y + h/2), "right": (x + w, y + h/2), "center": (x + w/2, y + h/2),
            }

    for ed in spec.get("edges", []):
        if "points" in ed:
            pts = ed["points"]
        else:
            src_pt = anchors[ed["from"]][ed.get("fromSide", "bottom")]
            dst_pt = anchors[ed["to"]][ed.get("toSide", "top")]
            via = ed.get("via", [])
            pts = [src_pt] + via + [dst_pt]
        col = ed.get("color", "#3B4D63")
        mk = ed.get("marker", "url(#arrow)")
        if col == "#C62828":
            mk = "url(#arrow-red)"
        elif col == "#D97706":
            mk = "url(#arrow-amber)"
        elif col == "#2E74B5":
            mk = "url(#arrow-blue)"
        elif col == "#059669":
            mk = "url(#arrow-green)"
        p.append(draw_arrow(pts, ed.get("label", ""), ed.get("labelPos"), stroke=col, marker=mk, dash=ed.get("dash", "")))

    return svg_wrap(width, height, title, "\n".join(p))


def render_sequence(spec: dict) -> str:
    width = int(spec.get("width", 1080))
    height = int(spec.get("height", 640))
    title = spec.get("title", "")
    parts = spec.get("participants", [])
    margin_x = float(spec.get("marginX", 88))
    step_x = (width - 2 * margin_x) / max(1, len(parts) - 1)
    xs = [margin_x + i * step_x for i in range(len(parts))]
    id_to_idx = {p.get("id", p["label"]): i for i, p in enumerate(parts)}
    top_y = 52
    bot_y = height - 24
    out = []

    for fr in spec.get("frames", []):
        fx, fy, fw, fh = fr["x"], fr["y"], fr["w"], fr["h"]
        flabel = fr["label"]
        fbg = fr.get("fill", "#F8FAFC")
        fbd = fr.get("stroke", "#2E74B5")
        out.append(f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="4" fill="{fbg}" stroke="{fbd}" stroke-width="1.3" stroke-dasharray="5,3"/>')
        tw = text_width_px(flabel, 11) + 18
        out.append(f'<path d="M {fx} {fy} L {fx+tw} {fy} L {fx+tw-8} {fy+20} L {fx} {fy+20} Z" fill="{fbd}"/>')
        out.append(f'<text x="{fx+8}" y="{fy+14}" font-size="11" font-weight="700" fill="#FFFFFF">{esc(flabel)}</text>')

    for idx, pt in enumerate(parts):
        cx = xs[idx]
        lbl = pt["label"]
        out.append(f'<line x1="{cx}" y1="{top_y+42}" x2="{cx}" y2="{bot_y}" stroke="#94A3B8" stroke-width="1.4" stroke-dasharray="5,4"/>')
        bw = max(116, text_width_px(lbl, 12) + 22)
        out.append(draw_box(cx - bw/2, top_y, bw, 40, [lbl], fill="#2E74B5", stroke="#1E3A5F", text_color="#FFFFFF", rx=5, font_size=12))

    for m in spec.get("messages", []):
        kind = m.get("kind", "msg")
        y = m["y"]
        if kind == "note":
            x1 = m.get("x", 60)
            x2 = m.get("x2", width - 60)
            nw = x2 - x1
            bg = m.get("fill", "#EFF6FF")
            bd = m.get("stroke", "#2E74B5")
            out.append(f'<rect x="{x1}" y="{y}" width="{nw}" height="24" rx="4" fill="{bg}" stroke="{bd}" stroke-width="1.2"/>')
            out.append(f'<text x="{x1+nw/2}" y="{y+16}" text-anchor="middle" font-size="11.5" font-weight="600" fill="#334155">{esc(m["label"])}</text>')
        else:
            src = id_to_idx[m["from"]]
            dst = id_to_idx[m["to"]]
            x1, x2 = xs[src], xs[dst]
            lbl = m["label"]
            col = m.get("color", "#3B4D63")
            dashed = bool(m.get("dashed", False))
            if src == dst:
                out.append(f'<path d="M {x1} {y} L {x1+44} {y} L {x1+44} {y+18} L {x1} {y+18}" fill="none" stroke="{col}" stroke-width="1.5" marker-end="url(#arrow)"/>')
                out.append(f'<text x="{x1+50}" y="{y+13}" font-size="11.5" font-weight="500" fill="#1E293B">{esc(lbl)}</text>')
            else:
                mk = "url(#arrow-red)" if col == "#C62828" else ("url(#arrow-blue)" if col == "#2E74B5" else ("url(#arrow-amber)" if col == "#D97706" else ("url(#arrow-green)" if col == "#059669" else "url(#arrow)")))
                dash_attr = 'stroke-dasharray="5,3"' if dashed else ''
                out.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="{col}" stroke-width="1.5" {dash_attr} marker-end="{mk}"/>')
                mx = (x1 + x2) / 2
                tw = text_width_px(lbl, 11.5) + 8
                out.append(f'<rect x="{mx - tw/2}" y="{y-16}" width="{tw}" height="15" rx="2" fill="#FFFFFF" fill-opacity="0.92"/>')
                out.append(f'<text x="{mx}" y="{y-4}" text-anchor="middle" font-size="11.5" font-weight="500" fill="#1E293B">{esc(lbl)}</text>')

    return svg_wrap(width, height, title, "\n".join(out))


def render_class(spec: dict) -> str:
    width = int(spec.get("width", 1120))
    height = int(spec.get("height", 620))
    title = spec.get("title", "")
    out = []
    anchors = {}

    for cls in spec.get("classes", []):
        cid = cls["id"]
        x, y = cls["x"], cls["y"]
        cname = cls.get("name", cid)
        stereo = cls.get("stereotype", "")
        attrs = cls.get("attrs", [])
        methods = cls.get("methods", [])
        role = cls.get("role", "default")
        header_fill = "#0F766E" if "interface" in stereo.lower() or role == "interface" else (
            "#1E3A5F" if role in ("core", "facade", "singleton") else (
                "#475569" if role == "constants" else "#2E74B5"
            )
        )
        header_fill = cls.get("headerFill", header_fill)
        border = cls.get("border", header_fill)

        # Auto-fit width to longest text line so signatures never overflow!
        all_lines = attrs + methods
        calc_w = max([text_width_px(cname, 13) + 26, text_width_px(stereo, 11) + 24] + [text_width_px(l, 11) + 24 for l in all_lines])
        w = max(cls.get("w", 220), calc_w)

        head_h = 40 if stereo else 28
        line_h = 16
        attr_h = (len(attrs) * line_h + 10) if attrs else 0
        meth_h = (len(methods) * line_h + 10) if methods else 0
        total_h = head_h + attr_h + meth_h

        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{total_h}" rx="5" fill="#FFFFFF" stroke="{border}" stroke-width="1.5" filter="url(#shadow)"/>')
        out.append(f'<path d="M {x} {y+5} Q {x} {y} {x+5} {y} L {x+w-5} {y} Q {x+w} {y} {x+w} {y+5} L {x+w} {y+head_h} L {x} {y+head_h} Z" fill="{header_fill}"/>')
        if stereo:
            out.append(f'<text x="{x+w/2}" y="{y+15}" text-anchor="middle" font-size="10.5" fill="#DCEBFB">{esc(stereo)}</text>')
            out.append(f'<text x="{x+w/2}" y="{y+32}" text-anchor="middle" font-size="13" font-weight="700" fill="#FFFFFF">{esc(cname)}</text>')
        else:
            out.append(f'<text x="{x+w/2}" y="{y+19}" text-anchor="middle" font-size="13" font-weight="700" fill="#FFFFFF">{esc(cname)}</text>')

        cy = y + head_h
        if attrs:
            out.append(f'<line x1="{x}" y1="{cy}" x2="{x+w}" y2="{cy}" stroke="{border}" stroke-width="1"/>')
            for idx, a in enumerate(attrs):
                out.append(f'<text x="{x+10}" y="{cy + 16 + idx*line_h}" font-family="Consolas, Menlo, Microsoft YaHei, PingFang SC, monospace" font-size="11" fill="#1E293B">{esc(a)}</text>')
            cy += attr_h
        if methods:
            out.append(f'<line x1="{x}" y1="{cy}" x2="{x+w}" y2="{cy}" stroke="{border}" stroke-width="1"/>')
            for idx, m in enumerate(methods):
                out.append(f'<text x="{x+10}" y="{cy + 16 + idx*line_h}" font-family="Consolas, Menlo, Microsoft YaHei, PingFang SC, monospace" font-size="11" fill="#0F172A">{esc(m)}</text>')

        anchors[cid] = {
            "top": (x + w/2, y), "bottom": (x + w/2, y + total_h),
            "left": (x, y + total_h/2), "right": (x + w, y + total_h/2),
            "x": x, "y": y, "w": w, "h": total_h,
        }

    for rel in spec.get("relations", []):
        kind = rel.get("kind", "assoc")
        if "points" in rel:
            pts = rel["points"]
        else:
            src = anchors[rel["from"]][rel.get("fromSide", "bottom")]
            dst = anchors[rel["to"]][rel.get("toSide", "top")]
            pts = [src] + rel.get("via", []) + [dst]

        dash = "5,3" if kind in ("depend", "realize") else ""
        mk = "url(#tri-empty)" if kind in ("inherit", "realize") else (
            "url(#open-arrow)" if kind == "notify" else "url(#arrow-blue)"
        )
        col = "#0F766E" if kind == "notify" else "#2E74B5"
        out.append(draw_arrow(pts, rel.get("label", ""), rel.get("labelPos"), stroke=col, marker=mk, dash=dash))

    return svg_wrap(width, height, title, "\n".join(out))


def render_layers(spec: dict) -> str:
    width = int(spec.get("width", 980))
    height = int(spec.get("height", 560))
    title = spec.get("title", "")
    out = []

    for ly in spec.get("layers", []):
        y = ly["y"]
        lh = ly.get("h", 92)
        bg = ly.get("fill", "#EFF6FF")
        bd = ly.get("stroke", "#2E74B5")
        out.append(f'<rect x="30" y="{y}" width="{width-60}" height="{lh}" rx="8" fill="{bg}" stroke="{bd}" stroke-width="1.6"/>')
        out.append(f'<text x="46" y="{y+22}" font-size="13" font-weight="700" fill="{bd}">{esc(ly["title"])}</text>')
        badge = ly.get("badge", "")
        if badge:
            pw = max(90, text_width_px(badge, 11) + 22)
            px = width - 42 - pw
            out.append(f'<rect x="{px}" y="{y+8}" width="{pw}" height="20" rx="4" fill="{bd}"/>')
            out.append(f'<text x="{px + pw/2}" y="{y+22}" text-anchor="middle" font-size="11" font-weight="700" fill="#FFFFFF">{esc(badge)}</text>')

        items = ly.get("items", [])
        if items:
            avail = width - 92
            gap = 16
            bw = (avail - gap * (len(items) - 1)) / len(items)
            for idx, it in enumerate(items):
                bx = 46 + idx * (bw + gap)
                lines = it if isinstance(it, list) else [it.get("title", ""), it.get("sub", "")]
                out.append(draw_box(bx, y + 32, bw, lh - 44, [l for l in lines if l], fill="#FFFFFF", stroke=bd, text_color="#1E293B", font_size=12))

    for arr in spec.get("arrows", []):
        col = arr.get("color", "#2E74B5")
        mk = "url(#arrow-blue)" if col == "#2E74B5" else ("url(#arrow-amber)" if col == "#D97706" else "url(#arrow-green)")
        out.append(draw_arrow(arr["points"], arr.get("label", ""), arr.get("labelPos"), stroke=col, marker=mk, dash=arr.get("dash", "")))

    footer = spec.get("footer", "")
    if footer:
        fy = height - 46
        out.append(f'<rect x="30" y="{fy}" width="{width-60}" height="34" rx="6" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>')
        out.append(f'<text x="{width/2}" y="{fy+21}" text-anchor="middle" font-size="12" font-weight="600" fill="#334155">{esc(footer)}</text>')

    return svg_wrap(width, height, title, "\n".join(out))


RENDERERS = {
    "flowchart": render_flowchart,
    "sequence": render_sequence,
    "class": render_class,
    "layers": render_layers,
}


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description="Render declarative diagram JSON into HTML/SVG files.")
    parser.add_argument("spec_json", help="Path to diagrams JSON specification file")
    parser.add_argument("out_dir", help="Output directory for generated HTML files")
    args = parser.parse_args()

    with open(args.spec_json, "r", encoding="utf-8-sig") as f:
        specs = json.load(f)
    out_dir = os.path.normpath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    if isinstance(specs, dict):
        specs = [specs]
    for sp in specs:
        kind = sp["type"]
        if kind not in RENDERERS:
            raise ValueError(f"Unsupported diagram type: {kind}")
        html_str = RENDERERS[kind](sp)
        out_html = os.path.join(out_dir, f"{sp['id']}.html")
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(html_str)
        print("Generated diagram HTML:", out_html)


if __name__ == "__main__":
    main()
