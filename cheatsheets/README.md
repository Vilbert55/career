# Шпаргалки

Краткие памятки по Python и SQL.

| Файл | Тема |
|---|---|
| [pydantic.md](pydantic.md) | pydantic v2: модели, свои типы через Annotated, валидаторы, вложенные модели, сериализация и псевдонимы, ConfigDict, наследование |
| [dataclasses.md](dataclasses.md) | dataclasses: поля, параметры, field(), __post_init__, наследование, отличия от pydantic |
| [iterators-generators.md](iterators-generators.md) | итераторы, генераторы, конвейеры, itertools, contextmanager и send |
| [decorators.md](decorators.md) | декораторы: шаблон, wraps, с аргументами и с необязательными аргументами, состояние, класс, async, регистрация, встроенные |
| [context-managers.md](context-managers.md) | контекстные менеджеры: протокол with, класс и @contextmanager, исключения, временная подмена значения, ExitStack, async with, готовые менеджеры, типы |
| [async.md](async.md) | asyncio: корутины, gather и TaskGroup, таймауты, Semaphore, очередь, to_thread, Lock, отмена, async with/for |
| [threads-processes.md](threads-processes.md) | потоки и процессы: что выбрать, GIL, ThreadPoolExecutor, Lock и Queue, ProcessPoolExecutor, общая память, API concurrent.futures, частые ошибки |
| [greenplum.md](greenplum.md) | Greenplum и PostgreSQL: MPP, распределение и перекос, motion и чтение плана, ORCA, heap/AO/AOCS, партиции, ресурсы, сводная таблица отличий, почему запрос медленный |
| [sql.md](sql.md) | SQL: порядок выполнения, NULL, соединения и их ловушки, группировка, оконные функции, подзапросы и CTE, изоляция транзакций, типы данных, приемы типовых задач |
| [sqlalchemy.md](sqlalchemy.md) | SQLAlchemy 2.0: модели Mapped, сессия и транзакции, запросы select, N+1 и способы загрузки связей, Core и массовая вставка, async, Alembic, частые ошибки |
| [pytest.md](pytest.md) | pytest: запуск, проверки, parametrize, фикстуры, monkeypatch и mock, async, чек-лист тестов |
| [pytest-example/](pytest-example/) | пример проекта: код, фикстуры в conftest.py, тесты; pytest.ini, VS Code без ИИ |
