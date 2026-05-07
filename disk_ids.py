import plistlib
import subprocess


def diskutil_info_plist(path: str) -> dict:
    """
    Запуск команды:
    diskutil — утилита для работы с дисками
    info — информация о диске
    -plist — вывод в формате plist (XML/бинарь)

    И пирсинг результатов для удобного вида в питоне
    """
    try:
        result = subprocess.run(
            ["diskutil", "info", "-plist", path],
            capture_output=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout:
            return {}
        return plistlib.loads(result.stdout) or {}
    except Exception:
        return {}


def stable_volume_id(info: dict) -> str:
    """
    Из предыдущего списка вытаскивает UUID
    """
    for k in ("VolumeUUID", "DiskUUID"):
        v = info.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

