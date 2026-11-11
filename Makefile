.PHONY: data data-train eval rescore test lint prepare-m2 train-orientation \n	eval-netting-oracle eval-pipeline demo

# Image2Net validation pairs (Apache-2.0), pinned commit, into git-ignored data/.
data:
	uv run python scripts/download_image2net_validation.py

# M2 training data: Image2Net training subsets (245 MB) and CGHD (4.9 GB).
# One dataset only: make data-train SETS=image2net
data-train:
	uv run python scripts/download_training_data.py $(SETS)

# M1 VLM baseline on all Image2Net validation circuits. Needs ANTHROPIC_API_KEY.
# Extra flags: make eval ARGS="--limit 5 --effort medium"
eval:
	uv run python -m vca.baseline.cli --data-approved --vlm-approved $(ARGS)

# Re-score an earlier run's saved predictions without new API calls:
# make rescore PRED=results/baseline/<run_id>/predictions
rescore:
	uv run python -m vca.baseline.cli --data-approved --vlm-approved \
		--predictions-dir $(PRED) $(ARGS)

test:
	uv run pytest -q

lint:
	uv run ruff check .

# M2 datasets under data/m2/ plus the Kaggle upload zips
# (data/m2_kaggle.zip: detectors + crossing; data/m2_kaggle_small.zip:
# orientation + netting check). Run after `make data data-train`.
prepare-m2:
	uv run python scripts/prepare_m2_data.py $(ARGS)
	uv run python scripts/prepare_m2_data.py --small-zip-only

# The detectors and crossing model train on a GPU: upload the zips to Kaggle
# and run notebooks/m2_kaggle_train.ipynb and
# notebooks/m2_kaggle_orientation_netting.ipynb. These targets are the same
# steps for a local GPU. Extra flags: ARGS="--device 0 --epochs 30"
train-orientation:
	uv run python scripts/train_orientation.py $(ARGS)

# Net extraction alone, on hand-drawn boxes (37 validation circuits).
eval-netting-oracle:
	uv run python scripts/eval_netting_oracle.py $(ARGS)

# Full pipeline on the 122 validation circuits:
# make eval-pipeline ARGS="--detector <best.pt> --crossings <best.pt> #     --orientation-results results/m2"
eval-pipeline:
	uv run python scripts/eval_pipeline.py $(ARGS)

demo:
	@echo "The accessible-output demo belongs to M3 and is not implemented yet."
	@exit 1
