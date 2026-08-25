#!/usr/bin/env python3
"""My annotation drawn over the reference -- the figures for the report.

Every figure shows one kind of disagreement: the reference in one colour,
mine in another. Frames are picked automatically -- the one holding the most
cases of the kind in question.

    .venv/bin/python annotation/make_figures.py \
        --mine annotation/my_labels/coco/instances_default.json \
        --reference data/coco/annotation/instances_val2017.json \
        --frames data/subset/frames --out reports/figures
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from agreement import match_frame
from boxes import CLASSES, iou, load_coco
from chrome import MINE_COLOR, REF_COLOR, load_font, with_chrome

HIGHLIGHT_COLOR = (214, 39, 40)   # the case under review


def draw_frame(image_path: Path, mine, ref, caption: str, out_path: Path,
               highlight=()) -> None:
    img = Image.open(image_path).convert("RGB")
    font = load_font(14)
    canvas, draw, BAR_H, _ = with_chrome(img, facts=caption,
                                         footer=image_path.name, font=font)

    # reference labels go above the box and mine below its bottom edge: when
    # both boxes sit on one object they nearly coincide, and one label would
    # otherwise cover the other
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

    # the case under review is outlined on top of everything else, so the eye
    # goes to it first
    for box in highlight:
        x1, y1, x2, y2 = box.xyxy
        draw.rectangle([x1 - 2, y1 + BAR_H - 2, x2 + 2, y2 + BAR_H + 2],
                       outline=HIGHLIGHT_COLOR, width=4)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, quality=90)


def review(stats: dict, args) -> int:
    """Every frame holding a case of the chosen kind, plus a checklist to work
    through by eye."""
    selected = [(n, s) for n, s in sorted(stats.items()) if s[args.review]]
    rows = []
    for i, (name, s) in enumerate(selected, start=1):
        cases = s[args.review]
        boxes = [c[0] if isinstance(c, tuple) else c for c in cases]
        draw_frame(args.frames / name, s["frame"].boxes, s["ref_boxes"],
                   f"{args.review}: {len(cases)}, outlined in red",
                   args.out / f"{i:02d}_{name}", highlight=boxes)
        for box in boxes:
            rows.append(f"- [ ] `{i:02d}_{name}` -- {box.cls}, "
                        f"{box.w:.0f}x{box.h:.0f} px -- chose not to annotate / did not notice")
    checklist = args.out / "checklist.md"
    checklist.write_text(
        f"# Review: {args.review}\n\n"
        f"The case is outlined in red, the reference in blue, mine in orange.\n"
        f"Against every case leave one of two: **chose not to annotate** "
        f"(cured by a rule in the guidelines) or **did not notice** (cured by "
        f"how the frame is scanned).\n\n" + "\n".join(rows) + "\n",
        encoding="utf-8")
    print(f"frames {len(selected)}, cases {len(rows)} -> {args.out}")
    print(f"checklist: {checklist}")
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
                   help="instead of the selection -- every frame holding a case "
                        "of this kind, the case outlined in red")
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
            # a large miss with no neighbour of the same class: a dense group
            # does not explain it, so the case is reviewed by eye
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
        ("01_mismatch_truck_car", "class disagreement: reference truck, mine car",
         lambda s: sum(1 for m, r in s["mismatch"] if r.cls == "truck" and m.cls == "car")),
        ("02_mismatch_any", "other class disagreements",
         lambda s: sum(1 for m, r in s["mismatch"] if not (r.cls == "truck" and m.cls == "car"))),
        ("03_missing_large", "large misses: object over 48 px and not annotated",
         lambda s: len(s["missing_large"])),
        ("03b_missing_large_solo",
         "a large solitary miss: a dense group does not explain it",
         lambda s: len(s["missing_large_solo"])),
        ("04_missing_small", "small misses: objects under 24 px",
         lambda s: len(s["missing_small"])),
        ("05_low_overlap", "the boundary drifted: IoU in the 0.25-0.5 band",
         lambda s: len(s["low"])),
        ("06_extra", "extra boxes: annotated beyond the reference",
         lambda s: len(s["extra"])),
        ("07_clean", "full agreement: class and boundaries both match",
         lambda s: len(s["matched"]) if not (s["mismatch"] or s["missing_large"]
                                             or s["extra"]) else 0),
    ]

    used: set[str] = set()
    made = 0
    for slug, caption, score in cases:
        ranked = sorted(((score(s), n) for n, s in stats.items() if n not in used),
                        reverse=True)
        if not ranked or ranked[0][0] == 0:
            print(f"{slug}: no suitable frame, skipped")
            continue
        count, name = ranked[0]
        used.add(name)
        s = stats[name]
        draw_frame(args.frames / name, s["frame"].boxes, s["ref_boxes"],
                   f"{caption} ({count})", args.out / f"{slug}.jpg")
        print(f"{slug}: {name}, cases {count}")
        made += 1
    print(f"done: {made} figures -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
