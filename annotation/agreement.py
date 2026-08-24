#!/usr/bin/env python3
"""Agreement between my annotation and the reference.

The main artefact of the project. It answers two different questions that are
often confused:

    mean IoU over matched boxes    -- how precisely the boundaries are drawn;
    agreement coefficient (Cohen's kappa) -- how far the class choice agrees.

The matching order:

 1. Boxes in a frame are matched greedily by descending IoU, threshold 0.5,
    class-AGNOSTICALLY -- otherwise a class error immediately disguises itself
    as a miss plus an extra box, and there is nothing left to compute kappa on.
 2. A matched pair carrying different labels is a `Mismatching label`.
 3. Unmatched boxes are then checked for "the boundary drifted": if a box has a
    counterpart of the same class with IoU in [--low-overlap, 0.5), the pair
    counts as `Low overlap` -- a warning rather than a pair of errors.
 4. The rest: a box of mine without a pair is an `Extra annotation`, a
    `Missing annotation`.

Reference annotations with iscrowd=1 are RLE crowd regions, not boxes; they do
not enter the matching, and the number of such frames goes into the report.

    python3 annotation/agreement.py \
        --mine annotation/my_labels/coco/instances_default.json \
        --reference data/coco/annotation/instances_val2017.json \
        --out reports/agreement_metrics.json
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from boxes import CLASSES, Box, Frame, iou, load_coco


def match_frame(mine: list[Box], ref: list[Box], iou_threshold: float,
                low_overlap: float):
    """Returns (pairs, my unmatched, reference unmatched, low-overlap pairs)."""
    candidates = sorted(
        ((iou(m, r), i, j) for i, m in enumerate(mine) for j, r in enumerate(ref)),
        key=lambda t: -t[0])
    used_mine: set[int] = set()
    used_ref: set[int] = set()
    pairs = []
    for score, i, j in candidates:
        if score < iou_threshold:
            break
        if i in used_mine or j in used_ref:
            continue
        used_mine.add(i)
        used_ref.add(j)
        pairs.append((mine[i], ref[j], score))

    free_mine = [i for i in range(len(mine)) if i not in used_mine]
    free_ref = [j for j in range(len(ref)) if j not in used_ref]

    low = []
    for i in list(free_mine):
        best = max(((iou(mine[i], ref[j]), j) for j in free_ref
                    if ref[j].cls == mine[i].cls), default=(0.0, None))
        if best[1] is not None and best[0] >= low_overlap:
            low.append((mine[i], ref[best[1]], best[0]))
            free_mine.remove(i)
            free_ref.remove(best[1])

    return pairs, [mine[i] for i in free_mine], [ref[j] for j in free_ref], low


def cohens_kappa(pairs: list[tuple[str, str]], classes: list[str]) -> float:
    """Class agreement over matched pairs, corrected for chance."""
    n = len(pairs)
    if n == 0:
        return float("nan")
    observed = sum(1 for a, b in pairs if a == b) / n
    mine = Counter(a for a, _ in pairs)
    ref = Counter(b for _, b in pairs)
    expected = sum((mine[c] / n) * (ref[c] / n) for c in classes)
    if expected >= 1.0:
        return float("nan")
    return (observed - expected) / (1 - expected)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--mine", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("reports/agreement_metrics.json"))
    p.add_argument("--iou-threshold", type=float, default=0.5)
    p.add_argument("--low-overlap", type=float, default=0.25,
                   help="lower edge of the 'object found, boundary drifted' band")
    p.add_argument("--classes", nargs="*", default=CLASSES)
    args = p.parse_args()

    keep = set(args.classes)
    mine_frames = {f.file_name: f for f in load_coco(args.mine, keep=keep)}
    ref_all = {f.file_name: f for f in load_coco(args.reference, keep=keep)}

    missing_ref = sorted(set(mine_frames) - set(ref_all))
    if missing_ref:
        raise SystemExit(f"no reference for {len(missing_ref)} frames, "
                         f"for instance {missing_ref[:3]}")

    crowd_frames = [name for name in mine_frames
                    if any(b.iscrowd for b in ref_all[name].boxes)]
    crowd_boxes = sum(1 for name in mine_frames
                      for b in ref_all[name].boxes if b.iscrowd)

    totals = Counter()
    ious: list[float] = []
    label_pairs: list[tuple[str, str]] = []
    confusion = defaultdict(Counter)
    per_class = defaultdict(Counter)
    per_class_iou = defaultdict(list)
    examples = defaultdict(list)

    for name, frame in sorted(mine_frames.items()):
        ref_boxes = [b for b in ref_all[name].boxes if not b.iscrowd]
        pairs, extra, missing, low = match_frame(
            frame.boxes, ref_boxes, args.iou_threshold, args.low_overlap)

        totals["mine"] += len(frame.boxes)
        totals["reference"] += len(ref_boxes)
        totals["matched"] += len(pairs)
        totals["extra"] += len(extra)
        totals["missing"] += len(missing)
        totals["low_overlap"] += len(low)

        for m, r, score in pairs:
            ious.append(score)
            label_pairs.append((m.cls, r.cls))
            confusion[r.cls][m.cls] += 1
            per_class_iou[r.cls].append(score)
            if m.cls == r.cls:
                per_class[r.cls]["matched"] += 1
            else:
                totals["mismatch"] += 1
                per_class[r.cls]["missing_as_other"] += 1
                per_class[m.cls]["extra_as_other"] += 1
                if len(examples[f"{r.cls}->{m.cls}"]) < 5:
                    examples[f"{r.cls}->{m.cls}"].append(name)
        for b in extra:
            per_class[b.cls]["extra"] += 1
            if len(examples[f"extra:{b.cls}"]) < 5:
                examples[f"extra:{b.cls}"].append(name)
        for b in missing:
            per_class[b.cls]["missing"] += 1
            if len(examples[f"missing:{b.cls}"]) < 5:
                examples[f"missing:{b.cls}"].append(name)
        for m, r, score in low:
            per_class[r.cls]["low_overlap"] += 1

    errors = totals["missing"] + totals["extra"] + totals["mismatch"]
    mean_iou = sum(ious) / len(ious) if ious else float("nan")
    same_class_iou = [s for (m, r), s in zip(label_pairs, ious) if m == r]
    kappa = cohens_kappa(label_pairs, args.classes)

    result = {
        "iou_threshold": args.iou_threshold,
        "low_overlap_threshold": args.low_overlap,
        "frames": len(mine_frames),
        "crowd_frames_in_reference": len(crowd_frames),
        "crowd_boxes_excluded": crowd_boxes,
        "boxes_mine": totals["mine"],
        "boxes_reference": totals["reference"],
        "matched": totals["matched"],
        "mismatching_label": totals["mismatch"],
        "missing_annotation": totals["missing"],
        "extra_annotation": totals["extra"],
        "low_overlap": totals["low_overlap"],
        "error_rate": errors / totals["reference"] if totals["reference"] else None,
        "mean_iou_matched": mean_iou,
        "mean_iou_same_class": (sum(same_class_iou) / len(same_class_iou)
                                if same_class_iou else float("nan")),
        "cohens_kappa": kappa,
        "per_class": {c: dict(per_class[c]) for c in args.classes},
        "per_class_mean_iou": {
            c: (sum(per_class_iou[c]) / len(per_class_iou[c])
                if per_class_iou[c] else None) for c in args.classes},
        "confusion_reference_to_mine": {
            r: dict(confusion[r]) for r in args.classes},
        "examples": dict(examples),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding="utf-8")

    print(f"frames {result['frames']}, boxes mine {result['boxes_mine']}, "
          f"reference {result['boxes_reference']}")
    print(f"matched {result['matched']}, of them with a different label "
          f"{result['mismatching_label']}")
    print(f"missing {result['missing_annotation']}, extra "
          f"{result['extra_annotation']}, low overlap {result['low_overlap']}")
    print(f"mean IoU {mean_iou:.3f}, kappa {kappa:.3f}")
    print(f"frames with iscrowd in the reference: {len(crowd_frames)} "
          f"({crowd_boxes} regions excluded)")
    print(f"metrics -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
