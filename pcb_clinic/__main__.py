# -*- coding: utf-8 -*-
"""命令行入口：pcb-clinic check board.zip"""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from .board import load_board
from .report import render_report, render_svg
from .rules import analyze


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pcb-clinic", description="PCB 打样前体检")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="检查一块板")
    check.add_argument("source", help="Gerber 目录或 zip")
    check.add_argument("--layers", type=int, default=2, help="层数，默认 2")
    check.add_argument("--qty", type=int, default=5, help="打样片数，默认 5")
    check.add_argument("--out", default="pcb-report.html", help="HTML 报告路径")
    check.add_argument("--json", action="store_true", help="同时打印 JSON 摘要")
    args = parser.parse_args(argv)

    if args.command == "check":
        layers, drills, warnings, workdir = load_board(args.source)
        result = analyze(layers, drills, layers_count=args.layers, qty=args.qty)
        meta = {"name": Path(args.source).stem, "layers": args.layers, "qty": args.qty}
        svg = render_svg(layers, drills)
        report = render_report(result, svg, meta)
        Path(args.out).write_text(report, encoding="utf-8")
        print("结论：%s" % result["verdict_text"])
        print("尺寸：%s × %s mm / 面积 %s cm²" % (
            result["metrics"].get("width_mm"), result["metrics"].get("height_mm"),
            result["metrics"].get("area_cm2")))
        print("问题：阻断 %d / 提醒 %d" % (result["blocker_count"], result["warning_count"]))
        print("粗算：¥%s（%d 片，非报价）" % (result["metrics"].get("price_estimate_cny"), args.qty))
        print("报告：%s" % Path(args.out).resolve())
        for warning in warnings:
            print("解析提醒：%s" % warning)
        if args.json:
            print(json.dumps({"verdict": result["verdict"], "metrics": result["metrics"],
                              "issues": result["issues"]}, ensure_ascii=False, indent=2))
        if str(workdir).startswith(tempfile.gettempdir()) and Path(args.source).is_file():
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
