# DATASETS

Audit of candidate datasets for `verified-circuit-access`. Compiled from
official sources only (Zenodo, GitHub, arXiv, project pages). Nothing has
been downloaded except this metadata research itself — no dataset files,
images, or archives.

**Network note:** this session's environment network policy blocks direct
fetches to `zenodo.org`, `arxiv.org`, and `masala-chai-llm.github.io`
(DNS resolution denied). `github.com` is allowed. Where a primary source
could not be fetched directly, findings below come from web-search result
snippets of that same official page, which is weaker evidence than a direct
read — flagged per dataset. Widening network access to those three hosts
(environment settings -> Network access -> Allowed domains) would let me
confirm the flagged items directly instead of relying on search snippets.

---

## 1. CGHD (handwritten circuit diagram dataset)

- **Official source:** Zenodo record [10.5281/zenodo.15333233](https://zenodo.org/records/15333233)
  (current version, published 2025-05-03). Companion GitHub repo:
  [github.com/DFKI/cghd](https://github.com/DFKI/cghd) (read directly).
  Underlying paper: Thoma, Bayer, Li, Dengel, "A Public Ground-Truth Dataset
  for Handwritten Circuit Diagram Images," ICDAR 2021 (arXiv 2402.11093).
- **License: UNCLEAR — conflicting signals across sources, not resolved.**
  - Task brief states the Zenodo record is "CC BY 4.0" — **not independently
    verified**; `zenodo.org` is network-blocked in this session, so the
    license field on the record page itself has not been read directly.
  - The GitHub companion repo's `LICENSE` file (read directly, HTTP 200) is
    the full text of **CC0 1.0 Universal**.
  - A Hugging Face mirror (`lowercaseonly/cghd`, found via search snippet
    only, not fetched directly) lists `license: cc-by-3.0`.
  - Three different licenses (CC BY 4.0 claimed, CC0 on GitHub, CC BY 3.0 on
    HF) attach to what may be different versions/packagings of the same
    dataset family — the GitHub repo's file layout (`drafter_D/` folders,
    PASCAL VOC XML, no total counts, README says "still being extended...
    under construction") does not match the Zenodo v15333233 record's
    stated contents (248,020 bbox annotations, 59 classes, 320 segmentation
    maps, 22,929 polygon annotations, single 4.9 GB zip), so they may not be
    the same release. **Do not assume a license until the actual Zenodo
    record page is read directly.**
- **Size:** 4.9 GB, single zip (per Zenodo search snippet, not independently
  confirmed by direct read).
- **Annotation format:** Bounding boxes (59 object classes), binary
  segmentation maps, polygon annotations (per Zenodo snippet). The GitHub
  mirror's older packaging uses PASCAL VOC XML per-image, plus LTspice
  `.asc` netlists for some images, plus `classes.json` class-to-int mapping.
- **Intended use:** Training/evaluating models that extract electrical
  graphs (components, wires) from raster images of hand-drawn circuits.
- **Risk:** License ambiguity (above) must be resolved by reading the
  Zenodo page directly before any use, including training. Size (4.9 GB)
  exceeds the 1 GB download-confirmation threshold in the project's data
  download rules.

## 2. Image2Net (`ci2n_datasets`)

- **Official source:** [github.com/LAD021/ci2n_datasets](https://github.com/LAD021/ci2n_datasets)
  (read directly, all pages HTTP 200). Paper: Xu et al., "Image2Net:
  Datasets, Benchmark and Hybrid Framework to Convert Analog Circuit
  Diagrams into Netlists," arXiv [2508.13157](https://arxiv.org/abs/2508.13157)
  (v2, 2025-12-08).
- **License: Apache License 2.0** for repository code and material (full
  Apache-2.0 text present at repo root `LICENSE`; GitHub sidebar confirms
  "Apache-2.0 license"). README (quoted): *"Repository code and material
  are released under the Apache License 2.0. Data users must also follow
  the requirements associated with original source material, paper
  citation, and any applicable data licenses."* — this caveat means the
  underlying circuit images' original-source licensing is not fully
  specified by the Apache-2.0 grant alone; treat as open but keep the
  citation/original-source caveat in mind.
- **Size:** 2,914 circuit diagrams, 84,195 annotations total (paper-time
  statistics per README, which notes current repo counts may differ):
  crossing/jumper set 1,983 images / 28,195 crossings; orientation/mirroring
  12,086 annotations; **104 manually verified circuit diagram/netlist pairs
  for evaluation** (this is the evaluation set named in the project brief).
- **Annotation format:** `device_identification/` — Labelme JSON (rectangle
  shapes, e.g. `"resistor"`); `jumper_identification/` — YOLO OBB rows
  (normalized 4-corner polygons); `device_orientation/` — class-organized
  JPG/PNG folders (no annotation file, label = folder); `validation/golden`
  — JSON netlists, e.g. `{"component_type": "NMOS", "port_connection":
  {"Drain": "net8", ...}}`. Files are tracked directly in the git repo
  (no git-lfs or external host mentioned).
- **Intended use:** Training detector/orientation/crossing classifiers; the
  104 netlist-labelled circuits are our evaluation set for extraction
  metrics (netlist edit distance, graph isomorphism, precision/recall).
- **Risk:** Low. Public repo, explicit Apache-2.0, no access restriction.
  Residual risk is the unnamed "applicable data licenses" caveat on
  original source material — worth re-checking if we ever redistribute
  derived images, not just use them for training/eval locally.

## 3. AMSnet 2.0

- **Official source:** arXiv [2505.09155](https://arxiv.org/abs/2505.09155)
  ("AMSnet 2.0: A Large AMS Database with AI Segmentation for Net
  Detection"), project page `amsnet2-0.github.io`. Direct fetch of both
  arxiv.org and the project's GitHub Pages site was blocked by this
  session's network policy; findings below are from web-search snippets of
  the arXiv PDF/HTML only, not a direct read.
- **License: GATED / UNCLEAR.** No license statement found in any snippet.
  No confirmed public download location, API, or repository identified for
  the actual data (only the project page URL, not independently read).
  The predecessor paper (AMSnet, arXiv 2405.09045, May 2024) said the
  dataset "would be released with the paper," which does not by itself
  confirm current public availability or license terms for AMSnet 2.0.
- **Size:** 2,686 circuits (per search snippet), each with schematic
  images, Spectre-format netlists, OpenAccess digital schematics, and
  component/net coordinates. Predecessor AMSnet had 792 circuits with
  SPICE netlists and no digital schematics.
- **Annotation format:** Schematic image + Spectre netlist + OpenAccess
  digital schematic + coordinates (per abstract; not independently
  verified against an actual sample file, since none was accessible).
- **Intended use (stated by authors):** Fine-tuning/RL of multimodal LLMs
  for netlist-to-schematic generation — not originally built as a
  verifier-training ground truth set, though that's our intended use.
- **Risk: as expected, this is the dataset most likely to be gated or
  restricted.** Do not download or use until license and access are
  confirmed directly (requires `arxiv.org` and/or
  `amsnet2-0.github.io` to be reachable, or the user supplying another
  official link).

## 4. Masala-CHAI

- **Official source:** Project page `masala-chai-llm.github.io` (network-
  blocked, not independently read). Paper: Bhandari, Bhat, He, Rahmani,
  Garg, Karri, "Masala-CHAI: A Large-Scale SPICE Netlist Dataset for Analog
  Circuits by Harnessing AI," arXiv [2411.14299](https://arxiv.org/abs/2411.14299)
  (v1 2024-11-21 through v5 2025-03-23). Findings below are from web-search
  snippets of the arXiv listing only.
- **License: UNCLEAR.** Authors state in the abstract that they
  "open-source our dataset and code for community-driven development," but
  no GitHub repository URL, license name, or Hugging Face dataset card was
  found in available snippets, and the project page itself could not be
  fetched directly in this environment. "Open-source" is an author claim,
  not a confirmed license grant.
- **Size:** Scope changed across versions — v1/v2 describe ~2,100
  schematics from one textbook; later versions (through v5) describe
  ~7,500 schematics spanning varying complexity across 10 textbooks.
- **Annotation format:** SPICE netlists plus metadata (figure captions,
  components, nodes), generated by an AI/LLM-driven pipeline rather than
  human-verified ground truth.
- **Intended use:** Per the project's hard rules, **weak labels only — the
  netlists are auto-generated, so this dataset is never to be used for
  evaluation**, only as (optionally) weak/noisy training signal if its
  license permits use at all.
- **Risk:** License and exact distribution channel both unconfirmed. Even
  if the license turns out to be permissive, the auto-generated-netlist
  caveat from the hard rules applies regardless — this is a training-only,
  never-evaluation dataset by policy, independent of licensing.

## 5. SINA

- **Official source:** Two arXiv papers, both located and distinct from
  the user's original brief IDs — note the IDs differ slightly from what
  was listed (2601.22114 and 2607.01609 did resolve, matching the brief):
  - arXiv [2601.22114](https://arxiv.org/abs/2601.22114) (v1, 2026-01,
    earlier version) — evaluates on "an open-source benchmark": a
    component-detection test set of 75 schematics with 1,000+ components
    across 10 types, spanning computer-generated, scanned, and hand-drawn
    schematics.
  - arXiv [2607.01609](https://arxiv.org/abs/2607.01609) ("SINA: A Fully
    Automated Circuit Schematic Image to Netlist Generator Using Artificial
    Intelligence," 2026-07-02, authors Saoud Aldowaish et al., cs.LG) —
    pipeline: object detection for components, connected-component
    labeling for connectivity, OCR for reference designators, a VLM for
    assigning them, and a dedicated wire-crossing-vs-junction module.
    Reports 96.67% overall netlist generation accuracy, ~2.72x the
    compared baselines; correctness checked via graph isomorphism.
  - Both IDs were confirmed to exist and match the claimed topic via
    web-search snippets; direct fetch of arxiv.org was blocked, so full
    text, any linked repo, and license were not independently read.
- **License: UNCLEAR.** Search summaries describe SINA as an "open-source
  tool" and reference an "open-source benchmark," but no GitHub repo URL or
  explicit license name was found in the available snippets.
- **Size:** Component-detection benchmark (2601.22114): 75 schematics,
  1,000+ components, 10 component types, mixed source types
  (computer-generated / scanned / hand-drawn). No separate size figure
  found yet for the July 2026 paper's own released data, if any.
- **Annotation format:** Not independently confirmed (would need the full
  paper or a linked repo to confirm exact format).
- **Intended use:** Open-source baseline/benchmark for extraction method
  comparison (per project brief); potential use for net-extraction
  (connected-component) methodology reference and as an eval benchmark if
  license permits.
- **Risk:** As expected, likely needs more digging once arxiv.org is
  reachable, or the user provides a repo link directly. Do not treat
  "open-source" claims in the abstract as a confirmed license.

## 6. CircuitReason-1k

- **Official source:** [github.com/CircuitReason/CircuitReason1K](https://github.com/CircuitReason/CircuitReason1K)
  (read directly, HTTP 200; `LICENSE` file fetch returned HTTP 404).
- **License: UNCLEAR / effectively none granted.** No `LICENSE` file
  exists in the repo (confirmed 404), no license badge or section in the
  README, and the repo's "About" box shows "No description, website, or
  topics provided." Absent an explicit license, default copyright applies
  and no reuse rights are granted — this needs the maintainers to add a
  license, or explicit permission, before any use.
- **Size:** Not stated as a final number. The README gives only
  intermediate pipeline-construction statistics: pipeline started from 27
  source materials and 18,576 pages; high-recall mining produced 4,039
  problem candidates and 5,053 candidate figures, before alignment and
  verification trims that down. The name implies roughly 1,000 final
  items, but this is not confirmed in the README.
- **Annotation format:** Each record: `id`, `family_id`, `image_paths`,
  `question`, `answer` (typed, e.g. "structured"), `short_answer`,
  `reference_solution`, `distractors`, `source`, `verification`. Evaluated
  model receives only `image_paths` and `question`; scoring uses a
  deterministic scorer plus "identity-blinded semantic Judges" with
  strict-majority resolution.
- **How images are distributed — this is the key risk flagged in the
  project brief, and it is confirmed, not resolved:** the repo does **not**
  ship circuit images. The README instructs users to *"Put locally licensed
  textbooks under `data/raw_pdfs/`"* and run a pipeline script that writes
  final files to `release/`. In other words, the benchmark's images are
  meant to be generated locally from textbooks the user already has rights
  to use — the repo does not re-host or redistribute textbook figures
  itself. However, this also means **the exact benchmark used in the
  paper is not reproducible from the repo alone** unless we have the same
  27 source materials, which are not named in the README.
- **Intended use:** Downstream comprehension/reasoning evaluation —
  comparing image-only VLM performance vs. verified-graph-grounded
  text-only LLM performance (per project brief, Milestone 3).
- **Risk:** No license on the code (needs clarification/permission before
  use, even for the pipeline code). No bundled or linked data release
  (needs either the original 27 source materials or a provided data
  release to reproduce the actual CircuitReason-1k benchmark — running the
  pipeline on different textbooks would produce a different, non-equivalent
  benchmark). This dataset needs the most follow-up of any on this list
  before it's actually usable.

---

## Summary table

| Dataset | Status | Why |
|---|---|---|
| Image2Net (`ci2n_datasets`) | **Clearly open** (with a minor caveat) | Apache-2.0 on the repo, public, no access restriction. Caveat: README references unnamed "applicable data licenses" for original source material. |
| CGHD | **Unclear** | Three different licenses found across three sources (CC BY 4.0 claimed / CC0 on GitHub mirror / CC BY 3.0 on HF mirror) for what may not even be the same dataset version. Needs a direct read of the actual Zenodo record (network-blocked this session). |
| AMSnet 2.0 | **Gated / unclear** | No license or confirmed public download found anywhere in available sources (network-blocked; only search snippets available). As anticipated in the brief. |
| Masala-CHAI | **Unclear** | Authors claim "open-source" but no repo URL, license name, or dataset card located; project page network-blocked. Also: weak-labels-only, never-evaluation, by project policy regardless of license outcome. |
| SINA | **Unclear** | Both papers confirmed to exist and match the topic, but no license or repo URL found in available snippets; arxiv.org network-blocked for a direct read. |
| CircuitReason-1k | **Unclear / effectively gated** | No LICENSE file at all (404) — no reuse rights granted by default. The actual ~1k benchmark data isn't in the repo either; only the construction pipeline is, and it needs source textbooks not named in the README. |

**Decision needed from you:** nothing has been or will be downloaded beyond
this metadata research. Per the hard rules, anything in the "unclear" or
"gated" rows stays untouched until you say otherwise — including Image2Net,
I'd like your explicit go-ahead before Step 2 downloads anything, since it's
the only one in the "clearly open" row.

Two things would help resolve the "unclear" rows faster, at your discretion:
1. Widening this environment's network access to `zenodo.org`, `arxiv.org`,
   and `masala-chai-llm.github.io` so I can read those primary sources
   directly instead of relying on search-result snippets.
2. Telling me if you already know a canonical license/source for any of
   these (e.g. if you've seen AMSnet 2.0 or SINA's actual repo) that I
   haven't found.
