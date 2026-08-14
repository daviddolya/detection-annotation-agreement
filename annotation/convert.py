#!/usr/bin/env python3
"""Конвертер аннотаций: COCO <-> YOLO <-> VOC.

Три формата хранят одну и ту же рамку в трёх системах координат:

    VOC   (xmin, ymin, xmax, ymax)   абсолютные пиксели
    COCO  (x, y, w, h)               абсолютные пиксели, левый верхний угол
    YOLO  (cx, cy, w, h)             доли размера кадра, центр рамки

Ошибка перевода не роняет обучение, а молча портит датасет: боксы уезжают,
loss падает, mAP остаётся около нуля. Поэтому у конвертера есть режим
--selftest: round-trip COCO -> YOLO -> COCO и COCO -> VOC -> COCO обязан
воспроизводить координаты с точностью до округления формата.

Примеры:
    python3 annotation/convert.py --from coco --to yolo \
        --input annotation/my_labels/coco/instances_default.json --output /tmp/yolo
    python3 annotation/convert.py --selftest \
        --input annotation/my_labels/coco/instances_default.json
"""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

from boxes import CLASSES, Box, Frame, load_coco, save_coco

# ---------------------------------------------------------------- YOLO


def save_yolo(frames: list[Frame], out_dir: Path,
              classes: list[str] = CLASSES) -> None:
    """Кадр -> <имя>.txt со строками `cls cx cy w h`, всё нормировано."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "obj.names").write_text("\n".join(classes) + "\n", encoding="utf-8")
    idx = {name: i for i, name in enumerate(classes)}
    for frame in frames:
        lines = []
        for box in frame.boxes:
            cx = (box.x + box.w / 2) / frame.width
            cy = (box.y + box.h / 2) / frame.height
            lines.append("%d %.6f %.6f %.6f %.6f" % (
                idx[box.cls], cx, cy, box.w / frame.width, box.h / frame.height))
        name = Path(frame.file_name).with_suffix(".txt").name
        (out_dir / name).write_text("\n".join(lines) + ("\n" if lines else ""),
                                    encoding="utf-8")


def load_yolo(in_dir: Path, sizes: dict[str, tuple[int, int]],
              classes: list[str] = CLASSES) -> list[Frame]:
    """Читает каталог YOLO. sizes — размеры кадров: из .txt их не узнать."""
    names_file = in_dir / "obj.names"
    if names_file.exists():
        classes = [l.strip() for l in names_file.read_text().splitlines() if l.strip()]
    frames = []
    for txt in sorted(in_dir.glob("*.txt")):
        stem = txt.stem
        file_name, (width, height) = _match_size(stem, sizes)
        frame = Frame(file_name, width, height)
        for line in txt.read_text().splitlines():
            if not line.strip():
                continue
            cls, cx, cy, w, h = line.split()
            bw, bh = float(w) * width, float(h) * height
            frame.boxes.append(Box(classes[int(cls)],
                                   float(cx) * width - bw / 2,
                                   float(cy) * height - bh / 2, bw, bh))
        frames.append(frame)
    return frames


def _match_size(stem: str, sizes: dict[str, tuple[int, int]]):
    for file_name, wh in sizes.items():
        if Path(file_name).stem == stem:
            return file_name, wh
    raise KeyError(f"нет размеров кадра для {stem}: YOLO их не хранит, "
                   f"передай исходный COCO через --sizes")

# ---------------------------------------------------------------- VOC


def save_voc(frames: list[Frame], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for frame in frames:
        root = ET.Element("annotation")
        ET.SubElement(root, "filename").text = frame.file_name
        size = ET.SubElement(root, "size")
        ET.SubElement(size, "width").text = str(frame.width)
        ET.SubElement(size, "height").text = str(frame.height)
        ET.SubElement(size, "depth").text = "3"
        for box in frame.boxes:
            obj = ET.SubElement(root, "object")
            ET.SubElement(obj, "name").text = box.cls
            ET.SubElement(obj, "difficult").text = "0"
            bnd = ET.SubElement(obj, "bndbox")
            xmin, ymin, xmax, ymax = box.xyxy
            for tag, value in zip(("xmin", "ymin", "xmax", "ymax"),
                                  (xmin, ymin, xmax, ymax)):
                # VOC исторически целочисленный, дробное здесь и теряется
                ET.SubElement(bnd, tag).text = "%.2f" % value
        name = Path(frame.file_name).with_suffix(".xml").name
        ET.ElementTree(root).write(out_dir / name, encoding="utf-8",
                                   xml_declaration=True)


def load_voc(in_dir: Path) -> list[Frame]:
    frames = []
    for xml in sorted(in_dir.glob("*.xml")):
        root = ET.parse(xml).getroot()
        size = root.find("size")
        frame = Frame(root.findtext("filename"),
                      int(float(size.findtext("width"))),
                      int(float(size.findtext("height"))))
        for obj in root.findall("object"):
            bnd = obj.find("bndbox")
            xmin, ymin, xmax, ymax = (float(bnd.findtext(t))
                                      for t in ("xmin", "ymin", "xmax", "ymax"))
            frame.boxes.append(Box(obj.findtext("name"),
                                   xmin, ymin, xmax - xmin, ymax - ymin))
        frames.append(frame)
    return frames

# ---------------------------------------------------------------- CLI


def selftest(coco_path: Path, tmp: Path) -> int:
    """COCO -> X -> COCO для X из {YOLO, VOC}. Возвращает код выхода."""
    src = load_coco(coco_path)
    sizes = {f.file_name: (f.width, f.height) for f in src}
    worst = {}

    save_yolo(src, tmp / "yolo")
    worst["YOLO"] = _max_error(src, load_yolo(tmp / "yolo", sizes))

    save_voc(src, tmp / "voc")
    worst["VOC"] = _max_error(src, load_voc(tmp / "voc"))

    ok = True
    for fmt, (err, tol) in worst.items():
        verdict = "ok" if err <= tol else "РАСХОЖДЕНИЕ"
        ok &= err <= tol
        print(f"COCO -> {fmt} -> COCO: максимальная ошибка {err:.4f} px "
              f"(допуск {tol} px) — {verdict}")
    return 0 if ok else 1


def _max_error(src: list[Frame], back: list[Frame]) -> tuple[float, float]:
    by_name = {f.file_name: f for f in back}
    worst = 0.0
    tol = 0.0
    for frame in src:
        other = by_name[frame.file_name]
        assert len(frame.boxes) == len(other.boxes), frame.file_name
        # допуск считаем от размера кадра: YOLO хранит доли с 6 знаками,
        # значит абсолютная ошибка не больше половины кванта нормировки
        tol = max(tol, max(frame.width, frame.height) * 1e-6)
        for a, b in zip(frame.boxes, other.boxes):
            assert a.cls == b.cls, f"{frame.file_name}: класс изменился"
            worst = max(worst, max(abs(u - v) for u, v in zip(a.xyxy, b.xyxy)))
    return worst, max(tol, 0.01)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--from", dest="src", choices=["coco", "yolo", "voc"])
    p.add_argument("--to", dest="dst", choices=["coco", "yolo", "voc"])
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path)
    p.add_argument("--sizes", type=Path,
                   help="COCO JSON с размерами кадров — обязателен для --from yolo")
    p.add_argument("--selftest", action="store_true",
                   help="round-trip через YOLO и VOC, сверка координат")
    args = p.parse_args()

    if args.selftest:
        tmp = Path(args.output or "/tmp/convert_selftest")
        return selftest(args.input, tmp)

    if not args.src or not args.dst or not args.output:
        p.error("нужны --from, --to и --output (или --selftest)")

    if args.src == "coco":
        frames = load_coco(args.input)
    elif args.src == "voc":
        frames = load_voc(args.input)
    else:
        if not args.sizes:
            p.error("--from yolo требует --sizes: размеров кадра в YOLO нет")
        sizes = {f.file_name: (f.width, f.height) for f in load_coco(args.sizes)}
        frames = load_yolo(args.input, sizes)

    if args.dst == "coco":
        save_coco(frames, args.output)
    elif args.dst == "yolo":
        save_yolo(frames, args.output)
    else:
        save_voc(frames, args.output)
    print(f"{args.src} -> {args.dst}: {len(frames)} кадров, "
          f"{sum(len(f.boxes) for f in frames)} боксов -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
