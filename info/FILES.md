# Файлы проекта и их назначение

Краткое руководство по установке и запуску — в корневом [`README.md`](../README.md).

## Структура

```
.
├── main.py                  # Запуск из терминала
├── api.py                   # Запуск через веб-интерфейс (FastAPI)
├── controller.py            # Глобальные флаги SETTINGS
├── config.py                # Правила, лимиты, списки устройств
├── disk_layer.py            # Сканирование подключённых томов
├── monitor.py               # Контроль копирования и лимитов
├── usb_layer.py             # Сканирование USB-устройств
├── disk_ids.py              # UUID томов через diskutil
├── blacklist_store.py       # Динамический чёрный список
├── logger.py                # Журнал security.log
├── notifier.py              # Уведомления на экране
├── dynamic_blacklist.json   # Данные динамического чёрного списка
├── security.log             # Журнал событий (создаётся автоматически)
└── info/
    ├── requirements.txt     # Зависимости и версии пакетов
    └── FILES.md             # Этот файл
```

---

## Точки входа

### `main.py`
Запуск системы из терминала.

- Принимает режим аргументом: `python main.py strict`
- Функция `set_mode(mode)` — переключает флаги `WHITELIST` и `LIMITS` в `SETTINGS`
- Функция `start_services(mode)` — запускает фоновые потоки: USB-сканер, сканер дисков, монитор файлов
- Режимы: `trusted`, `limited`, `whitelist`, `strict` (по умолчанию)

### `api.py`
Запуск через веб-интерфейс: `uvicorn api:app --reload`.

- При старте вызывает `start_services("strict")` — мониторинг работает так же, как в терминале
- `GET /` — статус и текущий режим
- `POST /mode/{mode}` — смена режима (логируется как `MODE CHANGE | ...`)
- `GET /logs` — последние 100 строк журнала
- `GET /blacklist` — просмотр динамического чёрного списка
- `POST /blacklist/add` — добавление тома в чёрный список (логируется как `BLACKLIST CHANGE | ADD | ...`)
- Swagger UI: `http://127.0.0.1:8000/docs`

---