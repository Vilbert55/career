# Каркас проекта под pytest

Скопировать папку, поднять окружение, заменить `example.py` своим кодом,
заготовки тестов брать из `test_example.py` и `test_template.py`.

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
| `conftest.py` | общие фикстуры: `FakeClock`, `clock`, фабрика объектов |
| `example.py` | пример кода: сервис с внедренными часами, уведомлениями и async-клиентом |
| `test_example.py` | рабочие примеры всех приемов: raises, parametrize, фикстуры, monkeypatch, Mock, async, capsys, tmp_path |
| `test_template.py` | пустая заготовка под новый код: скопировать, переименовать, заполнить |

Шпаргалка по приемам - `../pytest.md`.
