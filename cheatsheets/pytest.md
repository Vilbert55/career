# pytest: памятка

03.10.2026. Оригинал (Claude Docs, можно выгрузить в PDF): https://claude.ai/code/artifact/d1e73bbd-70ff-49df-89ee-bd115d73a36a

pytest 8-9, Python 3.10+. Готовый каркас проекта с заготовками - `cheatsheets/pytest-template/` в репозитории career. Все примеры проверены запуском.

## 1. Запуск и структура

```
project/
  promo.py            # код
  test_promo.py       # тесты: test_*.py или *_test.py
  conftest.py         # общие фикстуры, импортировать не нужно
  pytest.ini          # настройки (необязательно)
```

- pytest собирает функции `test_*` и методы `test_*` в классах `Test*` (без `__init__`).
- Код и тесты в одной папке - `from promo import ...` работает сразу. Тесты в `tests/`, код в корне - добавить в `pytest.ini` строку `pythonpath = .`.
- В одном проекте нельзя два тестовых файла с одинаковым именем в разных папках без `__init__.py` - ошибка сбора.

| Команда | Что делает |
| --- | --- |
| `pytest -q` | краткий вывод |
| `pytest -v` | имя каждого теста |
| `pytest test_promo.py::test_expired` | один тест |
| `pytest -k "expired or limit"` | тесты, в имени которых есть подстрока |
| `pytest -x` | остановиться на первом падении |
| `pytest --lf` | только упавшие в прошлый раз |
| `pytest -s` | показывать `print` (по умолчанию вывод перехватывается) |
| `pytest -vv` | полный diff длинных списков и словарей |
| `pytest --tb=short` | короткий traceback |
| `pytest --pdb` | отладчик в момент падения |
| `pytest --durations=5` | 5 самых медленных тестов |

В VS Code: панель Testing, запуск и отладка теста кнопкой рядом с функцией. Нужны выбранный интерпретатор из venv и `"python.testing.pytestEnabled": true`.

## 2. Проверки

Обычный `assert`: pytest сам покажет обе стороны и разницу. Никаких `assertEqual`.

```python
import logging
from decimal import Decimal

import pytest


def test_values():
    assert total(Decimal("500"), percent=20) == Decimal("400.00")
    assert result is None                         # None, True, False - через is
    assert "msk" in cities
    assert len(items) == 3, f"получили {items}"   # сообщение при падении
    assert 0.1 + 0.2 == pytest.approx(0.3)        # float сравнивать только так


def test_errors():
    with pytest.raises(ValueError):
        parse_price("abc")

    with pytest.raises(PromoExpired, match="AUTUMN"):   # match - regex по тексту ошибки
        service.apply("AUTUMN", user_id=1, price=Decimal("100"))

    with pytest.raises(LimitExceeded) as exc_info:
        service.apply("ONCE", user_id=1, price=Decimal("100"))
    assert exc_info.value.code == "ONCE"          # доступ к самому исключению


def test_output(capsys):
    print("готово")
    assert capsys.readouterr().out == "готово\n"


def test_logs(caplog):
    with caplog.at_level(logging.WARNING):
        logging.getLogger("promo").warning("лимит почти исчерпан")
    assert "лимит" in caplog.text
```

- В блоке `with pytest.raises` - только одна строка, которая должна упасть. Код после нее внутри блока не выполнится, и проверки там молча не сработают.
- `pytest.raises` ловит и наследников: `raises(PromoError)` пройдет на `PromoExpired`. Для точной причины - проверять конкретный класс.
- Деньги в `Decimal` сравниваются точно, `approx` не нужен.

## 3. Параметризация

Один тест - много наборов данных. Каждый набор - отдельный тест в отчете, падение одного не скрывает остальные.

```python
import pytest


@pytest.mark.parametrize(
    ("price", "percent", "cap", "expected"),
    [
        (Decimal("500"), 20, None, Decimal("100.00")),
        (Decimal("500"), 20, Decimal("50"), Decimal("50")),       # уперлись в потолок
        (Decimal("333.33"), 15, None, Decimal("49.99")),          # округление вниз
    ],
    ids=["plain", "capped", "rounding"],              # имена в отчете
)
def test_percent_discount(price, percent, cap, expected):
    assert percent_discount(price, percent, cap) == expected


@pytest.mark.parametrize("code", ["autumn20", " AUTUMN20 ", "Autumn20\n"])
def test_code_normalized(code):
    assert normalize(code) == "AUTUMN20"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("10", 10, id="int"),
        pytest.param("", None, id="empty"),
        pytest.param("1e3", 1000, id="sci", marks=pytest.mark.xfail(reason="не поддержано")),
    ],
)
def test_parse(raw, expected):
    assert parse(raw) == expected


@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.parametrize("y", [10, 20])
def test_grid(x, y):           # 4 теста: все сочетания x и y
    ...
```

