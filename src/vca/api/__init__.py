"""Local analysis engine: FastAPI app, job queue, upload storage.

Setting YOLO_AUTOINSTALL=False here, before anything in this package can
import ultralytics, is load-bearing: without it, ultralytics'
PIL.Image.open monkey-patch attempts a `pip install` the first time any
code (ours or a dependency's) opens a file PIL can't identify — a
network call, which this API must never make (see storage.validate_upload
and its tests for the case that exercises this).
"""

import os

os.environ.setdefault("YOLO_AUTOINSTALL", "False")
