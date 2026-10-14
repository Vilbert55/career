# Docker: памятка

Сквозной пример - HTTP-сервис списаний `payments` на FastAPI. Сборка и проверки сделаны на Docker с образом
`python:3.12-slim`. Как этот же сервис живет в кластере - [kubernetes.md](kubernetes.md).

**Содержание**

- [Понятия](#понятия)
- [Dockerfile](#dockerfile)
- [CMD, ENTRYPOINT и остановка контейнера](#cmd-entrypoint-и-остановка-контейнера)
- [Данные и сеть](#данные-и-сеть)
- [docker compose](#docker-compose)
- [Команды](#команды)
- [Частые вопросы](#частые-вопросы)

## Понятия

| Понятие | Что это |
|---|---|
| образ (image) | шаблон: файлы приложения и ОС плюс команда запуска. Не меняется, состоит из слоев |
| слой | результат одной инструкции Dockerfile (`RUN`, `COPY`). Слои кешируются и переиспользуются |
| контейнер | запущенный образ: обычный процесс хоста, изолированный (namespaces) и ограниченный по ресурсам (cgroups), плюс свой слой для записи |
| реестр (registry) | хранилище образов: Docker Hub, Harbor, Nexus, GitLab Registry |
| тег | версия образа: `payments:1.4.2`. `latest` - просто тег по умолчанию, "последнюю версию" он не гарантирует |
| том (volume) | данные вне контейнера, переживают его удаление |

Контейнер против виртуальной машины: контейнер использует ядро хоста, стартует за доли секунды и весит десятки
мегабайт. У виртуальной машины свое ядро и своя ОС.

## Dockerfile

```
payments/
├── app/
│   ├── __init__.py
│   └── main.py          # FastAPI, GET /health
├── requirements.txt     # fastapi, uvicorn
├── .dockerignore
└── Dockerfile
```

```dockerfile
# Этап 1: установка зависимостей
FROM python:3.12-slim AS build
WORKDIR /app
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Этап 2: итоговый образ - только venv и код
FROM python:3.12-slim
RUN useradd --uid 10001 --no-create-home app
COPY --from=build /venv /venv
ENV PATH="/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY app/ app/
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`.dockerignore` - что не отправлять в сборку:

```
.git
.venv
__pycache__
*.pyc
.env
tests/
```

- **Порядок слоев.** Сначала то, что меняется редко (`requirements.txt` и `pip install`), потом код. Поменяли код -
  при пересборке `pip install` берется из кеша (`CACHED`), сборка занимает секунды. Если `COPY . .` стоит до
  `pip install`, любая правка кода переустанавливает все зависимости.
- **Многоэтапная сборка.** Компиляторы, кеш pip и прочее для сборки остаются в первом этапе. В итоговый образ
  попадает только результат (`COPY --from=build`). Здесь итог - 217 МБ.
- **Не root.** `USER app`: если приложение взломают, у процесса не будет прав root в контейнере. Проверка -
  `docker exec payments id` дает `uid=10001(app)`.
- **`PYTHONUNBUFFERED=1`** - Python пишет логи в stdout сразу, без буфера: `docker logs` видит их без задержки.
- **Секреты в образ не кладут** - ни `COPY .env`, ни `ENV PASSWORD=...`, ни `ARG`. Они остаются в слоях,
  их видно в `docker history`. Секреты передают при запуске: переменными окружения или файлами.
- **База** - `python:3.12-slim` (Debian). Alpine для Python обычно хуже: другая libc (musl), готовые колеса
  пакетов подходят не всегда, и зависимости собираются из исходников. Версию базы фиксируют, без `latest`.

| Пара | Разница |
|---|---|
| `RUN` и `CMD` | `RUN` выполняется при сборке, `CMD` - при запуске контейнера |
| `ARG` и `ENV` | `ARG` есть только во время сборки, `ENV` - и при сборке, и в работающем контейнере |
| `COPY` и `ADD` | `ADD` еще распаковывает архивы и скачивает по URL. Обычно пишут `COPY` |
| `EXPOSE` и `-p` | `EXPOSE` только документирует порт. Открывает его `docker run -p` |

## CMD, ENTRYPOINT и остановка контейнера

`docker stop` (и Kubernetes при удалении пода) шлет процессу с PID 1 сигнал `SIGTERM` и ждет. Не завершился
за 10 секунд (в Kubernetes за 30) - `SIGKILL`, незаконченные запросы обрываются.

| Форма | PID 1 | `docker stop` |
|---|---|---|
| exec: `CMD ["uvicorn", "app.main:app", ...]` | uvicorn | 0,4 с: uvicorn получил `SIGTERM` и завершился штатно |
| shell: `CMD uvicorn app.main:app ...` | `/bin/sh -c uvicorn ...` | 10,1 с: `sh` не передает сигнал, приложение убито `SIGKILL` |

- Писать exec-форму - JSON-массив.
- `ENTRYPOINT` - что запускается всегда, `CMD` - аргументы по умолчанию. `CMD` заменяется аргументами
  `docker run образ ...`, `ENTRYPOINT` - только флагом `--entrypoint`.

```dockerfile
ENTRYPOINT ["uvicorn"]
CMD ["app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- Скрипт-обертка в `ENTRYPOINT` (миграции перед стартом и т. п.) заканчивается на `exec "$@"`: тогда
  приложение заменяет shell и само становится PID 1.

## Данные и сеть

- Все, что контейнер записал внутри себя, пропадает вместе с ним. Постоянные данные - в том:
  - `-v pgdata:/var/lib/postgresql/data` - именованный том, им управляет Docker;
  - `-v ./config:/app/config` - папка хоста (bind mount), удобно при разработке.
- Порт: `-p 8000:8000` - "порт хоста:порт контейнера".
- Контейнеры одной сети находят друг друга по имени. Compose создает сеть сам: из `payments` база доступна как
  `db:5432`. `localhost` внутри контейнера - сам контейнер.

## docker compose

Несколько контейнеров одним файлом - для разработки и тестов:

```yaml
services:
  db:
    image: postgres:14-alpine
    environment:
      POSTGRES_PASSWORD: pg
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]
      interval: 5s
      retries: 5

  payments:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:pg@db:5432/postgres
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```

- `depends_on` без `condition: service_healthy` ждет только запуска контейнера `db`. Сама база в этот момент
  может еще не принимать подключения.

## Команды

```bash
docker build -t payments:1.4.2 .                  # собрать образ из Dockerfile в текущей папке
docker run -d --name payments -p 8000:8000 -e DATABASE_URL=... payments:1.4.2
docker ps                                         # запущенные; -a - все, включая остановленные
docker logs -f payments                           # логи (stdout и stderr)
docker exec -it payments sh                       # зайти внутрь
docker stop payments && docker rm payments
docker images                                     # образы; docker rmi - удалить
docker history payments:1.4.2                     # слои образа и их размер
docker compose up -d --build                      # собрать и поднять все сервисы
docker compose logs -f payments
docker compose down                               # остановить и удалить; -v - вместе с томами
docker system prune                               # удалить остановленные контейнеры и неиспользуемые образы
```

## Частые вопросы

- **Как уменьшить образ.** Slim-база, многоэтапная сборка, `pip install --no-cache-dir`, `.dockerignore`.
  Ставить и чистить пакеты в одном `RUN`: `apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*`.
  Файл, удаленный следующей инструкцией, остается в предыдущем слое.
- **Почему `apt-get update` и `install` в одном `RUN`.** Иначе `update` закешируется отдельным слоем, и `install`
  через месяц возьмет устаревшие списки пакетов.
- **Один процесс на контейнер.** Веб-сервер, воркер очереди, планировщик - разные контейнеры из одного образа
  с разной командой запуска.
- **Логи** - в stdout и stderr, файлы логов внутри контейнера не пишут. Собирает их окружение.
- **Настройки - через переменные окружения.** Один образ идет на все контуры: dev, test, prod. Отличаются только
  переменные.
