#!/usr/bin/env python3
"""Наложение своей разметки на эталонную — картинки для отчёта.

Каждая картинка показывает один тип расхождения: эталон одним цветом,
своя разметка другим. Кадры выбираются автоматически — тот, где случаев
нужного типа больше всего.

    .venv/bin/python annotation/make_figures.py \
        --mine annotation/my_labels/coco/instances_default.json \
        --reference data/coco/annotation/instances_val2017.json \
        --frames data/subset/frames --out reports/figures
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from agreement import match_frame
from boxes import CLASSES, iou, load_coco

REF_COLOR = (31, 119, 180)        # эталон COCO
MINE_COLOR = (255, 127, 14)       # моя разметка
HIGHLIGHT_COLOR = (214, 39, 40)   # разбираемый случай
BAR_H = 34

FONT_CANDIDATES = [
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
]


def _font(size: int):
    """Подписи на картинках русские, поэтому шрифт нужен с кириллицей:
    встроенный в Pillow bitmap-шрифт рисует вместо неё квадраты."""
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    for path in sorted(Path("/usr/share/fonts").rglob("*.ttf")):
        try:
            font = ImageFont.truetype(str(path), size)
            if font.getmask("Ы").getbbox():  # кириллица в шрифте есть
                return font
        except OSError:
            continue
    raise SystemExit("не нашёл шрифта с кириллицей — поставь ttf-dejavu")


def draw_frame(image_path: Path, mine, ref, caption: str, out_path: Path,
               highlight=()) -> None:
    img = Image.open(image_path).convert("RGB")
    canvas = Image.new("RGB", (img.width, img.height + BAR_H), (255, 255, 255))
    canvas.paste(img, (0, BAR_H))
    draw = ImageDraw.Draw(canvas)
    font = _font(14)

    draw.rectangle([8, 10, 24, 24], fill=REF_COLOR)
    draw.text((30, 11), "эталон", fill=(20, 20, 20), font=font)
    draw.rectangle([90, 10, 106, 24], fill=MINE_COLOR)
    draw.text((112, 11), "моя разметка", fill=(20, 20, 20), font=font)
    draw.text((230, 11), caption, fill=(60, 60, 60), font=font)

    # подписи эталона идут над рамкой, свои — под нижней гранью: когда оба
    # бокса на одном объекте почти совпадают, иначе одна подпись закрывает другую
    for boxes, color, above in ((ref, REF_COLOR, True), (mine, MINE_COLOR, False)):
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy
            y1, y2 = y1 + BAR_H, y2 + BAR_H
            draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
            label = box.cls
            tw = draw.textlength(label, font=font)
            if above:
                ty = y1 - 15 if y1 > BAR_H + 15 else y1 + 1
            else:
                ty = y2 - 15 if y2 - 15 > y1 else y2 + 1
            ty = min(ty, canvas.height - 16)
            draw.rectangle([x1, ty, x1 + tw + 6, ty + 15], fill=color)
            draw.text((x1 + 3, ty + 1), label, fill=(255, 255, 255), font=font)

    # разбираемый случай обводится поверх остальных, чтобы взгляд шёл к нему
    for box in highlight:
        x1, y1, x2, y2 = box.xyxy
        draw.rectangle([x1 - 2, y1 + BAR_H - 2, x2 + 2, y2 + BAR_H + 2],
                       outline=HIGHLIGHT_COLOR, width=4)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=90)


def review(stats: dict, args) -> int:
    """Все кадры с случаями выбранного типа плюс чеклист для разбора глазами."""
    selected = [(n, s) for n, s in sorted(stats.items()) if s[args.review]]
    rows = []
    for i, (name, s) in enumerate(selected, start=1):
        cases = s[args.review]
        boxes = [c[0] if isinstance(c, tuple) else c for c in cases]
        draw_frame(args.frames / name, s["frame"].boxes, s["ref_boxes"],
                   f"{args.review}: {len(cases)} шт, обведены красным",
                   args.out / f"{i:02d}_{name}", highlight=boxes)
        for box in boxes:
            rows.append(f"- [ ] `{i:02d}_{name}` — {box.cls}, "
                        f"{box.w:.0f}x{box.h:.0f} px — решил не размечать / не заметил")
    checklist = args.out / "checklist.md"
    checklist.write_text(
        f"# Разбор: {args.review}\n\n"
        f"Красным обведён случай, синим эталон, оранжевым своя разметка.\n"
        f"Против каждого случая оставить одно из двух: **решил не размечать** "
        f"(лечится правилом в инструкции) или **не заметил** (лечится техникой "
        f"просмотра кадра).\n\n" + "\n".join(rows) + "\n",
        encoding="utf-8")
    print(f"кадров {len(selected)}, случаев {len(rows)} -> {args.out}")
    print(f"чеклист: {checklist}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mine", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--frames", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("reports/figures"))
    p.add_argument("--iou-threshold", type=float, default=0.5)
    p.add_argument("--low-overlap", type=float, default=0.25)
    p.add_argument("--review", choices=["missing_large_solo", "missing_large",
                                        "missing_small", "extra", "low"],
                   help="вместо подборки — все кадры с случаями этого типа, "
                        "разбираемый случай обведён красным")
    args = p.parse_args()

    keep = set(CLASSES)
    mine = {f.file_name: f for f in load_coco(args.mine, keep=keep)}
    ref = {f.file_name: f for f in load_coco(args.reference, keep=keep)}

    stats = {}
    for name, frame in mine.items():
        ref_boxes = [b for b in ref[name].boxes if not b.iscrowd]
        pairs, extra, missing, low = match_frame(
            frame.boxes, ref_boxes, args.iou_threshold, args.low_overlap)
        stats[name] = {
            "frame": frame,
            "ref_boxes": ref_boxes,
            "mismatch": [(m, r) for m, r, _ in pairs if m.cls != r.cls],
            "missing_large": [b for b in missing if min(b.w, b.h) >= 48],
            # крупный пропуск без соседа того же класса: плотной группой
            # его не объяснить, такой случай разбирается глазами
            "missing_large_solo": [
                b for b in missing if min(b.w, b.h) >= 48
                and max((iou(b, o) for o in ref_boxes if o is not b
                         and o.cls == b.cls), default=0) <= 0.1],
            "missing_small": [b for b in missing if min(b.w, b.h) < 24],
            "extra": extra,
            "low": low,
            "matched": [(m, r) for m, r, _ in pairs if m.cls == r.cls],
        }

    if args.review:
        return review(stats, args)

    cases = [
        ("01_mismatch_truck_car", "расхождение по классу: эталон truck, у меня car",
         lambda s: sum(1 for m, r in s["mismatch"] if r.cls == "truck" and m.cls == "car")),
        ("02_mismatch_any", "прочие расхождения по классу",
         lambda s: sum(1 for m, r in s["mismatch"] if not (r.cls == "truck" and m.cls == "car"))),
        ("03_missing_large", "крупные пропуски: объект больше 48 px, но не размечен",
         lambda s: len(s["missing_large"])),
        ("03b_missing_large_solo",
         "крупный одиночный пропуск: плотной группой не объясняется",
         lambda s: len(s["missing_large_solo"])),
        ("04_missing_small", "мелкие пропуски: объекты меньше 24 px",
         lambda s: len(s["missing_small"])),
        ("05_low_overlap", "граница уехала: IoU в зоне 0.25–0.5",
         lambda s: len(s["low"])),
        ("06_extra", "лишние боксы: размечено сверх эталона",
         lambda s: len(s["extra"])),
        ("07_clean", "полное согласие: класс и границы совпали",
         lambda s: len(s["matched"]) if not (s["mismatch"] or s["missing_large"]
                                             or s["extra"]) else 0),
    ]

    used: set[str] = set()
    made = 0
    for slug, caption, score in cases:
        ranked = sorted(((score(s), n) for n, s in stats.items() if n not in used),
                        reverse=True)
        if not ranked or ranked[0][0] == 0:
            print(f"{slug}: подходящих кадров нет, пропуск")
            continue
        count, name = ranked[0]
        used.add(name)
        s = stats[name]
        draw_frame(args.frames / name, s["frame"].boxes, s["ref_boxes"],
                   f"{caption} ({count})", args.out / f"{slug}.jpg")
        print(f"{slug}: {name}, случаев {count}")
        made += 1
    print(f"готово: {made} картинок -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
