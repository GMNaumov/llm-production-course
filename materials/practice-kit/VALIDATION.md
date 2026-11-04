# Протокол авторской проверки — 4 ноября 2026 года

[Инструкция запуска](README.md) · [Подготовка преподавателя](INSTRUCTOR.md)

Это проверка исполнимости **эталонного комплекта**, а не оценивание работ участников, промышленная приёмка или независимое исследование качества. Все предметные входы синтетические. Структура/часы/критерии `curriculum.md` сохранены: 40 работ, 112 практических часов, общий курс 150 = 38 + 112.

## Среда

Docker Desktop 4.96.3, Engine/CLI 29.9.2, Compose 5.6.1, Linux containers через `desktop-linux`. GPU **RTX 5060 Ti, 16311 MiB**, driver 620.67.01 (Windows KMD 621.01). Это отличается от учебной RTX 3060 12 ГБ; результаты не удостоверяют её вместимость/скорость. GPU passthrough подтверждён из контейнера, затем исполнены реальные CUDA-инференс и backward.

Полные Python-версии: [CPU](environment-cpu.txt), [GPU](environment-gpu.txt). Основной стек: Python 3.12, Torch 2.8.0+cu128, Transformers 4.57.1, PEFT 0.17.1, bitsandbytes 0.48.1, Pydantic 2.12.5. .NET SDK фактического контейнера — 8.0.427. Установка из исходных requirements без транзитивного lock может измениться; точное окружение сохраняется экспортом проверенных образов.

## Что реально исполнено

| Область | Выполнено | Наблюдение/граница вывода |
|---|---|---|
| CPU | demo all, метрики, экономика, fields/gates | Recall/RR/nDCG сверены; пустое измерение неизвестно; критичное нарушение блокирует |
| OCR | Tesseract rus+eng, 40 PNG | Повороты/обрезка/печати дают разные ошибки; это не набор реальной рукописи |
| PDF | Текстовый и scan PDF | У A-text извлечено 142 символа, у scan — 0 |
| Документы | OCR→JSON/provenance/review | 40 страниц отправлены на review; автоприём не заявлен |
| SQL | Настоящий PostgreSQL 16.6 + reader_a | Дефицит A=6, surplus=0, NULL→нет достоверного значения; B не участвует |
| .NET | API, клиент, baseline/reference build | 0 warnings/errors; 7 поведенческих проверок эталона |
| API-отказы | 401/403/404/503/timeout | Нет бесконечных retries; клиент различает исходы |
| Tools | Strict schema, auth, partial failures | ok/forbidden/dependency_error/invalid_arguments; максимум 2 попытки |
| Write/replay | SQLite preview/confirm/new connection/concurrent replay | Без согласия нет эффекта; повтор сохраняет version=2 |
| RAG | Реальные E5 и pretrained cross-encoder | На пяти ответных открытых dev-вопросах Recall@3/MRR/nDCG=1; lexical тоже 1 |
| LLM | Qwen2.5-0.5B FP16 и NF4, v1/v2 | Реальные ошибки JSON/смысла сохранены, это не гарантированный baseline качества |
| VLM | SmolVLM: overview/original/crop | Ошибки критичных знаков/связей; результат требует человека |
| QLoRA | 8 smoke и 40 шагов NF4/LoRA | Реальные backward/optimizer/save; затем PEFT adapter загружен в serving |
| Reranker | 4 smoke и 12 шагов BCE training | Веса/tokenizer/run сохранены; 4 открытые пары не доказывают перенос |
| Gateway/load | Auth, schema, audit, 1/2/4 клиента | Есть контролируемые 429; HTTP throughput отделён от сгенерированных ответов |
| Отказ модели | Реально остановленный inference | RAG явно degraded_search; поиска достаточно для деградации, не фиктивного ответа |
| Lifecycle | Backup/delete/revoke/restore | Release/shortage не возвращаются после актуального ledger |
| Чистая БД/API | Новый project `llm-course-clean`, новые volumes/сеть | Provision и init с нуля, те же SQL-результаты; прежнее состояние не удалялось |
| Open WebUI | Отдельный validation-volume, config/models/non-stream chat | Настоящий запрос через UI backend в локальную модель; аутентификация включена |

