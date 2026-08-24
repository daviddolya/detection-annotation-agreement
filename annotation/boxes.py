"""Shared structures for working with bounding boxes.

One internal representation serves every format: a frame knows its own size and
a box is held COCO-style (x, y, w, h) in absolute pixels. Conversion to VOC and
YOLO happens at the boundary -- on read and on write, never mid-computation.
That way a coordinate-system mistake stays in one place.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

CLASSES = ["person", "car", "truck", "bus", "bicycle", "motorcycle"]


@dataclass
class Box:
    cls: str
    x: float
    y: float
    w: float
    h: float
    iscrowd: bool = False

    @property
    def xyxy(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.x + self.w, self.y + self.h

    @property
    def area(self) -> float:
        return self.w * self.h


@dataclass
class Frame:
    file_name: str
    width: int
    height: int
    boxes: list[Box] = field(default_factory=list)


def iou(a: Box, b: Box) -> float:
    """Intersection over Union of two boxes. 0.0 when they do not overlap."""
    ax1, ay1, ax2, ay2 = a.xyxy
    bx1, by1, bx2, by2 = b.xyxy
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def load_coco(path: str | Path, keep: set[str] | None = None,
              drop_crowd: bool = False) -> list[Frame]:
    """Reads a COCO JSON. keep -- retain only these classes, None = all.

    drop_crowd discards annotations with iscrowd=1: those are RLE crowd regions
    rather than boxes, and matching them against hand annotation is not valid.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    names = {c["id"]: c["name"] for c in data["categories"]}
    frames = {
        img["id"]: Frame(img["file_name"], img["width"], img["height"])
        for img in data["images"]
    }
    for ann in data["annotations"]:
        name = names.get(ann["category_id"])
        if name is None or (keep is not None and name not in keep):
            continue
        crowd = bool(ann.get("iscrowd", 0))
        if crowd and drop_crowd:
            continue
        frame = frames.get(ann["image_id"])
        if frame is None:
            continue
        x, y, w, h = ann["bbox"]
        frame.boxes.append(Box(name, float(x), float(y), float(w), float(h), crowd))
    return list(frames.values())


def save_coco(frames: list[Frame], path: str | Path,
              classes: list[str] = CLASSES) -> None:
    cat_id = {name: i + 1 for i, name in enumerate(classes)}
    images, annotations = [], []
    for img_id, frame in enumerate(frames, start=1):
        images.append({
            "id": img_id,
            "file_name": frame.file_name,
            "width": frame.width,
            "height": frame.height,
        })
        for box in frame.boxes:
            annotations.append({
                "id": len(annotations) + 1,
                "image_id": img_id,
                "category_id": cat_id[box.cls],
                "bbox": [box.x, box.y, box.w, box.h],
                "area": box.area,
                "iscrowd": int(box.iscrowd),
            })
    payload = {
        "images": images,
        "annotations": annotations,
        "categories": [{"id": i, "name": n, "supercategory": ""}
                       for n, i in cat_id.items()],
    }
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                          encoding="utf-8")
