# HANDOFF — verified-circuit-access, M2

Status as of 2026-11-11, branch `feat/m2-training`, last pushed commit
`bd3275c`. Read `CLAUDE.md` first (commit identity and attribution rules).

## Working rules (agreed with the user)

- Commit as `Samaraditya PH <adimegarocker@gmail.com>` (local git config).
  No Claude/Anthropic mention or Co-Authored-By line in commits or PRs.
- Commit only when asked; approval to commit also covers the push to
  `feat/m2-training`. Force-pushes and other branches need their own OK.
- Real data only; never fabricate results. Every result is saved with its
  config, seed and code commit (`-dirty` runs also save the diff).
- Long jobs (hours) run on Kaggle, not on the user's desktop. Short
  CPU jobs (minutes) are fine locally. Scoring uses all cores but two.
- Secrets only from environment variables; never commit dataset files.
- Licences are not a concern (research project). The M1 Claude baseline
  run is "pending"; don't describe it otherwise.
- Run `ruff format` on specific files only, never on all of `src/`.

## What exists

| Area | Where | State |
|---|---|---|
| M1: schemas, Image2Net/CGHD loaders, NED, isomorphism, P/R, VLM baseline | `src/vca/{schemas,data,metrics,baseline}` | done; baseline run pending |
| M2 datasets (detector ×2, orientation ×8 tasks, crossing) | `scripts/prepare_m2_data.py`, `src/vca/{detect,classify}` | built in `data/m2/` |
| Training entry point (Ultralytics, provenance) | `src/vca/training.py`, `scripts/train_orientation.py` | done |
| Kaggle notebooks | `notebooks/m2_kaggle_train.ipynb` (detectors + crossing), `notebooks/m2_kaggle_orientation_netting.ipynb` | both run |
| Terminals, orientation, net extraction | `src/vca/netting/{terminals,orient,extract}.py` | done |
| Electrical rule checks | `src/vca/verify/rules.py` | done |
| End-to-end pipeline | `src/vca/pipeline.py`, `scripts/eval_pipeline.py` | done |
| Netting oracle eval (hand-drawn boxes, 37 circuits) | `scripts/eval_netting_oracle.py` | done |
| Tighter GED bound | `src/vca/metrics/assignment_ged.py` | done |
| Verifier (GBM + isotonic calibration) | — | **not started** |

Tests: 173 pass (`uv run pytest -q`), ruff clean. Makefile targets:
`prepare-m2`, `train-orientation`, `eval-netting-oracle`, `eval-pipeline`
(`make` is not installed on this Windows machine; run the commands directly).

## Results so far (real runs)

Trained models (`results/m2/`, unpacked from Kaggle `results_m2*.zip`):

| Model | Run | Metric |
|---|---|---|
| Detector, Image2Net only | `detector_i2n/20261111T084059Z` | mAP50 0.923, mAP50-95 0.724 (early stop, best epoch 30) |
| Detector, Image2Net + CGHD (**use this one**) | `detector_i2n_cghd/20261111T084059Z` | mAP50 0.930, mAP50-95 0.743, P 0.84, R 0.94 |
| Crossing (hop / dot / T, OBB) | `crossing/20261111T101421Z` | mAP50 0.968, mAP50-95 0.795 |
| Orientation, 8 tasks (`--fliplr 0`) | `orientation_<task>/2026…` | top-1 100 % on 5 tasks; bjt_m 98.5, switch 98.6, voltagelines 90.6 |

Weak detector classes: `vdd` (mAP50-95 ~0.31), `port` (~0.52), `*-bulk` MOS.
`diff-amp` has no val instances. The big Kaggle run used commit `4cc2610`.

Netlist quality (NED: lower is better; isomorphic = exactly right):

| Eval | Scoring | NED | Isomorphic | Conn. P / R |
|---|---|---|---|---|
| Oracle, 37 circuits, default orientations (Kaggle) | old | 0.68–0.70 | 8 % | 0.22 / 0.26 |
| Oracle, predicted orientations (Kaggle) | old | 0.541 | 21.6 % | 0.38 / 0.42 |
| Oracle + through-line fix | old | 0.489 | 21.6 % | 0.42 / 0.46 |
| Oracle + through-line fix | **new bound** | **0.173** | 21.6 % | 0.66 / 0.73 |
| Full pipeline, 122 circuits | old | 0.607 | 15.6 % | 0.31 / 0.32 |
| Full pipeline, 122 circuits | **new bound** | **0.234** (median 0.202) | 15.6 % | 0.64 / 0.66 |

"New bound" = the same predictions rescored with `assignment_ged.py`. The
recorded pipeline run (`results/m2/pipeline/20261111T150719Z`) was scored
with the old bound; the rescore lives only in the session scratchpad.
**First task next session: rerun `eval_pipeline.py` at `bd3275c`** (≈7 min
on 14 workers) so the 0.234 is recorded with a clean commit:

```bash
uv run python scripts/eval_pipeline.py --detector results/m2/detector_i2n_cghd/20261111T084059Z/weights/best.pt --crossings results/m2/crossing/20261111T101421Z/weights/best.pt --orientation-results results/m2
```

## Key findings (don't rediscover)

