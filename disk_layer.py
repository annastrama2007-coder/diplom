import time
import os
import subprocess
from logger import log_event, log_disk_access
from notifier import alert
from config import WHITELIST_DISKS, IGNORE_VOLUMES, AUTO_EJECT_BLOCKED_VOLUMES, DISK_BLACKLIST
from controller import SETTINGS
from blacklist_store import load_dynamic_volume_blacklist
from disk_ids import diskutil_info_plist, stable_volume_id


def get_mounted_volumes():
    """
    Получаем все подключённые тома из папки /Volumes
    """
    path = "/Volumes"
    if not os.path.isdir(path):
        return []
    vols = []
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if os.path.isdir(full):
            vols.append(name)
    return sorted(v for v in vols if v not in IGNORE_VOLUMES)

def _rule_match(rule, name: str, uuid: str) -> bool:
    """
    Проверяет правила (черный и белый список) сначала для UUID потом для имени
    """
    if isinstance(rule, str):
        return rule.strip() == name
    if not isinstance(rule, dict):
        return False
    r_name = str(rule.get("name", "")).strip()
    r_uuid = str(rule.get("uuid", "")).strip()
    if r_uuid and uuid and r_uuid.lower() == uuid.lower():
        return True
    if r_name and r_name == name:
        return True
    return False


def _in_ruleset(rules, name: str, uuid: str) -> bool:
    """
    Проверяет совпало ли хоть какое то правило с данным диском
    Для облегчения кода и неповторяемости строк
    """
    if isinstance(rules, (list, tuple, set)):
        for r in rules:
            if _rule_match(r, name, uuid):
                return True
    return False


def _volume_exempt_from_limits(volume_name, vol_uuid) -> bool:
    """Белый список томов учитывается только когда включён режим WHITELIST."""
    return SETTINGS.get("WHITELIST") and _in_ruleset(WHITELIST_DISKS, volume_name, vol_uuid)


def _access_message(volume_name, access):
    labels = {
        "FULL": "полный доступ",
        "LIMIT": "доступ с лимитами",
        "BLOCK": "доступ заблокирован",
    }
    label = labels.get(access, access)
    return f"Том «{volume_name}»: {label}"

def _volume_perms(volume_name):
    """
    Проверяет права доступа на уровне системы (везде будет чтение и запись)
    """
    mount_path = os.path.join("/Volumes", volume_name)
    can_read = os.access(mount_path, os.R_OK)
    can_write = os.access(mount_path, os.W_OK)
    if can_read and can_write:
        return mount_path, "R/W"
    if can_read and not can_write:
        return mount_path, "R/O"
    if not can_read and can_write:
        return mount_path, "W/O"
    return mount_path, "NO_ACCESS"

def _run_diskutil(args, mount_path, ok_message, fail_message):
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode == 0:
            log_event(f"{ok_message}: {mount_path}")
            return True
        msg = result.stderr.strip() or result.stdout.strip()
        log_event(f"{fail_message} (код {result.returncode}): {mount_path}. {msg}")
    except Exception as e:
        log_event(f"{fail_message}: {mount_path}. {e}")
    return False


def _eject_volume(mount_path):
    """
    Попытка изъять устройство, все действия логируются.
    При ошибке пробует принудительное отмонтирование.
    """
    if _run_diskutil(
        ["diskutil", "eject", mount_path],
        mount_path,
        "Том успешно извлечён",
        "Не удалось извлечь том",
    ):
        return True

    if _run_diskutil(
        ["diskutil", "unmount", "force", mount_path],
        mount_path,
        "Том принудительно отмонтирован",
        "Не удалось принудительно отмонтировать том",
    ):
        return True

    if _run_diskutil(
        ["diskutil", "unmountDisk", "force", mount_path],
        mount_path,
        "Диск принудительно отмонтирован",
        "Не удалось принудительно отмонтировать диск",
    ):
        return True

    return False


def disk_scan():
    """
    Основная функция постоянно сканирующая подключаемые устройства
    """
    seen = []

    while True:
        if not SETTINGS.get("DISK_CHECK", True):
            time.sleep(3)
            continue

        volumes = get_mounted_volumes()

        if volumes != seen:
            added = [v for v in volumes if v not in seen]
            seen = volumes

            if added:
                if SETTINGS.get("WHITELIST"):
                    dynamic_uuids, dynamic_names = load_dynamic_volume_blacklist()
                    for v in added:
                        mount_path, _ = _volume_perms(v)
                        info = diskutil_info_plist(mount_path)
                        vol_uuid = stable_volume_id(info)
                        # В whitelist-режимах: тома из чёрного списка всегда блокируем и извлекаем
                        if _in_ruleset(DISK_BLACKLIST, v, vol_uuid) or (vol_uuid and vol_uuid in dynamic_uuids) or (v in dynamic_names):
                            reason = "DISK_BLACKLIST" if _in_ruleset(DISK_BLACKLIST, v, vol_uuid) else "DYNAMIC_BLACKLIST"
                            log_disk_access("BLOCKED", v, "BLOCK", reason=reason)
                            alert("Диск заблокирован", _access_message(v, "BLOCK"))
                            _eject_volume(mount_path)
                            continue

                        if _in_ruleset(WHITELIST_DISKS, v, vol_uuid):
                            log_disk_access("ALLOWED", v, "FULL", reason="WHITELIST")
                            alert("Диск подключён", _access_message(v, "FULL"))
                        else:
                            log_disk_access("ALLOWED", v, "LIMIT", reason="UNKNOWN_ALLOWED")
                            alert("Диск подключён", _access_message(v, "LIMIT"))

                            # Eject unknown volumes only if KVM/blacklist triggered (lockdown).
                            if SETTINGS.get("KVM_LOCKDOWN") and AUTO_EJECT_BLOCKED_VOLUMES:
                                log_event("Режим блокировки KVM: извлечение неизвестного устройства")
                                _eject_volume(mount_path)
                else:
                    for v in added:
                        mount_path, _ = _volume_perms(v)
                        info = diskutil_info_plist(mount_path)
                        vol_uuid = stable_volume_id(info)
                        limits_apply = SETTINGS.get("LIMITS") and not _volume_exempt_from_limits(v, vol_uuid)
                        access = "LIMIT" if limits_apply else "FULL"
                        log_disk_access("ALLOWED", v, access, reason="WHITELIST_DISABLED")
                        alert("Диск подключён", _access_message(v, access))

        time.sleep(3)