- Имена параметров - кортежем или строкой через запятую: `"price,percent"`. Они должны совпадать с аргументами функции.
- Параметризация на классе `Test*` применяется ко всем его методам.
- Критерий: если тесты отличаются только данными - parametrize. Если разными действиями или проверками - отдельные тесты.

## 4. Фикстуры

Фикстура готовит данные или объект для теста. Тест получает ее, назвав аргумент тем же именем. По умолчанию фикстура создается заново для каждого теста - тесты не влияют друг на друга.

```python
import pytest


@pytest.fixture
def service(clock):                       # фикстура может зависеть от другой
    return PromoService(clock=clock)


@pytest.fixture
def db():
    conn = connect(":memory:")
    yield conn                             # до yield - подготовка, после - уборка
    conn.close()                           # выполнится даже если тест упал


@pytest.fixture
def make_promo():                         # фабрика: тест сам задает нужные поля
    def _make(**overrides):
        data = {"code": "AUTUMN20", "percent": Decimal("20"), "valid_until": datetime(2026, 10, 31)}
        data.update(overrides)
        return Promo(**data)
    return _make


def test_apply(service, make_promo):
    service.add(make_promo(max_uses_total=1))
    ...
```

| scope | Сколько живет |
| --- | --- |
| `function` (по умолчанию) | один тест |
| `class` | все тесты класса |
| `module` | все тесты файла |
| `session` | весь запуск pytest (дорогие ресурсы: контейнер БД) |

`@pytest.fixture(scope="module")`. Изменяемый объект в широком scope - тесты начнут зависеть от порядка.

**conftest.py** - фикстуры оттуда видны всем тестам в этой папке и ниже, без импорта.

**Встроенные фикстуры:**

| Фикстура | Зачем |
| --- | --- |
| `tmp_path` | временная папка `pathlib.Path`, своя у каждого теста |
| `monkeypatch` | временно подменить атрибут, переменную окружения, элемент словаря (раздел 5) |
| `capsys` | перехваченный stdout и stderr |
| `caplog` | перехваченные записи logging |
| `request` | сведения о текущем тесте; `request.param` в параметризованной фикстуре |

Параметризованная фикстура - все тесты, что ее используют, прогоняются на каждой реализации:

```python
@pytest.fixture(params=[InMemoryStorage, SqliteStorage])
def storage(request):
    return request.param()
```

## 5. Подмена зависимостей

Лучший способ - не подменять, а передать. Время, случайные числа, клиент API, хранилище - аргументом конструктора с нормальным значением по умолчанию. Тогда в тесте не нужно ничего патчить.

```python
# код
class PromoService:
    def __init__(self, clock: Callable[[], datetime] = datetime.now):
        self._clock = clock

    def is_expired(self, promo) -> bool:
        return self._clock() > promo.valid_until


# тест
class FakeClock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs):
        self.now += timedelta(**kwargs)


def test_expires(make_promo):
    clock = FakeClock(datetime(2026, 10, 31, 23, 59))
    service = PromoService(clock=clock)
    promo = make_promo(valid_until=datetime(2026, 10, 31, 23, 59))
    assert not service.is_expired(promo)
    clock.advance(minutes=1)
    assert service.is_expired(promo)
```

**monkeypatch** - когда зависимость зашита в код. Все подмены откатываются после теста.

```python
def test_env(monkeypatch):
    monkeypatch.setenv("PROMO_LIMIT", "5")
    monkeypatch.delenv("DEBUG", raising=False)
    monkeypatch.setattr(promo_module, "fetch_rate", lambda zone: 1.5)   # подмена функции в модуле
    monkeypatch.setitem(CONFIG, "currency", "RUB")
```

Главное правило подмены: патчить имя там, где его используют. Если в `promo.py` написано `from rates import fetch_rate`, патчить нужно `promo.fetch_rate`, а не `rates.fetch_rate`.

**unittest.mock** - когда нужно проверить, как вызвали зависимость:

```python
from unittest.mock import Mock, patch


def test_notifies_user():
    notifier = Mock()
    service = PromoService(notifier=notifier)
    service.redeem("AUTUMN20", user_id=7, price=Decimal("500"))
    notifier.send.assert_called_once_with(7, "Промокод применен")


def test_api_errors():
    api = Mock()
    api.get_rate.side_effect = [TimeoutError, 1.5]   # первый вызов падает, второй вернет 1.5
    api.get_status.return_value = "ok"
    ...
    assert api.get_rate.call_count == 2


def test_with_patch():
    with patch("promo.fetch_rate", return_value=1.5) as fake:
        assert calc_price("center", Decimal("100")) == Decimal("150")
    fake.assert_called_once_with("center")
```

