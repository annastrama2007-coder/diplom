# diplom — мониторинг USB/томов и ограничение копирования

Это учебный прототип для macOS, который:

- отслеживает появление томов в `/Volumes` (флешки/диски/виртуальные тома)
- логирует попытки копирования (создание файлов) на эти тома
- применяет лимиты на копирование (кол-во файлов и общий размер за минуту) **отдельно для каждого тома**
- при нарушении лимитов **сразу** извлекает том (`diskutil eject`)
- поддерживает белый/чёрный список томов и динамический чёрный список (после нарушения лимитов)

Логи пишутся в `security.log`, уведомления показываются через `plyer`.

## Требования

- macOS (используется `/Volumes` и `system_profiler`)
- Python 3.10+

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r info/requirements.txt
```

## Запуск

### Терминал

Режимы:

- `trusted`: полный доступ ко всем устройствам (без whitelist и без лимитов)
- `limited`: работают только лимиты (whitelist **выключен**) — лимиты действуют на **все** флешки, включая тома из `WHITELIST_DISKS`
- `whitelist`: whitelist + лимиты для неизвестных + авто-извлечение для томов из чёрного списка
- `strict` (по умолчанию): как `whitelist`

```bash
python main.py strict
python main.py limited
```

### Веб-интерфейс (FastAPI)

При запуске API автоматически стартует фоновый мониторинг (USB, диски, лимиты):

```bash
uvicorn api:app --reload
```

Документация и управление: `http://127.0.0.1:8000/docs`

Основные эндпоинты:

- `GET /` — текущий режим
- `POST /mode/{mode}` — смена режима (пишется в журнал: `MODE CHANGE | ...`)
- `GET /logs` — последние 100 строк `security.log`
- `GET /blacklist` — динамический чёрный список
- `POST /blacklist/add` — добавить том в чёрный список (пишется в журнал: `BLACKLIST CHANGE | ADD | ...`)

Настройки whitelist/лимитов редактируются в `config.py`.

## Подробные правила работы

### `trusted`
- **Разрешено**: все тома в `/Volumes`
- **Лимиты**: выключены
- **Авто-извлечение (eject)**: выключено

### `limited`
- **Разрешено**: все тома в `/Volumes`
- **Лимиты**: включены для **всех** томов (белый список `WHITELIST_DISKS` в этом режиме **не действует**)
- **Если лимит нарушен** (больше 5 файлов или больше 1 ГБ за минуту на одном томе):
  - пишется `❌ file limit` / `❌ size limit`
  - том **сразу** извлекается (`diskutil eject`, при ошибке — `diskutil unmountDisk`)
  - том добавляется в `dynamic_blacklist.json`

### `whitelist` / `strict`
- **Тома из `WHITELIST_DISKS`**: полный доступ (`ACCESS=FULL`), **без лимитов**
- **Остальные тома**: с лимитами (`ACCESS=LIMIT`)
- **Чёрный список томов**:
  - статический: `DISK_BLACKLIST` в `config.py`
  - динамический: `dynamic_blacklist.json` (пополняется при нарушении лимитов и через API)
  - том из чёрного списка: `ACCESS=BLOCK` + немедленное извлечение

## Журнал событий

Примеры записей:

```
🚀 Запуск мода: limited
MODE CHANGE | strict → limited
ALLOWED | REASON=WHITELIST_DISABLED | NAME=MY USB | ACCESS=LIMIT
FILE: /Volumes/MY USB/photo.jpg
❌ file limit
⏏️ EJECT (limit:file_limit): /Volumes/MY USB
✅ EJECT OK: /Volumes/MY USB
BLACKLIST CHANGE | ADD | NAME=MY USB | UUID=...
```

## Как устроены белые/чёрные списки томов

Проверка томов делается **по UUID и/или по имени**:

- **UUID** берётся из `diskutil info -plist "/Volumes/<NAME>"`:
  - сначала `VolumeUUID` (если есть)
  - иначе `DiskUUID`
- В `config.py` элементы `WHITELIST_DISKS` / `DISK_BLACKLIST` можно задавать так:
  - `{"uuid": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"}` (самый надёжный вариант)
  - `{"name": "TRUE DISK"}` (менее надёжно, имя можно переименовать)

Белый список томов учитывается **только** в режимах `whitelist` и `strict`. В режиме `limited` все флешки проверяются одинаково.
