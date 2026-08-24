# Annotation guidelines: detection, six classes

The reference version for this project. It is a living document: every new disputed
rule is appended to it with a date and an example frame.

Version 1.0 · 2026-08-13 · author: the project annotator

---

## 1. The task

Annotate objects of six classes with axis-aligned bounding boxes on a subset of the
COCO val2017 images. The annotation is used both to train a detector and to measure
agreement with the reference annotation.

Tool: CVAT (an equivalent substitute is Label Studio). Export to COCO 1.0 and YOLO 1.1.

## 2. Classes

The list is closed. Objects outside it are not annotated, however much they catch the eye.

| Class | Annotate | Do not annotate (goes to another class, or off the list) |
|---|---|---|
| `person` | a human of any age and pose, including partially visible; a driver or passenger discernible through glass; a cyclist and a motorcyclist -- as a box separate from the vehicle | statues, mannequins, people on posters, screens, paintings and in reflections |
| `bicycle` | a bicycle of any build: road, mountain, child's, tandem, cargo, e-bike | a bicycle on an advertising image; a kick scooter (off the list) |
| `car` | a passenger car: saloon, hatchback, estate, coupé, crossover, taxi, minivan up to eight seats | a pickup and a panel van (→ `truck`); a minibus-based shuttle (→ `bus`) |
| `motorcycle` | a motorcycle, moped, scooter, motor scooter, quad bike | an electric kick scooter and a unicycle (off the list); an e-bike (→ `bicycle`) |
| `bus` | passenger transport seating roughly nine or more: city, coach, school, shuttle, double-decker, trolleybus | a minivan up to eight seats (→ `car`) |
| `truck` | a vehicle with a cargo compartment or a platform structurally separate from the cab: pickup, panel van, lorry, articulated lorry, tipper, tow truck, concrete mixer, refuse collector | a van-bodied car glazed along its full length and fitted with passenger seats (→ `car`) |

**The dividing feature between `car` and `truck`** is not size but what the body is for.
A separate cargo volume without side windows, or an open platform -- `truck`. A cabin
glazed throughout and fitted with seats -- `car`. A pickup is always `truck`, however
car-like.

**The dividing feature between `car` and `bus`** is seating capacity, not length.
A guide: more than three rows of seats and a separate passenger door -- `bus`.

**The dividing feature between `bicycle` and `motorcycle`** is whether an engine is the
primary drive. A scooter and a moped are `motorcycle`; an e-bike with pedals is `bicycle`.

## 3. Rules for drawing the box

1. **The visible part only.** The box covers the visible pixels of the object. What is
   hidden by an occluder or cut off by the frame border is not completed along an
   imagined contour.
2. **Tight.** The boundaries touch the outermost visible pixels of the object, with a gap
   of no more than 2 px. Empty space inside the box is the commonest cause of a low IoU.
3. **One object, one box.** If an object is split into two visible parts by an occluder
   (a person behind a pillar), a single box covering both parts is drawn.
4. **An object cut off by the frame border** is annotated by its visible part, and the box
   stops at the edge of the image.
5. **A vehicle and a person are different objects.** A cyclist yields two boxes, `person`
   and `bicycle`. They overlap, and that is normal.
6. **Real objects only.** Images of objects inside the frame -- on posters, screens, shop
   windows, in mirrors and reflections -- are not annotated.

## 4. Threshold decisions

These four numbers account for more than half of the disagreements between annotators,
which is why they are fixed explicitly.

1. **Minimum size.** An object whose shorter box side is under **20 px** is not annotated.
   It is hard to make out at the working zoom level and takes disproportionate time. The
   threshold is deliberately higher than in public datasets such as COCO: when compared
   against them, small objects will account for a noticeable share of the misses, and that
   is an expected disagreement rather than a defect.
2. **Minimum visibility.** An object is annotated if roughly a quarter or more of it is
   visible and the visible fragment identifies the class. A wheel and nothing else is not
   annotated.
3. **Identifiability outranks visibility.** A large object whose class cannot be made out
   (the silhouette of a vehicle in the dark, where `car` and `truck` are indistinguishable)
   is not annotated, and the frame goes into the disputed-case log.
4. **A dense group.** If a group holds more than ten mutually overlapping objects of one
   class and individual instances cannot be told apart by eye, only those whose contour is
   discernible in full are annotated. A single box over the group is never drawn. The rule
   holds for all six classes, not just people: bicycles in a rack and buses in a row give
   the same picture.

