# SQLAlchemy 2.0: памятка

SQLAlchemy 2.0, Python 3.11+. Блоки 1-5 - один скрипт, выполнять по порядку: SQLite в памяти, нужен только
`pip install sqlalchemy`. Блок про async - отдельный скрипт.

**Содержание**

- [Что есть что](#что-есть-что)
- [1. Модели](#1-модели)
- [2. Сессия и транзакции](#2-сессия-и-транзакции)
- [3. Запросы](#3-запросы)
- [4. Связи и N+1](#4-связи-и-n1)
- [5. Core: text, массовая вставка](#5-core-text-массовая-вставка)
- [Async](#async)
- [Alembic](#alembic)
- [Частые ошибки](#частые-ошибки)

## Что есть что

| Объект | Что это |
|---|---|
| `Engine` | точка входа в БД: адрес, диалект, пул соединений. Один на приложение |
| `Connection` | одно соединение из пула; уровень Core - таблицы и SQL-выражения |
| `Session` | уровень ORM: работает с объектами, копит изменения и пишет их в БД одной транзакцией (unit of work) |
| `sessionmaker` | фабрика сессий с общими настройками |
| Core | SQL-выражения на Python: `select`, `insert`, `text` - без объектов |
| ORM | классы-модели, связи, сессия поверх Core |

Пул по умолчанию: `pool_size=5` постоянных соединений и `max_overflow=10` сверх них. `pool_pre_ping=True` проверяет
соединение перед выдачей, чтобы не получить оборванное после рестарта БД.

## 1. Модели

```python
from datetime import datetime

from sqlalchemy import ForeignKey, String, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)                     # автоинкремент
    name: Mapped[str] = mapped_column(String(100))                        # тип без None - NOT NULL
    email: Mapped[str | None] = mapped_column(unique=True)                # с None - NULL допустим
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())  # значение ставит БД

    accounts: Mapped[list["Account"]] = relationship(back_populates="client", cascade="all, delete-orphan")


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    balance: Mapped[int] = mapped_column(default=0)                       # в копейках; значение ставит Python

    client: Mapped[Client] = relationship(back_populates="accounts")


engine = create_engine("sqlite://")            # Postgres: "postgresql+psycopg://user:password@host:5432/db"
Base.metadata.create_all(engine)               # в проекте таблицы создает Alembic
```

- Стиль 2.0: `Mapped[тип]` + `mapped_column()`. Тип Python задает и тип колонки, и `NULL`/`NOT NULL`.
  Старый стиль `Column(Integer, nullable=False)` работает, но в новом коде его не пишут.
- `relationship` - связь объектов, `ForeignKey` - колонка в БД. `Mapped[list[...]]` - один-ко-многим,
  `Mapped[Client]` - многие-к-одному. Многие-ко-многим - `relationship(secondary=таблица_связи)`.
- `back_populates` связывает две стороны: `client.accounts.append(acc)` сразу заполняет `acc.client`.
- `cascade="all, delete-orphan"` - счета сохраняются и удаляются вместе с клиентом.
- `default` вычисляет Python при `INSERT`, `server_default` пишется в DDL и вычисляется БД.

## 2. Сессия и транзакции

```python
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(engine, expire_on_commit=False)

with SessionLocal.begin() as session:          # COMMIT в конце, ROLLBACK при исключении
    anna = Client(name="Анна", email="anna@example.com", accounts=[Account(balance=10000), Account(balance=5000)])
    session.add(anna)                          # счета сохранятся каскадом

with SessionLocal() as session:                # транзакцией управляем сами
    boris = Client(name="Борис")
    session.add(boris)
    session.flush()                            # INSERT ушел в БД, транзакция открыта
    print(boris.id)                            # 2: id уже известен
    session.rollback()                         # Бориса в БД нет

with SessionLocal() as session:
    a1 = session.get(Client, 1)                # SELECT
    a2 = session.get(Client, 1)                # без запроса: объект уже в сессии
    print(a1 is a2)                            # True - карта объектов (identity map)
```

| Действие | Что делает |
|---|---|
| `session.add(obj)` | поставить объект в очередь на запись, в БД еще ничего |
| `session.flush()` | отправить накопленные `INSERT`/`UPDATE`/`DELETE` в БД, транзакция открыта |
| `session.commit()` | `flush` + `COMMIT` |
| `session.rollback()` | откатить транзакцию, изменения объектов сбрасываются |
| `session.refresh(obj)` | перечитать объект из БД |

- Транзакция начинается сама при первом запросе (autobegin). `with SessionLocal.begin()` - короткая форма
  "начать, при успехе `commit`, при ошибке `rollback`".
- Перед каждым запросом сессия сама делает `flush` (autoflush): новые объекты видны в `select` той же сессии.
- `expire_on_commit=True` (по умолчанию) после `commit` помечает все объекты устаревшими: следующее обращение
  к атрибуту - новый `SELECT`. Если сессия уже закрыта - `DetachedInstanceError`. Поэтому в веб-приложениях
  и всегда в async ставят `False`.
- Одна сессия на запрос или задачу. Сессия не потокобезопасна, глобальную сессию на все приложение не держат.

## 3. Запросы

```python
from sqlalchemy import func, select, update

with SessionLocal() as session:
    anna = session.scalars(select(Client).where(Client.name == "Анна")).one()   # ровно одна строка, иначе ошибка
    nobody = session.scalars(select(Client).where(Client.id == 99)).one_or_none()  # None
    rich = session.scalars(
        select(Account).where(Account.balance > 6000, Account.client_id == anna.id).order_by(Account.id)
    ).all()                                                    # список объектов Account
    count = session.scalar(select(func.count()).select_from(Account))          # одно значение: 2
    totals = session.execute(
        select(Client.name, func.sum(Account.balance).label("total"))
        .join(Client.accounts)
        .group_by(Client.name)
    ).all()                                                    # список строк Row
    print(totals[0].name, totals[0].total)                     # Анна 15000

    session.execute(                                           # списание одной командой, без чтения в Python
        update(Account).where(Account.id == 1, Account.balance >= 3000).values(balance=Account.balance - 3000)
    )
    session.commit()
```

| Вызов | Что вернет |
|---|---|
| `session.get(Model, pk)` | объект по первичному ключу или `None` |
| `session.scalars(stmt)` | первый столбец каждой строки - для `select(Model)` это объекты |
| `session.execute(stmt)` | строки `Row` - когда выбираешь несколько колонок |
| `session.scalar(stmt)` | одно значение: `count`, `max` |
| `.all()`, `.first()`, `.one()`, `.one_or_none()` | список; первая или `None`; ровно одна; одна или `None` |

- Условия: несколько аргументов в `where` - это `AND`; `or_(a, b)`, `Client.id.in_([1, 2])`, `Client.email.is_(None)`,
  `Client.name.ilike("ан%")`. Питоновские `and`/`or` здесь не работают.
- Пагинация: `.limit(20).offset(40)`; для больших таблиц - по ключу: `.where(Client.id > last_id).limit(20)`.
- `session.query(Client).filter(...)` - старый стиль 1.x. Работает, но в 2.0 пишут `select()`.

## 4. Связи и N+1

```python
from sqlalchemy import event
from sqlalchemy.orm import joinedload, selectinload

queries = []
event.listen(engine, "before_cursor_execute", lambda *args: queries.append(args[2]))   # счетчик запросов

with SessionLocal() as session:
    session.add(Client(name="Вера", accounts=[Account(balance=700)]))
    session.commit()

with SessionLocal() as session:
    queries.clear()
    for c in session.scalars(select(Client)).all():            # 1 запрос: клиенты
        print(c.name, len(c.accounts))                         # + 1 запрос на каждого клиента
    print("лениво:", len(queries))                             # 3 = 1 + N, N = 2 клиента

with SessionLocal() as session:
    queries.clear()
    for c in session.scalars(select(Client).options(selectinload(Client.accounts))).all():
        print(c.name, len(c.accounts))
    print("selectinload:", len(queries))                       # 2: клиенты + все счета через IN (...)

with SessionLocal() as session:
    queries.clear()
    accounts = session.scalars(select(Account).options(joinedload(Account.client))).all()
    print([a.client.name for a in accounts])
    print("joinedload:", len(queries))                         # 1: счета JOIN клиенты
```

N+1 - один запрос за списком и еще по запросу на каждый элемент, когда код обращается к его связи.
На 1000 клиентов это 1001 запрос. Лечится явной загрузкой связей в исходном запросе:

| Способ | Как грузит | Когда |
|---|---|---|
| `lazy="select"` - по умолчанию | отдельный запрос при первом обращении к связи | N+1 в цикле |
| `selectinload` | второй запрос `WHERE client_id IN (...)` | коллекции, один-ко-многим - основной выбор |
| `joinedload` | `LEFT OUTER JOIN` в том же запросе | многие-к-одному (`account.client`). Для коллекций строки размножаются, нужен `.unique()` |
| `raiseload` / `lazy="raise"` | ошибка при попытке ленивой загрузки | найти N+1 в тестах; в async ленивой загрузки все равно нет |

- Увидеть все запросы: `create_engine(..., echo=True)`.
- Способ задают в запросе через `.options(...)` или по умолчанию в модели: `relationship(lazy="selectin")`.

## 5. Core: text, массовая вставка

```python
from sqlalchemy import insert, text

with engine.connect() as conn:
    rows = conn.execute(text("SELECT id, name FROM clients WHERE name = :name"), {"name": "Анна"}).all()
    print(rows)                                                # [(1, 'Анна')]

with SessionLocal.begin() as session:                          # одна команда на весь список
    session.execute(insert(Account), [{"client_id": 1, "balance": i * 100} for i in range(1000)])
```

- Значения - только через параметры (`:name`). Подстановка через f-строку - SQL-инъекция.
- `insert(Model)` со списком словарей вставляет пачкой, без создания объектов. `session.add` в цикле на 100 тысяч
  объектов в разы медленнее.

## Async

```python
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

# модели Base, Client, Account - из блока 1
engine = create_async_engine("postgresql+asyncpg://postgres:pg@localhost:5432/postgres", pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)          # синхронный код через run_sync

    async with SessionLocal.begin() as session:
        session.add(Client(name="Анна", accounts=[Account(balance=100)]))

    async with SessionLocal() as session:
        stmt = select(Client).options(selectinload(Client.accounts))
        clients = (await session.scalars(stmt)).all()
        print([len(c.accounts) for c in clients])              # [1]

    async with SessionLocal() as session:
        client = await session.get(Client, 1)                  # связи не загружены
        try:
            client.accounts
        except Exception as e:
            print(type(e).__name__)                            # MissingGreenlet: ленивой загрузки в async нет

    await engine.dispose()


asyncio.run(main())
```

- Драйвер асинхронный: `postgresql+asyncpg://`. Методы, которые ходят в БД, вызываются с `await`.
- Ленивой загрузки нет: обращение к незагруженной связи падает с `MissingGreenlet`. Связи грузят явно
  (`selectinload`) или через `await client.awaitable_attrs.accounts` (примесь `AsyncAttrs` в `Base`).
- `expire_on_commit=False` обязательно: иначе после `commit` любой атрибут требует запроса - та же ошибка.
- Одна `AsyncSession` на задачу. Делить ее между задачами в `asyncio.gather` нельзя.
- FastAPI: сессия через зависимость - `async with SessionLocal() as session: yield session`.

## Alembic

```bash
alembic init migrations                               # в env.py: target_metadata = Base.metadata
alembic revision --autogenerate -m "add accounts"     # сравнить модели с БД и написать миграцию
alembic upgrade head                                  # применить все
alembic downgrade -1                                  # откатить одну
alembic current                                       # текущая версия БД (таблица alembic_version)
alembic history                                       # цепочка миграций
```

- Миграция - файл с `upgrade()` и `downgrade()`; `revision` и `down_revision` выстраивают цепочку.
  Две ветки разработки дали две "головы" - `alembic merge heads`.
- Autogenerate не видит переименований: колонку или таблицу он удалит и создаст заново, данные пропадут.
  Сгенерированную миграцию всегда читать глазами.
- Перенос данных пишут в миграции руками: `op.execute("UPDATE ...")`.

## Частые ошибки

- **N+1** - связи в цикле без `selectinload`/`joinedload`. Видно по `echo=True`.
- **`DetachedInstanceError`** - обращение к незагруженной связи или устаревшему атрибуту после закрытия сессии.
- **`MissingGreenlet`** - то же в async: ленивая загрузка или чтение атрибута после `commit` с `expire_on_commit=True`.
- **Сессия на все приложение** или общая на несколько потоков и задач - сессия не потокобезопасна,
  в ней копятся объекты.
- **`flush` вместо `commit`** - в БД изменения видны только этой транзакции; закрыли сессию - все откатилось.
- **Чтение, расчет в Python и запись** (`acc.balance -= 30`) - потерянное обновление при параллельных
  запросах. Нужен `update(...).values(balance=Account.balance - 30)` или `select(...).with_for_update()`.
- **`and`/`or` в `where`** - нужны `and_()`/`or_()` или несколько аргументов `where`.
