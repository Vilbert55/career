"""Примеры приемов pytest и заготовка под свой код. Копировать нужный кусок и менять.

Фикстуры из conftest.py (clock, service, make_promo) видны всем тестам в папке - импортировать их не нужно,
pytest подставляет фикстуру по имени аргумента.

Чек-лист случаев: основной сценарий; границы (0, 1, пусто, ровно на лимите, +-1);
некорректный вход (какое исключение); деньги и округление; состояние (повтор, порядок,
неудачная операция ничего не меняет); несколько пользователей; время через часы.
"""
import json
import logging
import sqlite3
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch

import pytest

import example
from example import PromoError, PromoExpired, PromoNotFound, fetch_all, percent_discount

# --- 0. Заготовка под свой код: раскомментировать и заполнить -------------------
#
# from my_module import MyService, MyError
#
#
# @pytest.fixture
# def svc(clock):
#     return MyService(clock=clock)
#
#
# def test_happy_path(svc):
#     assert svc.do(...) == ...
#
#
# @pytest.mark.parametrize(("value", "expected"), [(..., ...), (..., ...)])
# def test_boundaries(svc, value, expected):
#     assert svc.do(value) == expected
#
#
# def test_invalid_input_raises(svc):
#     with pytest.raises(MyError, match="..."):
#         svc.do(...)
#
#
# def test_failed_operation_changes_nothing(svc):
#     before = svc.state()
#     with pytest.raises(MyError):
#         svc.do(...)
#     assert svc.state() == before

# --- 1. Простая проверка и исключения -------------------------------------

def test_quote_applies_discount(service, make_promo):     # фикстуры из conftest.py, без импорта
    service.add(make_promo())
    assert service.quote("AUTUMN20", Decimal("500")) == Decimal("400.00")


def test_unknown_code_raises(service):
    with pytest.raises(PromoNotFound, match="NOPE"):
        service.quote("NOPE", Decimal("500"))


def test_all_errors_share_base_class(service):
    with pytest.raises(PromoError):
        service.quote("NOPE", Decimal("500"))


def test_exception_details(service, make_promo, clock):
    service.add(make_promo())
    clock.advance(days=30)
    with pytest.raises(PromoExpired) as exc_info:
        service.quote("AUTUMN20", Decimal("500"))
    assert exc_info.value.args == ("AUTUMN20",)


def test_float_needs_approx():
    assert 0.1 + 0.2 == pytest.approx(0.3)


# --- 2. Свои фикстуры: yield с уборкой, scope, params --------------------------

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("create table used (code text, user_id int)")
    yield conn                # до yield - подготовка, тест получает conn
    conn.close()              # после yield - уборка, выполнится и после упавшего теста


def test_yield_fixture(db):
    db.execute("insert into used values ('AUTUMN20', 7)")
    assert db.execute("select count(*) from used").fetchone() == (1,)


@pytest.fixture(scope="module")
def heavy_config():
    # одна на все тесты файла; scope: function (по умолчанию), class, module, session
    return {"limit": 3}


def test_scope_module(heavy_config):
    assert heavy_config["limit"] == 3


@pytest.fixture(params=[dict, lambda: {"preset": 1}], ids=["empty", "preset"])
def storage(request):
    return request.param()    # тест ниже выполнится для каждого params


def test_runs_for_each_storage(storage):
    storage["x"] = 1
    assert storage["x"] == 1


@pytest.fixture
async def async_client():
    client = AsyncMock()
    yield client              # async-фикстура с уборкой
    await client.aclose()


async def test_async_yield_fixture(async_client):
    await async_client.get("a")
    async_client.get.assert_awaited_once_with("a")



# --- 3. Параметризация ------------------------------------------------------

