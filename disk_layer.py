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

def _eject_volume(mount_path):
    """
    Попытка изъять устройство, все действия логируются
    """
    try:
        result = subprocess.run(
            ["diskutil", "eject", mount_path],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode == 0:
            log_event(f"✅ EJECT OK: {mount_path}")
            return True
        log_event(f"⚠️ EJECT FAILED ({result.returncode}): {mount_path} | {result.stderr.strip() or result.stdout.strip()}")
    except Exception as e:
        log_event(f"⚠️ EJECT ERROR: {mount_path} | {e}")

    try:
        result = subprocess.run(
            ["diskutil", "unmountDisk", mount_path],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode == 0:
            log_event(f"✅ UNMOUNT OK: {mount_path}")
            return True
        log_event(f"⚠️ UNMOUNT FAILED ({result.returncode}): {mount_path} | {result.stderr.strip() or result.stdout.strip()}")
    except Exception as e:
        log_event(f"⚠️ UNMOUNT ERROR: {mount_path} | {e}")

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
                        mount_path, perms = _volume_perms(v)
                        info = diskutil_info_plist(mount_path)
                        vol_uuid = stable_volume_id(info)
                        # В whitelist-режимах: тома из чёрного списка всегда блокируем и извлекаем
                        if _in_ruleset(DISK_BLACKLIST, v, vol_uuid) or (vol_uuid and vol_uuid in dynamic_uuids) or (v in dynamic_names):
                            perms = f"{perms} (BLOCKED)"
                            reason = "DISK_BLACKLIST" if _in_ruleset(DISK_BLACKLIST, v, vol_uuid) else "DYNAMIC_BLACKLIST"
                            log_disk_access("BLOCKED", v, mount_path, perms, reason=reason)
                            alert("DISK заблокирован", f"{v} | {perms}")
                            _eject_volume(mount_path)
                            continue

                        if _in_ruleset(WHITELIST_DISKS, v, vol_uuid):
                            policy = "FULL"
                            perms = f"{perms} ({policy})"
                            log_disk_access("ALLOWED", v, mount_path, perms, reason="WHITELIST")
                            alert("DISK разрешён", f"{v} | {perms}")
                        else:
                            policy = "LIMITED"
                            perms = f"{perms} ({policy})"
                            log_disk_access("ALLOWED", v, mount_path, perms, reason="UNKNOWN_ALLOWED")
                            alert("DISK разрешён", f"{v} | {perms}")

                            if SETTINGS.get("KVM_LOCKDOWN") and AUTO_EJECT_BLOCKED_VOLUMES:
                                log_event("⚠️ KVM_LOCKDOWN: изъятие неизвестного устройства")
                                _eject_volume(mount_path)
                else:
                    for v in added:
                        mount_path, perms = _volume_perms(v)
                        info = diskutil_info_plist(mount_path)
                        vol_uuid = stable_volume_id(info)
                        limits_apply = SETTINGS.get("LIMITS") and (not _in_ruleset(WHITELIST_DISKS, v, vol_uuid))
                        policy = "LIMITED" if limits_apply else "FULL"
                        perms = f"{perms} ({policy})"
                        log_disk_access("ALLOWED", v, mount_path, perms, reason="WHITELIST_DISABLED")
                        alert("DISK разрешён", f"{v} | {perms}")

        time.sleep(3)
