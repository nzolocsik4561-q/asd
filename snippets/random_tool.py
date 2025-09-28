"""Small utility with deterministic pseudo-random output."""

from __future__ import annotations

import hashlib


def fingerprint(text: str, length: int = 8) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:length]


if __name__ == "__main__":
    print(fingerprint("codex-demo"))
