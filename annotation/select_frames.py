#!/usr/bin/env python3
"""Отбор подмножества кадров COCO val2017 для ручной разметки (P2, этап 1).

Кадр берётся, если в нём есть объекты из шести целевых классов, их немного
(не толпа) и они не микроскопические. Классы и боксы наружу НЕ выводятся:
разметка идёт вслепую, иначе коэффициент согласия на этапе 3 считать не на чем.
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
    p.add_argument("--images", type=Path, required=True, help="каталог val2017/")
    p.add_argument("--out", type=Path, required=True, help="куда сложить отобранное")
    p.add_argument("--count", type=int, default=120)
    p.add_argument("--min-objects", type=int, default=2)
    p.add_argument("--max-objects", type=int, default=12)
    p.add_argument("--min-area", type=float, default=400.0, help="px^2, отсев мелочи")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--stats", action="store_true",
                   help="напечатать эталонное распределение классов — только для дня 8")
    args = p.parse_args()

    data = json.loads(args.ann.read_text(encoding="utf-8"))

    name_by_id = {c["id"]: c["name"] for c in data["categories"]}
    target_ids = {cid for cid, name in name_by_id.items() if name in CLASSES}
    missing = set(CLASSES) - {name_by_id[cid] for cid in target_ids}
    if missing:
        raise SystemExit(f"в аннотациях нет категорий: {sorted(missing)}")

    images = {img["id"]: img for img in data["images"]}

    per_image = {}      # image_id -> Counter по целевым классам
    crowd_images = set()  # кадры с iscrowd=1 в целевом классе

    for a in data["annotations"]:
        if a["category_id"] not in target_ids:
            continue
        if a.get("iscrowd", 0) == 1:
            # толпа хранится одной RLE-областью, а не боксами: разметить её
            # покадрово нельзя, и на этапе 3 такие кадры дают ложные лишние боксы
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
        raise SystemExit(f"после фильтров осталось {len(pool)} кадров, нужно {args.count}")

    # жадный отбор: на каждом шаге тянем кадр с самым редким пока классом,
    # иначе выборка станет наполовину из одних person/car
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
        file_name = images[img_id]["file_name"]  # имя не менять: по нему день 8 достаёт эталон
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

    print(f"отобрано {len(file_names)} кадров -> {frames_dir}")
    print(f"манифест: {args.out / 'selection.json'}")
    if args.stats:
        print("эталонное распределение:", dict(got))


if __name__ == "__main__":
    main()
