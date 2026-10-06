# Шпаргалки

Краткие памятки по Python. Примеры кода проверены запуском.

| Файл | Тема |
|---|---|
| [pydantic.md](pydantic.md) | pydantic v2: модели, свои типы через Annotated, валидаторы, вложенные модели, сериализация и псевдонимы, ConfigDict, наследование |
| [dataclasses.md](dataclasses.md) | dataclasses: поля, параметры, field(), __post_init__, наследование, отличия от pydantic |
| [iterators-generators.md](iterators-generators.md) | итераторы, генераторы, конвейеры, itertools, contextmanager и send |
| [decorators.md](decorators.md) | декораторы: шаблон, wraps, с аргументами и с необязательными аргументами, состояние, класс, async, регистрация, встроенные |
| [context-managers.md](context-managers.md) | контекстные менеджеры: протокол with, класс и @contextmanager, исключения, временная подмена значения, ExitStack, async with, готовые менеджеры, типы |
| [async.md](async.md) | asyncio: корутины, gather и TaskGroup, таймауты, Semaphore, очередь, to_thread, Lock, отмена, async with/for |
| [pytest.md](pytest.md) | pytest: запуск, проверки, parametrize, фикстуры, monkeypatch и mock, async, чек-лист тестов |
| [pytest-example/](pytest-example/) | пример проекта: код, фикстуры в conftest.py, тесты; pytest.ini, VS Code без ИИ |
