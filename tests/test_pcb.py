# -*- coding: utf-8 -*-
import shutil
import zipfile
from pathlib import Path

from pcb_clinic.board import load_board
from pcb_clinic.excellon import parse_excellon
from pcb_clinic.gerber import parse_gerber
from pcb_clinic.report import render_report, render_svg
from pcb_clinic.rules import analyze

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo-board"


def test_parse_gerber_counts_and_bbox():
    layer = parse_gerber(DEMO / "F_Cu.gbr", "F_Cu")
    assert len(layer.segments) == 3
    assert len(layer.flashes) == 6
    box = layer.bbox()
    assert box[0] < 5 and box[2] > 35


def test_parse_excellon():
    drills = parse_excellon(DEMO / "demo.drl")
    assert len(drills) == 6
    assert {round(d.diameter, 2) for d in drills} == {0.4, 0.8}


def test_demo_board_passes_and_price():
    layers, drills, warnings, _ = load_board(DEMO)
    result = analyze(layers, drills, layers_count=2, qty=5)
    assert warnings == []
    assert result["verdict"] == "pass"
    assert result["metrics"]["width_mm"] == 40.0
    assert result["metrics"]["height_mm"] == 30.0
    assert result["metrics"]["min_trace_mm"] == 0.25
    assert result["metrics"]["min_drill_mm"] == 0.4
    assert result["metrics"]["price_estimate_cny"] > 0


def test_missing_outline_blocks(tmp_path):
    shutil.copy(DEMO / "F_Cu.gbr", tmp_path / "F_Cu.gbr")
    layers, drills, warnings, _ = load_board(tmp_path)
    result = analyze(layers, drills)
    assert result["verdict"] == "blocked"
    assert result["blocker_count"] >= 1
    assert any(item["code"] == "missing_layer" for item in result["issues"])


def test_thin_trace_warning(tmp_path):
    text = (DEMO / "F_Cu.gbr").read_text(encoding="utf-8").replace("ADD10C,0.250", "ADD10C,0.100")
    (tmp_path / "F_Cu.gbr").write_text(text, encoding="utf-8")
    for name in ("B_Cu.gbr", "F_Mask.gbr", "B_Mask.gbr", "Edge_Cuts.gbr"):
        shutil.copy(DEMO / name, tmp_path / name)
    layers, drills, _, _ = load_board(tmp_path)
    result = analyze(layers, drills)
    assert result["verdict"] == "review"
    assert any(item["code"] == "thin_trace" for item in result["issues"])


def test_zip_source(tmp_path):
    archive = tmp_path / "board.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for path in DEMO.iterdir():
            handle.write(path, path.name)
    layers, drills, warnings, workdir = load_board(archive)
    assert len(layers) == 6
    assert len(drills) == 6
    assert warnings == []


def test_svg_and_report():
    layers, drills, _, _ = load_board(DEMO)
    result = analyze(layers, drills)
    svg = render_svg(layers, drills)
    assert "<svg" in svg and "Edge_Cuts" not in svg
    html_text = render_report(result, svg, {"name": "demo", "layers": 2, "qty": 5})
    assert "打样门诊" in html_text
    assert "可以打样" in html_text
