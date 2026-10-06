# Контекстные менеджеры: памятка

Python 3.11+. Каждый блок самостоятельный, можно копировать целиком.
`with cm as x:` - Python вызывает у объекта `__enter__`, результат кладет в `x`, после блока вызывает
`__exit__` - даже если в блоке было исключение, `return` или `break`.

**Содержание**

- [Что делает with](#что-делает-with)
- [Класс с `__enter__` и `__exit__`](#класс-с-__enter__-и-__exit__)
- [Генератор и `@contextmanager`](#генератор-и-contextmanager)
- [Исключения внутри блока](#исключения-внутри-блока)
- [Временная подмена значения](#временная-подмена-значения)
- [Несколько менеджеров и ExitStack](#несколько-менеджеров-и-exitstack)
- [async with](#async-with)
- [Готовые менеджеры](#готовые-менеджеры)
- [Типы](#типы)
- [Частые ошибки](#частые-ошибки)

## Что делает with

```python
# схема, не для запуска
with cm as x:
    body()

# примерно то же самое:
x = type(cm).__enter__(cm)              # методы ищутся у класса объекта
try:
    body()
except BaseException as exc:
    if not type(cm).__exit__(cm, type(exc), exc, exc.__traceback__):
        raise                           # __exit__ вернул не True - исключение летит дальше
else:
    type(cm).__exit__(cm, None, None, None)
```

Менеджер - любой объект, у класса которого есть `__enter__` и `__exit__`. Функции с такими именами
внутри обычной функции менеджером ее не делают.

## Класс с `__enter__` и `__exit__`

```python
import time


class Timer:
    def __enter__(self):
        self.start = time.perf_counter()
        return self                     # попадет в переменную после as

    def __exit__(self, exc_type, exc, tb):
        self.elapsed = time.perf_counter() - self.start
        return None                     # None или False - исключение не глушим


with Timer() as t:
    sum(range(1_000_000))
print(f"{t.elapsed:.3f} с")
```

Состояние держим в `self`: у каждого `with Timer()` свой объект.

## Генератор и `@contextmanager`

```python
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def cd(path: str) -> Iterator[str]:
    old = os.getcwd()                   # до yield - это __enter__
    os.chdir(path)
    try:
        yield path                      # значение попадет в as, здесь выполняется тело with
    finally:
        os.chdir(old)                   # после yield - это __exit__, finally - и при исключении


with cd(tempfile.gettempdir()) as p:
    print(os.getcwd(), p)
```

- Без `try/finally` код после `yield` при исключении в блоке не выполнится.
- `yield` ровно один раз. Такой менеджер одноразовый: второй `with` по тому же объекту - `RuntimeError`.
- Функция-генератор аннотируется `-> Iterator[T]`, `T` - тип того, что попадет в `as`.

## Исключения внутри блока

`__exit__(exc_type, exc, tb)` получает исключение из блока или три `None`, если блок прошел без ошибок.
Вернул `True` - исключение подавлено, иначе летит дальше.

```python
import sqlite3


class Transaction:
    """commit при успехе, rollback при ошибке, ошибку не глушим."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        return False


conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE t (x INT)")
try:
    with Transaction(conn) as c:
        c.execute("INSERT INTO t VALUES (1)")
        raise ValueError("ошибка в блоке")
except ValueError:
    pass
print(conn.execute("SELECT count(*) FROM t").fetchone())   # (0,) - вставка откатилась
```

То же генератором: исключение из блока вылетает в точке `yield`.

```python
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise                           # без raise исключение будет подавлено
    else:
        conn.commit()


conn = sqlite3.connect(":memory:")
with transaction(conn) as c:
    c.execute("CREATE TABLE t (x INT)")
```

Подавить конкретное исключение - `contextlib.suppress`:

```python
import os
from contextlib import suppress

with suppress(FileNotFoundError):
    os.remove("нет_такого_файла.txt")
```

## Временная подмена значения

Шаблон "запомнить - подменить - вернуть", с учетом случая, когда значения не было:

```python
import os
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def env(name: str, value: str) -> Iterator[str]:
    old = os.environ.get(name)          # None - переменной не было
    os.environ[name] = value
    try:
        yield value
    finally:
        if old is None:
            del os.environ[name]
        else:
            os.environ[name] = old


with env("APP_MODE", "test"):
    print(os.environ["APP_MODE"])       # test
print("APP_MODE" in os.environ)         # False
```

- Сохраняем ссылку на старое значение, без копии: после блока должен вернуться тот же объект.
- Если `None` - допустимое значение (атрибуты, словари), маркером "не было" берут свой объект:
  `_MISSING = object()`, проверка `old is _MISSING`.
- Атрибут по имени из переменной: `getattr(obj, name, default)`, `setattr(obj, name, value)`, `delattr(obj, name)`.

## Несколько менеджеров и ExitStack

```python
with open("a.txt", "w") as a, open("b.txt", "w") as b:
    a.write("a")
    b.write("b")

with (                                  # в скобках - по одному на строке
    open("a.txt") as a,
    open("b.txt") as b,
):
    print(a.read(), b.read())
```

Число менеджеров известно только при выполнении - `ExitStack`:

```python
from contextlib import ExitStack

paths = ["a.txt", "b.txt"]
with ExitStack() as stack:
    files = [stack.enter_context(open(p)) for p in paths]
    stack.callback(print, "выход")      # любое действие при выходе
    print([f.read() for f in files])
# выход идет в обратном порядке: callback, затем файлы с конца
```

## async with

```python
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class Connection:
    async def __aenter__(self):
        await asyncio.sleep(0)          # открыть соединение
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await asyncio.sleep(0)          # закрыть соединение


@asynccontextmanager
async def session() -> AsyncIterator[str]:
    await asyncio.sleep(0)
    try:
        yield "сессия"
    finally:
        await asyncio.sleep(0)


async def main():
    async with Connection() as conn, session() as s:
        print(conn, s)


asyncio.run(main())
```

## Готовые менеджеры

| Менеджер | Что делает |
|---|---|
| `open(path)` | закрывает файл |
| `threading.Lock()`, `asyncio.Lock()` | захватывает и освобождает блокировку |
| `tempfile.TemporaryDirectory()` | временная папка, удаляется после блока |
| `contextlib.suppress(Exc)` | подавляет указанные исключения |
| `contextlib.chdir(path)` | временно меняет рабочую папку |
| `contextlib.redirect_stdout(buf)` | перехватывает `print` |
| `contextlib.closing(obj)` | вызывает `obj.close()` у объекта без своего `with` |
| `contextlib.nullcontext(x)` | заглушка, когда менеджер нужен не всегда |
| `unittest.mock.patch.object(obj, "attr", v)` | временно подменяет атрибут (в тестах) |
| `pytest.raises(Exc)` | проверяет, что блок бросил исключение |
| соединение `sqlite3`, `psycopg2` | commit или rollback транзакции, соединение не закрывает |

```python
import threading
from contextlib import nullcontext

use_threads = False
lock = threading.Lock() if use_threads else nullcontext()
with lock:
    print("работаем")
```

## Типы

```python
from types import TracebackType
from typing import Self


class Resource:
    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        print("освобождаю")


with Resource() as r:
    print(r)
```

- Генератор под `@contextmanager`: `-> Iterator[T]`; async-вариант: `-> AsyncIterator[T]`.
- Параметр "любой менеджер": `contextlib.AbstractContextManager[T]`.
- `__exit__` с `-> bool` - для менеджера, который может подавлять исключения.

## Частые ошибки

- Функции `__enter__` и `__exit__` внутри обычной функции: она возвращает `None`, и `with` падает
  с `'NoneType' object does not support the context manager protocol`. Нужен класс или `@contextmanager`.
- `__exit__` без трех параметров `(exc_type, exc, tb)` - `TypeError` при выходе из блока.
- В генераторе нет `try/finally` - при исключении в блоке очистка не выполняется.
- `except` в генераторе без `raise` - исключение молча подавлено.
- `__exit__` случайно возвращает истину - исключение пропадает.
- Состояние в глобальной переменной или атрибуте класса - вложенные и параллельные `with` затирают
  друг друга. Держать в `self` или в локальной переменной генератора.
- `__enter__` ничего не вернул - в `as` попадет `None`.
