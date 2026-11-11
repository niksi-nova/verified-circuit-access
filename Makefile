.PHONY: data data-train eval rescore test lint train demo

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

train:
	@echo "Training belongs to M2 and is not implemented yet."
	@exit 1

demo:
	@echo "The accessible-output demo belongs to M3 and is not implemented yet."
	@exit 1
