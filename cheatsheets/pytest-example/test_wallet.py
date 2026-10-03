"""Тесты для wallet.py. Фикстуры wallet, empty_wallet, make_wallet, db - из conftest.py."""
from unittest.mock import AsyncMock, Mock

import pytest

from wallet import InsufficientFunds, Wallet, fetch_balance, load, save, transfer


# 1. Простая проверка
def test_deposit(wallet):
    wallet.deposit(50)
    assert wallet.balance == 150


# 2. Исключение
def test_withdraw_more_than_balance(wallet):
    with pytest.raises(InsufficientFunds, match="need 500"):
        wallet.withdraw(500)
    assert wallet.balance == 100              # неудачная операция ничего не поменяла


# 3. Параметризация: один тест - много наборов данных
@pytest.mark.parametrize("amount", [0, -1, -100])
def test_deposit_rejects_non_positive(wallet, amount):
    with pytest.raises(ValueError):
        wallet.deposit(amount)


@pytest.mark.parametrize(
    ("balance", "amount", "expected"),
    [
        (100, 1, 99),
        (100, 100, 0),                        # граница: снять все
    ],
    ids=["one", "all"],
)
def test_withdraw(make_wallet, balance, amount, expected):
    w = make_wallet(balance=balance)
    w.withdraw(amount)
    assert w.balance == expected


# 4. Несколько фикстур в одном тесте
def test_transfer(wallet, empty_wallet):
    transfer(wallet, empty_wallet, 30)
    assert (wallet.balance, empty_wallet.balance) == (70, 30)


# 5. Фикстура с yield (db) и фикстура на фикстурах (db_with_wallet)
def test_save_and_load(db, wallet):
    save(db, wallet)
    loaded = load(db, "anna")
    assert (loaded.owner, loaded.balance) == ("anna", 100)


def test_load_missing(db):
    assert load(db, "nobody") is None


def test_db_with_wallet(db_with_wallet):
    assert load(db_with_wallet, "anna").balance == 100


# 6. Mock: подменить зависимость и проверить, как ее вызвали
def test_transfer_notifies(wallet, empty_wallet):
    notifier = Mock()
    transfer(wallet, empty_wallet, 30, notifier=notifier)
    notifier.send.assert_called_once_with("boris", "+30")


def test_no_notification_when_transfer_fails(wallet, empty_wallet):
    notifier = Mock()
    with pytest.raises(InsufficientFunds):
        transfer(wallet, empty_wallet, 500, notifier=notifier)
    notifier.send.assert_not_called()


# 7. monkeypatch: временно поменять окружение или атрибут, после теста все вернется
def test_limit_from_env(monkeypatch):
    monkeypatch.setenv("WALLET_LIMIT", "50")
    w = Wallet("anna", 40)
    with pytest.raises(ValueError, match="limit"):
        w.deposit(20)


def test_limit_patched_function(monkeypatch):
    monkeypatch.setattr("wallet.get_limit", lambda: 10_000)
    w = Wallet("anna", 900)
    w.deposit(5000)
    assert w.balance == 5900


# 8. Async: тест - обычная async-функция (asyncio_mode = auto в pytest.ini)
async def test_fetch_balance():
    client = AsyncMock()
    client.get.return_value = {"balance": 42}
    assert await fetch_balance(client, "anna") == 42
    client.get.assert_awaited_once_with("/wallets/anna")