65 авторских инженерных проверок находятся в [author_checks.py](validation/author_checks.py): метрики/gates, NaN/Infinity, source/schema, ACL, replay/stale/expiry/concurrency, SQL AST/права/семантика, настоящий API/gateway и audit allowlist без токенов. Это не grader: он не ищет и не оценивает решения участников. Результат авторского запуска — все 65 пройдены.

## Измеренные иллюстративные результаты

Macro-CER по восьми страницам каждого вида: clean **0,0192**, blur **0,0546**, cropped **0,3093**, rotated **1,1803**, stamp-notes **0,1641**. P95 OCR одного данного прогона ≈ **798 мс**. CER выше 1 допустим при вставках. Значения не включают автоматическую оценку структуры/таблиц и не являются обещанием скорости.

Открытая статусная задача, шесть случаев, по одной попытке; P95 при таком N нестабилен, первый запрос включает прогрев:

| Вариант | Верный смысл | Валидная схема |
|---|---|---|
| 0.5B FP16, v1 | 1/6 | 2/6 |
| 0.5B FP16, v2 | 2/6 | 5/6 |
| 0.5B NF4, v2 | 1/6 | 1/6 |
| 0.5B NF4 + RAG, v2 | 1/6 | 1/6 |
| 0.5B NF4 + adapter, v2 | 5/6 | 6/6 |
| 0.5B NF4 + adapter + RAG, v2 | 4/6 | 6/6 |
| 1.5B FP16, v2 | 2/6 | 2/6 |

Это демонстрация pipeline и ошибок, **не независимое преимущество fine-tuning**: примеры публичны и близки обучающей постановке. Во вход RAG передаются только корпусные правила, не expected labels. В serving-ответах зафиксированы quantized/adapter/base revision, чтобы имя файла отчёта не подменяло реальную конфигурацию.

QLoRA 40 шагов: пик PyTorch allocated **886834688 байт** (≈0,826 GiB); dev_loss ≈0,000495. Это маленькая 0,5B и короткие данные; вся занятая VRAM больше allocated, reserved/прочие процессы учитываются отдельно. Низкая dev_loss не доказывает перенос, нет проверки 7–8B на RTX 3060. JSON run сохраняет все гиперпараметры, маску, template, версии/seed/данные и время.

VLM на crop исходной подписи «Поз. 7: 5±0,02 мм» выдала «7:5+0,02 MM»: неверный знак допуска. Overview выдал другие числа/связи; original не восстановил все поля. Исполнимость модели подтверждена, инженерная достоверность не подтверждена — маршрут только review. Первый VLM-запрос занял ≈18,3 с, последующие ≈0,6–0,7 с; это иллюстрирует необходимость прогрева.

Нагрузка RAG с 4 клиентами/12 запросами на одном прогоне: 2 draft_for_review и 10 HTTP-ошибок перегрузки, P95 всех ≈10,9 с. Все исходы сохранены; быстрые 429 не считаются полезной генерацией. Короткий CPU search-прогон 20 запросов дал иной профиль и не экстраполируется на LLM.

## Проверенные снимки и артефакты

Модельные ревизии разрешены один раз при загрузке, полные checksums сохранены локально в models/alias/course-source.json:

| Alias | Commit |
|---|---|
| chat-small | `7ae557604adf67be50417f59c2c2f167def9a775` |
| chat-alt | `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` |
| embedding | `614241f622f53c4eeff9890bdc4f31cfecc418b3` |
| reranker | `1427fd652930e4ba29e8149678df786c240d8825` |
| vlm | `7e3e67edbbed1bf9888184d9df282b700a323964` |

Проверенные image IDs/digests:

