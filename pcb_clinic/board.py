# -*- coding: utf-8 -*-
"""装载一块板：目录或 zip，识别层名并解析。"""

import os
import tempfile
import zipfile
from pathlib import Path

from .excellon import parse_excellon
from .gerber import parse_gerber


_LAYER_PATTERNS = [
    (("edge_cuts", "edge"), "Edge_Cuts"),
    (("f_cu", ".gtl"), "F_Cu"),
    (("b_cu", ".gbl"), "B_Cu"),
    (("f_mask", ".gts"), "F_Mask"),
    (("b_mask", ".gbs"), "B_Mask"),
    (("f_silkscreen", ".gto"), "F_Silkscreen"),
    (("b_silkscreen", ".gbo"), "B_Silkscreen"),
]


def identify(name):
    low = name.lower()
    for needles, layer in _LAYER_PATTERNS:
        if any(needle in low for needle in needles):
            return layer
    return None


def _files(root):
    for base, _dirs, names in os.walk(root):
        for name in names:
            yield Path(base) / name


def load_board(source):
    """返回 (layers, drills, warnings, workdir)。

    workdir 是 zip 的解压目录；调用方用完后可删除。目录输入时为原目录。
    """
    source = Path(source)
    workdir = source
    temp = None
    if source.is_file() and source.suffix.lower() == ".zip":
        temp = tempfile.mkdtemp(prefix="pcb-clinic-")
        with zipfile.ZipFile(source) as archive:
            archive.extractall(temp)
        workdir = Path(temp)

    layers = {}
    drills = []
    warnings = []
    drill_files = []
    for path in _files(workdir):
        suffix = path.suffix.lower()
        if suffix in (".drl", ".xln") or (suffix == ".txt" and "drill" in path.name.lower()):
            drill_files.append(path)
            continue
        name = identify(path.name)
        if name and suffix in (".gbr", ".ger", ".gtl", ".gbl", ".gts", ".gbs", ".gto", ".gbo"):
            try:
                layers[name] = parse_gerber(path, name)
            except Exception as exc:
                warnings.append("%s 解析失败：%s" % (path.name, exc))
        elif suffix in (".gbr", ".ger", ".gtl", ".gbl", ".gts", ".gbs", ".gto", ".gbo"):
            warnings.append("未识别的层：%s" % path.name)

    for path in drill_files:
        try:
            drills.extend(parse_excellon(path))
        except Exception as exc:
            warnings.append("%s 解析失败：%s" % (path.name, exc))

    if not drill_files:
        warnings.append("没有找到钻孔文件（.drl / .xln）")
    return layers, drills, warnings, workdir
