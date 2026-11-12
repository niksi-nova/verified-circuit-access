"""Translate explanation text using Liblouis and paginate the resulting cells."""

from __future__ import annotations

import os
import shutil
import subprocess
import threading

WIDTH = 40
HEIGHT = 25
DEFAULT_TABLE = "en-ueb-g1.ctb"
_LOCK = threading.Lock()


def available() -> bool:
    return shutil.which("lou_translate") is not None


def _translate(text: str, table: str, display: str) -> str:
    try:
        import louis
    except (ImportError, OSError):
        result = subprocess.run(
            ["lou_translate", "-f", "-d", display, table],
            input=text + "\n",
            text=True,
            capture_output=True,
            check=True,
            timeout=15,
        )
        return result.stdout.rstrip("\n")
    with _LOCK:
        return "\n".join(
            louis.translateString([display, table], line) if line else ""
            for line in text.split("\n")
        )


def _wrap(ascii_line: str, unicode_line: str):
    while len(unicode_line) > WIDTH:
        split = max(unicode_line.rfind(blank, 0, WIDTH + 1) for blank in (" ", "⠀"))
        end = split if split > 0 else WIDTH
        yield ascii_line[:end], unicode_line[:end]
        start = end + (split > 0)
        ascii_line, unicode_line = ascii_line[start:], unicode_line[start:]
    yield ascii_line, unicode_line


def translate(text: str, table: str | None = None) -> dict:
    table = table or os.environ.get("VCA_BRAILLE_TABLE", DEFAULT_TABLE)
    header, body = "Braille Press", text.strip()
    content = f"{header}\n{body}"
    ascii_lines = _translate(content, table, "en-us-brf.dis").split("\n")
    unicode_lines = _translate(content, table, "unicode.dis").split("\n")
    rows = list(zip(ascii_lines, unicode_lines, strict=True))
    if any(
        len(a) != len(u)
        or any(not 32 <= ord(c) <= 95 for c in a)
        or any(c != " " and not 0x2800 <= ord(c) <= 0x283F for c in u)
        for a, u in rows
    ):
        raise ValueError("The selected Liblouis table did not produce six-dot braille.")
    header_ascii, header_unicode = rows[0]
    if len(header_unicode) > WIDTH:
        raise ValueError("The braille header exceeds one line.")
    wrapped = [row for pair in rows[1:] for row in _wrap(*pair)]
    pages = [
        [(header_ascii, header_unicode), *wrapped[i : i + HEIGHT - 1]]
        for i in range(0, max(1, len(wrapped)), HEIGHT - 1)
    ]
    return {
        "table": table,
        "brf": "\f".join("\r\n".join(a for a, _ in page) + "\r\n" for page in pages),
        "pages": ["\n".join(u for _, u in page) for page in pages],
    }


def braille_output(text: str) -> dict | None:
    if not available():
        return None
    return translate(text)
