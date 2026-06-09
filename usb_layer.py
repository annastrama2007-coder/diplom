import subprocess
import re
import time
import plistlib

from logger import log_event, log_usb_access
from notifier import alert
from config import WHITELIST_USB, USB_BLACKLIST
from controller import SETTINGS


def get_usb():
    """
    Выполняет команду:
    system_profiler — даёт информацию о железе
    SPUSBDataType — только USB
    -xml — вывод в plist/XML
    """
    result = subprocess.run(
        ["system_profiler", "-xml", "SPUSBDataType"],
        capture_output=True,
        check=False,
        timeout=10,
    )
    return result.stdout


def _walk_items(node):
    """
    Распаковывает глубоко вложенные структуры
    """
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_items(v)
    elif isinstance(node, list):
        for x in node:
            yield from _walk_items(x)


def _parse_vid_pid(text: str):
    """
    Парсит VID
    """
    if not text:
        return "-", "-"
    m = re.search(r"0x([0-9a-fA-F]{4})", text)
    return (m.group(1).lower() if m else "-")


def extract_devices(data: bytes):
    """
    Приводит данные к общему удобному виду (список устройств)
    """
    try:
        plist = plistlib.loads(data)
    except Exception:
        return []

    devices = []
    for d in _walk_items(plist):
        if not isinstance(d, dict):
            continue

        name = d.get("_name")
        if not name:
            continue

        vendor = d.get("vendor_name") or d.get("manufacturer") or "UNKNOWN"
        product = name

        vid = _parse_vid_pid(str(d.get("vendor_id", "")))
        pid = _parse_vid_pid(str(d.get("product_id", "")))

        devices.append(
            {
                "type": "USB",
                "vendor": vendor,
                "product": product,
                "vid": vid,
                "pid": pid,
            }
        )

    uniq = {}
    for dev in devices:
        uniq[(dev.get("vendor"), dev.get("product"), dev.get("vid"), dev.get("pid"))] = dev
    return list(uniq.values())


def check_whitelist(device):
    """
    Сравнивает личны номера устройств с белым списком
    """
    for allowed in WHITELIST_USB:
        if str(allowed.get("vid", "")).lower() == device["vid"] and str(allowed.get("pid", "")).lower() == device["pid"]:
            return True

    return False

def _norm(s):
    """
    Приводит строки к единому стилю, убирая ложные значения, лишние пробелы и приводит к нижнему регистру
    """
    return (s or "").strip().lower()


def is_blacklisted(device):
    """
    Сравнивает по черному списку
    """
    dv = _norm(device.get("vendor"))
    dp = _norm(device.get("product"))
    dvid = _norm(device.get("vid"))
    dpid = _norm(device.get("pid"))

    for rule in USB_BLACKLIST:
        rv = _norm(rule.get("vendor"))
        rp = _norm(rule.get("product"))
        rvid = _norm(rule.get("vid"))
        rpid = _norm(rule.get("pid"))

        if rvid and rvid != "-" and rvid != dvid:
            continue
        if rpid and rpid != "-" and rpid != dpid:
            continue
        if rv and rv not in dv:
            continue
        if rp and rp not in dp:
            continue
        return True

    return False


def detect_kvm(devices):
    """
    Определяет КВМ это или нет
    """
    names = " ".join(d.get("product", "") for d in devices)
    if "Keyboard" in names and "Mouse" in names and ("Storage" in names or "Mass Storage" in names):
        log_event("Обнаружено KVM-устройство")
        alert("KVM-устройство", "Обнаружено подозрительное KVM-устройство.")


def handle_device(device, is_allowed):
    """
    Итог разрешено/нет
    """
    if is_allowed:
        log_usb_access("ALLOWED", device, reason="WHITELIST" if SETTINGS.get("WHITELIST") else "UNKNOWN_ALLOWED")
        return

    log_usb_access("BLOCKED", device, reason="BLACKLIST_KVM" if SETTINGS.get("WHITELIST") else "UNKNOWN")
    name = device.get("product", "неизвестное устройство")
    alert("USB-устройство заблокировано", f"Устройство «{name}» заблокировано.")


def usb_scan():
    """
    Основная функция, использует все вышенаписанные
    """
    seen = b""
    last_devices = []

    while True:
        if not SETTINGS.get("USB_CHECK", True):
            time.sleep(2)
            continue

        try:
            data = get_usb()
        except Exception:
            time.sleep(2)
            continue

        if data != seen:
            seen = data
            devices = extract_devices(data)
            detect_kvm(devices)

            # Реакция только на новые устройства
            old_keys = {(d.get("vendor"), d.get("product"), d.get("vid"), d.get("pid")) for d in last_devices}
            for dev in devices:
                key = (dev.get("vendor"), dev.get("product"), dev.get("vid"), dev.get("pid"))
                if key in old_keys:
                    continue
                is_allowed = True
                if SETTINGS.get("WHITELIST"):
                    # Если КВМ = блок, если неизвестное устройство = лимит
                    if is_blacklisted(dev):
                        is_allowed = False
                        SETTINGS["KVM_LOCKDOWN"] = True
                    else:
                        is_allowed = True
                handle_device(dev, is_allowed)

            last_devices = devices

        time.sleep(1)