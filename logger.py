import logging

logging.basicConfig(
    filename="security.log",
    level=logging.INFO,
    format="%(asctime)s | %(message)s"
)

def log_event(msg):
    print(msg)
    logging.info(msg)


def log_usb_access(action, device, reason=""):
    """
    Статус: ALLOWED / BLOCKED / WARNING
    Устройство: vendor/product/vid/pid/type
    Причина блока: KVM / WHITELIST / UNKNOWN
    """

    message = (
        f"{action} | "
        f"REASON={reason or 'NONE'} | "
        f"TYPE={device.get('type','UNKNOWN')} | "
        f"NAME={device.get('product','UNKNOWN')} | "
        f"VENDOR={device.get('vendor','UNKNOWN')} | "
        f"VID={device.get('vid','-')} PID={device.get('pid','-')}"
    )

    log_event(message)


def log_disk_access(action, volume_name, mount_path, perms, reason=""):
    message = (
        f"{action} | "
        f"REASON={reason or 'NONE'} | "
        f"TYPE=VOLUME | "
        f"NAME={volume_name} | "
        f"PATH={mount_path} | "
        f"PERMS={perms}"
    )
    log_event(message)


def log_start(mode):
    log_event(f"🚀 Запуск мода: {mode}")