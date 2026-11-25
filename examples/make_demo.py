# -*- coding: utf-8 -*-
"""生成一块 40 x 30 mm 的示例双面板，用来跑通解析、规则和报告。

完全用 RS-274X / Excellon 文本生成，不依赖 KiCad。
"""

from pathlib import Path

HEADER = "%FSLAX46Y46*%\n%MOMM*%\n"


def xy(x, y):
    return "X%dY%d" % (round(x * 1e6), round(y * 1e6))


def gerber(path, body):
    path.write_text(HEADER + body + "\nM02*\n", encoding="utf-8")


def build(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    # 板框：40 x 30，闭合矩形
    edge = [
        "%ADD14C,0.100*%", "D14*",
        xy(0, 0) + "D02*", xy(40, 0) + "D01*", xy(40, 30) + "D01*",
        xy(0, 30) + "D01*", xy(0, 0) + "D01*",
    ]
    gerber(out / "Edge_Cuts.gbr", "\n".join(edge))

    # 顶层铜：0.25mm 走线 + 1.5x1.0 焊盘
    fcu = [
        "%ADD10C,0.250*%", "D10*",
        xy(5, 5) + "D02*", xy(35, 5) + "D01*",
        xy(5, 10) + "D02*", xy(35, 10) + "D01*",
        xy(20, 5) + "D02*", xy(20, 20) + "D01*",
        "%ADD11R,1.500X1.000*%", "D11*",
    ]
    for x, y in [(5, 5), (35, 5), (5, 10), (35, 10), (20, 15), (20, 20)]:
        fcu.append(xy(x, y) + "D03*")
    gerber(out / "F_Cu.gbr", "\n".join(fcu))

    bcu = [
        "%ADD15C,0.300*%", "D15*",
        xy(5, 25) + "D02*", xy(35, 25) + "D01*",
        xy(10, 15) + "D02*", xy(10, 25) + "D01*",
        "%ADD16R,1.500X1.000*%", "D16*",
    ]
    for x, y in [(5, 25), (35, 25), (10, 15)]:
        bcu.append(xy(x, y) + "D03*")
    gerber(out / "B_Cu.gbr", "\n".join(bcu))

    mask = ["%ADD12C,1.600*%", "D12*"]
    for x, y in [(5, 5), (35, 5), (5, 10), (35, 10), (20, 15), (20, 20),
                 (5, 25), (35, 25), (10, 15)]:
        mask.append(xy(x, y) + "D03*")
    gerber(out / "F_Mask.gbr", "\n".join(mask))
    gerber(out / "B_Mask.gbr", "\n".join(mask))

    silk = [
        "%ADD13C,0.150*%", "D13*",
        xy(2, 28) + "D02*", xy(38, 28) + "D01*",
        xy(2, 2) + "D02*", xy(2, 2.6) + "D01*",
    ]
    gerber(out / "F_Silkscreen.gbr", "\n".join(silk))

    drill = """M48
METRIC,TZ
T1C0.400
T2C0.800
%
T1
X5.0Y5.0
X35.0Y5.0
X5.0Y10.0
X35.0Y10.0
T2
X20.0Y15.0
X20.0Y20.0
M30
"""
    (out / "demo.drl").write_text(drill, encoding="utf-8")
    return out


if __name__ == "__main__":
    build(Path(__file__).resolve().parent / "demo-board")
