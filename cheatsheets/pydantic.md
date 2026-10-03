# Pydantic v2: памятка

Оригинал (Claude Docs, можно выгрузить в PDF): https://claude.ai/code/artifact/4d0bac19-c231-4d3b-8d23-5ed0460252d5

Pydantic 2.x, Python 3.10+.

## Модель

```python
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel, Field


class Promo(BaseModel):
    code: str                                   # обязательное
    value: Decimal = Field(gt=0)                # обязательное, > 0
    max_discount: Decimal | None = None         # необязательное
    tags: list[str] = []                        # можно: pydantic копирует умолчание
    max_uses: int | None = Field(default=None, ge=1)
    CURRENCY: ClassVar[str] = "RUB"             # атрибут класса, не поле
```

- Атрибут без аннотации (`kind = "x"`) - ошибка при объявлении класса. Нужно `kind: Literal["x"] = "x"` или `ClassVar`.
- `x: int | None` без `= None` - обязательное поле, в которое можно передать None.
- `Field`: `gt` `ge` `lt` `le`, `min_length` `max_length` `pattern`, `max_digits` `decimal_places`, `alias`, `default_factory`.

## Создание и ошибки

```python
from pydantic import ValidationError

p = Promo(code="A", value="20")                       # только по имени; "20" -> Decimal
p = Promo.model_validate({"code": "A", "value": 5})
p = Promo.model_validate_json('{"code": "A", "value": 5}')

try:
    Promo(code="A", value=-1)
except ValidationError as e:
    e.errors()[0]["loc"], e.errors()[0]["type"]        # ('value',), 'greater_than'
```

- Лишние поля молча отбрасываются (см. `extra`).
- Без проверки: `Promo.model_construct(...)`.

## Валидаторы

```python
from typing import Self

from pydantic import field_validator, model_validator


class Promo(BaseModel):
    code: str
    percent: Decimal | None = None
    fixed: Decimal | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("пустой код")
        return v

    @model_validator(mode="after")
    def one_kind(self) -> Self:
        if (self.percent is None) == (self.fixed is None):
            raise ValueError("нужен ровно один вид скидки")
        return self
```

- `@classmethod` под `@field_validator` обязателен. Без `return` поле станет None.
- `mode="before"` - сырое значение до приведения типа. Несколько полей: `@field_validator("a", "b")`.
- Ошибка - `raise ValueError(...)`, pydantic завернет в `ValidationError`.

## Сериализация

| Вызов | Результат |
| --- | --- |
| `p.model_dump()` | dict, Decimal и datetime как есть |
| `p.model_dump(mode="json")` | dict из JSON-типов |
| `p.model_dump_json()` | JSON-строка |
| `p.model_dump(exclude_none=True)` | без полей со значением None |
| `p.model_dump(include={"code"})` | только эти поля; `exclude=` - кроме этих |
| `p.model_copy(update={"value": 10})` | копия с изменениями, без проверки |
| `Promo.model_fields` | описание полей |

Устаревшие имена v1: `dict()`, `json()`, `parse_obj()`, `copy()`, `@validator`, `class Config`.

## ConfigDict

```python
from pydantic import ConfigDict


class Promo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)
    code: str
```

| Настройка | Что делает |
| --- | --- |
| `frozen=True` | присваивание - ошибка; объект хешируемый |
| `extra="forbid"` | лишние поля - ошибка; `"ignore"` по умолчанию; `"allow"` - сохранить |
| `validate_assignment=True` | проверять `p.x = ...` |
| `str_strip_whitespace=True` | обрезать пробелы во всех строках |
| `str_to_upper=True` | строки в верхний регистр |
| `strict=True` | без приведения типов: `"5"` для int - ошибка |
| `use_enum_values=True` | хранить значение перечисления, а не член |
| `from_attributes=True` | создавать из объекта с атрибутами (ORM) |

Значения по умолчанию не валидируются и настройками строк не обрабатываются.

## Деньги, перечисления, даты

```python
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from typing import Literal


class Kind(StrEnum):            # Python 3.11+; в 3.10: class Kind(str, Enum)
    PERCENT = "percent"
    FIXED = "fixed"


class Promo(BaseModel):
    kind: Kind                                       # примет Kind.PERCENT или "percent"
    value: Decimal = Field(gt=0, decimal_places=2)
    valid_until: datetime                            # примет "2026-10-31T23:59:59"
    channel: Literal["app", "web"] = "app"


Decimal("333.33") * 15 / 100                         # 49.9995
(Decimal("333.33") * 15 / 100).quantize(Decimal("0.01"), ROUND_DOWN)   # 49.99
```

- Деньги - `Decimal` из строки (`Decimal("0.1")`, не `Decimal(0.1)`) или копейки в `int`.
- Дата с часовым поясом и без несравнимы: `TypeError`.

## Наследование и выбор класса по полю

```python
from abc import ABC, abstractmethod
from typing import Annotated, Literal

from pydantic import TypeAdapter


class PromoBase(BaseModel, ABC):
    code: str

    @abstractmethod
    def discount(self, price: Decimal) -> Decimal: ...


class PercentPromo(PromoBase):
    kind: Literal["percent"] = "percent"
    percent: Decimal = Field(gt=0, le=100)

    def discount(self, price: Decimal) -> Decimal:
        return price * self.percent / 100


class FixedPromo(PromoBase):
    kind: Literal["fixed"] = "fixed"
    amount: Decimal = Field(gt=0)

    def discount(self, price: Decimal) -> Decimal:
        return min(self.amount, price)


AnyPromo = Annotated[PercentPromo | FixedPromo, Field(discriminator="kind")]

TypeAdapter(AnyPromo).validate_python({"kind": "fixed", "code": "A", "amount": 100})  # -> FixedPromo


class Order(BaseModel):
    promo: AnyPromo | None = None
```

- Константа класса без поля: `kind: ClassVar[Kind] = Kind.FIXED`; аннотацию можно один раз объявить в базе (`kind: ClassVar[Kind]`), в наследниках писать `kind = Kind.FIXED`.
- `TypeAdapter(list[int]).validate_python(["1", 2])` - `[1, 2]`.

## Частые ошибки

| Ошибка | Правильно |
| --- | --- |
| `kind = Kind.FIXED` без аннотации | `kind: Literal[...] = ...` или `ClassVar` |
| `label = str` | `label: str` |
| `label: str = Field(...)` | `label: str` |
| `def calc():` в модели | `def calc(self):` |
| `x: int \| None` как необязательное | `x: int \| None = None` |
| валидатор без `return` | вернуть значение (или `self`) |
| `p.value = -5` без ошибки | `validate_assignment=True` или `frozen=True` |
| деньги в `float` | `Decimal` или копейки в `int` |
