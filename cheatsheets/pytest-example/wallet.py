"""Рабочий код: кошелек, перевод, хранение в БД, запрос баланса по сети."""
import os
import sqlite3


class InsufficientFunds(Exception):
    pass


def get_limit() -> int:
    """Максимальный баланс кошелька, задается переменной окружения."""
    return int(os.getenv("WALLET_LIMIT", "1000"))


class Wallet:
    def __init__(self, owner: str, balance: int = 0):
        if balance < 0:
            raise ValueError("balance must be >= 0")
        self.owner = owner
        self.balance = balance

    def deposit(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("amount must be > 0")
        if self.balance + amount > get_limit():
            raise ValueError("limit exceeded")
        self.balance += amount

    def withdraw(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("amount must be > 0")
        if amount > self.balance:
            raise InsufficientFunds(f"{self.owner}: need {amount}, have {self.balance}")
        self.balance -= amount


def transfer(src: Wallet, dst: Wallet, amount: int, notifier=None) -> None:
    src.withdraw(amount)
    dst.deposit(amount)
    if notifier is not None:
        notifier.send(dst.owner, f"+{amount}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("create table if not exists wallets (owner text primary key, balance int)")


def save(conn: sqlite3.Connection, wallet: Wallet) -> None:
    conn.execute("insert or replace into wallets values (?, ?)", (wallet.owner, wallet.balance))


def load(conn: sqlite3.Connection, owner: str) -> Wallet | None:
    row = conn.execute("select owner, balance from wallets where owner = ?", (owner,)).fetchone()
    return Wallet(*row) if row else None


async def fetch_balance(client, owner: str) -> int:
    """Запросить баланс у внешнего сервиса через асинхронный клиент."""
    response = await client.get(f"/wallets/{owner}")
    return response["balance"]
