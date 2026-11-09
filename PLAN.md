# PLAN: verified-circuit-access

## Problem

Blind students at high-school and undergraduate level cannot access circuit
diagrams in textbooks. This project builds a pipeline that turns a circuit
image into a layered, verified explanation usable by a screen reader, a
braille display, or a tactile printer:

```
circuit image -> extraction -> verified netlist graph -> layered explanation
    -> (a) screen-reader text
    -> (b) braille-ready text (liblouis)
    -> (c) tactile-printable SVG
```

The novelty is not extraction (Masala-CHAI, AMSnet, Image2Net and SINA
already do this). It is:

1. A trained, calibrated per-element **verifier** that predicts which
   extracted components and connections are wrong and flags them for a
   teacher, instead of trusting extraction output silently.
2. A **graph-grounded explanation layer** whose numeric claims (equivalent
   resistance, operating points) come from an ngspice simulation on the
   verified graph, not from an LLM guessing.
3. **Evaluation by downstream comprehension** (CircuitReason-1k), not just
   extraction accuracy.

## Hard rules (binding for every milestone)

- Real data only. No synthetic/procedurally generated images or labels for
  training or testing; only standard on-the-fly augmentation of real images.
- Never fabricate results. Every metric reported anywhere comes from an
  actual run, saved under `results/` with its config, seed, and git commit
  hash. Anything not run is marked "not run".
- If a dataset is gated, needs an agreement, or has unclear licensing: stop
  and ask before using it. No scraping, no unofficial mirrors, no
  redistribution.
- No copyrighted textbook images or dataset files committed to the repo.
  `data/` and `data/private/` are git-ignored.
- Secrets only from environment variables (`.env.example` documents the
  shape, never real values).
- Python 3.11, pinned dependencies in `pyproject.toml`, `pytest`, `ruff`,
  fixed seeds, a `Makefile` with targets `data`, `train`, `eval`, `demo`.

## Folder layout (target, built incrementally per milestone)

```
verified-circuit-access/
  PLAN.md
  DATASETS.md                 # M1: source, license, size, format, risk per dataset
  README.md                   # M1: problem statement, architecture diagram, repro steps
  pyproject.toml              # M1: pinned deps, Python 3.11
  Makefile                    # M1: data / train / eval / demo targets
  .env.example
  src/
    vca/
      schemas/                # netlist JSON graph schema (Pydantic), COCO taxonomy mapping
      data/                   # dataset loaders, format converters, unit-tested
      metrics/                # netlist edit distance, graph-isomorphism accuracy,
                               # component/connection precision & recall
      baseline/                # pluggable VLM provider -> netlist JSON, retry on invalid JSON
      detect/                  # M2: component detector (YOLO-family)
      classify/                # M2: orientation/polarity, crossing-vs-junction classifiers
      netting/                 # M2: connected-component net extraction, optional segmentation
      verify/                  # M2: feature extraction + gradient boosting + calibration
      explain/                 # M3: layered explanation, ngspice-grounded facts
      outputs/                 # M3: screen-reader text, liblouis braille, tactile SVG
  tests/                      # pytest, mirrors src/vca layout
  data/                       # git-ignored: downloaded datasets
    private/                  # git-ignored: curriculum annotations (M3), never invented
  results/                    # metrics from real runs only, each with config+seed+commit hash
  notebooks/                  # exploratory only, not a source of truth
```

## Milestones

### M1 — Data audit and baseline (next, pending approval of this plan)

- `DATASETS.md`: official source, license, size, annotation format, intended
  use, and risk for each of CGHD, Image2Net, AMSnet 2.0, Masala-CHAI
  (weak labels only, never for evaluation), SINA, CircuitReason-1k.
  AMSnet 2.0 and SINA licensing/access must be verified before any download.
  Excludes synthetic subsets (Netlistify, FlowLearn-simulated) and
  primary/middle-school diagram sets (AI2D, TQA).
- Unified formats: COCO-style boxes with a documented harmonized class
  taxonomy, and a netlist JSON graph schema (Pydantic). Loaders unit-tested.
- Metrics: netlist edit distance (Image2Net definition), graph-isomorphism
  accuracy, component precision/recall, connection precision/recall.
- Baseline: one VLM call returning netlist JSON (pluggable provider, retry
  on invalid JSON), evaluated on Image2Net's 104 labelled circuits. Failure
  cases (wrong polarity, wrong connection, missed component) saved with
  overlay images.
- README with problem statement, mermaid architecture diagram, repro steps.

### M2 — Training (plan only for now, build after M1 is approved)

