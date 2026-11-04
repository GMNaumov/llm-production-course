# Практический комплект курса

[Все материалы](../README.md) · [Программа](../../curriculum.md) · [Подготовка преподавателя](INSTRUCTOR.md) · [Фактические проверки](VALIDATION.md)

40 работ в `modules/*/practice/` выполняются последовательно в пределах **112 академических часов**, по 45 минут. У каждой есть самостоятельный маршрут, негативные случаи, критерии и отдельный файл `solutions/` для сверки после своей попытки. Контактные часы и 38 часов теории не увеличены. Самостоятельный режим означает достаточные инструкции и эталоны; независимые review, разметка и финальная приёмка требуют коллеги/преподавателя.

Общий кейс — вымышленный завод A: инженер ищет действующий регламент, читает спецификацию, проверяет заказ и готовит учебное изменение. Завод B нужен для проверки ACL. Идентификаторы, документы, числа и canary полностью синтетические. Здесь нет производственных адресов/секретов, неизвестные API/IdP/.NET-версии предприятия не заменены догадками.

## Что подготовлено

| Компонент | Назначение | Где находится |
|---|---|---|
| Корпус и открытые вопросы | Lexical/dense/hybrid/rerank, цитаты, ACL | `data/`, `scripts/rag.py` |
| Генератор PDF/PNG | Кириллица, таблица на двух страницах, дефекты | `scripts/documents.py` |
| OCR и JSON/HITL | Настоящий Tesseract, provenance, schema | `scripts/documents.py`, `scripts/contracts.py` |
| .NET API/клиент | Штатные и ошибочные HTTP-исходы | `dotnet/Api`, `dotnet/Client` |
| PostgreSQL | Узкий semantic layer, AST и read-only role | `sql/init.sql`, `scripts/sql_client.py` |
| Tools и эффекты | Schema, auth, timeout, preview/confirm/replay | `scripts/tool_dispatch.py`, `scripts/tools.py` |
| C# baseline/патч | Компиляция, контракт и review | `dotnet/Quantity`, `dotnet/reference` |
| GPU-профиль | LLM, embeddings, reranker, маленькая VLM | `scripts/model_server.py`, `scripts/vlm.py` |
| Обучение | Настоящий NF4/LoRA и cross-encoder training | `scripts/train_qlora.py`, `scripts/train_reranker.py` |
| Эксплуатация | Gateway, load, audit, manifest, restore | `scripts/gateway.py`, `load.py`, `release.py`, `lifecycle.py` |

Эталон маленький и читаемый: точный numpy-поиск вместо обязательного ANN, SQLite для локального атомарного эффекта, закрытые SQL-шаблоны вместо произвольного SQL, один процесс gateway. Это позволяет изучить границы. Масштабирование, корпоративная идентичность, совместимость legacy и распределённые транзакции требуют отдельной проверки.

## Как проходить работу

1. Прочитайте соответствующий `self-study.md` и задание. Проверьте prerequisites.
2. Зафиксируйте [протокол](templates/protocol.md), baseline, данные и ожидаемые негативные исходы до запуска.
3. Работайте в `work/<ID>/` или отдельной учебной копии/ветке. Исходный эталон сохраните.
4. Соберите построчные результаты, включая ошибки. Затем откройте решение в `solutions/` и объясните расхождения.
5. Заполните [отчёт](templates/report.md) и [ручной review](templates/review.md). Сдаваемый код не загружается в автоматический grader: его здесь нет.

Скрипты метрик/инженерные проверки эталона не выставляют оценку и не заменяют review. Для точного ответа используйте расчёт/схему/тест, для смысла источника/критичного поля — эксперта. LLM-судья необязателен и применяется только после калибровки по модулю 3.

Открытые `*-dev.json`, генератор данных и решения — **отладочные/регрессионные**, не независимый test. Перед итоговой оценкой хранитель готовит новые разрешённые группы, фиксирует manifest и не раскрывает ответы разработчику. Если проходите один, выполните открытый эксперимент и явно оставьте независимую проверку ожидающей; собственная сверка не создаёт независимость.

## Среда и ресурсы

