# -*- coding: utf-8 -*-
"""把板子画成 SVG，并生成可存档的 HTML 体检报告。"""

import html

from .model import bbox_union

_COLORS = {
    "B_Cu": "#ff8a4c",
    "F_Cu": "#35d6c4",
    "F_Mask": "#8b5cf6",
    "B_Mask": "#8b5cf6",
    "F_Silkscreen": "#e5e7eb",
    "B_Silkscreen": "#cbd5e1",
    "Edge_Cuts": "#ffb84d",
}


def _edge_bbox(layers):
    edge = layers.get("Edge_Cuts")
    if edge and edge.segments:
        xs = [v for seg in edge.segments for v in (seg.x1, seg.x2)]
        ys = [v for seg in edge.segments for v in (seg.y1, seg.y2)]
        return min(xs), min(ys), max(xs), max(ys)
    boxes = [layer.bbox() for layer in layers.values()]
    return bbox_union(boxes)


def render_svg(layers, drills, width=960):
    bbox = _edge_bbox(layers)
    if not bbox:
        return "<svg xmlns='http://www.w3.org/2000/svg' width='960' height='300'></svg>"
    min_x, min_y, max_x, max_y = bbox
    margin = 4.0
    board_w = max(max_x - min_x, 0.1)
    board_h = max(max_y - min_y, 0.1)
    scale = width / (board_w + margin * 2)
    height = int((board_h + margin * 2) * scale)

    def px(x, y):
        return ((x - min_x + margin) * scale, (max_y - y + margin) * scale)

    parts = [
        "<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' viewBox='0 0 %d %d'>" % (width, height, width, height),
        "<rect width='100%' height='100%' fill='#080d18'/>",
        "<rect x='%0.2f' y='%0.2f' width='%0.2f' height='%0.2f' fill='#0c1423' stroke='#1d2a42'/>" % (
            margin * scale, margin * scale, board_w * scale, board_h * scale),
    ]

    for name in ("B_Cu", "F_Mask", "B_Mask", "F_Cu", "F_Silkscreen", "B_Silkscreen"):
        layer = layers.get(name)
        if not layer:
            continue
        color = _COLORS.get(name, "#888")
        opacity = "0.18" if "Mask" in name else "0.9"
        for region in layer.regions:
            pts = " ".join("%0.2f,%0.2f" % px(x, y) for x, y in region.points)
            parts.append("<polygon points='%s' fill='%s' fill-opacity='%s'/>" % (pts, color, opacity))
        for seg in layer.segments:
            x1, y1 = px(seg.x1, seg.y1)
            x2, y2 = px(seg.x2, seg.y2)
            stroke_w = max(seg.width * scale, 1.2)
            parts.append("<line x1='%0.2f' y1='%0.2f' x2='%0.2f' y2='%0.2f' stroke='%s' stroke-width='%0.2f' stroke-opacity='%s'/>" % (
                x1, y1, x2, y2, color, stroke_w, opacity))
        for flash in layer.flashes:
            x, y = px(flash.x, flash.y)
            w, h = flash.aperture.size()
            if flash.aperture.shape == "C":
                parts.append("<circle cx='%0.2f' cy='%0.2f' r='%0.2f' fill='%s' fill-opacity='%s'/>" % (
                    x, y, max(w * scale / 2, 1.0), color, opacity))
            else:
                parts.append("<rect x='%0.2f' y='%0.2f' width='%0.2f' height='%0.2f' rx='%0.2f' fill='%s' fill-opacity='%s'/>" % (
                    x - w * scale / 2, y - h * scale / 2, w * scale, h * scale,
                    min(w, h) * scale / 4, color, opacity))

    edge = layers.get("Edge_Cuts")
    if edge:
        for seg in edge.segments:
            x1, y1 = px(seg.x1, seg.y1)
            x2, y2 = px(seg.x2, seg.y2)
            parts.append("<line x1='%0.2f' y1='%0.2f' x2='%0.2f' y2='%0.2f' stroke='%s' stroke-width='2'/>" % (
                x1, y1, x2, y2, _COLORS["Edge_Cuts"]))

    for drill in drills:
        x, y = px(drill.x, drill.y)
        r = max(drill.diameter * scale / 2, 1.4)
        parts.append("<circle cx='%0.2f' cy='%0.2f' r='%0.2f' fill='#05070c' stroke='#dbe7ff' stroke-width='1'/>" % (x, y, r))

    parts.append("</svg>")
    return "\n".join(parts)


