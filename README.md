# Детекция и качество разметки

100 кадров подмножества COCO val2017 размечены вручную вслепую по шести классам
(`person`, `car`, `truck`, `bus`, `bicycle`, `motorcycle`); своя разметка сравнивается
с эталонной численно — отчёт о согласованности в `reports/`, правила разметки
и приёмки в [`annotation/GUIDELINES.md`](annotation/GUIDELINES.md).

## Данные

- изображения: http://images.cocodataset.org/zips/val2017.zip
- аннотации: http://images.cocodataset.org/annotations/annotations_trainval2017.zip
  (нужен только `instances_val2017.json`)

Датасет под git не хранится. Выборка воспроизводится из `data/subset/selection.json`.

## Отбор кадров

```bash
python3 annotation/select_frames.py \
    --ann data/coco/annotation/instances_val2017.json \
    --images data/val2017 \
    --out data/subset --count 100 --max-objects 8
```
