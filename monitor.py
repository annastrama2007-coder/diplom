from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import time
from logger import log_event
from notifier import alert
from controller import SETTINGS
from config import (
    MAX_FILES_AT_ONCE,
    MAX_TRANSFER_SIZE,
    IGNORE_VOLUMES,
    AUTO_EJECT_ON_LIMIT_VIOLATION,
)
from blacklist_store import add_volume_to_dynamic_blacklist
from disk_ids import diskutil_info_plist, stable_volume_id
from disk_layer import _eject_volume, _volume_exempt_from_limits

_LIMIT_REASON_LABELS = {
    "file_limit": "превышено количество файлов",
    "size_limit": "превышен объём файлов",
    "file_and_size_limit": "превышены количество и объём файлов",
}

"""
watchdog-  слушает файловую систему, ловит события (создание, удаление и т.д.)
"""
class Handler(FileSystemEventHandler):
    """
    Задаётся счётчик, сколько файлов, размер и за какое время
    """
    def __init__(self):
        self._volume_stats = {}
        self._volume_uuid_cache = {}

    def _parse_volume(self, file_path):
        if not file_path.startswith("/Volumes/"):
            return None
        try:
            rel = os.path.relpath(file_path, "/Volumes")
            if rel.startswith(".."):
                return None
            top = rel.split(os.sep, 1)[0]
            if not top or top in IGNORE_VOLUMES:
                return None
            return top
        except Exception:
            return None

    def _get_volume_uuid(self, volume_name):
        if volume_name not in self._volume_uuid_cache:
            info = diskutil_info_plist(os.path.join("/Volumes", volume_name))
            self._volume_uuid_cache[volume_name] = stable_volume_id(info)
        return self._volume_uuid_cache[volume_name]

    def _get_volume_stats(self, volume_name):
        stats = self._volume_stats.setdefault(
            volume_name,
            {"files": 0, "size": 0, "start": time.time()},
        )
        if time.time() - stats["start"] > 60:
            stats["files"] = 0
            stats["size"] = 0
            stats["start"] = time.time()
        return stats

    def on_created(self, event):
        if event.is_directory:
            return
        self._handle_new_file(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        self._handle_new_file(event.dest_path)

    def _handle_new_file(self, file_path):
        """
        Отслеживает появление файлов на съёмных томах (created и moved).
        """
        volume_name = self._parse_volume(file_path)
        if not volume_name:
            return

        try:
            size = os.path.getsize(file_path)
        except OSError:
            size = 0

        log_event(f"Создан файл: {file_path}")

        vol_uuid = self._get_volume_uuid(volume_name)
        if _volume_exempt_from_limits(volume_name, vol_uuid):
            return

        stats = self._get_volume_stats(volume_name)
        stats["files"] += 1
        stats["size"] += size

        if not SETTINGS.get("LIMITS"):
            return

        file_limit = stats["files"] > MAX_FILES_AT_ONCE
        size_limit = stats["size"] > MAX_TRANSFER_SIZE
        if not file_limit and not size_limit:
            return

        if file_limit:
            alert("Превышен лимит", "Слишком много файлов. Том будет извлечён.")
            log_event("Превышен лимит на количество файлов")
        if size_limit:
            alert("Превышен лимит", "Превышен лимит объёма файлов. Том будет извлечён.")
            log_event("Превышен лимит на объём файлов")

        if file_limit and size_limit:
            reason = "file_and_size_limit"
        elif file_limit:
            reason = "file_limit"
        else:
            reason = "size_limit"

        self._eject_on_limit(volume_name, vol_uuid, reason=reason)
        self._blacklist_on_limit(volume_name, vol_uuid, reason=reason)

    def _blacklist_on_limit(self, volume_name, vol_uuid, reason):
        """
        При нарушении лимита добавляет устройство в чёрный список
        """
        added = add_volume_to_dynamic_blacklist(volume_name, volume_uuid=vol_uuid)
        if added:
            reason_label = _LIMIT_REASON_LABELS.get(reason, reason)
            extra = f", uuid {vol_uuid}" if vol_uuid else ""
            log_event(
                f"Том «{volume_name}» добавлен в чёрный список "
                f"({reason_label}){extra}"
            )

    def _eject_on_limit(self, volume_name, vol_uuid, reason):
        """
        Немедленное извлечение тома при нарушении лимита
        """
        if not AUTO_EJECT_ON_LIMIT_VIOLATION:
            return
        if _volume_exempt_from_limits(volume_name, vol_uuid):
            return

        mount_path = os.path.join("/Volumes", volume_name)
        reason_label = _LIMIT_REASON_LABELS.get(reason, reason)
        log_event(f"Извлечение тома из-за лимита ({reason_label}): {mount_path}")
        _eject_volume(mount_path)
        self._volume_stats.pop(volume_name, None)
        self._volume_uuid_cache.pop(volume_name, None)


def start_monitor():
    """
    Запускает мониторинг
    """
    path = "/Volumes"
    if not os.path.isdir(path):
        log_event(f"Путь для мониторинга не найден: {path}")
        return

    observer = Observer()
    observer.schedule(Handler(), path=path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
