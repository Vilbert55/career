"""Пример кода под тесты. На секции заменить своим."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal

KOPECK = Decimal("0.01")


class PromoError(Exception):
    """База для ошибок промокодов: вызывающий код ловит одну."""


class PromoNotFound(PromoError):
    pass


class PromoExpired(PromoError):
    pass


@dataclass(frozen=True)
class Promo:
    code: str
    percent: Decimal
    valid_until: datetime
    max_discount: Decimal | None = None


def percent_discount(price: Decimal, percent: Decimal, cap: Decimal | None = None) -> Decimal:
    discount = (price * percent / 100).quantize(KOPECK, ROUND_DOWN)
    if cap is not None:
        discount = min(discount, cap)
    return min(discount, price)


class PromoService:
    def __init__(self, clock: Callable[[], datetime] = datetime.now, notifier=None):
        self._clock = clock
        self._notifier = notifier
        self._promos: dict[str, Promo] = {}

    def add(self, promo: Promo) -> None:
        self._promos[promo.code.strip().upper()] = promo

    def quote(self, code: str, price: Decimal) -> Decimal:
        promo = self._promos.get(code.strip().upper())
        if promo is None:
            raise PromoNotFound(code)
        if self._clock() > promo.valid_until:
            raise PromoExpired(promo.code)
        return price - percent_discount(price, promo.percent, promo.max_discount)

    def redeem(self, code: str, user_id: int, price: Decimal) -> Decimal:
        total = self.quote(code, price)
        if self._notifier is not None:
            self._notifier.send(user_id, f"Промокод {code.strip().upper()} применен")
        return total


async def fetch_all(client, urls: list[str]) -> list[dict]:
    """Последовательно запросить все url у асинхронного клиента."""
    return [await client.get(url) for url in urls]
