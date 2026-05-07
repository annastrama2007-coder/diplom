# Файлы проекта и их назначение

## Точки входа

- `main.py`: выбор режима (`trusted/limited/whitelist/strict`) и запуск мониторинга.

## Конфигурация

- `controller.py`: глобальные флаги `SETTINGS` (включены ли whitelist/лимиты/сканеры).
- `config.py`: настройки и правила:
  - лимиты `MAX_FILES_AT_ONCE`, `MAX_TRANSFER_SIZE`
  - исключения системных томов `IGNORE_VOLUMES`
  - белый/чёрный список томов `WHITELIST_DISKS`, `DISK_BLACKLIST` (по имени и/или UUID)
  - авто‑извлечение: `AUTO_EJECT_BLOCKED_VOLUMES`, `AUTO_EJECT_ON_LIMIT_VIOLATION`

## Сканирование и контроль

- `disk_layer.py`: отслеживает появление томов в `/Volumes`, применяет whitelist/blacklist, пишет в лог и может делать изъятие `diskutil eject`.
- `monitor.py`: следит за созданием файлов в `/Volumes` (через `watchdog`) и применяет лимиты; при нарушении лимитов может:
  - попытаться извлечь том
  - добавить том в динамический чёрный список
- `usb_layer.py`: считывает USB‑дерево через `system_profiler -xml SPUSBDataType`, логирует появление USB‑устройств. (Этот слой полезен для детекта подозрительных USB‑устройств, но “блок” в проекте реализуется через работу с томами.)

## Идентификаторы/хранилища

- `disk_ids.py`: получение информации о томе через `diskutil info -plist` и выбор стабильного UUID (`VolumeUUID`/`DiskUUID`).
- `blacklist_store.py`: хранит список запрещённых томов `dynamic_blacklist.json` и безопасно обновляет его без риска повредить файл (добавляется при нарушении лимитов).

## Логирование и уведомления

- `logger.py`: запись событий в `security.log` + вывод в консоль.
- `notifier.py`: системные уведомления (через `plyer`).

## Прочее

- `requirements.txt`: зависимости (`watchdog`, `plyer`).