def render_report(analysis, svg, meta=None):
    meta = meta or {}
    issues = analysis["issues"]
    metrics = analysis["metrics"]
    issue_html = []
    if issues:
        for item in issues:
            issue_html.append("""
        <article class="issue %s">
          <div class="issue-head"><span>%s</span><b>%s</b></div>
          <p>%s</p>
        </article>""" % (item["severity"], html.escape(item["severity"].upper()), html.escape(item["title"]),
                            html.escape(item["detail"])))
    else:
        issue_html.append("<div class='clean'>没有发现阻断项。可以打样，但仍建议让板厂做最终 DFM。</div>")
    note = html.escape(metrics.get("price_note", ""))
    title = html.escape(meta.get("name", "未命名板"))
    verdict_class = analysis["verdict"]
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s · 打样门诊</title>
<style>
:root{--bg:#070b15;--panel:#0d1526;--line:#1c2b47;--text:#dbe7ff;--muted:#7d8fae;--cyan:#35d6c4;--amber:#ffb84d;--red:#ff5d6c;--violet:#8b5cf6}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1000px 600px at 75%% -10%%,#10284a,#070b15 60%%);color:var(--text);font-family:"Segoe UI","Noto Sans SC",sans-serif}
.wrap{width:min(1180px,calc(100%% - 40px));margin:34px auto 70px}.top{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:18px}
.brand b{font-size:24px;letter-spacing:.08em}.brand small{display:block;color:var(--muted);font:11px monospace;letter-spacing:.18em;margin-top:5px}
.stamp{font:12px monospace;border:1px solid;padding:8px 12px;border-radius:5px;transform:rotate(-2deg)}.pass{color:var(--cyan)}.review{color:var(--amber)}.blocked{color:var(--red)}
.grid{display:grid;grid-template-columns:1.2fr .8fr;gap:20px;margin-top:22px}.panel{background:linear-gradient(180deg,#111d33,#0b1220);border:1px solid var(--line);border-radius:14px;padding:20px}
h1{font-size:20px;margin:0 0 14px}.meta{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:14px 0}.metric{border:1px solid var(--line);border-radius:9px;padding:12px}.metric small{display:block;color:var(--muted);font-size:11px}.metric b{font:22px monospace;color:var(--cyan);display:block;margin-top:6px}
.board{overflow:hidden;border:1px solid var(--line);border-radius:10px;background:#080d18}.board svg{display:block;width:100%%;height:auto}
.issues{display:grid;gap:10px;margin-top:16px}.issue{border:1px solid var(--line);border-left:3px solid var(--muted);border-radius:8px;padding:12px 14px;background:#0a1220}.issue.blocker{border-left-color:var(--red)}.issue.warning{border-left-color:var(--amber)}.issue.info{border-left-color:var(--violet)}
.issue-head{display:flex;gap:10px;align-items:center}.issue-head span{font:10px monospace;color:var(--muted);letter-spacing:.1em}.issue-head b{font-size:14px}.issue p{color:var(--muted);font-size:12px;line-height:1.7;margin:7px 0 0}
.clean{border:1px solid #1e5c53;background:#09201d;color:var(--cyan);border-radius:8px;padding:13px;font-size:13px}
.price{display:flex;align-items:baseline;gap:10px;margin-top:10px}.price b{font:34px monospace;color:var(--amber)}.price span{color:var(--muted);font-size:12px}
.note{color:var(--muted);font-size:12px;line-height:1.7;margin-top:12px}.foot{color:var(--muted);font:11px monospace;margin-top:18px}
@media(max-width:850px){.grid{grid-template-columns:1fr}.meta{grid-template-columns:1fr 1fr}}
</style></head><body><div class="wrap">
<header class="top"><div class="brand"><b>打样门诊</b><small>PCB PREFLIGHT / DFM CHECK</small></div><div class="stamp %s">%s</div></header>
<main class="grid"><section class="panel"><h1>%s</h1>
<div class="meta">
<div class="metric"><small>板框尺寸</small><b>%s × %s mm</b></div>
<div class="metric"><small>面积</small><b>%s cm²</b></div>
<div class="metric"><small>层数 / 片数</small><b>%s / %s</b></div>
</div>
<div class="board">%s</div>
<h1 style="margin-top:22px">发现 %d 个问题</h1><div class="issues">%s</div></section>
<section class="panel"><h1>处置建议</h1><div class="price"><b>¥%s</b><span>粗算 / %s 片</span></div><p class="note">%s</p>
<h3>关键指标</h3><p class="note">最细铜线 %s mm<br>最小钻孔 %s mm<br>钻孔数量 %s<br>阻断项 %s / 提醒 %s</p>
<h3>怎么用</h3><p class="note">把这份报告连同 Gerber 一起发给板厂，或者在嘉立创下单前先对照修改。它不是工厂 DFM 的替代品，最终能不能做以板厂审核为准。</p>
<div class="foot">generated by pcb-clinic · 本地解析，不上传板文件</div></section></main></div></body></html>""" % (
        title, verdict_class, html.escape(analysis["verdict_text"]), title,
        metrics.get("width_mm"), metrics.get("height_mm"), metrics.get("area_cm2"),
        meta.get("layers", 2), meta.get("qty", 5), svg, len(issues), "".join(issue_html),
        metrics.get("price_estimate_cny"), meta.get("qty", 5), note,
        metrics.get("min_trace_mm"), metrics.get("min_drill_mm"), metrics.get("drill_count"),
        analysis["blocker_count"], analysis["warning_count"])
