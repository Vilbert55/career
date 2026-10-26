# LinkedIn: https://www.linkedin.com/in/vilbert55/

Легенда резюме А (A-senior-python.md, hh). Основной профиль на русском, второй - на английском (решение Павла, 26.10.2026).
Отличия от hh: в "Общих сведениях" нет блока "Слабые стороны" (решение Павла), в описании ЦС убрано
"(Data Build Tool)" - лимит LinkedIn 2000 знаков на описание места работы. Промгидро не указываем, как на hh.
Текст между линиями `---` вставляется в поле как есть.

## Заголовок и раздел "Интересует"

- Заголовок: Senior Python Developer (Backend, DWH, ETL) | Greenplum, PostgreSQL, Airflow, Kafka
- Местоположение: Сочи, Краснодарский край, Россия. Отрасль: Разработка программного обеспечения.
- Контакты: телефон и почта (видны контактам 1-го уровня, были заполнены раньше), сайты
  https://github.com/vilbert55 (тип "Портфолио") и https://t.me/p_savelichev (тип "Другое"), видны всем.
- "В поиске работы": видно только рекрутерам (рамка #OpenToWork на фото снята). Должности (максимум 5,
  названия из справочника LinkedIn) - Python-разработчик, Разработчик серверной части, Инженер по работе
  с данными, Архитектор данных, Ведущий разработчик; регион - Россия; формат - в офисе, гибрид, удаленно;
  полная занятость. Рассылку о вакансиях не включали.
- Оповещение контактов об изменениях профиля выключено, посты о новой должности не публиковали.

## Общие сведения (RU)

---
Python-разработчик со специализацией на аналитических хранилищах данных (DWH, OLAP, ETL), более 6 лет в коммерческой разработке, последние 3,5 года - платформа больших данных для холдинга РЖД. Разрабатываю бэкенд и компоненты платформы данных, веду задачи от требований до приемки. В разработке использую ИИ-агентов.

Сильные стороны:
- Системное и продуктовое мышление (soft skills). Вижу процессы целиком: как устроена работа команды и как взаимодействуют сервисы в микросервисной архитектуре. Разбираю сценарии использования продукта до начала разработки и учитываю их в требованиях и решениях. Добиваюсь, чтобы команда выпускала качественный продукт, удобный пользователям.
- Расследование сложных инцидентов на проде: от симптома до причины и исправления.
- Передача знаний команде: доклады, учебные материалы, наставничество.
- Работа с ИИ-агентами: веду для них контекст, свой и общий для команды в репозиториях, и отношусь к нему так же ответственно, как к коду.

Разбираюсь в устройстве аналитических хранилищ: MPP-архитектура, типовые OLAP-сценарии (агрегации, витрины данных, аналитические запросы), моделирование данных (звезда, снежинка, Data Vault 2.0), нормальные формы, принципы сетки данных (Data Mesh). Проектирую решения от требований: функциональные и измеримые нефункциональные требования, выбор архитектуры и его обоснование.

В бэкенде: асинхронный Python с пониманием устройства на уровне операционной системы.

В 2025-2026 годах прошел обучение в Яндекс Практикуме по программе для разработчиков с опытом, чтобы актуализировать знания по современной backend-разработке.

Хочу расти в сторону архитектуры: проектировать решения, обосновывать их и доводить до прода.

GitHub: github.com/Vilbert55
---

## About (EN)

---
Python developer specializing in analytical data warehouses (DWH, OLAP, ETL), more than 6 years in commercial software development, the last 3.5 years on a big data platform for the Russian Railways (RZD) holding. I develop backend services and data platform components and take tasks from requirements to acceptance. I use AI agents in development.

Strengths:
- Systems and product thinking (soft skills). I see processes as a whole: how the team works and how services interact in a microservice architecture. I analyze product use cases before development starts and take them into account in requirements and design decisions. I make sure the team ships a high-quality product that is convenient for users.
- Investigating complex production incidents: from symptom to root cause and fix.
- Knowledge sharing: talks, training materials, mentoring.
- Working with AI agents: I maintain context for them, both my own and shared with the team in repositories, and treat it as responsibly as code.

I understand how analytical data warehouses work: MPP architecture, typical OLAP scenarios (aggregations, data marts, analytical queries), data modeling (star, snowflake, Data Vault 2.0), normal forms, Data Mesh principles. I design solutions starting from requirements: functional and measurable non-functional requirements, choice of architecture and its justification.

Backend: asynchronous Python with an understanding of how it works at the operating system level.

In 2025-2026 I completed a Yandex Practicum program for experienced developers to update my knowledge of modern backend development.

I want to grow toward architecture: designing solutions, justifying them and bringing them to production.

GitHub: github.com/Vilbert55
---

## Опыт работы

### Цифровые Сервисы, март 2023 - настоящее время

Должность: Старший Python-разработчик / Senior Python Developer. Компания в английской версии -
Tsifrovye Servisy (транслитерация, английского названия компании не знаем). Полная занятость, в офисе, Сочи.

---
Платформа больших данных - корпоративное хранилище данных холдинга РЖД (КХД), построенное по принципам сетки данных (Data Mesh), в котором более сотни доменов. В основе платформы - Greenplum, Kafka, Hadoop и Airflow. Поверх них разрабатываю на Python и SQL слой управления - то, что делает из них самообслуживаемую платформу: доменные команды получают готовые хранилища, интерфейсы для создания конвейеров данных и управления ими, контроль доступа. Слой включает API метаданных, генерацию DAG для Airflow и сервисы продуктов данных, прав доступа и заданий на инфраструктуру. Веду задачи от требований и ТЗ до приемки. С декабря 2024 года - старший разработчик: распределяю задачи в бэкенде, провожу код-ревью, был наставником младшего разработчика.