- **fliplr bug:** Ultralytics' default horizontal flip mislabels l/r and
  mirror classes. Orientation trains with `--fliplr 0`. Old runs are in
  `results/m2/_superseded_fliplr/`.
- **Orientation frames:** the 4 rotation classes are exact `np.rot90`
  copies. `l` = symbol faces left. `bjt_m` is defined in the l frame and
  `amp_m` in the d frame. Mapping in `netting/orient.py`.
- **T-junction overshoot** in plain-crossing detection was fixed with a
  near/far arm band.
- **Gate buses drawn through MOS symbols** (circuit 029) were cut by box
  blanking. Now rejoined (`find_through_lines`).
- **Plain 4-way crossings:** golden netlists sometimes treat them as
  connected (circuit 1768). After the fixes, cutting vs. joining differs
  by <0.01 NED. Default stays "cut".
- **GED timeouts:** `optimize_edit_paths` stalls far above the optimum on
  circuits with 20+ components, and more time doesn't help (029: 1.15 at
  10/60/180 s). The assignment bound gives 0.074 there. All 40 pipeline
  circuits with NED > 0.3 are still non-exact upper bounds.
- **Net extraction is the main bottleneck, detection the smaller one:** on
  the 37 oracle circuits the new bound gives 0.173 with hand-drawn boxes
  vs. 0.220 with detected boxes. The old bound hid this (0.489 vs 0.492).
- `extra_contacts` are mostly designator text touching the box ring and
  are usually left unassigned. They are noisy as a feature.

## Remaining error profile (pipeline, new bound, 122 circuits)

- 753 of 1,572 predicted components are in at least one error (47.9 %).
- Error kinds: wrong_connection 726, wrong_component_type 19,
  wrong_polarity 6, missed 3, extra 2.
- Wrong connections by category (errors / components): pmos 292/575,
  nmos 263/553, **capacitor 72/102**, resistor 58/178, pnp 16/45, npn 13/35.
- Rule flags vs. error rate: drain_source_short 41 → 100 %,
  shorted_two_terminal 14 → 100 %, unconnected_terminal 23 → 100 %,
  floating_terminal 516 → 57 %, extra_contacts 1,207 → 48 %.
- Worst circuits: 042 (0.90), 065, 039, 050, 023, 007, 064, 120, 019, 029,
  080 (0.51–0.74).

Note: error labels come from a non-exact alignment on large circuits, so
some are mis-attributed. Step 1 below exists to fix that.

## Plan to reduce NED and errors

1. **Trust the measurement.** Record the clean run (above). Strengthen the
   scorer by adding net split/merge and 3-way swap moves to the descent,
   plus a cheap lower bound (category and degree multisets), so each
   circuit reports a gap. Done when the worst circuits have
   upper − lower bounds reported and the error labels are stable across
   reruns.
2. **Capacitors first** (71 % error rate, a concrete lead). Check whether
   the box-shape orientation is wrong for vertical capacitors (horizontal
   plates make a tall-wired symbol's box wide), and whether the plate gap
   splits or merges nets. Add the fix and a synthetic test. Rescore.
3. **MOS terminal assignment** (~50 % error rate). Overlay the 11 worst
   circuits and categorise failures: Drain/Source swap from orientation or
   mirroring, body/bulk handling, extra contacts winning the Hungarian
   match, stubs reaching the wrong box edge. Likely fixes: restrict each
   terminal to contacts on its side of the box, drop text-like contacts
   (small isolated blobs with no second anchor), and a mirror classifier
   for MOS (there is none today; `mos` has no mirror task).
4. **Detection gap (0.173 → 0.220 on the oracle subset).** Diff oracle vs.
   pipeline per circuit to find missed or misclassified symbols.
5. **Rails and ports.** `vdd`/`port` detection is weak (mAP50-95 0.31/0.52).
   Measure how often GND/VDD nets are missed or merged (`rail_conflict`,
   `no_supply`). Options: retrain with more weight on those classes, or
   detect rails from net-label text.
6. **Per-drawing crossing convention.** Cut plain crossings only when the
   drawing uses dot junctions elsewhere (crossing model or dot detector).
   Score on the circuits where cut vs. join disagreed (007, 019, 036, 039,
   063, 108).
7. **Verifier (the M2 deliverable).** Train gradient boosting plus isotonic
   calibration on `predictions/*.json` component rows, labelled by
   `errors`, split by circuit. Report ECE, AUROC and flag precision/recall.
   The rule flags above are already strong signals. Retrain after steps
   2–6, since fixes change the labels.

Each step: change → oracle (37) + pipeline (122) rescore → compare per
circuit against the previous run → commit with results recorded.

## Paths

- Data: `data/image2net/` (122 validation pairs, training subsets),
  `data/cghd/`, `data/m2/` (built datasets), `data/m2_kaggle*.zip`
  (upload zips).
- Results: `results/m2/` (Kaggle runs, pipeline run). Kaggle zips:
  `results/results_m2.zip`, `results/m2/results_m2_small.zip`.
- Machine: Windows 11, 16 logical cores, AMD RX 9070 XT (not used; PyTorch
  here is CPU-only). Kaggle log timestamps are UTC.