## 4.5. What is not annotated even when the object is large

Three cases in which size and visibility are beside the point. They have been checked in
practice and produce a predictable disagreement with an external reference, so they are
declared explicitly.

- **The carrier of the scene.** The object fills almost the whole frame and is visible only
  in fragments between other objects -- a vehicle interior from within, a body against
  which everything else is shot. That is the setting, not an object of annotation.
  Example: `000000336628.jpg`, a carriage in close-up.
- **A fragment without identification.** Part of an object is visible but does not
  establish the class with confidence -- even when that part is itself large.
  Example: `000000226903.jpg`, a person behind a shop window.
- **The background.** The object takes no part in the subject of the frame: distant,
  blurred, standing as backdrop. What is in focus is what gets annotated.

All three are a source of systematic disagreement with COCO: the reference does annotate
such objects. When working against an external reference the rules are agreed before
annotation begins.

## 5. Working order

1. Go through the frame once left to right annotating the large objects, then a second
   time for the small ones. Objects on the periphery are lost less often that way.
2. When in doubt about the class, put down the most likely one and record the frame number
   in the disputed-case log. Skipping an object out of doubt is not allowed: a miss and a
   class error are different errors and are cured differently.
3. Save every 20-30 frames.
4. Do not go back to already annotated frames to "redo them properly". If a rule changed
   along the way, write it into section 4 or 6 and apply it to every frame at once in a
   separate pass, recording that in the log.

## 6. Disputed-case log

Kept while annotating, not afterwards. Five to seven entries is normal for a hundred frames.

| Frame | What was unclear | Decision | The rule that follows from it |
|---|---|---|---|
| `000000012345.jpg` | a van glazed along its full length | `car` | glazing along the full length → `car`, added to section 2 |

## 7. Accepting someone else's annotation

The guidelines describe not only how to annotate but also how to accept the work.

**Scope of the check.** For a new annotator 100% of the first batch is checked, then 20%,
and after two clean batches in a row, 10% by random sample. A return to 100% follows any
batch rejected in full.

**What counts as an error** (CVAT terminology, so that it lines up with its comparison
report):

- `Missing annotation` -- an object of a listed class is not annotated;
- `Extra annotation` -- something not on the list is annotated, or an object is duplicated;
- `Mismatching label` -- an object is annotated with the wrong class;
- `Low overlap` -- the box is there and the class is right, but the boundaries are drawn
  loosely: the IoU lands between 0.25 and the matching threshold of 0.5. This is a warning,
  not an error: three `Low overlap` cases per batch are acceptable.

**Acceptance threshold.** A batch is accepted if, over the checked sample, the share of
errors of the first three kinds does not exceed 5%, the mean IoU over matched boxes is no
lower than 0.75, and the class agreement coefficient (Cohen's kappa) is no lower than 0.6.
Otherwise the batch goes back in full -- selective fixing by the reviewer masks the
annotator's systematic error instead of curing it.

**A disagreement with the annotator.** The dispute is settled neither by vote nor by
seniority: if the rule is in the guidelines, whoever followed it is right; if there is no
rule, the annotator is right by definition, and the rule is written into the guidelines
with a date, an example frame and a notice to the whole team. Work already handed in is
never rejected retroactively under a new rule.

**Feedback.** What goes back to the annotator is not a list of frames but a statement of
the systematic error: "vans are going to `car`, the guidelines make them `truck`, see
section 2". A list of frames without the generalisation changes nothing in their work.

## 8. Changes

| Date | What changed | Example frame |
|---|---|---|
| 2026-08-13 | first version | -- |
| 2026-08-14 | section 4.5 (4.1 when added): carrier of the scene, fragment without identification, background -- from the analysis of disagreements with COCO | `000000336628.jpg`, `000000226903.jpg` |
| 2026-08-14 | the dense-group rule extended from `person` to all six classes | `000000185157.jpg` |
| 2026-08-14 | `Low overlap` redefined as the 0.25-0.5 band; the previous wording contradicted the matching threshold | -- |
| 2026-08-14 | the minimum-size threshold raised from 5 to 20 px -- the declared value did not match practice. Under the acceptance rule (section 7) it is not applied retroactively to the batch already handed in: it holds 65 boxes under 20 px, and they stay | -- |
| 2026-08-18 | the items of section 4 numbered (4.1-4.4), the former section 4.1 became 4.5. A technical change: the content of the rules did not move. It was needed for acceptance -- an arbitration decision has to cite a specific item, and there was nothing to cite | -- |
