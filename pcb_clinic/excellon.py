# -*- coding: utf-8 -*-
"""Excellon 钻孔文件解析（十进制坐标，METRIC/INCH）。"""

import re
from pathlib import Path

from .model import Drill

_TOOL_RE = re.compile(r"T(\d+)C([0-9.]+)")
_HOLE_RE = re.compile(r"X([+-]?[0-9.]+)Y([+-]?[0-9.]+)")


def parse_excellon(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    tools = {}
    holes = []
    current_tool = None
    unit = "mm"
    for raw in text.replace("\r", "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("METRIC"):
            unit = "mm"
            continue
        if line.startswith("INCH"):
            unit = "inch"
            continue
        match = _TOOL_RE.search(line)
        if match:
            tools[match.group(1)] = float(match.group(2))
            continue
        if line.startswith("T") and line[1:].isdigit():
            current_tool = line[1:]
            continue
        match = _HOLE_RE.search(line)
        if match and current_tool in tools:
            diameter = tools[current_tool]
            if unit == "inch":
                diameter *= 25.4
            x = float(match.group(1))
            y = float(match.group(2))
            if unit == "inch":
                x *= 25.4
                y *= 25.4
            holes.append(Drill(x, y, diameter, "T" + current_tool))
    return holes
