# -*- coding: utf-8 -*-
"""一个够用的 RS-274X 解析器：支持 DRAW/FLASH/REGION 和常见光圈。

不追求完整 Gerber 规范：圆弧按直线近似、宏光圈不支持，遇到会记录警告。
对 2 层 DIY 板的打样预审，这些已经够抓住大多数翻车点。
"""

import re
from pathlib import Path

from .model import Aperture, Flash, Layer, Region, Segment

_ADD_RE = re.compile(r"ADD(\d+)([A-Z]+),([0-9.X]+)")
_FS_RE = re.compile(r"FS([LT])([AI])X(\d)(\d)Y(\d)(\d)")
_COORD_RE = re.compile(r"([XY])([+-]?\d+)")


def parse_gerber(path, name=None):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    layer_name = name or Path(path).stem
    layer = Layer(layer_name)
    warnings = []

    scale = 1e6
    unit = "mm"
    apertures = {}
    current_aperture = None
    current = (0.0, 0.0)
    in_region = False
    region_points = []

    for raw in text.replace("\r", "").split("*"):
        token = raw.replace("%", "").strip()
        if not token:
            continue

        if token.startswith("FS"):
            match = _FS_RE.search(token)
            if match:
                decimal = int(match.group(4))
                scale = 10 ** decimal
            continue
        if token.startswith("MO"):
            unit = "inch" if "IN" in token else "mm"
            if unit == "inch":
                scale = scale / 25.4
            continue
        if token.startswith("ADD"):
            match = _ADD_RE.search(token)
            if match:
                code = int(match.group(1))
                shape = match.group(2)
                params = [float(part) for part in match.group(3).split("X")]
                apertures[code] = Aperture(code, shape, params)
            continue
        if token in ("G01", "G02", "G03", "G04"):
            if token == "G04":
                continue
            continue
        if token == "G36":
            in_region = True
            region_points = []
            continue
        if token == "G37":
            if len(region_points) >= 3:
                layer.regions.append(Region(region_points[:], layer_name))
            in_region = False
            region_points = []
            continue
        if token in ("M02", "M00"):
            break

        if token.startswith("D") and token[1:].isdigit():
            code = int(token[1:])
            if code >= 10:
                if code in apertures:
                    current_aperture = apertures[code]
                else:
                    warnings.append("未定义光圈 D%d" % code)
                continue
            if code in (1, 2, 3):
                continue

        coords = dict(_COORD_RE.findall(token))
        operation = None
        for code, name_op in (("D01", "draw"), ("D02", "move"), ("D03", "flash")):
            if code in token:
                operation = name_op
                break
        new_x = current[0]
        new_y = current[1]
        if "X" in coords:
            new_x = int(coords["X"]) / scale
        if "Y" in coords:
            new_y = int(coords["Y"]) / scale
        if not coords and operation is None:
            continue

        if operation == "move":
            if in_region:
                region_points = [(new_x, new_y)]
            current = (new_x, new_y)
            continue
        if operation == "draw":
            if in_region:
                region_points.append((new_x, new_y))
            elif current_aperture is not None:
                layer.segments.append(Segment(current[0], current[1], new_x, new_y,
                                              current_aperture.width, layer_name))
            current = (new_x, new_y)
            continue
        if operation == "flash":
            if current_aperture is not None:
                layer.flashes.append(Flash(new_x, new_y, current_aperture, layer_name))
            current = (new_x, new_y)
            continue
        current = (new_x, new_y)

    if in_region and len(region_points) >= 3:
        layer.regions.append(Region(region_points[:], layer_name))
    layer.warnings = warnings
    return layer
