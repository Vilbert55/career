"""Профили специалистов Хабр Карьеры: срез конкурентов по близким запросам.

Без аккаунта компании Хабр отдаёт первые 10 профилей на запрос, поэтому объём набираем
сочетанием запросов и сортировок. Имена и ссылки на профили не сохраняем — только
обезличенные поля, нужные для анализа рынка.

Запуск: .venv/bin/python tools/habr_resumes.py
Результат: data/habr/resumes.json
"""

import json
import random
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "habr"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
QUERIES = [
    "greenplum", "airflow", "data engineer", "dwh", "python airflow", "архитектор данных",
    "arenadata", "dbt", "python senior", "kafka greenplum", "python lead", "data architect",
    "python postgresql", "python fastapi senior",
]
ORDERS = ["relevance", "last_visited", "salary_desc"]
KEEP = [
    "specialization", "qualification", "salary", "availability", "location", "remoteWork",
    "relocation", "skills", "age", "experience", "lastJob", "specializations",
    "experienceSpecializations", "foreignLanguages", "education", "aboutArray",
    "experienceDescriptions", "companiesHistory",
]

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json"})


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = {}
    for q in QUERIES:
        for order in ORDERS:
            resp = session.get(
                "https://career.habr.com/api/frontend_v1/resumes",
                params={"q": q, "type": "all", "page": 1, "order": order},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            print(f"{q} | {order}: {len(data['list'])} of {data['meta']['profilesTotal']}", flush=True)
            for r in data["list"]:
                key = r["id"]
                if key in rows:
                    rows[key]["queries"].append(q)
                    continue
                rows[key] = {"queries": [q], **{k: r.get(k) for k in KEEP}}
            time.sleep(random.uniform(2.0, 4.0))
    # Ключ-логин нужен только для дедупликации, в файл не пишем.
    (OUT / "resumes.json").write_text(json.dumps(list(rows.values()), ensure_ascii=False, indent=1))
    print(f"saved {len(rows)}")


if __name__ == "__main__":
    main()
