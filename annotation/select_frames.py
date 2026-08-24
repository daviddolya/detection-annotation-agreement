#!/usr/bin/env python3
"""Selecting a subset of COCO val2017 frames for hand annotation.

A frame is taken when it holds objects of the six target classes, not too many
of them (no crowd) and none microscopic. Classes and boxes are NOT printed: the
annotation is done blind, otherwise there is nothing to compute agreement on.
"""

import argparse
import json
import random
import shutil
from collections import Counter
from pathlib import Path

CLASSES = ["person", "car", "truck", "bus", "bicycle", "motorcycle"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ann", type=Path, required=True, help="instances_val2017.json")
    p.add_argument("--images", type=Path, required=True, help="the val2017/ directory")
    p.add_argument("--out", type=Path, required=True, help="where to put what was selected")
    p.add_argument("--count", type=int, default=120)
    p.add_argument("--min-objects", type=int, default=2)
    p.add_argument("--max-objects", type=int, default=12)
    p.add_argument("--min-area", type=float, default=400.0, help="px^2, drops the tiny stuff")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--stats", action="store_true",
                   help="print the reference class distribution -- only after annotating")
    args = p.parse_args()

    data = json.loads(args.ann.read_text(encoding="utf-8"))

    name_by_id = {c["id"]: c["name"] for c in data["categories"]}
    target_ids = {cid for cid, name in name_by_id.items() if name in CLASSES}
    missing = set(CLASSES) - {name_by_id[cid] for cid in target_ids}
    if missing:
        raise SystemExit(f"categories absent from the annotations: {sorted(missing)}")

    images = {img["id"]: img for img in data["images"]}

    per_image = {}      # image_id -> Counter over the target classes
    crowd_images = set()  # frames with iscrowd=1 in a target class

    for a in data["annotations"]:
        if a["category_id"] not in target_ids:
            continue
        if a.get("iscrowd", 0) == 1:
            # a crowd is stored as a single RLE region rather than boxes: it
            # cannot be annotated object by object, and such frames later produce
            # spurious extra boxes
            crowd_images.add(a["image_id"])
            continue
        w, h = a["bbox"][2], a["bbox"][3]
        if w * h < args.min_area:
            continue
        per_image.setdefault(a["image_id"], Counter())[name_by_id[a["category_id"]]] += 1

    pool = [
        img_id for img_id, cnt in per_image.items()
        if img_id not in crowd_images
        and args.min_objects <= sum(cnt.values()) <= args.max_objects
    ]
    if len(pool) < args.count:
        raise SystemExit(f"{len(pool)} frames left after filtering, {args.count} needed")

    # greedy selection: at every step take the frame carrying the rarest class
    # so far, otherwise half the sample turns out to be person/car
    random.Random(args.seed).shuffle(pool)
    selected, got = [], Counter({c: 0 for c in CLASSES})
    while pool and len(selected) < args.count:
        rare = min(CLASSES, key=lambda c: got[c])
        pick = next((i for i in pool if per_image[i][rare]), pool[0])
        pool.remove(pick)
        selected.append(pick)
        got.update(per_image[pick])

    args.out.mkdir(parents=True, exist_ok=True)
    frames_dir = args.out / "frames"
    frames_dir.mkdir(exist_ok=True)

    file_names = []
    for img_id in selected:
        file_name = images[img_id]["file_name"]  # do not rename: the reference is looked up by it
        shutil.copy2(args.images / file_name, frames_dir / file_name)
        file_names.append(file_name)

    manifest = {
        "source": "COCO val2017",
        "classes": CLASSES,
        "filters": {
            "min_objects": args.min_objects,
            "max_objects": args.max_objects,
            "min_area_px2": args.min_area,
            "drop_iscrowd": True,
        },
        "seed": args.seed,
        "count": len(file_names),
        "files": sorted(file_names),
    }
    (args.out / "selection.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"selected {len(file_names)} frames -> {frames_dir}")
    print(f"manifest: {args.out / 'selection.json'}")
    if args.stats:
        print("reference distribution:", dict(got))


if __name__ == "__main__":
    main()
