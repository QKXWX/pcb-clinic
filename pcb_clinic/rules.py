# -*- coding: utf-8 -*-
"""打样前体检规则：只报能定位、能解释的问题。"""

from collections import Counter

from .model import bbox_intersects

MIN_TRACE_MM = 0.15
MIN_DRILL_MM = 0.30
EDGE_CLEARANCE_MM = 0.20
SILK_MARGIN_MM = 0.10


def _round(value, digits=2):
    return None if value is None else round(float(value), digits)


def _issue(severity, code, title, detail):
    return {"severity": severity, "code": code, "title": title, "detail": detail}


def _edge_closure(edge):
    endpoints = []
    for seg in edge.segments:
        endpoints.append((round(seg.x1, 2), round(seg.y1, 2)))
        endpoints.append((round(seg.x2, 2), round(seg.y2, 2)))
    degrees = Counter(endpoints)
    bad = [point for point, degree in degrees.items() if degree != 2]
    return len(bad) == 0, len(bad), len(edge.segments)


def analyze(layers, drills, layers_count=2, qty=5):
    issues = []
    metrics = {}

    required = ["Edge_Cuts", "F_Cu", "B_Cu", "F_Mask", "B_Mask"]
    if layers_count == 1:
        required = ["Edge_Cuts", "F_Cu", "F_Mask"]
    for name in required:
        if name not in layers or layers[name].is_empty():
            issues.append(_issue("blocker", "missing_layer", "缺少 %s 层" % name,
                                 "板厂无法确认这一层的图形；请检查导出文件名或层映射。"))

    edge = layers.get("Edge_Cuts")
    if edge and edge.segments:
        xs = [point for seg in edge.segments for point in (seg.x1, seg.x2)]
        ys = [point for seg in edge.segments for point in (seg.y1, seg.y2)]
        edge_bbox = (min(xs), min(ys), max(xs), max(ys))
    else:
        edge_bbox = None
    if edge is None or edge.is_empty():
        metrics.update({"width_mm": None, "height_mm": None, "area_cm2": None})
    else:
        width = edge_bbox[2] - edge_bbox[0]
        height = edge_bbox[3] - edge_bbox[1]
        metrics.update({"width_mm": _round(width), "height_mm": _round(height),
                        "area_cm2": _round(width * height / 100)})
        closed, bad_points, segment_count = _edge_closure(edge)
        if segment_count < 3:
            issues.append(_issue("blocker", "outline_open", "板框线段太少",
                                 "只找到 %d 条板框线段，无法形成闭合轮廓。" % segment_count))
        elif not closed:
            issues.append(_issue("blocker", "outline_open", "板框没有闭合",
                                 "有 %d 个端点的连接数为奇数，轮廓可能是断开的。" % bad_points))
        if width <= 0 or height <= 0:
            issues.append(_issue("blocker", "outline_empty", "板框尺寸为零", "请检查 Edge_Cuts 的坐标格式。"))

    copper_segments = []
    copper_flashes = []
    for name in ("F_Cu", "B_Cu"):
        layer = layers.get(name)
        if layer:
            copper_segments.extend(layer.segments)
            copper_flashes.extend(layer.flashes)
    if copper_segments:
        metrics["min_trace_mm"] = _round(min(seg.width for seg in copper_segments))
        if metrics["min_trace_mm"] < MIN_TRACE_MM:
            issues.append(_issue("warning", "thin_trace", "最细铜线 %.2f mm" % metrics["min_trace_mm"],
                                 "低于常见的 0.15 mm 工艺下限；打样可能蚀刻断线，建议加宽或改设计。"))
    else:
        metrics["min_trace_mm"] = None
        issues.append(_issue("warning", "no_copper", "没有找到铜线", "F_Cu / B_Cu 里没有 DRAW 段，检查是否只导出了焊盘。"))

    if drills:
        metrics["min_drill_mm"] = _round(min(d.diameter for d in drills))
        metrics["drill_count"] = len(drills)
        if metrics["min_drill_mm"] < MIN_DRILL_MM:
            issues.append(_issue("warning", "small_drill", "最小钻孔 %.2f mm" % metrics["min_drill_mm"],
                                 "低于 0.30 mm 的常见钻头下限；孔径太小会加价或直接做不了。"))
    else:
        metrics["min_drill_mm"] = None
        metrics["drill_count"] = 0
        issues.append(_issue("warning", "no_drill", "没有钻孔", "如果板上有插件/过孔，钻孔文件可能漏导了。"))

    if edge_bbox:
        outside = 0
        for flash in copper_flashes:
            w, h = flash.aperture.size()
            box = (flash.x - w / 2, flash.y - h / 2, flash.x + w / 2, flash.y + h / 2)
            if not bbox_intersects(box, edge_bbox, 0.01):
                outside += 1
        if outside:
            issues.append(_issue("warning", "pad_outside", "%d 个焊盘在板框外" % outside,
                                 "焊盘中心/外形超出 Edge_Cuts，可能是拼板或坐标偏移。"))

        near_edge = 0
        for flash in copper_flashes:
            distance = min(abs(flash.x - edge_bbox[0]), abs(flash.x - edge_bbox[2]),
                           abs(flash.y - edge_bbox[1]), abs(flash.y - edge_bbox[3]))
            if distance < EDGE_CLEARANCE_MM:
                near_edge += 1
        if near_edge:
            issues.append(_issue("warning", "edge_clearance", "%d 个焊盘离板边过近" % near_edge,
                                 "最小边距低于 %.1f mm，铣边时可能切到铜。" % EDGE_CLEARANCE_MM))

    silk = layers.get("F_Silkscreen") or layers.get("B_Silkscreen")
    if silk and copper_flashes:
        overlaps = 0
        for seg in silk.segments:
            box = (min(seg.x1, seg.x2), min(seg.y1, seg.y2),
                   max(seg.x1, seg.x2), max(seg.y1, seg.y2))
            for flash in copper_flashes:
                w, h = flash.aperture.size()
                pad_box = (flash.x - w / 2, flash.y - h / 2, flash.x + w / 2, flash.y + h / 2)
                if bbox_intersects(box, pad_box, SILK_MARGIN_MM):
                    overlaps += 1
                    break
        if overlaps:
            issues.append(_issue("info", "silk_over_pad", "丝印疑似压住 %d 处焊盘" % overlaps,
                                 "丝印压焊盘会影响可焊性；如果只是标注线，可忽略。"))

    if layers_count >= 2 and ("F_Mask" not in layers or "B_Mask" not in layers):
        issues.append(_issue("warning", "mask_missing", "阻焊层不完整",
                             "双面板通常需要 F_Mask 与 B_Mask，缺少会导致焊盘被盖油。"))

    blockers = sum(1 for item in issues if item["severity"] == "blocker")
    warnings = sum(1 for item in issues if item["severity"] == "warning")
    verdict = "blocked" if blockers else ("review" if warnings else "pass")
    verdict_text = {"blocked": "先别打样", "review": "建议修改后再打", "pass": "可以打样"}[verdict]

    width = metrics.get("width_mm") or 0
    height = metrics.get("height_mm") or 0
    area = width * height / 100
    price = 20 + area * 0.08 + layers_count * 8
    price = price * (1 + max(0, qty - 5) * 0.12)
    metrics["price_estimate_cny"] = _round(price, 1)
    metrics["price_note"] = "按 2 层/5 片/普通工艺粗算，不是板厂报价；以实际 DFM 与运费为准。"

    return {
        "verdict": verdict,
        "verdict_text": verdict_text,
        "issues": issues,
        "metrics": metrics,
        "blocker_count": blockers,
        "warning_count": warnings,
    }
