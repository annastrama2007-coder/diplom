import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "security.log")

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

_ACTION_LABELS = {
    "ALLOWED": "Разрешено",
    "BLOCKED": "Заблокировано",
}

_ACCESS_LABELS = {
    "FULL": "полный",
    "LIMIT": "с лимитами",
    "BLOCK": "заблокирован",
}

_REASON_LABELS = {
    "WHITELIST": "белый список",
    "UNKNOWN_ALLOWED": "неизвестное устройство, разрешено",
    "WHITELIST_DISABLED": "белый список отключён",
    "DISK_BLACKLIST": "чёрный список",
    "DYNAMIC_BLACKLIST": "динамический чёрный список",
    "BLACKLIST_KVM": "чёрный список KVM",
    "UNKNOWN": "неизвестное устройство",
}


def log_event(msg):
    print(msg)
    logging.info(msg)


def log_usb_access(action, device, reason=""):
    action_label = _ACTION_LABELS.get(action, action)
    reason_label = _REASON_LABELS.get(reason, reason or "не указана")
    name = device.get("product", "неизвестно")
    vendor = device.get("vendor", "неизвестно")
    vid = device.get("vid", "-")
    pid = device.get("pid", "-")

    message = (
        f"{action_label}: устройство «{name}» ({vendor}), "
        f"идентификатор {vid}:{pid}, причина: {reason_label}"
    )
    log_event(message)


def log_disk_access(action, volume_name, access, reason=""):
    action_label = _ACTION_LABELS.get(action, action)
    access_label = _ACCESS_LABELS.get(access, access)
    reason_label = _REASON_LABELS.get(reason, reason or "не указана")

    message = (
        f"{action_label}: том «{volume_name}», доступ {access_label}, "
        f"причина: {reason_label}"
    )
    log_event(message)


def log_start(mode):
    log_event(f"Запуск в режиме: {mode}")


def log_mode_change(old_mode, new_mode):
    log_event(f"Смена режима: {old_mode} → {new_mode}")


def log_blacklist_change(action, volume_name="", volume_uuid=""):
    action_labels = {
        "ADD": "добавление",
        "REMOVE": "удаление",
    }
    action_label = action_labels.get(action, action.lower())
    parts = [f"Изменение чёрного списка: {action_label}"]
    if volume_name:
        parts.append(f"том «{volume_name}»")
    if volume_uuid:
        parts.append(f"uuid {volume_uuid}")
    log_event(", ".join(parts))