- CPU: `sha256:b3869a746920c8d552bd785186a35672c6825347e0b7d237b1f7a2b22ebcaab7`.
- GPU: `sha256:49e15e6032c9b1a4680949b9b9971c40952a9506f00a52c64b079419f67ebeac`.
- .NET API: `sha256:9c9945c5aaadf8ec837492b627c2785179e8d7c4b3712274c074470c0f02b56b`.
- PostgreSQL: `sha256:557fea37a744d5f4c8faab304b0a90858b53ab119735a88c131fd19dab802f36`.
- .NET SDK: `sha256:6ba9644da07bb5b560a402acec9ca38711a0762969f1b61da261df5c9f6f85da`.
- Open WebUI: `sha256:ff87dd7605720f33411d87ed5550357b665cec4880378176f2f95bfe751f5e32`.

Исходники Python подключались в контейнеры из репозитория, поэтому image ID без code manifest не фиксирует весь выпуск. Скрипты release связывают код/config/data, а полный bundle дополняется model/adapter/image/evaluation/rights. Веса, адаптеры, бинарные входы и raw work-результаты исключены из Git; воспроизводятся командами README. Секреты не приложены.

## Что остаётся проверкой организатора/предприятия

- Эталонный ПК RTX 3060 12 ГБ, real useful context и разрешённые модели/образы.
- Реальные .NET/API/IdP/secret lifecycle, legacy/CI, схема/права БД и распределённые эффекты.
- Реальные русские сканы/рукопись/чертежи, table/layout evaluation и предметные критичные поля.
- Облачная песочница с реальным API/ключом/биллингом: автор её не вызывал и не подставлял фиктивный результат.
- Финальный закрытый test, другой независимый reviewer/команда, actual baseline процесса/экономика и production-нагрузка.
- Полный export/load всех тяжёлых образов/моделей на другой ПК и наблюдение egress по политике ИБ. Закрытая Docker-сеть и offline flags проверены конфигурационно; сетевой аудит предприятия не имитировался.

Независимый человеческий запуск/оценка и корпоративные допуски не заявляются выполненными авторским локальным прогоном. Учебный комплект не является production-ready.

## Итоговые структурные проверки

Проверены 40 заданий и 40 решений, 112 часов, совпадение критериев программы, UTF-8, парность ограждений кода и локальные ссылки: ошибок нет. Python-файлы прошли синтаксический разбор. git diff --check прошёл. Полный набор 65 инженерных проверок требует db/api/gateway/inference и включает запреты неизвестной модели, streaming=true и превышения контекста. Машиночитаемые итоги — [results.json](validation/results.json), модельные контрольные суммы — [model-sources.json](validation/model-sources.json).

Open WebUI повторно прошёл вход, список только training и non-stream chat с включённой аутентификацией. Дополнительным пользователям администратор выдаёт согласованный доступ; пустой список не исправляется отключением защиты.

## Повторная проверка после ревью — 4 ноября 2026 года

Этот раздел относится к изменениям [ревью курса](../REVIEW.md). Измерения выше и `validation/results.json` сохранены как исторический протокол; текущие итоги записаны отдельно в [review-results.json](validation/review-results.json). Для проверки создан project `llm-course-review` с новыми PostgreSQL- и secret-volumes; старые volumes не удалялись. Использованы прежние CPU/GPU-образы с обновлёнными исходниками через bind mount и отдельный образ `course-dotnet-review:2026-11`.

