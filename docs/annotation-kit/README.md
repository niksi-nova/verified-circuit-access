# Private curriculum folder layout

Keep this layout inside `data/private/curriculum/`. The repository ignores
that directory. This checked-in README contains only the folder instructions.

```text
curriculum/
  README.md
  manifest.tsv                  # id, textbook, edition, page, figure, notes
  images/fig-0001.png
  labelme/fig-0001.json
  netlists/fig-0001.json
```

Copy this README into the private folder as needed. Use matching stems across
the three input directories. JPEG is also accepted. Keep citations and any
crop notes in the private manifest.

```sh
uv run python scripts/check_annotation.py data/private/curriculum/labelme/fig-0001.json data/private/curriculum/netlists/fig-0001.json
uv run --extra train python scripts/eval_curriculum.py data/private/curriculum
```

The evaluator validates each pair and writes predictions, per-figure scores,
a summary, and the run configuration under `results/m2/curriculum/`. Keep
those outputs private too. The kit ships with zero annotated figures.
