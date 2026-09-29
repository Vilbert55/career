"""Проверка резюме: только символы с обычной клавиатуры (латиница, кириллица, цифры, ASCII-знаки, №).

Запуск: .venv/bin/python tools/check_resume.py [файлы...]; по умолчанию — resume/*.md.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = re.compile(r"[\x20-\x7EА-Яа-яЁё№\n]")


def main():
    files = [Path(f) for f in sys.argv[1:]] or sorted((ROOT / "resume").glob("*.md"))
    bad = 0
    for f in files:
        for n, line in enumerate(f.read_text().splitlines(), 1):
            chars = sorted({c for c in line if not ALLOWED.match(c)})
            if chars:
                bad += 1
                print(f"{f.name}:{n}: {' '.join(repr(c) for c in chars)} | {line.strip()[:90]}")
    print("ok" if not bad else f"строк с лишними символами: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
