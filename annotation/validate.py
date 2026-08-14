#!/usr/bin/env python3
"""Проверка целостности разметки в формате COCO.

Ловит то, что не видно глазом в интерфейсе разметчика, но ломает обучение
или искажает метрики: боксы за границей кадра, вырожденные рамки, ссылки
на несуществующие изображения, рассинхрон файлов и аннотаций.

Проблемы делятся на ошибки (ломают датасет) и предупреждения (подозрительно,
но законно). Код выхода 1 только при ошибках.

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
                   help="каталог кадров: проверить, что файлы и аннотации в паре")
    p.add_argument("--classes", nargs="*", default=CLASSES,
                   help="ожидаемый закрытый список классов")
    p.add_argument("--min-side", type=float, default=0.0,
                   help="порог из GUIDELINES: меньшая сторона бокса, px")
    p.add_argument("--tolerance", type=float, default=0.5,
                   help="допуск выхода за границу кадра, px")
    args = p.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    raw = json.loads(args.coco.read_text(encoding="utf-8"))
    declared = [c["name"] for c in raw["categories"]]
    unexpected = set(declared) - set(args.classes)
    if unexpected:
        errors.append(f"в файле есть классы вне закрытого списка: {sorted(unexpected)}")

    frames = load_coco(args.coco)
    seen_names = set()
    total_boxes = 0

    for frame in frames:
        if frame.file_name in seen_names:
            errors.append(f"{frame.file_name}: кадр встречается в файле дважды")
        seen_names.add(frame.file_name)
        if frame.width <= 0 or frame.height <= 0:
            errors.append(f"{frame.file_name}: некорректный размер кадра "
                          f"{frame.width}x{frame.height}")
        if not frame.boxes:
            warnings.append(f"{frame.file_name}: ни одного бокса")

        for i, box in enumerate(frame.boxes):
            total_boxes += 1
            tag = f"{frame.file_name}[{i}] {box.cls}"
            if box.w <= 0 or box.h <= 0:
                errors.append(f"{tag}: вырожденный бокс {box.w:.1f}x{box.h:.1f}")
                continue
            x1, y1, x2, y2 = box.xyxy
            if (x1 < -args.tolerance or y1 < -args.tolerance
                    or x2 > frame.width + args.tolerance
                    or y2 > frame.height + args.tolerance):
                errors.append(
                    f"{tag}: бокс за границей кадра "
                    f"({x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f}) "
                    f"при размере {frame.width}x{frame.height}")
            if args.min_side and min(box.w, box.h) < args.min_side:
                warnings.append(f"{tag}: меньшая сторона {min(box.w, box.h):.1f} px "
                                f"< порога {args.min_side} px из GUIDELINES")

    if args.images:
        on_disk = {p.name for p in args.images.iterdir()
                   if p.suffix.lower() in IMAGE_SUFFIXES}
        for missing in sorted(seen_names - on_disk):
            errors.append(f"{missing}: есть в аннотациях, нет файла на диске")
        for orphan in sorted(on_disk - seen_names):
            errors.append(f"{orphan}: файл есть, аннотаций нет")

    print(f"кадров: {len(frames)}, боксов: {total_boxes}, "
          f"классов: {len(declared)}")
    for kind, items in (("ОШИБКА", errors), ("предупреждение", warnings)):
        for item in items[:40]:
            print(f"  {kind}: {item}")
        if len(items) > 40:
            print(f"  ... и ещё {len(items) - 40} ({kind})")
    print(f"итог: ошибок {len(errors)}, предупреждений {len(warnings)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
