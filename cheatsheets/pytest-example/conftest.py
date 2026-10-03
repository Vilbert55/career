"""Фикстуры: pytest сам находит этот файл, в тестах фикстуры доступны без импорта."""
import sqlite3

import pytest

from wallet import Wallet, init_db, save


@pytest.fixture
def wallet() -> Wallet:
    """Простая фикстура: новый объект для каждого теста."""
    return Wallet("anna", 100)


@pytest.fixture
def empty_wallet() -> Wallet:
    return Wallet("boris")


@pytest.fixture
def make_wallet():
    """Фабрика: тест сам задает нужные значения."""

    def _make(owner: str = "anna", balance: int = 0) -> Wallet:
        return Wallet(owner, balance)

    return _make


@pytest.fixture
def db():
    """Фикстура с yield: до yield - подготовка, после - уборка (выполнится, даже если тест упал)."""
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def db_with_wallet(db, wallet):
    """Фикстура, которая использует другие фикстуры."""
    save(db, wallet)
    return db
