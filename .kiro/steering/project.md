# Verified Circuit Access — Project Steering Rules

## Project authority
- `PLAN.md` is the primary project specification.
- `DATASETS.md` is the dataset licensing and access audit.
- Follow both documents. If instructions conflict or a requirement is ambiguous, stop and ask the user.
- Do not silently change project scope, research objectives, dataset policy, or evaluation methodology.

## Scope
- Current implementation milestone: **M1 only**.
- M2 and M3 may be documented as future work but must not be implemented.
- Do not add unrelated features, frameworks, services, or dependencies.
- Follow the existing repository structure in `PLAN.md`.

## Approval gates
The user is a beginner and wants the agent to implement approved work while reviewing decisions.

- Explain proposed changes in understandable language.
- Work in small, reviewable steps.
- Before implementation, present the proposed scope and wait for approval.
- Stop at milestone boundaries for user review.
- Do not autonomously proceed to the next milestone.
- Do not download datasets, access restricted data, make external API calls, incur costs, or train models without explicit user approval.
- Never expose secrets or put API keys in source code.

## Dataset and research integrity
- Use only real data for training and evaluation.
- No synthetic or procedurally generated training/test images or labels.
- Standard augmentation of real training data is allowed where appropriate.
- Respect `DATASETS.md`: unclear, gated, or restricted datasets remain unused until explicitly approved.
- Masala-CHAI is weak-label training data only, never evaluation.
- Do not commit copyrighted textbook images or dataset files.
- Keep dataset contents and private data out of Git.
- Do not scrape datasets or use unofficial mirrors.
- Preserve source labels; do not silently discard unknown taxonomy classes.

## Experimental integrity
- Never invent, estimate, or fabricate results, metrics, benchmarks, or completed experiments.
- Clearly distinguish implemented, tested, planned, and not-run work.
- Every reported metric must come from a real run and be saved under `results/` with configuration, seed, and Git commit hash.
- If an experiment has not run, state `not run`.
- Do not claim reproducibility unless it has been verified.

## Engineering
- Python 3.11.
- Use pinned dependencies and the existing project structure.
- Write tests for schemas, data conversions, and metrics.
- Use pytest and Ruff.
- Keep implementations modular and understandable.
- Avoid unnecessary abstractions and dependencies.
- Do not modify system Python or the user's global environment.
- Explain commands and meaningful code changes briefly.

## Git
- Never commit automatically.
- Show the user what changed and explain how to review it.
- Ask before creating commits, pushing, or changing branches.
- Do not commit datasets, secrets, virtual environments, or model weights.

## Definition of done
For each approved task:
1. Implementation matches the approved requirements.
2. Relevant tests are added or updated.
3. Tests and lint checks are run when possible.
4. Failures and limitations are reported honestly.
5. Changes are summarized for user review.
6. Stop and wait for approval before continuing.
