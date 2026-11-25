# -*- coding: utf-8 -*-
"""板图的最小数据模型：坐标单位统一为毫米。"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Aperture:
    code: int
    shape: str          # C / R / O / P
    params: List[float]

    @property
    def width(self):
        if not self.params:
            return 0.0
        if self.shape == "C":
            return self.params[0]
        if self.shape in ("R", "O"):
            return self.params[0]
        return self.params[0]

    def size(self):
        """返回 (宽, 高)。圆形宽高相等。"""
        if self.shape == "C":
            return self.params[0], self.params[0]
        if self.shape in ("R", "O"):
            return self.params[0], self.params[1]
        return self.params[0], self.params[0]


@dataclass
class Segment:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    layer: str = ""


@dataclass
class Flash:
    x: float
    y: float
    aperture: Aperture
    layer: str = ""


@dataclass
class Region:
    points: List[Tuple[float, float]]
    layer: str = ""


@dataclass
class Layer:
    name: str
    segments: List[Segment] = field(default_factory=list)
    flashes: List[Flash] = field(default_factory=list)
    regions: List[Region] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def bbox(self) -> Optional[Tuple[float, float, float, float]]:
        points = []
        for seg in self.segments:
            half = seg.width / 2.0
            points.extend([(seg.x1 - half, seg.y1 - half), (seg.x1 + half, seg.y1 + half),
                           (seg.x2 - half, seg.y2 - half), (seg.x2 + half, seg.y2 + half)])
        for flash in self.flashes:
            w, h = flash.aperture.size()
            points.extend([(flash.x - w / 2, flash.y - h / 2), (flash.x + w / 2, flash.y + h / 2)])
        for region in self.regions:
            points.extend(region.points)
        if not points:
            return None
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return min(xs), min(ys), max(xs), max(ys)

    def is_empty(self):
        return not (self.segments or self.flashes or self.regions)


@dataclass
class Drill:
    x: float
    y: float
    diameter: float
    tool: str = ""

    def bbox(self):
        return self.x - self.diameter / 2, self.y - self.diameter / 2, \
               self.x + self.diameter / 2, self.y + self.diameter / 2


def bbox_union(boxes):
    boxes = [box for box in boxes if box]
    if not boxes:
        return None
    return (min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes))


def bbox_intersects(a, b, margin=0.0):
    if not a or not b:
        return False
    return not (a[2] + margin < b[0] or b[2] + margin < a[0] or
                a[3] + margin < b[1] or b[3] + margin < a[1])