@pytest.mark.parametrize(
    ("price", "percent", "cap", "expected"),
    [
        (Decimal("500"), Decimal("20"), None, Decimal("100.00")),
        (Decimal("500"), Decimal("20"), Decimal("50"), Decimal("50")),
        (Decimal("333.33"), Decimal("15"), None, Decimal("49.99")),
        (Decimal("100"), Decimal("150"), None, Decimal("100")),
    ],
    ids=["plain", "capped", "rounding_down", "not_more_than_price"],
)
def test_percent_discount(price, percent, cap, expected):
    assert percent_discount(price, percent, cap) == expected


@pytest.mark.parametrize("code", ["autumn20", " AUTUMN20 ", "Autumn20\n"])
def test_code_is_normalized(service, make_promo, code):
    service.add(make_promo())
    assert service.quote(code, Decimal("100")) == Decimal("80.00")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("10", 10, id="int"),
        pytest.param("1e3", 1000, id="sci", marks=pytest.mark.xfail(reason="int() так не умеет", strict=True)),
    ],
)
def test_param_with_marks(raw, expected):
    assert int(raw) == expected


# --- 4. Время через внедренные часы ------------------------------------------

def test_valid_until_is_inclusive(service, make_promo, clock):
    clock.now = datetime(2026, 10, 31, 23, 59)
    service.add(make_promo())
    assert service.quote("AUTUMN20", Decimal("100")) == Decimal("80.00")
    clock.advance(minutes=1)
    with pytest.raises(PromoExpired):
        service.quote("AUTUMN20", Decimal("100"))


# --- 5. Mock: проверить, как вызвали зависимость ------------------------------

def test_redeem_notifies_user(clock, make_promo):
    notifier = Mock()
    service = example.PromoService(clock=clock, notifier=notifier)
    service.add(make_promo())
    service.redeem("autumn20", user_id=7, price=Decimal("500"))
    notifier.send.assert_called_once_with(7, "Промокод AUTUMN20 применен")


def test_no_notification_on_error(clock):
    notifier = Mock()
    service = example.PromoService(clock=clock, notifier=notifier)
    with pytest.raises(PromoNotFound):
        service.redeem("NOPE", user_id=7, price=Decimal("500"))
    notifier.send.assert_not_called()


def test_side_effect_sequence():
    api = Mock()
    api.get_rate.side_effect = [TimeoutError, 1.5]
    with pytest.raises(TimeoutError):
        api.get_rate("center")
    assert api.get_rate("center") == 1.5
    assert api.get_rate.call_count == 2


# --- 6. monkeypatch и patch: подменить то, что зашито в код -------------------

def test_monkeypatch_function(monkeypatch):
    monkeypatch.setattr(example, "percent_discount", lambda price, percent, cap=None: Decimal("1"))
    assert example.percent_discount(Decimal("500"), Decimal("20")) == Decimal("1")


def test_monkeypatch_env(monkeypatch):
    monkeypatch.setenv("PROMO_LIMIT", "5")
    import os
    assert os.environ["PROMO_LIMIT"] == "5"


def test_patch_context():
    with patch("example.percent_discount", return_value=Decimal("0")) as fake:
        service = example.PromoService(clock=lambda: datetime(2026, 1, 1))
        service.add(example.Promo("X", Decimal("10"), datetime(2027, 1, 1)))
        assert service.quote("X", Decimal("100")) == Decimal("100")
    fake.assert_called_once()


# --- 7. Async ----------------------------------------------------------------

async def test_fetch_all_async():
    client = AsyncMock()
    client.get.side_effect = lambda url: {"url": url}
    assert await fetch_all(client, ["a", "b"]) == [{"url": "a"}, {"url": "b"}]
    assert client.get.await_count == 2


# --- 8. Вывод, логи, файлы -----------------------------------------------------

def test_capsys(capsys):
    print("готово")
    assert capsys.readouterr().out == "готово\n"


def test_caplog(caplog):
    with caplog.at_level(logging.WARNING):
        logging.getLogger("promo").warning("лимит почти исчерпан")
    assert "лимит" in caplog.text


def test_tmp_path(tmp_path):
    path = tmp_path / "promos.json"
    path.write_text(json.dumps({"code": "A"}), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == {"code": "A"}