Результаты:
- Выполнил множество задач во всех компонентах платформы: от расследования инцидентов на проде и исправления ошибок до разработки нового функционала.
- Спроектировал перенос данных и метаданных платформы на новую инфраструктуру заказчика. Перенос прошел с первой попытки, с минимальным простоем: поступление данных и доступ потребителей к витринам не прерывались.
- Разработал ролевую модель для совместной работы нескольких проектных команд в одном домене, от требований до приемки, во всех компонентах платформы.
- Разработал концепции резервного копирования и регламентного обслуживания хранилища данных на Greenplum.
- Постоянно улучшаю процесс разработки в команде: ввел журнал архитектурных решений (ADR) и правила хранения контекста для разработчиков и ИИ-агентов (контекст ведется и проходит ревью наравне с кодом), убираю регламенты, потерявшие актуальность.
- Провожу доклады для команды и пополняю внутреннюю базу знаний: учебный курс по dbt, материалы по проектированию систем от требований до архитектуры, инструкции для пользователей платформы.

Стек: Python, FastAPI, asyncio, PostgreSQL, Greenplum 6, Apache Airflow, Apache Kafka, Hadoop (HDFS, YARN), Apache Spark, dbt, Flyway, Ansible, Docker, GitLab CI, Linux.
---

---
Big data platform - the corporate data warehouse of the Russian Railways (RZD) holding, built on Data Mesh principles, with more than a hundred domains. The platform is based on Greenplum, Kafka, Hadoop and Airflow. On top of them I develop the management layer in Python and SQL that turns them into a self-service platform: domain teams get ready-made storage, interfaces to create and manage data pipelines, and access control. The layer includes a metadata API, DAG generation for Airflow, and services for data products, access rights and infrastructure jobs. I take tasks from requirements and specifications to acceptance. Senior developer since December 2024: I distribute backend tasks, do code reviews, and mentored a junior developer.

Results:
- Completed many tasks across all platform components: from investigating production incidents and fixing bugs to developing new features.
- Designed the migration of platform data and metadata to the customer's new infrastructure. The migration succeeded on the first attempt with minimal downtime: data ingestion and consumer access to data marts were not interrupted.
- Developed a role model for several project teams working together in one domain, from requirements to acceptance, across all platform components.
- Developed backup and maintenance concepts for the Greenplum data warehouse.
- Continuously improve the team's development process: introduced an architecture decision record (ADR) log and rules for keeping context for developers and AI agents (context is maintained and reviewed on par with code), remove outdated procedures.
- Give talks to the team and contribute to the internal knowledge base: a dbt training course, materials on system design from requirements to architecture, user guides for the platform.

Stack: Python, FastAPI, asyncio, PostgreSQL, Greenplum 6, Apache Airflow, Apache Kafka, Hadoop (HDFS, YARN), Apache Spark, dbt, Flyway, Ansible, Docker, GitLab CI, Linux.
---

### Techboss, декабрь 2020 - февраль 2023

Должность: Python-разработчик / Python Developer. Полная занятость.

---
Внутренние системы для сети ресторанов и собственного производства: рабочие места кассиров, поваров и сотрудников производства, административная панель.

- Бэкенд на Python (Flask, aiohttp), SQLAlchemy, MySQL, MongoDB, Redis, Nginx.
- Интеграции с оборудованием: фискальные регистраторы, платежные терминалы, весы, принтеры, система маячков в зале.
- Интеграции с внешними сервисами: Тинькофф, Yandex Go, Smartomato, ЕГАИС, АТОЛ Онлайн.
---

---
Internal systems for a restaurant chain and its own food production: workstations for cashiers, cooks and production staff, an admin panel.

- Backend in Python (Flask, aiohttp), SQLAlchemy, MySQL, MongoDB, Redis, Nginx.
- Hardware integrations: fiscal registers, payment terminals, scales, printers, an in-hall beacon system.
- Integrations with external services: Tinkoff, Yandex Go, Smartomato, EGAIS, ATOL Online.
---

## Образование

- Санкт-Петербургский государственный аграрный университет / Saint Petersburg State Agrarian University,
  2011 - 2016, бакалавр / Bachelor's degree (запись Павла от 2020 года), "Эксплуатация транспортно-технологических
  машин и комплексов" / Operation of Transport and Technological Machines and Complexes.
- Яндекс Практикум / Yandex Practicum, ноябрь 2025 - июнь 2026, "Backend-разработка на Python (программа
  для разработчиков с опытом)" / Backend Development in Python (program for experienced developers).
- Яндекс.Практикум (АНО ДПО "ШАД") / Yandex Practicum, февраль 2020 - ноябрь 2020, "Python-разработчик" /
  Python Developer. Старое описание (список навыков джуниора) удалено. В шапке профиля показан университет.

## Навыки

30 навыков с hh (A-senior-python.md). Где в справочнике LinkedIn есть свое название, взято оно:
Code Review - "Анализ кода", DWH - "Архитектура хранилища данных", dbt - "DBT", Микросервисная
архитектура - "Микросервисы", Разработка технических заданий - "Техническое задание (ТЗ)",
Разработка нефункциональных требований - "Нефункциональные требования", Постановка задач
разработчикам - "Постановка задач". Остальные - как на hh. Навыки привязаны к местам работы и учебе:
платформенные - к ЦС; SQLAlchemy и Redis - к Techboss и Практикуму 2026; RabbitMQ - к Практикуму 2026.

Старые навыки 2020 года (django и django rest framework с одним подтверждением, "Алгоритмы",
"Структуры данных", Nginx, CI) и Промгидро в опыте удалены 26.10.2026 с подтверждения Павла.
В профиле 30 навыков, как на hh.
