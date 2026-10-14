# SQLAlchemy 2.0: памятка

SQLAlchemy 2.0, Python 3.11+. Блоки 1-5 - один скрипт, выполнять по порядку: SQLite в памяти, нужен только
`pip install sqlalchemy`. Блок про async - отдельный скрипт.

**Содержание**

- [Что есть что](#что-есть-что)
- [Что изменилось после 1.x](#что-изменилось-после-1x)
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

## Что изменилось после 1.x

Версия 1.4 - переходная: новый стиль уже есть, старый работает с предупреждениями. В 2.0 старое удалено или
объявлено устаревшим.

| Было в 1.x | Стало в 2.0 |
|---|---|
| `session.query(Client).filter(Client.id == 1).first()` | `session.scalars(select(Client).where(Client.id == 1)).first()` |
| `session.query(Client).get(1)` | `session.get(Client, 1)` |
| `Base = declarative_base()` | `class Base(DeclarativeBase): pass` |
| `id = Column(Integer, primary_key=True)` | `id: Mapped[int] = mapped_column(primary_key=True)` |
| `engine.execute(...)`, автокоммит | удалены: `with engine.begin() as conn: conn.execute(...)` |
| строка SQL в `execute("SELECT ...")` | только через `text("SELECT ...")` |
| async нет | `create_async_engine`, `AsyncSession` (с 1.4) |
| `joinedload` по списку, затем `.all()` | перед `.all()` нужен `.unique()` |

`session.query()` в 2.0 работает, но считается старым API.

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

**Что такое N+1.** Получили список клиентов одним запросом и в цикле обращаемся к `client.accounts`. Счета
не загружены, и SQLAlchemy на каждое обращение делает отдельный запрос. Итого 1 запрос за список и еще N за связями:
на 1000 клиентов - 1001 запрос.

```python
from sqlalchemy.orm import joinedload, raiseload, selectinload

engine.echo = True                                       # печатать SQL - видно каждый запрос

with SessionLocal() as session:
    session.add(Client(name="Вера", accounts=[Account(balance=700)]))
    session.commit()

# Плохо: 1 + N запросов
with SessionLocal() as session:
    clients = session.scalars(select(Client)).all()           # SELECT ... FROM clients
    for c in clients:
        print(c.name, len(c.accounts))                        # SELECT ... FROM accounts WHERE ? = accounts.client_id
                                                              # - для каждого клиента заново
```

**Что делать: сразу сказать в запросе, какие связи понадобятся.**

```python
# Список связанных объектов (client.accounts) - selectinload: 2 запроса при любом числе клиентов
with SessionLocal() as session:
    clients = session.scalars(select(Client).options(selectinload(Client.accounts))).all()
    # SELECT ... FROM clients
    # SELECT ... FROM accounts WHERE accounts.client_id IN (1, 2)
    for c in clients:
        print(c.name, len(c.accounts))                        # без запросов: счета уже загружены

# Один связанный объект (account.client) - joinedload: 1 запрос
with SessionLocal() as session:
    accounts = session.scalars(select(Account).options(joinedload(Account.client))).all()
    # SELECT ... FROM accounts LEFT OUTER JOIN clients ON clients.id = accounts.client_id
    print([a.client.name for a in accounts])

# Объекты не нужны, нужны только цифры - посчитать в SQL: 1 запрос
with SessionLocal() as session:
    rows = session.execute(
        select(Client.name, func.count(Account.id)).join(Client.accounts).group_by(Client.name)
    ).all()
    print(rows)                                               # [('Анна', 2), ('Вера', 1)]

engine.echo = False
```

| Что нужно | Чем грузить |
|---|---|
| список: `client.accounts` | `selectinload` |
| один объект: `account.client` | `joinedload` |
| только количество или сумма | `func.count`, `func.sum` в самом запросе |

**Как не допустить N+1.** Запретить ленивую загрузку: обращение к незагруженной связи сразу дает ошибку,
и N+1 ловится в тестах, а не на проде.

```python
with SessionLocal() as session:
    client = session.scalars(select(Client).options(raiseload(Client.accounts))).first()
    try:
        client.accounts
    except Exception as e:
        print(e)                                              # 'Client.accounts' is not available due to lazy='raise'
```

- Запрет для всей модели: `relationship(lazy="raise")`. Тогда каждый запрос явно говорит, какие связи грузить.
- Загрузку по умолчанию можно поменять в модели: `relationship(lazy="selectin")`. Удобно, но счета будут грузиться
  и там, где они не нужны.
- `joinedload` для списка тоже работает, но строки клиента размножаются по числу счетов, и нужен `.unique()`
  перед `.all()`. Для списков проще `selectinload`.
- В async ленивой загрузки нет вообще: незагруженная связь сразу дает `MissingGreenlet`. Там `selectinload`
  обязателен.

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
