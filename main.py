import sys
import threading

from controller import SETTINGS
from logger import log_start

from usb_layer import usb_scan
from disk_layer import disk_scan
from monitor import start_monitor


def set_mode(mode):
    """
    Выбор режима
    """
    SETTINGS["MODE"] = mode

    if mode == "trusted":
        SETTINGS["WHITELIST"] = False
        SETTINGS["LIMITS"] = False

    elif mode == "limited":
        SETTINGS["WHITELIST"] = False
        SETTINGS["LIMITS"] = True

    elif mode == "whitelist":
        SETTINGS["WHITELIST"] = True
        SETTINGS["LIMITS"] = True

    elif mode == "strict":
        SETTINGS["WHITELIST"] = True
        SETTINGS["LIMITS"] = True
    else:
        SETTINGS["WHITELIST"] = True
        SETTINGS["LIMITS"] = True


if __name__ == "__main__":

    mode = sys.argv[1] if len(sys.argv) > 1 else "strict"

    set_mode(mode)
    # сброс флага
    SETTINGS["KVM_LOCKDOWN"] = False
    log_start(mode)

    threads = []

    if SETTINGS.get("USB_CHECK", True):
        threads.append(threading.Thread(target=usb_scan, name="usb_scan", daemon=True))
    if SETTINGS.get("DISK_CHECK", True):
        threads.append(threading.Thread(target=disk_scan, name="disk_scan", daemon=True))
    threads.append(threading.Thread(target=start_monitor, name="monitor", daemon=True))

    for t in threads:
        t.start()

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        pass
