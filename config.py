WHITELIST_USB = [
    {
        """
        Если флешка видится как USB-устройство
        """
    }
]

USB_BLACKLIST = [
    {
        """
        Если флешка видится как USB-устройство
        """
    }
]

DISK_BLACKLIST = [
    # Можно задать имя {"name": "NanoKVM"},
    {"uuid": "EBA452DC-5327-3520-9C66-300ABEA824DD"}
]

WHITELIST_DISKS = [
    {"name": "TRUE DISK"},
    {"uuid": "D92F9857-CA8F-3801-B4DB-11A2538FB271"}
]

# Системные тома исключаем
IGNORE_VOLUMES = {
    "Macintosh HD",
    "Macintosh HD - Data",
    "Preboot",
    "Recovery",
    "VM",
}

# Если включено — при подключении «неизвестного» тома (не в WHITELIST_DISKS)
# программа попытается автоматически извлечь (eject) устройство.
AUTO_EJECT_BLOCKED_VOLUMES = True

# Если включено — при нарушении лимитов на томе (не из WHITELIST_DISKS)
# программа попытается автоматически извлечь (eject) устройство.
AUTO_EJECT_ON_LIMIT_VIOLATION = True

# Лимиты по количеству файлов и их весу
MAX_FILES_AT_ONCE = 5
MAX_TRANSFER_SIZE = 1 * 1024 * 1024 * 1024  # 1GB