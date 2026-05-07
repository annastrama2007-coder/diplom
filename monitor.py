from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import time
import subprocess
from logger import log_event
from notifier import alert
from controller import SETTINGS
from config import (
    MAX_FILES_AT_ONCE,
    MAX_TRANSFER_SIZE,
    IGNORE_VOLUMES,
    WHITELIST_DISKS,
    AUTO_EJECT_ON_LIMIT_VIOLATION,
)
from blacklist_store import add_volume_to_dynamic_blacklist
from disk_ids import diskutil_info_plist, stable_volume_id
from disk_layer import _in_ruleset

"""
watchdog-  слушает файловую систему, ловит события (создание, удаление и т.д.)
"""
class Handler(FileSystemEventHandler):
    """
    Задаётся счётчик, сколько файлов, размер и за какое время
    """
    def __init__(self):
        self.files = 0
        self.size = 0
        self.start = time.time()
        self._last_eject_at = {}

    def reset(self):
        # Скидывает счётчик каждые 60 секуед
        if time.time() - self.start > 60:
            self.files = 0
            self.size = 0
            self.start = time.time()

    def on_created(self, event):
        """
        Отслеживает создание файлов в накопителях
        """
        if event.is_directory:
            return

        # Не реагируем на события внутри системных томов macOS в /Volumes
        volume_name = None
        try:
            rel = os.path.relpath(event.src_path, "/Volumes")
            top = rel.split(os.sep, 1)[0]
            volume_name = top
            if top in IGNORE_VOLUMES:
                return
        except Exception:
            pass

        size = os.path.getsize(event.src_path)

        log_event(f"FILE: {event.src_path}")

        # Том из белого списка — без лимитов (но лог остаётся)
        if volume_name:
            info = diskutil_info_plist(os.path.join("/Volumes", volume_name))
            vol_uuid = stable_volume_id(info)
            if _in_ruleset(WHITELIST_DISKS, volume_name, vol_uuid):
                return

        self.reset()
        self.files += 1
        self.size += size

        if SETTINGS.get("LIMITS"):
            if self.files > MAX_FILES_AT_ONCE:
                alert("LIMIT", "Слишком много файлов")
                log_event("❌ file limit")
                self._blacklist_on_limit(volume_name, reason="file_limit")
                self._maybe_eject_on_limit(volume_name, reason="file_limit")

            if self.size > MAX_TRANSFER_SIZE:
                alert("LIMIT", "Вес файлов 1GB превышен")
                log_event("❌ size limit")
                self._blacklist_on_limit(volume_name, reason="size_limit")
                self._maybe_eject_on_limit(volume_name, reason="size_limit")

    def _blacklist_on_limit(self, volume_name, reason):
        """
        При нарушении лимита добавляет устройство в чёрный список
        """
        if not volume_name:
            return
        mount_path = os.path.join("/Volumes", volume_name)
        info = diskutil_info_plist(mount_path)
        vol_uuid = stable_volume_id(info)
        added = add_volume_to_dynamic_blacklist(volume_name, volume_uuid=vol_uuid)
        if added:
            extra = f" UUID={vol_uuid}" if vol_uuid else ""
            log_event(f"⛔ Added to dynamic blacklist (limit:{reason}): {volume_name}{extra}")

    def _maybe_eject_on_limit(self, volume_name, reason):
        """
        Попытка изъятия устройства, не чаще 30 секунд
        """
        if not AUTO_EJECT_ON_LIMIT_VIOLATION:
            return
        if not volume_name:
            return

        info = diskutil_info_plist(os.path.join("/Volumes", volume_name))
        vol_uuid = stable_volume_id(info)
        if _in_ruleset(WHITELIST_DISKS, volume_name, vol_uuid):
            return

        now = time.time()
        last = self._last_eject_at.get(volume_name, 0)
        if now - last < 30:
            return
        self._last_eject_at[volume_name] = now

        mount_path = os.path.join("/Volumes", volume_name)
        try:
            result = subprocess.run(
                ["diskutil", "eject", mount_path],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            if result.returncode == 0:
                log_event(f"✅ EJECT (limit:{reason}) OK: {mount_path}")
            else:
                msg = result.stderr.strip() or result.stdout.strip()
                log_event(f"⚠️ EJECT (limit:{reason}) FAILED ({result.returncode}): {mount_path} | {msg}")
        except Exception as e:
            log_event(f"⚠️ EJECT (limit:{reason}) ERROR: {mount_path} | {e}")


def start_monitor():
    """
    Запускает мониторинг
    """
    path = "/Volumes"
    if not os.path.isdir(path):
        log_event(f"⚠️ Monitor path not found: {path}")
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