| Атрибут Mock | Зачем |
| --- | --- |
| `return_value` | что вернет вызов |
| `side_effect` | исключение, список ответов по очереди или функция |
| `assert_called_once_with(...)` | вызван ровно один раз с этими аргументами |
| `assert_not_called()` | не вызван |
| `call_count`, `call_args_list` | сколько раз и с чем вызывали |
| `Mock(spec=RealClass)` | обращение к несуществующему методу - ошибка, а не новый Mock |

Опечатка `mock.asert_called_once()` в старых версиях молча проходила. Сейчас это `AttributeError`, но `spec=` все равно стоит ставить.

## 6. Асинхронные тесты и метки

Для `async def` тестов нужен плагин: `pip install pytest-asyncio`. В `pytest.ini` - `asyncio_mode = auto`, тогда метка на каждом тесте не нужна.

```python
import asyncio
from unittest.mock import AsyncMock


async def test_fetch_all():
    client = AsyncMock()
    client.get.side_effect = lambda url: {"url": url}
    result = await fetch_all(client, ["a", "b"])
    assert result == [{"url": "a"}, {"url": "b"}]
    assert client.get.await_count == 2


async def test_timeout():
    async def slow():
        await asyncio.sleep(1)

    with pytest.raises(TimeoutError):          # Python 3.11+; в 3.10 - asyncio.TimeoutError
        await asyncio.wait_for(slow(), timeout=0.01)
```

- `AsyncMock` - как `Mock`, но вызов возвращает корутину. Проверки: `assert_awaited_once_with`, `await_count`.
- Без плагина можно обойтись обычным тестом: `assert asyncio.run(fetch_all(client, urls)) == ...`.

**Метки:**

```python
@pytest.mark.skip(reason="ждем исправления API")
def test_a(): ...

@pytest.mark.skipif(sys.version_info < (3, 12), reason="нужен itertools.batched")
def test_b(): ...

@pytest.mark.xfail(reason="известная ошибка округления", strict=True)
def test_c(): ...          # strict: если вдруг пройдет - тест красный
```

Свои метки (`@pytest.mark.slow`) нужно объявить в `pytest.ini` в `markers =`, запуск без них - `pytest -m "not slow"`.

## 7. Как покрыть задачу тестами на собеседовании

Порядок: сигнатуры кода - один тест на основной сценарий - реализация - тесты на границы и ошибки. Запускать тесты часто, после каждого шага.

**Чек-лист случаев** - пройти по списку и назвать вслух, какие применимы:

1. Основной сценарий: обычный вход - ожидаемый результат.
2. Границы: 0, 1, пустой список или строка, ровно на лимите, на единицу выше и ниже, минимум и максимум, момент окончания срока.
3. Некорректный вход: отрицательные числа, None, неверный формат, неизвестный ключ - какое именно исключение.
4. Округление и деньги: копейки, итог не уходит в минус.
5. Состояние: повторный вызов, порядок операций, счетчики, неудачная операция ничего не меняет.
6. Несколько участников: два пользователя, два объекта не делят состояние.
7. Время: через внедренные часы, никаких `sleep` в тестах.

**Структура теста - подготовка, действие, проверка (Arrange, Act, Assert):**

```python
def test_user_limit_exceeded_on_second_use(service, make_promo):
    service.add(make_promo(code="ONCE", max_uses_per_user=1))      # подготовка
    service.redeem("ONCE", user_id=1, price=Decimal("500"))

    with pytest.raises(UserLimitExceeded):                           # действие + проверка
        service.redeem("ONCE", user_id=1, price=Decimal("500"))

    assert service.quote("ONCE", user_id=2, price=Decimal("500"))    # другому пользователю можно
```

- Имя теста - что проверяем: `test_<что>_<при каких условиях>`. Интервьюер читает список имен как спецификацию.
- Один тест - одно поведение. Несколько `assert` про одно поведение - нормально.
- Тестировать публичный интерфейс, а не приватные поля `_storage`.
- Времени мало - вслух перечислить тесты, которые написал бы еще. Это тоже засчитывают.

Справка: [docs.pytest.org](https://docs.pytest.org/en/stable/how-to/index.html), [unittest.mock](https://docs.python.org/3/library/unittest.mock.html).
