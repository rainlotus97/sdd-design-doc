#!/usr/bin/env python3
"""Verify Python, Node.js, and browser/Playwright readiness for sdd-design-doc (cross-platform)."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def configure_stdio():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def run_cmd(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def check_environment():
    ok = True
    print(f"[CHECK] Platform : {sys.platform}")
    print(f"[CHECK] Python   : {sys.version.split()[0]} ({sys.executable})")

    try:
        import xml.etree.ElementTree as ET
        ET.fromstring("<root/>")
        print("[CHECK] pyexpat  : OK")
    except Exception as exc:
        print(f"[CHECK] pyexpat  : FAILED ({exc})")
        if sys.platform == "darwin" and os.path.exists("/usr/bin/python3") and sys.executable != "/usr/bin/python3":
            print("[TIP] macOS detected: run with /usr/bin/python3 (which bundles pyexpat).")
        ok = False

    node_bin = shutil.which("node")
    if not node_bin:
        print("[CHECK] Node.js  : MISSING (node not found on PATH)")
        ok = False
    else:
        nv = run_cmd([node_bin, "--version"])
        print(f"[CHECK] Node.js  : {nv.stdout.strip()} ({node_bin})")
        snap_script = os.path.join(SCRIPT_DIR, "snap_diagrams.cjs")
        res = run_cmd([node_bin, snap_script, "--check"])
        if res.stdout.strip():
            info = json.loads(res.stdout.strip())
            print(f"[CHECK] Renderer : engine={info.get('selectedEngine')}, browser={info.get('browserExecutable')}, playwright={info.get('playwright')}")
        if res.returncode != 0:
            print("[CHECK] Renderer : FAILED (no Playwright and no Chrome/Edge executable detected)")
            if res.stderr.strip():
                print(res.stderr.strip())
            ok = False

    return ok


def run_smoke_test(engine="auto", keep_docx=""):
    node_bin = shutil.which("node")
    if not node_bin:
        raise RuntimeError("node is required for --smoke-test")

    with tempfile.TemporaryDirectory(prefix="sdd-smoke-") as tmp:
        diagrams_json = os.path.join(tmp, "diagrams.json")
        diagrams_out = os.path.join(tmp, "diagrams_out")
        spec_json = os.path.join(tmp, "spec.json")
        out_docx = keep_docx if keep_docx else os.path.join(tmp, "smoke_test_sdd.docx")

        diagrams_payload = [
            {
                "id": "fig_smoke_flow",
                "type": "flowchart",
                "title": "图 1-1 跨平台自检流程图",
                "width": 860,
                "height": 340,
                "nodes": [
                    {"id": "s", "kind": "start", "x": 310, "y": 55, "w": 240, "h": 48, "lines": ["输入 JSON 规格"]},
                    {"id": "d", "kind": "decision", "cx": 430, "cy": 165, "w": 220, "h": 64, "lines": ["环境检测通过?"]},
                    {"id": "ok", "kind": "end", "x": 310, "y": 245, "w": 240, "h": 48, "lines": ["生成正式版 Word (.docx)"]},
                ],
                "edges": [
                    {"from": "s", "fromSide": "bottom", "to": "d", "toSide": "top"},
                    {"from": "d", "fromSide": "bottom", "to": "ok", "toSide": "top", "label": "通过", "color": "#059669"},
                ],
            }
        ]
        spec_payload = {
            "docTitle": "跨平台环境自检说明书（Smoke Test）",
            "headerTitle": "跨平台环境自检说明书 V1.0",
            "creator": "sdd-design-doc",
            "blocks": [
                {"type": "doc_title", "text": "跨平台环境自检说明书"},
                {
                    "type": "table",
                    "headers": ["检查项", "结果"],
                    "rows": [["Python XML 解析", "通过"], ["SVG -> PNG 渲染", "通过"]],
                    "colWidths": [3200, 6443],
                },
                {"type": "toc"},
                {"type": "heading", "level": 1, "text": "1 自检验证", "pageBreak": True, "estPage": 3, "center": True},
                {"type": "para", "text": "本文件由 check_env.py --smoke-test 自动生成，用于验证 Windows / macOS / Linux 工具链。"},
                {"type": "bullet", "boldPrefix": "流程图：", "text": "验证中文字符渲染与 PNG 嵌入。"},
                {
                    "type": "api_card",
                    "method": "POST",
                    "endpoint": "/api/v1/demo/query",
                    "summary": "示例接口卡片渲染自检",
                    "trigger": "页面初始化时触发",
                    "request": "Header: Authorization；Body: { id }",
                    "fields": [{"name": "code / data", "desc": "状态码与返回结果集合"}],
                    "display": "校验通过后刷新界面状态",
                    "fallback": "网络超时或返回异常时保留旧值并提示重试"
                },
                {"type": "code", "lines": ["python scripts/check_env.py --smoke-test"]},
                {"type": "image", "file": "fig_smoke_flow.png", "caption": "图 1-1 跨平台自检流程图"},
            ],
        }

        mod_spec_json = os.path.join(tmp, "spec_module.json")
        mod_out_docx = os.path.join(tmp, "smoke_module_sdd.docx")
        mod_payload = {
            "docTitle": "第 3 章 详细设计（自检模块）",
            "headerTitle": "第 3 章 模块设计自检 V1.0",
            "blocks": [
                {"type": "doc_title", "text": "第 3 章 详细设计（自检模块）"},
                {"type": "heading", "level": 1, "text": "3 模块详细设计", "center": True},
                {"type": "heading", "level": 2, "text": "3.1 示例可迁移模块详细设计"},
                {"type": "heading", "level": 3, "text": "3.1.1 方案概述"},
                {"type": "para", "text": "验证仅第 3 章可移植模块输出模式，不含第 1/2 章与多余目录。"},
                {
                    "type": "api_card",
                    "method": "GET",
                    "endpoint": "/api/v1/demo/status",
                    "summary": "模块模式接口卡片自检",
                    "trigger": "进页触发",
                    "fields": [{"name": "status", "desc": "运行状态"}],
                    "fallback": "超时重试并维持旧状态"
                },
                {"type": "image", "file": "fig_smoke_flow.png", "caption": "图 3-1 自检流程图"},
            ],
        }

        # Write with UTF-8 BOM on purpose to verify Windows PowerShell compatibility
        with open(diagrams_json, "w", encoding="utf-8-sig") as f:
            json.dump(diagrams_payload, f, ensure_ascii=False, indent=2)
        with open(spec_json, "w", encoding="utf-8-sig") as f:
            json.dump(spec_payload, f, ensure_ascii=False, indent=2)
        with open(mod_spec_json, "w", encoding="utf-8-sig") as f:
            json.dump(mod_payload, f, ensure_ascii=False, indent=2)

        for cmd in (
            [sys.executable, os.path.join(SCRIPT_DIR, "diagram_dsl.py"), diagrams_json, diagrams_out],
            [node_bin, os.path.join(SCRIPT_DIR, "snap_diagrams.cjs"), f"--engine={engine}", diagrams_out],
            [sys.executable, os.path.join(SCRIPT_DIR, "build_from_spec.py"), "--spec", spec_json, "--diagrams-dir", diagrams_out, "--mode", "full", "--strict-delivery", "--out", out_docx],
            [sys.executable, os.path.join(SCRIPT_DIR, "build_from_spec.py"), "--spec", mod_spec_json, "--diagrams-dir", diagrams_out, "--mode", "module", "--strict-delivery", "--out", mod_out_docx],
        ):
            res = run_cmd(cmd)
            if res.stdout:
                print(res.stdout.rstrip())
            if res.returncode != 0:
                if res.stderr:
                    print(res.stderr.rstrip(), file=sys.stderr)
                raise RuntimeError(f"Smoke test command failed: {' '.join(cmd)}")

        png_path = os.path.join(diagrams_out, "fig_smoke_flow.png")
        with open(png_path, "rb") as f:
            hdr = f.read(24)
        pw = int.from_bytes(hdr[16:20], "big")
        ph = int.from_bytes(hdr[20:24], "big")
        print(f"[SMOKE] PNG dimensions: {pw}x{ph} px")

        with zipfile.ZipFile(out_docx, "r") as z:
            bad = [n for n in z.namelist() if "\\" in n]
            if bad:
                raise RuntimeError(f"Non-POSIX zip paths detected in docx: {bad}")
        print(f"[SMOKE] PASSED (engine={engine}, docx={out_docx})")


def main():
    configure_stdio()
    parser = argparse.ArgumentParser(description="Check environment and optionally run smoke test.")
    parser.add_argument("--smoke-test", action="store_true", help="Run end-to-end HTML -> PNG -> DOCX test")
    parser.add_argument("--engine", default="auto", choices=["auto", "playwright", "cdp"], help="Renderer engine for smoke test")
    parser.add_argument("--out", default="", help="Optional path to keep generated smoke-test .docx")
    args = parser.parse_args()

    ok = check_environment()
    if not ok:
        sys.exit(2)
    if args.smoke_test:
        run_smoke_test(engine=args.engine, keep_docx=args.out)


if __name__ == "__main__":
    main()
