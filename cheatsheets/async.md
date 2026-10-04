# Асинхронный Python (asyncio): памятка

Python 3.11+. Каждый блок самостоятельный, можно копировать целиком.
asyncio - один поток, один цикл событий. Пока корутина ждет ввод-вывод на `await`, цикл выполняет другие.
Ускоряет ожидание (сеть, БД, файлы), вычисления не ускоряет.

## Корутина, await и asyncio.run

```python
import asyncio


async def fetch(name: str, delay: float) -> str:   # async def - корутинная функция
    await asyncio.sleep(delay)                     # await - ждать, отдав управление циклу
    return f"{name} готов"


async def main():
    result = await fetch("a", 0.1)                 # последовательно: ждем, потом дальше
    print(result)


asyncio.run(main())                                # точка входа: создает цикл, запускает, закрывает
```

`fetch("a", 0.1)` без `await` только создает объект корутины, код не выполняется.

## Несколько корутин одновременно: gather, create_task, TaskGroup

```python
import asyncio


async def fetch(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return name


async def main():
    # gather: запустить все и дождаться всех, результаты в порядке аргументов
    results = await asyncio.gather(fetch("a", 0.2), fetch("b", 0.1))   # ['a', 'b'] за 0.2 с

    # create_task: запустить в фоне сейчас, дождаться потом
    task = asyncio.create_task(fetch("c", 0.1))
    ...                                            # своя работа, пока задача идет
    c = await task

    # TaskGroup (3.11+): ошибка в одной задаче отменяет остальные
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(fetch("d", 0.1))
        t2 = tg.create_task(fetch("e", 0.1))
    print(results, c, t1.result(), t2.result())


asyncio.run(main())
```

## Обработка ошибок в gather

```python
import asyncio


async def ok():
    return 1


async def fail():
    raise ValueError("сбой")


async def main():
    try:
        await asyncio.gather(ok(), fail())         # первая ошибка летит наружу
    except ValueError as e:
        print("ошибка:", e)

    results = await asyncio.gather(ok(), fail(), return_exceptions=True)
    print(results)                                 # [1, ValueError('сбой')]
    for r in results:
        if isinstance(r, Exception):
            ...                                    # обработать ошибку


asyncio.run(main())
```

## Таймауты: timeout и wait_for

```python
import asyncio


async def slow():
    await asyncio.sleep(10)


async def main():
    try:
        async with asyncio.timeout(0.1):           # 3.11+
            await slow()
    except TimeoutError:
        print("не успели")

    try:
        await asyncio.wait_for(slow(), timeout=0.1)   # то же для одной корутины
    except TimeoutError:
        print("не успели")


asyncio.run(main())
```

## Ограничить число одновременных запросов: Semaphore

```python
import asyncio


async def fetch(url: str, sem: asyncio.Semaphore) -> str:
    async with sem:                                # не больше N внутри одновременно
        await asyncio.sleep(0.1)
        return url


async def main():
    sem = asyncio.Semaphore(10)
    urls = [f"/item/{i}" for i in range(100)]
    results = await asyncio.gather(*(fetch(u, sem) for u in urls))
    print(len(results))                            # 100, за ~1 с вместо 0.1 с или 10 с


asyncio.run(main())
```

## Результаты по мере готовности: as_completed

```python
import asyncio


async def fetch(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return name


async def main():
    coros = [fetch("медленный", 0.3), fetch("быстрый", 0.1)]
    for next_done in asyncio.as_completed(coros):
        print(await next_done)                     # быстрый, медленный


asyncio.run(main())
```

## Очередь задач: производитель и обработчики (Queue)

