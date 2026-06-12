"""Validates that all lesson codes (L-NNN) in licoes-aprendidas.md are unique.

Exits with code 1 and prints duplicates if any are found.
Run as part of the quality gate.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

LICOES_PATH = Path(__file__).resolve().parents[1] / "docs" / "licoes-aprendidas.md"


def main() -> int:
    text = LICOES_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\*\*L-(\d+)\s*\|")
    occurrences: dict[str, list[int]] = defaultdict(list)

    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in pattern.finditer(line):
            code = f"L-{m.group(1)}"
            occurrences[code].append(lineno)

    duplicates = {k: v for k, v in occurrences.items() if len(v) > 1}
    if duplicates:
        print("ERRO: códigos de lição duplicados em docs/licoes-aprendidas.md:")
        for code, lines in sorted(duplicates.items()):
            print(f"  {code}: linhas {lines}")
        return 1

    print(f"OK: {len(occurrences)} lições únicas verificadas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
