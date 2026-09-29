"""Сбор вакансий Хабр Карьеры через публичный JSON сайта (/api/frontend/vacancies).

Запуск: .venv/bin/python tools/habr_collect.py
Результат: data/habr/vacancies.json — уникальные вакансии с пометкой, по каким запросам найдены.
"""

import json
import random
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "habr"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
QUERIES = ["python", "greenplum", "data engineer", "airflow", "dwh", "архитектор", "kafka", "postgresql", "arenadata"]
MAX_PAGES = 8

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json"})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    found = {}
    for q in QUERIES:
        page, pages = 1, 1
        while page <= min(pages, MAX_PAGES):
            resp = session.get(
                "https://career.habr.com/api/frontend/vacancies",
                params={"q": q, "type": "all", "page": page, "sort": "relevance"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            pages = data["meta"]["totalPages"]
            print(f"{q}: page {page}/{pages}, total {data['meta']['totalResults']}", flush=True)
            for v in data["list"]:
                item = found.setdefault(v["id"], {**v, "queries": []})
                item["queries"].append(q)
            page += 1
            time.sleep(random.uniform(2.0, 4.0))
    (OUT / "vacancies.json").write_text(json.dumps(list(found.values()), ensure_ascii=False, indent=1))
    print(f"saved {len(found)}")


if __name__ == "__main__":
    main()
