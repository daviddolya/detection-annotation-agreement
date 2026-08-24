# Annotation agreement report

100 frames of a COCO val2017 subset were annotated by hand across six classes with no
access to the reference annotations. What follows is a numerical comparison of my
annotation against the COCO reference and an analysis of the systematic disagreements.

The rules the work was done under: [`annotation/GUIDELINES.md`](../annotation/GUIDELINES.md).
The metrics are reproduced by the command in "How this was produced".

## Method

Boxes within a frame are matched greedily by descending IoU with a threshold of **0.5**,
**class-agnostically**. Class-agnostic matching matters on principle: require the labels to
agree and a class error immediately splits into a miss plus an extra box, leaving nothing
to compute the agreement coefficient on.

The disagreement categories are named as in the CVAT quality report:

| Category | What it means | Weight |
|---|---|---|
| `Mismatching label` | the pair matched, the labels differ | error |
| `Missing annotation` | a reference box with no pair | error |
| `Extra annotation` | a box of mine with no pair | error |
| `Low overlap` | a same-class pair with IoU in [0.25, 0.5) -- the object was found, the boundary drifted | warning |

The 0.5 threshold is named explicitly because every number moves with it at once: CVAT
defaults to `iou_threshold` = 0.4, and at that value part of `Low overlap` would become
matched pairs.

Reference annotations with `iscrowd=1` are RLE crowd regions rather than boxes and do not
enter the matching. **There is not a single such frame in the sample**: the filter at the
frame-selection stage did its job and dropped them before annotation.

## Result

