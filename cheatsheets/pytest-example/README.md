# Пример проекта с pytest

| Файл | Что внутри |
|---|---|
| `wallet.py` | рабочий код: кошелек, перевод, хранение в sqlite, async-запрос |
| `conftest.py` | фикстуры: простая, фабрика, с yield, на других фикстурах |
| `test_wallet.py` | тесты: assert, raises, parametrize, фикстуры, Mock, monkeypatch, async |
| `pytest.ini` | короткий вывод, async-тесты без меток |
| `.vscode/settings.json` | ИИ выключен, pytest в панели Testing |

```bash
cp -r ~/career/cheatsheets/pytest-example ~/my-project
cd ~/my-project
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest            # 16 passed - окружение готово
```

Для своего кода: заменить `wallet.py`, фикстуры в `conftest.py`, тесты в `test_wallet.py`.
Приемы подробнее - `../pytest.md`.
