# Каркас проекта под pytest

Скопировать папку, поднять окружение, заменить `example.py` своим кодом,
примеры и заготовку тестов брать из `test_example.py`.

```bash
cp -r ~/career/cheatsheets/pytest-template ~/yandex-interview
cd ~/yandex-interview
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest            # все тесты зеленые - окружение готово
code .                      # выбрать интерпретатор .venv
```

| Файл | Что внутри |
|---|---|
| `pytest.ini` | настройки: короткий вывод, asyncio без меток, своя метка slow |
| `.vscode/settings.json` | ИИ выключен, pytest включен в панели Testing |
| `conftest.py` | общие фикстуры: `FakeClock`, `clock`, фабрика объектов; в тестах доступны без импорта |
| `example.py` | пример кода: сервис с внедренными часами, уведомлениями и async-клиентом |
| `test_example.py` | заготовка под свой код (раздел 0) и рабочие примеры: raises, фикстуры с yield, scope и params, parametrize, monkeypatch, Mock, async, capsys, tmp_path |

Шпаргалка по приемам - `../pytest.md`.
