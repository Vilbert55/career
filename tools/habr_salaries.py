"""Зарплаты из калькулятора Хабр Карьеры (данные анкет пользователей, суммы на руки).

Запуск: .venv/bin/python tools/habr_salaries.py
Результат: data/habr/salaries.json — медиана и квартили по квалификациям для каждого среза.
"""

import itertools
import json
import random
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
SPECS = [None, "backend", "data_engineer", "software_architect", "database_developer"]
SKILLS = {None: None, "python": 446}
LOCATIONS = {None: None, "Москва": "c_678", "Санкт-Петербург": "c_679"}


def main():
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "application/json"})
    out = []
    for spec, skill, loc in itertools.product(SPECS, SKILLS, LOCATIONS):
        params = [("employment_type", 0)]
        if spec:
            params.append(("spec_aliases[]", spec))
        if SKILLS[skill]:
            params.append(("skills[]", SKILLS[skill]))
        if LOCATIONS[loc]:
            params.append(("locations[]", LOCATIONS[loc]))
        data = session.get(
            "https://career.habr.com/api/frontend_v1/salary_calculator/general_graph", params=params, timeout=30
        ).json()
        groups = {g["name"]: {k: g[k] for k in ("median", "p25", "p75", "min", "max", "total")} for g in data["groups"]}
        out.append({"spec": spec, "skill": skill, "location": loc, "groups": groups})
        print(spec, skill, loc, {k: (v["median"], v["total"]) for k, v in groups.items() if k in ("Senior", "Lead")}, flush=True)
        time.sleep(random.uniform(1.5, 3.0))
    (ROOT / "data" / "habr" / "salaries.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