| Проверка | Фактический результат |
|---|---|
| Интеграционные инварианты | **68/68**: SQL AST/права/семантика, API, gateway, ACL, replay и строгие типы inference |
| Регрессии ревью | **15/15** методов unittest с негативными подслучаями; сеть и GPU не требуются |
| Python в конспектах | Все 13 блоков разобраны; 12 исполнены в CPU-образе, конфигурация PEFT/Transformers — в GPU-образе |
| C# | Два блока конспектов и проекты эталона собраны без предупреждений и ошибок; 7 проверок Quantity + 11 ClientChecks |
| Настоящий HTTP-клиент | `ok`, `forbidden`, `dependency_error`, `timeout`, `not_found` против локального .NET API |
| PowerShell | 3 регрессии с подставными командами; настоящий Windows/WSL/Docker/GPU preflight успешен, журнал UTF-8 без NUL |
| OCR и JSON/HITL | Настоящий Tesseract: 40 страниц, отказов процесса нет; 40 результатов направлены на review |
| QLoRA | 2 реальных шага NF4/LoRA, backward/optimizer/save, отдельный `work/review-adapter`; затем адаптер загружен в serving |
| Reranker | 2 шага с `--pairs`, 1 шаг в сохранённом демонстрационном режиме; веса/manifest сохранены; 3 некорректных входа отклонены |
| Dense/rerank serving | Реальные E5 и дообученный cross-encoder: Recall@3/MRR/nDCG = 1 на открытом dev; это проверка механики |
| Ошибка модели | Реальная остановка inference: ошибки RAG сохранены; 2/2 запроса gateway дали `degraded_search`, генераций 0; сервис восстановлен |
| Нагрузка | 4 запроса, 4 клиента: 2 `draft_for_review`, 2 отказа перегрузки; P95 всего ≈11,54 с |
| Стиль и структура | Ruff 0.14.3: lint/format проходят; локальные ссылки, UTF-8, ограждения, 40+40, часы каждого модуля и маршруты проверены |

OCR macro-CER совпал с предыдущим прогоном; P95 текущего запуска ≈553 мс. Модель VLM на crop снова прочитала знак допуска неверно: `7:5+0,02 MM` вместо `Поз. 7: 5±0,02 мм`. Автоматическая приёмка инженерного значения не включалась.

Двухшаговый адаптер дал правильный смысл **1/6** и допустимую схему **3/6** на открытой статусной выборке. Это короткая проверка работоспособности и загрузки, не повтор прежнего 40-шагового эксперимента и не доказательство улучшения качества. Все шесть исходов сохранены. Пиковая PyTorch allocated-память QLoRA составила 886834688 байт; dev_loss ≈0,06050. Величины не описывают всю занятую VRAM и не подтверждают 7–8B на RTX 3060.

Основные команды, выполненные из `materials/practice-kit`:

```powershell
# Отдельный project; локальный override задавал image course-dotnet-review:2026-11.
docker compose -p llm-course-review -f compose.yaml -f work/review-compose.yaml run --rm secrets-init
docker compose -p llm-course-review -f compose.yaml -f work/review-compose.yaml --profile integration up -d --build --wait db api gateway
docker compose -p llm-course-review -f compose.yaml -f work/review-compose.yaml run --rm lab python validation/author_checks.py

# Регрессии и конспекты: полная копия репозитория, временный work.
docker run --rm --network none --mount "type=bind,source=${PWD}/../..,target=/repo,readonly" --tmpfs /repo/materials/practice-kit/work course-cpu:2026-11 python /repo/materials/practice-kit/validation/review_checks.py
docker run --rm --network none --mount "type=bind,source=${PWD}/../..,target=/repo,readonly" course-cpu:2026-11 python /repo/materials/practice-kit/validation/check_materials.py /repo
powershell -NoProfile -ExecutionPolicy Bypass -File validation/preflight_checks.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/preflight.ps1 -Image course-gpu:2026-11
```

Подробные команды обычных OCR/SQL/обучающих запусков находятся в README и заданиях; в ревью для обучения заданы отдельные `--out /kit/work/review-*` и меньшие smoke-бюджеты. Локальные диагностические скрипты и сырые результаты в `work/` не являются обязательными исходниками курса. Повторяемые регрессии сохранены в `validation/review_checks.py`, `validation/preflight_checks.ps1`, `validation/author_checks.py` и `dotnet/ClientChecks/`.

Проверочная GPU — RTX 5060 Ti 16 ГБ. RTX 3060 12 ГБ, корпоративные данные/аутентификация, закрытый независимый test, внешний reviewer, облачный биллинг и перенос полного офлайн-комплекта на другой физический ПК не проверены этим ревью. Совместимость Open WebUI ранее проверялась; его конфигурация в текущем ревью не менялась, повтор UI-прогона не выполнялся. Предупреждения закреплённого GPU-стека о `torch_dtype` и параметре checkpointing сохранены в локальных логах; исполняемые шаги прошли, обновление зависимостей не выполнялось.