| Metric | Value |
|---|---|
| Frames | 100 |
| Boxes, mine / reference | 364 / 551 |
| Pairs matched | 338 |
| `Mismatching label` | 21 |
| `Missing annotation` | 197 |
| `Extra annotation` | 10 |
| `Low overlap` | 16 |
| Mean IoU over matched pairs | **0.867** |
| Mean IoU where the class also matched | 0.864 |
| Agreement coefficient (Cohen's kappa) | **0.914** |
| Error rate against the reference | 41.4% |

The project's reference points -- IoU 0.75+ and kappa 0.6+ -- are cleared with room to
spare. The error rate of 41.4% is nevertheless high, and almost all of it is misses: 197
of 228 errors. The two metrics speak about different things and both are true: **the
objects that were found are outlined precisely and named correctly, but only two thirds of
what the reference annotates was found at all**.

A separate caveat about kappa: it is computed over the 338 matched pairs, so it answers the
question "how far do I agree on the class once the object has been found at all". Misses do
not enter it by construction -- they are what `Missing annotation` measures.

## By class

The row is the reference class, the column is the class I assigned.

| Reference \ Mine | person | car | truck | bus | bicycle | motorcycle | Missed | Mean IoU |
|---|---|---|---|---|---|---|---|---|
| person | **145** | -- | -- | -- | -- | -- | 92 | 0.841 |
| car | -- | **78** | -- | -- | -- | -- | 54 | 0.877 |
| truck | -- | 18 | **10** | 2 | -- | -- | 12 | 0.886 |
| bus | -- | -- | 1 | **32** | -- | -- | 9 | 0.917 |
| bicycle | -- | -- | -- | -- | **21** | -- | 16 | 0.868 |
| motorcycle | -- | -- | -- | -- | -- | **31** | 14 | 0.886 |

Extra boxes: `person` 3, `car` 4, `bicycle` 2, `bus` 1.

## Systematic disagreements

### 1. Goods vehicles go to `car` -- a disagreement over class policy

Of the 30 matched reference `truck` objects I called only 10 `truck`, 18 `car` and 2 `bus`.
This is not scatter but the consistent application of my own rule: in `GUIDELINES.md` the
dividing feature between `car` and `truck` is **what the body is for** (a separate cargo
volume without side windows, or an open platform), whereas the COCO convention is closer to
overall size and chassis type, and pickups, minivans and glazed vans land inside it.

The disagreement is reproducible and explicable, so in a real project it is cured not by
re-annotating but by agreeing the convention with the customer **before** the work starts.
The flip side: my `car` is overfull -- 18 of my 96 `car` objects are trucks to the reference.

Example frames: `000000006723.jpg`, `000000007386.jpg`, `000000033221.jpg`.

### 2. Small objects missed -- a disagreement over the threshold

Median shorter box side: **62.6 px** among matched objects against **16.3 px** among missed
ones. Of the 197 misses, 69% fall on objects under 24 px, and 69 of them are under 12 px.

The threshold declared in the guidelines (5 px) did not match practice: in fact objects
under 20-25 px were not annotated. The disagreement was resolved in favour of the fact --
**the threshold was raised to 20 px**, and missing the small stuff became a declared policy
rather than an accident. The COCO reference annotates objects down to a few pixels, so the
share of misses in a comparison against it will stay high by construction.

The batch already handed in holds 65 boxes below the new threshold. They stay: under the
acceptance rule (section 7 of the guidelines) a new rule is not applied retroactively to
work already delivered.

The distinction matters for the report: a miss of the "deliberately not annotated under a
rule" kind is cured by changing the guidelines, a miss of the "did not notice" kind only by
changing how the frame is scanned (zooming, a second pass over the periphery).

### 3. Thirty-two misses that size does not explain

32 missed reference boxes have a shorter side of 48 px or more, the largest being 427, 314
and 247 px. The threshold cannot account for those: such objects are plainly visible. They
spread widely across classes: `bicycle` 9, `bus` 7, `person` 6, `truck` 4, `motorcycle` 4,
`car` 2, over 24 frames out of 100.

The group splits on a test for overlap with a neighbour of the same class:

- **8 misses sit inside a dense group** (bicycles in a rack, buses in a row). This is the
  guidelines rule at work: within a dense group only objects whose contour is discernible
  in full are annotated. The rule was written about people yet applied in practice to every
  class -- the guidelines have to be brought in line with the fact.
- **24 misses are solitary**, with no neighbour of the same class nearby. Rules do not
  explain them, so they were reviewed by eye frame by frame (`--review missing_large_solo`).

The outcome of reviewing those 24 solitary cases:

| | Cases | Classes |
|---|---|---|
| Chose not to annotate | 16 | `bus` 5, `truck` 4, `motorcycle` 3, `bicycle` 2, `person` 1, `car` 1 |
| Did not notice | 8 | `person` 4, `bicycle` 2, `bus` 2 |

Two thirds of the large solitary misses are deliberate decisions, and that changes the
conclusion outright: the annotation is not "full of holes" but made under rules that the
guidelines never stated. The review turned up three such rules, and all three are now
written into section 4.5: **the carrier of the scene** (the object fills the frame and is
visible in fragments between others), **a fragment without identification** (part is
visible but does not establish the class), **the background** (the object takes no part in
the subject of the frame).
Telling frames: `000000110784.jpg` -- a food-van shop, which the reference annotates as
`truck` in full; `000000336628.jpg` -- a cable car in close-up, which the reference
annotates as `bus` across almost the whole frame, the object visible only in fragments
between passengers; `000000226903.jpg` -- a person outside behind a shop window, visible
as a fragment.

The remaining 8 are inattention, and half of them are people. That is cured not by a rule
but by technique: a second pass over the frame for `person` alone.

A separate caveat about method: one case (`000000546976.jpg`) landed in this group by
mistake. The motorcycle there is annotated, but as `bicycle` and with a shifted box
(IoU 0.47), and the "rescue" of a pair through `Low overlap` works only within one class --
so the case doubled into a miss plus an extra box. The present matching scheme cannot tell
apart a disagreement in class and in boundary occurring at once; over 551 boxes that is a
single case, but the metric is worth refining before scaling up.

### 4. The `bus` / `truck` boundary

Three disagreements on the boundary of large vehicles: 2 reference `truck` objects called
`bus` and 1 reference `bus` called `truck` (`000000161128.jpg`, `000000447342.jpg`). The
volume is small but the pair is contentious: the guidelines set the feature by capacity, the
reference goes rather by purpose. A candidate for a rule with an example.

### 5. The boundaries are drawn precisely

A mean IoU of 0.867 with 16 `Low overlap` cases out of 354 pairs means the drawing technique
is not the problem. The most "drifted" boundaries belong to `person` (7) and `bicycle` (5):
both classes present a complex silhouette, and the difference accumulates on limbs and
spokes.

## Figures

Blue is the COCO reference, orange is mine. Frames are picked automatically: for every kind
of disagreement, the frame holding the most cases of that kind
(`annotation/make_figures.py`).

| Figure | What it shows |
|---|---|
| [`01_mismatch_truck_car.jpg`](figures/01_mismatch_truck_car.jpg) | three reference `truck` objects annotated as `car` -- the class-policy disagreement |
| [`02_mismatch_any.jpg`](figures/02_mismatch_any.jpg) | the `bus` / `truck` boundary |
| [`03_missing_large.jpg`](figures/03_missing_large.jpg) | bicycles in a rack: the discernible ones annotated, the occluded ones missed |
| [`03b_missing_large_solo.jpg`](figures/03b_missing_large_solo.jpg) | a large solitary miss: the food van is annotated by the reference, by me only the person |
| [`04_missing_small.jpg`](figures/04_missing_small.jpg) | nine small objects below the effective threshold |
| [`05_low_overlap.jpg`](figures/05_low_overlap.jpg) | the object was found, the boundary drifted (IoU 0.25-0.5) |
| [`06_extra.jpg`](figures/06_extra.jpg) | an extra box: annotated beyond the reference |
| [`07_clean.jpg`](figures/07_clean.jpg) | ten objects matching on both class and boundary |

## What changes in the guidelines

1. **`car` / `truck`** -- the feature stays as it was, but an explicit line goes into
   section 2: the project convention differs from COCO, and when working against an
   external reference it has to be agreed before annotation begins.
2. **The small-object threshold** -- raised from 5 to 20 px to match the fact (decision of
   2026-08-14). Not applied retroactively to the batch handed in.
3. **`bus` / `truck`** -- an example with a shuttle minibus goes into the class table.
4. **A second pass over the frame** -- the "large first, then small" rule is extended with
   a check of the frame periphery: part of the large misses fall on the edges.
5. **The dense group** -- the rule is worded about people only yet was applied to every
   class (bicycles in a rack, buses in a row). The wording is extended to all six classes
   explicitly.
6. **A new section 4.5, "What is not annotated even when the object is large"** -- three
   rules found by the review: the carrier of the scene, a fragment without identification,
   the background. Those are exactly what produces 16 of the 32 large misses, and without
   them the guidelines described annotation other than the one that came out.
7. **`Low overlap`** -- section 7 of the guidelines defined it as "IoU below 0.5", which
   contradicts the matching threshold of 0.5. The correct wording is the band [0.25, 0.5):
   the object was found, the boundary drifted.

## Limitations

- 100 frames and 551 reference boxes is a small sample. The conclusions about `truck` (30
  boxes) and `bicycle` (37) are noisy and worth rechecking at greater volume.
- The COCO reference is not the final word: part of the disagreement is its own misses and
  contentious decisions. That does not hinder the report, but the claim "I was wrong"
  requires looking at the frame.
- The annotation was done by one person in one sitting: fatigue and rule drift within the
  session are not measured. The classic way to measure them is to re-annotate part of the
  frames a few days later (intra-annotator agreement).

## How this was produced

```bash
python3 annotation/validate.py --coco annotation/my_labels/coco/instances_default.json --min-side 20
python3 annotation/convert.py --selftest --input annotation/my_labels/coco/instances_default.json
python3 annotation/agreement.py \
    --mine annotation/my_labels/coco/instances_default.json \
    --reference data/coco/annotation/instances_val2017.json \
    --out reports/agreement_metrics.json
```

The full numbers, the matrix and example frames for every category are in
[`agreement_metrics.json`](agreement_metrics.json).
