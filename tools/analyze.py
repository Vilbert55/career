"""Сводка по собранным вакансиям hh.ru и Хабр Карьеры.

Запуск: .venv/bin/python tools/analyze.py > analysis/raw-stats.txt
Деньги приводятся к сумме до вычета НДФЛ по шкале 2026 года: 13 % до 200 тыс. в месяц,
15 % сверх (ставки для доходов до 5 млн в год).
"""

import collections
import json
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HH = ROOT / "data" / "hh"

# Термины для поиска в тексте вакансий: ключ — как показываем, значение — регулярка.
TERMS = {
    "Python": r"\bpython", "SQL": r"\bsql\b", "PostgreSQL": r"postgres", "Greenplum": r"greenplum|\bgp\b",
    "Arenadata": r"arenadata|\badb\b", "ClickHouse": r"clickhouse", "Oracle": r"oracle", "MS SQL": r"ms ?sql|t-sql",
    "Airflow": r"airflow", "dbt": r"\bdbt\b", "Spark": r"spark", "Hadoop/HDFS": r"hadoop|hdfs|hive",
    "Kafka": r"kafka", "NiFi": r"nifi", "Flink": r"flink", "Trino/Presto": r"trino|presto", "Iceberg": r"iceberg",
    "S3/MinIO": r"\bs3\b|minio", "Data Vault/Anchor": r"data ?vault|anchor", "Kimball/звезда": r"kimball|звезд|snowflake schema",
    "Data Mesh": r"data ?mesh", "Lakehouse": r"lakehouse", "Docker": r"docker", "Kubernetes": r"kubernetes|\bk8s",
    "CI/CD": r"ci ?/ ?cd|gitlab ci", "Ansible": r"ansible", "Terraform": r"terraform", "Linux": r"linux",
    "FastAPI": r"fastapi", "Django": r"django", "asyncio": r"asyncio|async", "Celery": r"celery",
    "RabbitMQ": r"rabbit", "Redis": r"redis", "gRPC": r"grpc", "микросервисы": r"микросервис|microservice",
    "высоконагруж.": r"высоконагруж|highload|high-load", "архитектура": r"архитектур", "ревью": r"ревью|review",
    "менторство": r"ментор|наставни", "лидерство команды": r"руковод[а-я]* команд|управлени[ея] команд|тимлид|team ?lead",
    "ИИ/LLM": r"\bllm\b|нейросет|\bии\b|\bai\b|copilot|cursor", "английский": r"английск|english",
    "ADR/документация": r"\badr\b|документац", "мониторинг": r"мониторинг|grafana|prometheus",
    "OpenMetadata/каталог": r"openmetadata|datahub|каталог данных|data catalog", "качество данных": r"качеств[а-я]* данных|data quality",
}
EXP = {"noExperience": "нет", "between1And3": "1–3", "between3And6": "3–6", "moreThan6": "6+"}


def gross(value, is_gross):
    if value is None:
        return None
    if is_gross:
        return value
    # На руки -> до вычета: net = G - 0.13*200k - 0.15*(G-200k) = 0.85*G + 4000 при G > 200k.
    return value / 0.87 if value <= 174000 else (value - 4000) / 0.85


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else None


def money(xs):
    xs = [x for x in xs if x and 30000 < x < 3000000]
    if not xs:
        return "нет данных"
    return f"n={len(xs)} p25={pct(xs, .25) / 1000:.0f} медиана={st.median(xs) / 1000:.0f} p75={pct(xs, .75) / 1000:.0f} тыс."


def clean(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def comp(v):
    c = v.get("compensation") or {}
    if c.get("noCompensation") or not (c.get("from") or c.get("to")):
        return None, None
    if c.get("currencyCode", "RUR") != "RUR":
        return None, None
    g = c.get("gross", False)
    return gross(c.get("from"), g), gross(c.get("to"), g)


def hh_report():
    cards = {}
    for line in (HH / "vacancies.jsonl").open():
        v = json.loads(line)
        cards[v["id"]] = v
    for f in sorted(HH.glob("search_*.json")):
        s = json.loads(f.read_text())
        name = f.stem.removeprefix("search_")
        vs = [cards[i["id"]] for i in s["items"] if i["id"] in cards]
        print(f"\n===== hh.ru: {name} — всего на сайте {s['total']}, в выборке {len(vs)}")
        print(f"запрос: {s['query']}")
        froms, tos = zip(*[comp(v) for v in vs]) if vs else ((), ())
        with_salary = sum(1 for a, b in zip(froms, tos) if a or b)
        print(f"с зарплатой: {with_salary} из {len(vs)}")
        print(f"зарплата ОТ (до вычета): {money(froms)}")
        print(f"зарплата ДО (до вычета): {money(tos)}")
        print("опыт:", dict(collections.Counter(EXP.get(v["experience"], v["experience"]) for v in vs)))
        fmts = collections.Counter(x for v in vs for x in (v.get("work_formats") or []))
        print("формат:", dict(fmts))
        print("города:", collections.Counter(v["area"] for v in vs).most_common(6))
        ks = collections.Counter(k for v in vs for k in (v.get("key_skills") or []))
        print("ключевые навыки (поле hh):", ks.most_common(35))
        text = [(v["name"] + " " + v["description"]).lower() for v in vs]
        tf = {t: sum(1 for x in text if re.search(rx, x)) for t, rx in TERMS.items()}
        print("упоминания в тексте, % вакансий:",
              ", ".join(f"{t} {100 * n // max(1, len(vs))}" for t, n in sorted(tf.items(), key=lambda x: -x[1]) if n))
        print("компании:", collections.Counter(v["company"] for v in vs).most_common(40))
    return cards


def habr_report():
    vac = json.loads((ROOT / "data" / "habr" / "vacancies.json").read_text())
    print(f"\n===== Хабр: вакансии, уникальных {len(vac)}")
    by_q = collections.defaultdict(list)
    for v in vac:
        for q in v["queries"]:
            by_q[q].append(v)
    for q, vs in by_q.items():
        rel = [v for v in vs if v.get("qualification") in ("Senior", "Lead")]
        sal = [(v["salary"] or {}).get("from") for v in rel if (v["salary"] or {}).get("currency") in ("rur", None)]
        print(f"{q}: всего {len(vs)}, Senior/Lead {len(rel)}; ОТ на руки {money(sal)}")
    rel = [v for v in vac if v.get("qualification") in ("Senior", "Lead")]
    print("навыки Senior/Lead:", collections.Counter(s["title"] for v in rel for s in v["skills"]).most_common(40))

    res = json.loads((ROOT / "data" / "habr" / "resumes.json").read_text())
    print(f"\n===== Хабр: профили специалистов, {len(res)}")
    q = collections.Counter(clean((r["qualification"] or {}).get("title")) for r in res)
    print("квалификация:", q.most_common())
    for grade in (("Senior", "Старший"), ("Lead", "Ведущий")):
        xs = [r["salary"]["value"] for r in res
              if clean((r["qualification"] or {}).get("title")) in grade and r.get("salary")
              and r["salary"].get("currency") == "rur"]
        print(f"желаемая зарплата {grade[0]} (на руки): {money(xs)}")
    print("навыки:", collections.Counter(clean(s["title"]) for r in res for s in r["skills"]).most_common(50))
    print("должности:", collections.Counter(clean((r["lastJob"] or {}).get("position")) for r in res).most_common(25))


if __name__ == "__main__":
    hh_report()
    habr_report()