```python
import asyncio


async def producer(queue: asyncio.Queue, n: int):
    for i in range(n):
        await queue.put(i)


async def worker(name: str, queue: asyncio.Queue, results: list):
    while True:
        item = await queue.get()
        try:
            await asyncio.sleep(0.01)              # обработка
            results.append(item)
        finally:
            queue.task_done()                      # отметить элемент обработанным


async def main():
    queue: asyncio.Queue[int] = asyncio.Queue(maxsize=100)
    results: list[int] = []
    workers = [asyncio.create_task(worker(f"w{i}", queue, results)) for i in range(3)]
    await producer(queue, 20)
    await queue.join()                             # ждать, пока все обработают
    for w in workers:
        w.cancel()                                 # остановить бесконечные циклы
    await asyncio.gather(*workers, return_exceptions=True)
    print(len(results))                            # 20


asyncio.run(main())
```

## Блокирующий код внутри корутины: to_thread

```python
import asyncio
import time


def blocking_io() -> str:                          # requests, open(), psycopg2, time.sleep ...
    time.sleep(0.1)
    return "готово"


async def main():
    result = await asyncio.to_thread(blocking_io)  # в отдельном потоке, цикл не стоит
    print(result)
    # time.sleep(1) прямо здесь остановил бы весь цикл и все задачи
    # тяжелые вычисления - в процесс: loop.run_in_executor(ProcessPoolExecutor(), func)


asyncio.run(main())
```

## Общие данные между задачами: Lock

```python
import asyncio


class Wallet:
    def __init__(self):
        self.balance = 100
        self._lock = asyncio.Lock()

    async def withdraw(self, amount: int) -> bool:
        async with self._lock:                     # проверка и списание без вмешательства других задач
            if self.balance < amount:
                return False
            await asyncio.sleep(0.01)              # await внутри - точка переключения
            self.balance -= amount
            return True


async def main():
    w = Wallet()
    results = await asyncio.gather(*(w.withdraw(30) for _ in range(5)))
    print(results, w.balance)                      # три True, баланс 10; без Lock ушел бы в минус


asyncio.run(main())
```

## Отмена задачи: cancel и CancelledError

```python
import asyncio


async def job():
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        print("уборка")                            # закрыть соединения
        raise                                      # CancelledError пробрасывать обязательно


async def main():
    task = asyncio.create_task(job())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("отменена")


asyncio.run(main())
```

## async with, async for, асинхронный генератор

```python
import asyncio
from contextlib import asynccontextmanager


@asynccontextmanager
async def connection(dsn: str):
    print("открыть", dsn)
    try:
        yield {"dsn": dsn}                         # тело async with
    finally:
        print("закрыть")


async def ticks(n: int):                           # асинхронный генератор
    for i in range(n):
        await asyncio.sleep(0.01)
        yield i


async def main():
    async with connection("db://") as conn:
        async for i in ticks(3):
            print(conn["dsn"], i)
    squares = [i * i async for i in ticks(3)]      # [0, 1, 4]


asyncio.run(main())
```

Свой класс: `async with` - методы `__aenter__` / `__aexit__`, `async for` - `__aiter__` / `__anext__`.

## Что выбрать: потоки, процессы или asyncio

| Задача | Чем | Почему |
| --- | --- | --- |
| много сетевых запросов, БД | asyncio | тысячи ожиданий в одном потоке |
| блокирующая библиотека без async | потоки (`to_thread`, `ThreadPoolExecutor`) | на ожидании ввода-вывода GIL отпускается |
| вычисления на CPU | процессы (`ProcessPoolExecutor`) | GIL не дает потокам считать параллельно |

## Частые ошибки

| Ошибка | Правильно |
| --- | --- |
| `fetch()` без `await` | `await fetch()`; иначе предупреждение "coroutine was never awaited" |
| `time.sleep()` в корутине | `await asyncio.sleep()` |
| `requests` в корутине | `httpx.AsyncClient` / `aiohttp` или `asyncio.to_thread` |
| `for` с `await` по одному, когда нужно параллельно | `asyncio.gather(...)` или `TaskGroup` |
| `create_task(...)` без сохранения ссылки | сохранить задачу (в переменную, множество) и дождаться |
| `asyncio.run()` внутри работающего цикла | `await` корутину; `asyncio.run` - только точка входа |
| глотать `CancelledError` | после уборки - `raise` |
| тысячи запросов разом | `asyncio.Semaphore(N)` |
