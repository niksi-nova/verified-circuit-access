"""Run the local analysis engine API.

    uv run python scripts/serve_api.py

Binds to 127.0.0.1:8000 only (not 0.0.0.0) — this is a local demo tool,
never meant to be reachable from the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    import uvicorn

    uvicorn.run("vca.api.app:app", host="127.0.0.1", port=8000, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
