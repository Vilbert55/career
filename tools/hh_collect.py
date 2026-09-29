"""Сбор небольшой выборки вакансий с hh.ru через публичные страницы сайта.

API для соискателей закрыт (см. hh-api/README.md), поэтому читаем то же, что видит браузер:
JSON-состояние страницы из <template id="HH-Lux-InitialState">. Темп — одна страница
в 2–4 секунды, объём — сотни страниц за прогон.

Запуск: .venv/bin/python tools/hh_collect.py [имя_запроса ...]
Результат: data/hh/search_<запрос>.json и data/hh/vacancies.jsonl (карточки, дописываются).
"""

import html
import json
import random
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "hh"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"

# Запросы на языке поиска hh: NAME: — поиск по названию вакансии.
QUERIES = {
    "py_senior": 'NAME:(python OR питон) AND NAME:(senior OR lead OR ведущий OR старший OR "tech lead" OR техлид OR тимлид)',
    "data_engineer": 'NAME:("data engineer" OR "дата инженер" OR "инженер данных" OR DWH OR ETL OR "big data")',
    "greenplum": "greenplum",
    "architect": 'NAME:(архитектор OR architect) AND (DWH OR "платформ данных" OR "data platform" OR "архитектор данных" OR "data architect" OR "big data" OR greenplum)',
    "arenadata": "arenadata",
}
PAGES = 2  # по 50 вакансий на страницу

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})


def pause():
    time.sleep(random.uniform(2.0, 4.0))


def initial_state(url, params=None):
    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    m = re.search(r'<template[^>]*id="HH-Lux-InitialState"[^>]*>(.*?)</template>', resp.text, re.S)
    if not m:
        raise RuntimeError(f"no initial state: {resp.url}")
    return json.loads(html.unescape(m.group(1)))


def snippet(v):
    return {
        "id": v["vacancyId"],
        "name": v["name"],
        "company": (v.get("company") or {}).get("visibleName") or (v.get("company") or {}).get("name"),
        "company_id": (v.get("company") or {}).get("id"),
        "area": (v.get("area") or {}).get("name"),
        "compensation": v.get("compensation"),
        "experience": v.get("workExperience"),
        "work_formats": v.get("workFormats"),
        "published": v.get("publicationTime", {}).get("@timestamp") if isinstance(v.get("publicationTime"), dict) else v.get("publicationTime"),
    }


def search(name, text):
    items, total = [], None
    for page in range(PAGES):
        state = initial_state(
            "https://hh.ru/search/vacancy",
            {"text": text, "area": 113, "per_page": 50, "page": page, "order_by": "relevance"},
        )
        res = state["vacancySearchResult"]
        total = res["totalResults"]
        items += [snippet(v) for v in res["vacancies"]]
        print(f"{name}: page {page} -> {len(res['vacancies'])} of {total}", flush=True)
        pause()
        if len(items) >= total:
            break
    (OUT / f"search_{name}.json").write_text(
        json.dumps({"query": text, "total": total, "items": items}, ensure_ascii=False, indent=1)
    )
    return items


def details(vid):
    v = initial_state(f"https://hh.ru/vacancy/{vid}")["vacancyView"]["vacancyFull"]["vacancy"]
    desc = re.sub(r"<[^>]+>", " ", v.get("description") or "")
    return {
        "id": vid,
        "name": v.get("name"),
        "company": (v.get("company") or {}).get("visibleName") or (v.get("company") or {}).get("name"),
        "area": (v.get("area") or {}).get("name"),
        "compensation": v.get("compensation"),
        "experience": v.get("workExperience"),
        "work_formats": v.get("workFormats"),
        "key_skills": v.get("keySkills"),
        "professional_roles": v.get("professionalRoleIds"),
        "published": v.get("publicationTimeIso"),
        "description": re.sub(r"\s+", " ", html.unescape(desc)).strip(),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = sys.argv[1:] or list(QUERIES)
    ids = []
    for name in names:
        for it in search(name, QUERIES[name]):
            if it["id"] not in ids:
                ids.append(it["id"])
    store = OUT / "vacancies.jsonl"
    done = set()
    if store.exists():
        done = {json.loads(line)["id"] for line in store.open()}
    todo = [i for i in ids if i not in done]
    print(f"details: {len(todo)} new of {len(ids)}", flush=True)
    with store.open("a") as f:
        for n, vid in enumerate(todo, 1):
            try:
                f.write(json.dumps(details(vid), ensure_ascii=False) + "\n")
                f.flush()
            except Exception as exc:  # noqa: BLE001
                print(f"{vid}: {exc}", flush=True)
            if n % 25 == 0:
                print(f"details {n}/{len(todo)}", flush=True)
            pause()


if __name__ == "__main__":
    main()
