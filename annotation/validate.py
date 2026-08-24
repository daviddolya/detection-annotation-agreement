#!/usr/bin/env python3
"""Integrity check of a COCO-format annotation.

Catches what the eye misses in the annotation tool but which breaks training or
distorts metrics: boxes outside the frame, degenerate rectangles, references to
images that do not exist, files and annotations out of sync.

Problems split into errors (they break the dataset) and warnings (suspicious but
legal). The exit code is 1 only on errors.

    python3 annotation/validate.py --coco annotation/my_labels/coco/instances_default.json \
        --images data/subset/frames --min-side 5
"""

import argparse
import json
from pathlib import Path

from boxes import CLASSES, load_coco

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--coco", type=Path, required=True)
    p.add_argument("--images", type=Path,
                   help="frame directory: check that files and annotations pair up")
    p.add_argument("--classes", nargs="*", default=CLASSES,
                   help="the expected closed list of classes")
    p.add_argument("--min-side", type=float, default=0.0,
                   help="the threshold from GUIDELINES: shorter box side, px")
    p.add_argument("--tolerance", type=float, default=0.5,
                   help="tolerance for running past the frame border, px")
    args = p.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    raw = json.loads(args.coco.read_text(encoding="utf-8"))
    declared = [c["name"] for c in raw["categories"]]
    unexpected = set(declared) - set(args.classes)
    if unexpected:
        errors.append(f"the file carries classes outside the closed list: {sorted(unexpected)}")

    frames = load_coco(args.coco)
    seen_names = set()
    total_boxes = 0

    for frame in frames:
        if frame.file_name in seen_names:
            errors.append(f"{frame.file_name}: the frame appears twice in the file")
        seen_names.add(frame.file_name)
        if frame.width <= 0 or frame.height <= 0:
            errors.append(f"{frame.file_name}: invalid frame size "
                          f"{frame.width}x{frame.height}")
        if not frame.boxes:
            warnings.append(f"{frame.file_name}: not a single box")

        for i, box in enumerate(frame.boxes):
            total_boxes += 1
            tag = f"{frame.file_name}[{i}] {box.cls}"
            if box.w <= 0 or box.h <= 0:
                errors.append(f"{tag}: degenerate box {box.w:.1f}x{box.h:.1f}")
                continue
            x1, y1, x2, y2 = box.xyxy
            if (x1 < -args.tolerance or y1 < -args.tolerance
                    or x2 > frame.width + args.tolerance
                    or y2 > frame.height + args.tolerance):
                errors.append(
                    f"{tag}: box outside the frame "
                    f"({x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f}) "
                    f"for a frame of {frame.width}x{frame.height}")
            if args.min_side and min(box.w, box.h) < args.min_side:
                warnings.append(f"{tag}: shorter side {min(box.w, box.h):.1f} px "
                                f"< the {args.min_side} px threshold from GUIDELINES")

    if args.images:
        on_disk = {p.name for p in args.images.iterdir()
                   if p.suffix.lower() in IMAGE_SUFFIXES}
        for missing in sorted(seen_names - on_disk):
            errors.append(f"{missing}: present in the annotations, no file on disk")
        for orphan in sorted(on_disk - seen_names):
            errors.append(f"{orphan}: the file exists, the annotations do not")

    print(f"frames: {len(frames)}, boxes: {total_boxes}, "
          f"classes: {len(declared)}")
    for kind, items in (("ERROR", errors), ("warning", warnings)):
        for item in items[:40]:
            print(f"  {kind}: {item}")
        if len(items) > 40:
            print(f"  ... and {len(items) - 40} more ({kind})")
    print(f"total: errors {len(errors)}, warnings {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