- Component detector (YOLO-family) on Image2Net + CGHD; per-class mAP.
- Orientation/polarity classifier and crossing-vs-junction classifier on
  Image2Net (+ CGHD rotation/mirror labels).
- Net extraction via connected-component labeling after masking components
  (SINA-style); optional segmentation model on CGHD maps.
- Verifier: gradient boosting + isotonic calibration over detector
  confidences, crossing/polarity probabilities, detector-vs-VLM agreement,
  rule violations (floating nets, shorted sources, no ground), OCR
  confidence. Labelled correct/incorrect against ground-truth netlists.
  Report ECE, AUROC, flagging precision/recall. Split by source textbook to
  prevent leakage.
- Stretch only: LoRA fine-tune of an open VLM.

### M3 — Explanation and evaluation (plan only for now)

- Layered explanation (overview -> functional blocks -> details) from the
  verified graph; equivalent resistance and operating points from ngspice.
  The LLM may only phrase facts already present in the graph/simulation.
- Outputs: screen-reader text, braille via liblouis (`.brf`), tactile SVG.
- Evaluation: CircuitReason-1k accuracy for (i) image-only VLM vs.
  (ii) verified-graph -> text-only LLM; flag-rate vs. errors caught.
- Curriculum test set: annotation tooling/guideline (labelme or CVAT +
  netlist JSON) for manually annotating 60-100 real textbook figures into
  `data/private/`. Annotations are never invented.

### Phase 2 — not started

Flowcharts and block diagrams (FlowLearn scientific subset, DiagramNet),
real data only, through the same graph core. Out of scope until M1-M3 land.

## Compute needs

- Primary local machine: MacBook Pro, Apple M5, 16GB unified memory. No
  dedicated NVIDIA GPU — usable via CPU/MPS for light work (data prep,
  metrics, the gradient-boosting verifier, CPU-side ngspice simulation,
  small-scale inference), but not a good fit for detector/VLM training at
  any real speed.
- Secondary: Google Colab and Kaggle notebook GPUs (free-tier T4-class,
  time-limited sessions) for anything that actually needs a GPU — YOLO-family
  detector training (M2) and any stretch LoRA fine-tuning. Training code
  must run both locally (CPU/MPS, small smoke runs) and on a rented
  Colab/Kaggle GPU (full runs), with checkpoints/results pulled back into
  `results/` after each run.
- Implication for M2 scheduling: keep detector/classifier training jobs
  small enough to fit Colab/Kaggle session time limits (checkpoint and
  resume rather than one long run); the verifier (gradient boosting) and
  M3 (ngspice, liblouis, text generation) are not GPU-bound and run fine on
  the M5 locally.
- M1 baseline uses a hosted VLM API (pluggable provider), not local compute.

## Risks

- **Dataset licensing/access uncertain**: AMSnet 2.0 and SINA need explicit
  license/access verification before use (arXiv papers don't guarantee an
  open, redistributable dataset). CircuitReason-1k's image distribution
  mechanism needs checking so images stay local, not re-hosted. Mitigation:
  DATASETS.md audit is the first deliverable of M1; nothing is downloaded
  until its source and license are confirmed per-dataset, and anything
  gated/unclear is flagged before use, not worked around.
- **Taxonomy mismatch across datasets**: CGHD, Image2Net, and AMSnet likely
  use different component class vocabularies. Mitigation: an explicit,
  documented class-mapping table in M1, with unit tests on the mapping
  itself, not just the loaders.
- **Evaluation leakage**: components/connections from the same textbook or
  circuit family appearing in both train and verifier-eval splits would
  inflate verifier metrics. Mitigation: split by source textbook, not
  randomly, as specified in M2.
- **GPU scarcity**: no local dedicated GPU; Colab/Kaggle free tiers have
  session time limits and can preempt long runs. Mitigation: checkpointed,
  resumable training jobs; keep M2 models small (YOLO-nano/small class,
  gradient boosting) rather than assuming large-batch, long-horizon training.
- **Baseline VLM cost/availability**: a pluggable provider with retry-on-
  invalid-JSON is needed because VLM structured output can be unreliable;
  budget for repeated calls across 104 evaluation circuits.
- **Downstream comprehension evaluation (M3) is the hardest metric to get
  right**: CircuitReason-1k may not cleanly support an apples-to-apples
  image-only vs. verified-graph-text comparison. Mitigation: this is
  explicitly scoped as "plan only for now" in M3, to be designed once M1's
  dataset audit clarifies what CircuitReason-1k actually provides.
- **Curriculum annotation effort (M3)**: 60-100 real textbook figures
  annotated by hand is a real time cost and must use real figures only
  (never invented), stored in git-ignored `data/private/`.
