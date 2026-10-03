# pytest: памятка

pytest 8+, Python 3.10+. Каркас проекта - `cheatsheets/pytest-template/`.

## Запуск

| Команда | Что делает |
| --- | --- |
| `pytest -q` / `-v` | кратко / имя каждого теста |
| `pytest test_promo.py::test_expired` | один тест |
| `pytest -k "expired or limit"` | по подстроке в имени |
| `pytest -x` | стоп на первом падении |
| `pytest --lf` | только упавшие в прошлый раз |
| `pytest -s` | показывать `print` |
| `pytest -vv` | полный diff |
| `pytest --pdb` | отладчик при падении |

- Файлы `test_*.py`, функции `test_*`, классы `Test*` без `__init__`.
- Тесты в `tests/`, код в корне - в `pytest.ini`: `pythonpath = .`.
- `conftest.py` - общие фикстуры, импорт не нужен.

## Проверки

```python
import pytest

assert total == Decimal("400.00")
assert result is None
assert len(items) == 3, f"получили {items}"
assert 0.1 + 0.2 == pytest.approx(0.3)

with pytest.raises(PromoExpired, match="AUTUMN"):      # match - regex по тексту
    service.quote("AUTUMN", Decimal("100"))

with pytest.raises(LimitExceeded) as exc_info:
    service.redeem("ONCE", user_id=1, price=Decimal("100"))
assert exc_info.value.code == "ONCE"


def test_output(capsys):
    print("готово")
    assert capsys.readouterr().out == "готово\n"


def test_logs(caplog):
    with caplog.at_level(logging.WARNING):
        logging.getLogger("promo").warning("лимит")
    assert "лимит" in caplog.text
```

- В `with pytest.raises` - только строка, которая падает: код после нее не выполнится.
- `raises(Base)` ловит и наследников.

## Параметризация

```python
@pytest.mark.parametrize(
    ("price", "percent", "expected"),
    [
        (Decimal("500"), 20, Decimal("100.00")),
        (Decimal("333.33"), 15, Decimal("49.99")),
        pytest.param(Decimal("1"), 150, None, marks=pytest.mark.xfail, id="over_100"),
    ],
    ids=["plain", "rounding", "over_100"],
)
def test_discount(price, percent, expected):
    assert discount(price, percent) == expected


@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.parametrize("y", [10, 20])
def test_grid(x, y): ...                    # 4 теста
```

## Фикстуры

```python
@pytest.fixture
def service(clock):                         # зависит от другой фикстуры
    return PromoService(clock=clock)


@pytest.fixture
def db():
    conn = connect(":memory:")
    yield conn                              # после yield - уборка, даже если тест упал
    conn.close()


@pytest.fixture
def make_promo():                           # фабрика
    def _make(**overrides):
        data = {"code": "AUTUMN20", "percent": Decimal("20")}
        data.update(overrides)
        return Promo(**data)
    return _make


@pytest.fixture(params=[InMemoryStorage, SqliteStorage])
def storage(request):                       # тесты пройдут на каждой реализации
    return request.param()
```

| Встроенная | Что дает |
| --- | --- |
| `tmp_path` | временная папка `Path` на тест |
| `monkeypatch` | временная подмена атрибутов, env, словарей |
| `capsys`, `caplog` | вывод и логи |
| `request` | `request.param` в параметризованной фикстуре |

`scope`: `function` (по умолчанию), `class`, `module`, `session`.
Фикстура подставляется по имени аргумента; из `conftest.py` - без импорта.

## Время и зависимости

Лучше передать зависимость в конструктор, чем патчить.

```python
class FakeClock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


clock = FakeClock(datetime(2026, 10, 31, 23, 59))
service = PromoService(clock=clock)         # в коде: clock=datetime.now по умолчанию
clock.advance(minutes=1)
```

## monkeypatch и mock

```python
def test_env(monkeypatch):
    monkeypatch.setenv("PROMO_LIMIT", "5")
    monkeypatch.setattr(promo, "fetch_rate", lambda zone: 1.5)
    monkeypatch.setitem(CONFIG, "currency", "RUB")


from unittest.mock import AsyncMock, Mock, patch

notifier = Mock()
service = PromoService(notifier=notifier)
service.redeem("AUTUMN20", user_id=7, price=Decimal("500"))
notifier.send.assert_called_once_with(7, "Промокод AUTUMN20 применен")

api = Mock()
api.get_rate.side_effect = [TimeoutError, 1.5]       # 1-й вызов падает, 2-й -> 1.5
api.get_status.return_value = "ok"

with patch("promo.fetch_rate", return_value=1.5) as fake:
    ...
fake.assert_called_once_with("center")
```

- Патчить имя там, где его используют: `from rates import fetch_rate` в `promo.py` - патчить `promo.fetch_rate`.
- `assert_called_once_with`, `assert_not_called`, `call_count`, `call_args_list`; `Mock(spec=Real)` - нет лишних атрибутов.

## Async

`pip install pytest-asyncio`, в `pytest.ini`: `asyncio_mode = auto`.

```python
async def test_fetch_all():
    client = AsyncMock()
    client.get.side_effect = lambda url: {"url": url}
    assert await fetch_all(client, ["a"]) == [{"url": "a"}]
    client.get.assert_awaited_once_with("a")
```

Без плагина: `assert asyncio.run(fetch_all(client, urls)) == ...`.

## Метки

```python
@pytest.mark.skip(reason="...")
@pytest.mark.skipif(sys.version_info < (3, 12), reason="...")
@pytest.mark.xfail(reason="...", strict=True)       # strict: неожиданный успех - красный
```

Свои метки - объявить в `pytest.ini` (`markers =`), запуск без них: `pytest -m "not slow"`.

## Какие случаи покрыть

1. Основной сценарий.
2. Границы: 0, 1, пусто, ровно на лимите, +-1, момент окончания срока.
3. Некорректный вход - какое исключение.
4. Деньги: копейки, итог не меньше нуля.
5. Состояние: повтор, порядок, неудачная операция ничего не меняет.
6. Несколько пользователей или объектов не делят состояние.
7. Время - через подменные часы, без `sleep`.

Имя теста - `test_<что>_<при каком условии>`. Один тест - одно поведение. Проверять публичный интерфейс.
