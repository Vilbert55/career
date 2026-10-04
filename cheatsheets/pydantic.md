# Pydantic v2: памятка

Pydantic 2.x, Python 3.11+. Каждый блок самостоятельный: импорты внутри, можно копировать целиком.

**Содержание**

- [Модель и поля](#модель-и-поля)
- [Свои типы через Annotated](#свои-типы-через-annotated)
- [Создание и ошибки](#создание-и-ошибки)
- [Валидаторы и вычисляемые поля](#валидаторы-и-вычисляемые-поля)
- [Вложенные модели и коллекции](#вложенные-модели-и-коллекции)
- [Сериализация и псевдонимы](#сериализация-и-псевдонимы)
- [Настройки модели (ConfigDict)](#настройки-модели-configdict)
- [Перечисления, Literal, даты, деньги](#перечисления-literal-даты-деньги)
- [Наследование и выбор класса по полю](#наследование-и-выбор-класса-по-полю)
- [Частые ошибки](#частые-ошибки)

## Модель и поля

```python
from datetime import datetime
from decimal import Decimal
from typing import ClassVar
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Promo(BaseModel):
    code: str                                             # обязательное
    percent: Decimal = Field(gt=0, le=100)                # обязательное, 0 < x <= 100
    max_discount: Decimal | None = None                   # необязательное
    max_uses: int | None = Field(default=None, ge=1)      # необязательное с проверкой
    title: str = Field(default="", max_length=100)
    tags: list[str] = []                                  # так можно: pydantic копирует умолчание
    id: UUID = Field(default_factory=uuid4)               # новое значение для каждого объекта
    created_at: datetime = Field(default_factory=datetime.now)
    CURRENCY: ClassVar[str] = "RUB"                       # атрибут класса, не поле


p = Promo(code="A", percent="20")                         # только именованные аргументы; "20" -> Decimal
```

`Field`: `gt` `ge` `lt` `le`, `min_length` `max_length` `pattern`, `max_digits` `decimal_places`,
`alias`, `default_factory`, `description`, `examples`.

## Свои типы через Annotated

```python
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field, PlainSerializer, StringConstraints

# ограничения в типе: объявить один раз, использовать в любых моделях
PositiveInt = Annotated[int, Field(gt=0)]
Percent = Annotated[Decimal, Field(gt=0, le=100, decimal_places=2)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
Code = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=3, max_length=20)]
Phone = Annotated[str, StringConstraints(pattern=r"^\+7\d{10}$")]


def check_even(v: int) -> int:                            # своя проверка: после приведения типа
    if v % 2:
        raise ValueError("нужно четное число")
    return v


def split_csv(v):                                         # своя обработка: сырое значение до приведения
    return v.split(",") if isinstance(v, str) else v


EvenInt = Annotated[int, AfterValidator(check_even)]
CsvList = Annotated[list[str], BeforeValidator(split_csv)]
MoneyStr = Annotated[Decimal, PlainSerializer(lambda v: f"{v:.2f}", return_type=str)]   # вывод в dump


class Order(BaseModel):
    qty: PositiveInt
    discount: Percent
    total: Money
    promo: Code
    phone: Phone | None = None
    seats: EvenInt = 2
    tags: CsvList = []
    scores: list[PositiveInt] = []                        # ограничение на каждый элемент
    paid: MoneyStr = Decimal("0")


o = Order(qty=1, discount="10", total="99.90", promo=" autumn ", tags="a,b", paid="5")
o.promo                  # 'AUTUMN'
o.tags                   # ['a', 'b']
o.model_dump()["paid"]   # '5.00'
```

## Создание и ошибки

```python
from pydantic import BaseModel, ValidationError


class Item(BaseModel):
    name: str
    price: int


Item(name="a", price=10)
Item.model_validate({"name": "a", "price": "10"})          # из dict
Item.model_validate_json('{"name": "a", "price": 10}')     # из JSON-строки
Item.model_construct(name="a", price=10)                   # без проверки

try:
    Item(name="a", price="дорого")
except ValidationError as e:
    print(e.errors()[0]["loc"], e.errors()[0]["type"])     # ('price',) int_parsing
```

## Валидаторы и вычисляемые поля

```python
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, computed_field, field_validator, model_validator


class Promo(BaseModel):
    code: str
    percent: Decimal | None = None
    fixed: Decimal | None = None
    price: Decimal = Decimal("0")

    @field_validator("code")                               # после приведения типа
    @classmethod
    def normalize_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("пустой код")
        return v                                           # без return поле станет None

    @field_validator("percent", "fixed", mode="before")    # несколько полей, сырое значение
    @classmethod
    def comma_to_dot(cls, v):
        return v.replace(",", ".") if isinstance(v, str) else v

    @model_validator(mode="before")                        # весь входной dict до проверки полей
    @classmethod
    def rename_old_keys(cls, data):
        if isinstance(data, dict) and "promo_code" in data:
            data = {**data, "code": data.pop("promo_code")}
        return data

    @model_validator(mode="after")                         # проверка связи полей
    def one_kind(self) -> Self:
        if (self.percent is None) == (self.fixed is None):
            raise ValueError("нужен ровно один вид скидки")
        return self

    @computed_field                                        # попадет в model_dump
    @property
    def discount(self) -> Decimal:
        if self.fixed is not None:
            return min(self.fixed, self.price)
        return self.price * self.percent / 100


Promo(promo_code=" a ", percent="10,5", price=200).discount   # Decimal('21.0')
```

## Вложенные модели и коллекции

```python
from decimal import Decimal

from pydantic import BaseModel, Field


class Item(BaseModel):
    name: str
    price: Decimal
    qty: int = Field(default=1, ge=1)


class Cart(BaseModel):
    user_id: int
    items: list[Item] = []
    meta: dict[str, str] = {}
    coupons: set[str] = set()
    point: tuple[float, float] | None = None


cart = Cart.model_validate({"user_id": 1, "items": [{"name": "a", "price": "10"}]})
cart.items[0].price                                        # Decimal('10')
```

## Сериализация и псевдонимы

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from pydantic.alias_generators import to_camel


class User(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, validate_by_name=True)   # user_id <-> userId
    user_id: int
    full_name: str
    email: str | None = Field(default=None, alias="mail")  # свой псевдоним для одного поля
    balance: Decimal = Decimal("0")
    created_at: datetime = datetime(2026, 10, 5)

    @field_serializer("created_at")
    def date_only(self, v: datetime) -> str:
        return v.date().isoformat()


u = User.model_validate({"userId": 1, "fullName": "Анна"})  # по псевдонимам
u = User(user_id=1, full_name="Анна")                       # по именам (validate_by_name)

u.model_dump()                     # dict, Decimal остается Decimal
u.model_dump(mode="json")          # dict только из JSON-типов: Decimal -> '0'
u.model_dump(by_alias=True)        # ключи userId, fullName, mail
u.model_dump_json()                # JSON-строка
u.model_dump(exclude_none=True)    # без полей со значением None
u.model_dump(exclude_unset=True)   # только то, что передали явно (для PATCH)
u.model_dump(include={"user_id"})  # только эти поля; exclude= - кроме этих
u.model_copy(update={"full_name": "Борис"})   # копия с изменениями, без проверки
User.model_json_schema()           # JSON Schema
```

## Настройки модели (ConfigDict)

```python
from pydantic import BaseModel, ConfigDict


class Promo(BaseModel):
    model_config = ConfigDict(
        frozen=True,                 # нельзя присваивать, объект хешируемый
        extra="forbid",              # лишние поля - ошибка ("ignore" по умолчанию, "allow" - сохранить)
        str_strip_whitespace=True,   # обрезать пробелы во всех строках
        validate_assignment=True,    # проверять p.x = ... (для нефрозен-моделей)
        validate_default=True,       # проверять и значения по умолчанию
        use_enum_values=True,        # хранить "percent" вместо Kind.PERCENT
        from_attributes=True,        # model_validate(obj) из объекта с атрибутами (ORM)
        # strict=True,               # без приведения типов: "5" для int - ошибка
    )
    code: str
```

## Перечисления, Literal, даты, деньги

```python
from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field


class Kind(StrEnum):
    PERCENT = "percent"
    FIXED = "fixed"


class Promo(BaseModel):
    kind: Kind                                   # примет Kind.PERCENT или "percent"
    channel: Literal["app", "web"] = "app"       # одно из значений
    valid_until: datetime                        # примет "2026-10-31T23:59:59"
    starts_at: AwareDatetime | None = None       # только с часовым поясом
    day: date | None = None                      # примет "2026-10-31"
    ttl: timedelta = timedelta(hours=1)          # примет 3600 или "PT1H"
    value: Decimal = Field(gt=0, decimal_places=2)


KOPECK = Decimal("0.01")
(Decimal("333.33") * 15 / 100).quantize(KOPECK, ROUND_DOWN)   # Decimal('49.99')
Decimal("0.1")                                   # деньги - из строки
Decimal(0.1)                                     # Decimal('0.1000000000000000055511151231257827...')
```

## Наследование и выбор класса по полю

```python
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


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


class Order(BaseModel):
    promo: AnyPromo | None = None


Order.model_validate({"promo": {"kind": "fixed", "code": "A", "amount": 100}}).promo   # FixedPromo
TypeAdapter(AnyPromo).validate_python({"kind": "percent", "code": "B", "percent": 5})  # PercentPromo
TypeAdapter(list[int]).validate_python(["1", 2])                                       # [1, 2]
```

Константа класса без поля: `kind: ClassVar[str] = "fixed"`.

## Частые ошибки

| Ошибка | Правильно |
| --- | --- |
| `kind = "fixed"` без аннотации | `kind: Literal["fixed"] = "fixed"` или `ClassVar` |
| `label = str` | `label: str` |
| `x: int \| None` как необязательное | `x: int \| None = None` |
| валидатор без `return` | вернуть значение (или `self`) |
| `@field_validator` без `@classmethod` | `@classmethod` строкой ниже |
| `p.value = -5` без ошибки | `validate_assignment=True` или `frozen=True` |
| деньги в `float` | `Decimal` из строки или копейки в `int` |
| `dict()`, `json()`, `parse_obj()`, `@validator`, `class Config` | это v1: `model_dump()`, `model_dump_json()`, `model_validate()`, `@field_validator`, `model_config` |