Базовая учебная среда: Windows 11, PowerShell, WSL2, Docker Desktop Linux/WSL2, RTX 3060 12 ГБ. Сначала проверьте `docker context show`: команды должны обращаться к одному движку. GPU требует поддерживаемого Windows-драйвера; Linux GPU-драйвер внутри WSL не устанавливают по обычной Linux-инструкции. См. [Docker GPU](https://docs.docker.com/desktop/features/gpu/) и [NVIDIA WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

Организатор выделяет дисковое место: GPU-образ и CUDA-зависимости занимают много гигабайт, веса нескольких моделей — дополнительные гигабайты; закладывайте не менее 30 ГБ свободного места для этого небольшого комплекта и измерьте реальный размер перед тиражированием. Docker RAM/CPU должны позволять одновременно CPU-сервисы; конкретный лимит подбирают preflight. Не запускайте обучение, VLM и LLM одновременно на 12 ГБ.

Проверки автора выполнены на другой GPU, RTX 5060 Ti 16 ГБ; [протокол](VALIDATION.md) не удостоверяет вместимость на RTX 3060. Выбор меньшей учебной модели сохраняет методику QLoRA, но не доказывает возможность обучения 7–8B.

Все команды далее — **PowerShell из `materials/practice-kit`**. В bash синтаксис `${PWD}` и переменных окружения адаптируется. Docker используется локально; промышленные данные остаются on-prem.

## Подготовка образов с сетью — до занятия

Организатор выполняет это один раз в разрешённой среде, проверяет licenses/образы, сохраняет их в согласованный registry/офлайн-комплект. На занятии участник использует готовые артефакты. Теги исходных образов могут изменяться: фактические digest/ID и полный `pip freeze` входят в выпуск; перед следующим потоком нужен повторный preflight.

```powershell
docker build -t course-cpu:2026-11 .
docker build -f Dockerfile.gpu -t course-gpu:2026-11 .
docker compose --profile integration build api
docker pull postgres:16.6-bookworm
docker pull mcr.microsoft.com/dotnet/sdk:8.0
docker pull ghcr.io/open-webui/open-webui:v0.6.18
```

Основные Python-зависимости закреплены в `requirements*.txt`. Полные транзитивные версии фактически собранного окружения сохраняются в `environment-*.txt`; для строгого повторения используйте экспортированный образ с проверенным ID, а не повторную установку с плавающими транзитивными пакетами. Выбор этих версий — учебный снимок, не закрепление стека предприятия.

### Подготовка моделей

```powershell
docker run --rm --mount "type=bind,source=${PWD},target=/kit" course-gpu:2026-11 python scripts/download_models.py chat-small chat-alt embedding reranker vlm
```

Команда передаёт публичному репозиторию только запросы публичных файлов. Она разрешает ветку в immutable commit и сохраняет repo/revision и SHA-256 каждого файла в `models/<alias>/course-source.json`. Уже подготовленный снимок не обновляется молча. Проверяйте эти manifest и model cards до повторного использования; remote code выключен. Веса/кэши не включены в Git.

| Alias | Учебный кандидат | Назначение/ограничение |
|---|---|---|
| chat-small | [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) | Небольшой inference/QLoRA; качество нужно измерить |
| chat-alt | [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct) | Вторая локальная модель для сравнения |
| embedding | [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) | Query/passage prefixes и нормированное mean pooling |
| reranker | [mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1) | Сильный готовый cross-encoder для учебного сравнения |
| vlm | [SmolVLM-256M-Instruct](https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct) | Механика изображений/кропов; английская tiny VLM, не рекомендация для чертежей предприятия |

Не называйте эти модели промышленно выбранными. Проверяйте отдельно лицензию/русский язык/полезный контекст/квантование/VRAM по программе. Права на использование/распространение весов и данных согласуются предприятием.

## Первый CPU-запуск

```powershell
docker compose config --quiet
docker compose run --rm secrets-init
docker compose run --rm lab python scripts/demo.py all
docker compose run --rm lab python scripts/documents.py generate
docker compose run --rm lab python scripts/documents.py ocr
```

`work/` создаётся автоматически и исключён из Git. Генератор создаёт 40 изображений, четыре двухстраничных текстовых PDF, скан-PDF и broken.pdf. OCR действительно вызывает Tesseract rus+eng; метрики текста в `ocr-results.json`/`ocr-summary.json`. Оценка структуры/таблиц выполняется отдельно по П5.1; TSV сам по себе таблицу не восстанавливает.

Полный малый эталон `docker compose run --rm lab python scripts/document_pipeline.py` преобразует OCR в статус/позиции с provenance и очередь `review-queue.json`. Парсер ограничен сгенерированным шаблоном, не использует эталон для подстановки пропусков и по умолчанию отправляет все критичные результаты на review. Это честный строгий baseline; автоматический приём требует проверки source и калибровки на dev. Для явного человеческого шага изменения есть `docker compose run --rm -it lab python scripts/workflow.py`: показываются последствия, по умолчанию отказ, модель этот CLI не вызывает.

`demo.py all` исполняет baseline, метрики, lexical retrieval, поля, транзакционный replay, gates и экономику. Его числа не являются порогами компании. `demo.py effects` использует отдельную временную синтетическую SQLite, не изменяет учебные результаты других запусков.

### Секреты и изоляция

`secrets-init` создаёт **новые случайные учебные** значения в named volume `llm-course_course-secrets`; существующие значения не ротирует. Файлы gateway имеют 0400 root, .NET — 0440 root:GID1654, PostgreSQL — 0440 root:GID999. Проверьте UID/GID закреплённых образов при их замене. Секреты не печатаются, не попадают в слои образа/репозиторий/bundle. Сам Docker administrator имеет доступ к volume — это граница доверия учебного ПК.

Локальный файловый provider и volume **не заменяют** корпоративное secret storage с выдачей, expiry, отзывом, ротацией и аудитом. Это отдельная часть П6.1, зависящая от ИБ. `init_secrets.py` создаёт только локальные 0600-файлы для отдельного облачного упражнения; Compose их не использует. На Windows ограничьте ACL такого каталога по правилам компании.

Порты gateway/UI привязаны к 127.0.0.1. PostgreSQL/.NET/inference не публикуются на хост. Сеть `training` — internal. Inference endpoint внутри неё учебный, без enterprise-auth; к сети не подключают недоверенные контейнеры. Для enterprise каждый сервис/инструмент должен сам обеспечивать согласованную авторизацию.

## Локальный LLM и RAG

```powershell
.\scripts\preflight.ps1
docker compose --profile gpu up -d inference gateway
docker compose --profile gpu up -d --wait --wait-timeout 45 inference
docker compose run --rm lab python scripts/benchmark.py --prompt v1 --tag base-v1
docker compose run --rm lab python scripts/benchmark.py --prompt v2 --tag base-v2
docker compose run --rm lab python scripts/rag.py --mode lexical
docker compose run --rm lab python scripts/rag.py --mode dense --answers
docker compose run --rm lab python scripts/rag.py --mode hybrid
docker compose run --rm lab python scripts/rag.py --mode rerank
```

Если readiness не успела за 45 секунд, проверьте `docker compose logs --tail 40 inference` и повторите ожидание; не увеличивайте бесконечно timeout при явной ошибке. Server `/ready` подтверждает загрузку chat; embeddings/reranker ленивые, их проверяют соответствующими запросами.

Учебный server реализует `/v1/models`, `/v1/chat/completions`, `/v1/embeddings` и `/rerank`. Чат: только roles/content, temperature, max_tokens; **нет streaming, tools API и constrained JSON**. Бюджет чата 2048 токенов вместе с выходом; embeddings/reranker — 512. Превышение отклоняется, не усекается скрыто. Использование generic OpenAI-клиента требует отключить неподдерживаемые поля.

Для второй модели задайте `MODEL_PATH: /models/chat-alt` в своей Compose-копии и пересоздайте inference; сохраните разные tags отчётов. Для FP16/NF4 одной модели:

```powershell
$env:QUANTIZE='1'
docker compose --profile gpu up -d --force-recreate inference
docker compose run --rm lab python scripts/benchmark.py --prompt v2 --tag base-nf4
$env:QUANTIZE='0'
```

### Open WebUI

На новом локальном UI первый созданный аккаунт становится администратором. Если список моделей у дополнительного пользователя пуст, администратор должен предоставить ему согласованный доступ к модели; это не повод отключать authentication или model access control. В учебной конфигурации явно задан единственный model ID `training`, случайная arena-маршрутизация выключена. Изменённые переменные окружения могут не перекрывать ранее сохранённую UI-конфигурацию: проверьте provider/model list в административных настройках.

```powershell
docker compose --profile ui up -d webui
```

Откройте localhost:3000, создайте локальную учётную запись на выделенном учебном стенде и проверьте provider `http://inference:8000/v1`. Нужен заранее загруженный UI-образ. Отключите streaming в параметрах чата: сервер его не реализует. UI проверяется функциональным запросом, а количественное сравнение идёт через benchmark. История хранится в `webui-data`; задайте retention/удаление по политике. Если версия UI требует более полный API, используйте утверждённый inference-provider и повторите preflight, не заявляйте непроверенную совместимость.

## .NET API, PostgreSQL, tools и C#

```powershell
docker compose run --rm secrets-init
docker compose --profile integration up -d --wait --wait-timeout 45 db api
docker compose run --rm lab python scripts/sql_client.py
docker compose run --rm lab python scripts/tool_dispatch.py
docker compose run --rm lab python scripts/demo.py effects
docker compose run --rm lab python scripts/lifecycle.py
```

`db` использует отдельный volume `pg-data-v2`; `init.sql` выполняется только при первом создании. Не удаляйте чужие volumes и не меняйте пароли существующих БД для «починки» упражнения. Для независимого запуска используйте другой project name/context и соответствующую сеть/volume. У API есть `/live`; readiness БД проверяется healthcheck.

Учебный SQL guard сравнивает полный AST с серверным шаблоном. Это закрытый semantic layer: модель предлагает operation/аргумент, а не произвольный SQL. Роль читает только view A. Пустой shortage для NULL означает «данных недостаточно», не ноль. Для общего Text-to-SQL требуется отдельный рекурсивный guard/проверка рисков.

Сборка baseline/эталона и клиент против локального API в одноразовом SDK-контейнере:

```powershell
docker run --rm --network llm-course_training --mount "type=bind,source=${PWD}/dotnet,target=/source,readonly" --mount "type=bind,source=${PWD}/scripts/run-dotnet.sh,target=/run-dotnet.sh,readonly" --mount "type=volume,source=llm-course_course-secrets,target=/run/secrets,readonly" -e RUN_API_CLIENT=1 mcr.microsoft.com/dotnet/sdk:8.0 sh /run-dotnet.sh
```

Исходники ro, временная копия и obj/bin внутри одноразового контейнера; NuGet.Config не содержит внешних feeds. Для П7 работайте со своей копией `Quantity`; `reference` открывайте после попытки. Семь проверок reference — инженерная проверка эталона, не grader сдаваемых решений. Legacy/API предприятия этими примерами не проверены.

Запуск `run-dotnet.sh` также выполняет 11 проверок `ClientChecks` через подставной HTTP-handler: ответы API, ограничение тела при неизвестной длине, конечное число повторов, таймаут и отмена во время задержки. Реальный API-клиент использует ту же реализацию `OrdersClient`.

## VLM и обучение

Сначала остановите inference, чтобы не держать несколько моделей на учебной GPU:

```powershell
docker compose stop inference
docker run --rm --gpus all --network none --mount "type=bind,source=${PWD},target=/kit" --mount "type=bind,source=${PWD}/models,target=/models,readonly" course-gpu:2026-11 python scripts/vlm.py
docker compose run --rm lab python scripts/prepare_training.py
docker run --rm --gpus all --network none --mount "type=bind,source=${PWD},target=/kit" --mount "type=bind,source=${PWD}/models,target=/models,readonly" course-gpu:2026-11 python scripts/train_qlora.py --steps 8
```

8 шагов — smoke механики, не полноценное исследование качества. В П8.2 заранее задайте план, memory boundary и согласованные steps (по умолчанию 40); настройка по dev. Train — 18 сильно зависимых синтетических строк, dev — 6; объём не заявляется достаточным. Loss — только assistant + конец template, без скрытого truncation. Реализация следует [PEFT k-bit training](https://huggingface.co/docs/peft/developer_guides/quantization); ручной цикл делает маску/накопление обозримыми. Нет обязательной зависимости от TRL.

Serving того же адаптера:

```powershell
$env:QUANTIZE='1'
$env:ADAPTER_PATH='/kit/work/adapter'
docker compose --profile gpu up -d --force-recreate inference
docker compose run --rm lab python scripts/benchmark.py --prompt v2 --tag adapter-nf4
docker compose run --rm lab python scripts/benchmark.py --prompt v2 --rag-context --tag adapter-rag-nf4
```

Для base+RAG на **той же статусной задаче** очистите ADAPTER_PATH, оставьте precision/модель/набор, используйте `--rag-context`. Retrieval берёт только разрешённый корпус правил, не expected test labels. Не сравнивайте статусную классификацию с другой QA-задачей как эффект обучения.

```powershell
docker compose stop inference
docker run --rm --gpus all --network none --mount "type=bind,source=${PWD},target=/kit" --mount "type=bind,source=${PWD}/models,target=/models,readonly" course-gpu:2026-11 python scripts/train_reranker.py --steps 12
```

Четыре пары hard negatives — механика cross-encoder. Для П8.3 нужны собственные разрешённые train/dev, диагностика ошибки, независимая проверка negatives и финальная оценка. Для serving укажите RERANKER_PATH=/kit/work/reranker-adapted в своей Compose-копии; веса сохраняются в work и доступны inference. См. [официальное руководство cross-encoder](https://sbert.net/docs/cross_encoder/training_overview.html).

После упражнений очистите `$env:ADAPTER_PATH=''`, `$env:QUANTIZE='0'` и пересоздайте inference для base-режима. Флаг окружения применяется при создании контейнера, а не меняет уже работающий процесс.

Для своего train reranker передайте `--pairs /kit/work/<каталог-прогона>/pairs-train.json`: JSON-массив троек `["запрос", "документ", 1.0]` или `["запрос", "документ", 0.0]`. Скрипт сохраняет hash файла, базовый model manifest и параметры в `run.json`. Data card, групповой split и независимая проверка разметки остаются обязательными.

## Облачное сравнение П1.1

Это единственный путь с внешним API; выполняется участником только в согласованной песочнице на разрешённой синтетике. Автоматического fallback в облако нет. Ключ получает участник через разрешённый provider; значение не пишут в команду/репозиторий. Адрес, модель и тариф не выдумываются — их сообщает организатор.

Используйте отдельный подготовленный контейнер с разрешённым egress, а не internal-сеть Compose. Передайте `--base <approved-base>/v1 --model <approved-id> --token-file /run/secrets/cloud-token.txt --dataset /kit/data/status-dev.json --tag cloud`. Смонтируйте только учебный комплект и отдельно ro-файл ключа. Заполнители заменяются реальными разрешёнными значениями; без допуска облачная часть остаётся невыполненной, а не имитируется.

Benchmark поддерживает chat-completions subset. Если API имеет другой контракт, адаптируйте transport, сохранив методику и все исходы. Зафиксируйте фактический биллинг/тариф/токены и общий бюджет $50–100 на участника. Внутренние документы, код, тестовые секреты и базы в облако не отправляются.

## Нагрузка и отказы

```powershell
docker compose up -d gateway
docker compose run --rm lab python scripts/load.py --clients 1 --requests 20 --route search
docker compose run --rm lab python scripts/load.py --clients 4 --requests 20 --route rag
docker stats --no-stream
docker compose exec inference nvidia-smi
```

`load.py` читает токен из volume, сохраняет только ID/статусы/время в отчёт. Модель нагрузки закрытая, разные счётчики успешных/всех ответов. Quota gateway в памяти, на срок жизни процесса; перед исследованием новых лимитов используйте отдельную тестовую конфигурацию. Search throughput не выдаётся за LLM throughput.

Остановите по одной зависимости и вызовите соответствующий путь: inference→rag, db→sql_client, api→.NET Client. У gateway есть /live и /ready; при отсутствии модели search работает, rag явно degraded_search. Восстановите сервис и повторите штатный запрос. Audit в `work/audit.jsonl` содержит метаданные, без prompt/body/secret.

## Офлайн-выпуск и восстановление

```powershell
docker compose run --rm lab python scripts/release.py --id training-r1
New-Item -ItemType Directory -Force bundle | Out-Null
docker image inspect course-cpu:2026-11 course-gpu:2026-11 course-dotnet:2026-11 --format '{{.RepoTags}} {{.Id}} {{.RepoDigests}}' | Set-Content -Encoding UTF8 bundle/release-images.txt
docker save -o bundle/course-images.tar course-cpu:2026-11 course-gpu:2026-11 course-dotnet:2026-11 postgres:16.6-bookworm mcr.microsoft.com/dotnet/sdk:8.0 ghcr.io/open-webui/open-webui:v0.6.18
```

Дополните candidate manifest реальными image IDs, model snapshots/checksums, adapter/tokenizer/template при использовании, prompt/schema/policy/config, data/index snapshot и вручную одобренным evaluation report. `release.py` не одобряет выпуск и не генерирует фиктивный commit/evaluation.

Передайте исходники, `models/` со снимками, необходимые `work/adapter`/index snapshots и manifest отдельно от images.tar; **не копируйте `secrets/`, секретный volume, историю UI и все work-логи автоматически**. Список разрешённых файлов задаётся manifest. На чистой машине выполните `docker load -i ...`, сверьте checksums, provision новых секретов и `docker compose --profile gpu up -d --pull never --no-build inference gateway`. Изолированная сеть и HF offline дополняются наблюдением egress по правилам предприятия.

Rollback возвращает цельный совместимый комплект, но не старые права и не повторяет уже совершённые эффекты. Restore накладывает **актуальный** ledger отзывов/удалений; пример — `lifecycle.py`. RTO/RPO подтверждаются измеренным восстановлением. Для другого project name замените имена сети/volume в .NET-команде.

## Типовые затруднения

После изменений эталона автор материалов проверяет регрессии и примеры конспектов без сети и GPU. Для этого нужна полная копия репозитория, а временные результаты размещаются в tmpfs:

```powershell
docker run --rm --network none --mount "type=bind,source=${PWD}/../..,target=/repo,readonly" --tmpfs /repo/materials/practice-kit/work course-cpu:2026-11 python /repo/materials/practice-kit/validation/review_checks.py
docker run --rm --network none --mount "type=bind,source=${PWD}/../..,target=/repo,readonly" course-cpu:2026-11 python /repo/materials/practice-kit/validation/check_materials.py /repo
```

Вторая команда проверяет структуру, локальные ссылки, часы и синтаксис Python-блоков. Полная интеграционная проверка `validation/author_checks.py` дополнительно требует db/api/gateway/inference. Ни один из этих скриптов не проверяет сдаваемые работы.

На Windows `powershell -NoProfile -ExecutionPolicy Bypass -File validation/preflight_checks.ps1` проверяет три диагностических исхода с подставными командами, без обращения к Docker и WSL. Она перезаписывает `work/preflight.txt` синтетическим журналом; для реального протокола после неё запустите `scripts/preflight.ps1`.

| Симптом | Проверить | Действие |
|---|---|---|
| Docker permission/context | Доступ к Desktop и context | Запуск в разрешённой сессии, согласованный context |
| CUDA недоступна | Host→WSL→container→tensor | Локализовать слой по preflight |
| Нет модели offline | Snapshot/config/tokenizer, mount /models | Доукомплектовать до занятия |
| OOM | Длина, другие процессы, batch, reserved/total VRAM | Согласованная меньшая конфигурация/резерв |
| SQL connection refused | db healthcheck | Дождаться readiness, не менять пароль |
| SQL auth failure | Новый ли volume, secrets-init и UID/GID | Проверить комплект/инициализацию; не печатать пароль |
| Gateway 401 | Provision volume, правильный client | load.py использует токен без вывода |
| 429 | Rate/quota/concurrency | Классифицировать; не считать это inference speed |
| JSON неверен | Сырой синтетический ответ, schema, token budget | Контролируемая ошибка/review, не бесконечный retry |

При остановке: `docker compose stop`. Команды удаления volumes здесь намеренно не требуются: для нового независимого опыта создаётся новый project/context. Учебный прототип и комплект не удостоверяют production-ready.
