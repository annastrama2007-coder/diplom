import json
import os
import tempfile
from typing import Set, Tuple


_PATH = os.path.join(os.path.dirname(__file__), "dynamic_blacklist.json")


def load_dynamic_volume_blacklist() -> Tuple[Set[str], Set[str]]:
    """
    Возвращает (uuids, names).

    Вводные данные:
    - старый формат: ["Untitled", "OtherName"]
    - новый формат: {"uuids": [...], "names": [...]}
    """
    try:
        with open(_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            names = {str(x).strip() for x in data if str(x).strip()}
            return set(), names

        if isinstance(data, dict):
            uuids_raw = data.get("uuids", [])
            names_raw = data.get("names", [])
            uuids = {str(x).strip() for x in (uuids_raw or []) if str(x).strip()}
            names = {str(x).strip() for x in (names_raw or []) if str(x).strip()}
            return uuids, names

        return set(), set()
    except FileNotFoundError:
        return set(), set()
    except Exception:
        return set(), set()


def add_volume_to_dynamic_blacklist(volume_name: str, volume_uuid: str = "") -> bool:
    """
    Загружает (uuids, names) в черный список, безопасно проверяя его наличие.
    """
    name = (volume_name or "").strip()
    uuid = (volume_uuid or "").strip()
    if not name and not uuid:
        return False

    uuids, names = load_dynamic_volume_blacklist()
    changed = False
    if uuid and uuid not in uuids:
        uuids.add(uuid)
        changed = True
    if name and name not in names:
        names.add(name)
        changed = True
    if not changed:
        return False

    tmp_dir = os.path.dirname(_PATH) or "."
    os.makedirs(tmp_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="dynamic_blacklist_", suffix=".json", dir=tmp_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                {"uuids": sorted(uuids), "names": sorted(names)},
                f,
                ensure_ascii=False,
                indent=2,
            )
            f.write("\n")
        os.replace(tmp_path, _PATH)
        return True
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

