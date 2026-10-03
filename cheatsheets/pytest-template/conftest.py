"""Общие фикстуры: видны всем тестам в папке без импорта."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from example import Promo, PromoService


class FakeClock:
    """Подменные часы: время стоит, пока его не сдвинуть."""

    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 10, 5, 12, 0))


@pytest.fixture
def service(clock) -> PromoService:
    return PromoService(clock=clock)


@pytest.fixture
def make_promo():
    """Фабрика: значения по умолчанию + то, что тест передал явно."""

    def _make(**overrides) -> Promo:
        data = {
            "code": "AUTUMN20",
            "percent": Decimal("20"),
            "valid_until": datetime(2026, 10, 31, 23, 59),
        }
        data.update(overrides)
        return Promo(**data)

    return _make
