from contextlib import asynccontextmanager

from fastapi import FastAPI
from blacklist_store import add_volume_to_dynamic_blacklist, load_dynamic_volume_blacklist
from controller import SETTINGS
from logger import LOG_PATH, log_blacklist_change, log_mode_change
from main import set_mode, start_services


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_services("strict")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/", summary="Просмотреть состояние системы")
def root():

    return {
        "статус": "запущено",
        "режим": SETTINGS["MODE"]
    }


@app.post("/mode/{mode}", summary="Выбрать режим работы", description="""- `trusted`: полный доступ ко всем устройствам (без whitelist и без лимитов)
- `limited`: работают только лимиты (whitelist выключен) — режим удобен, чтобы проверять лимиты на любых флешках
- `whitelist`: whitelist + лимиты для неизвестных + авто-извлечение для томов из чёрного списка
- `strict` (по умолчанию): как `whitelist` (whitelist + лимиты + чёрный список + авто-извлечение)""")
def change_mode(mode: str):

    old_mode = SETTINGS["MODE"]
    set_mode(mode)
    log_mode_change(old_mode, mode)

    return {
        "new_mode": mode
    }

@app.get("/logs", summary="Просмотреть журнал событий", description="Данный журнал ведётся не в реальном времени!"
                                                                    "Выводится журнал, созранённый в файле security.log")
def get_logs():

    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    return {
        "logs": lines[-100:]
    }

@app.post("/blacklist/add", summary="Добавить устройства в чёрный список")
def add_blacklist(volume_name = "", volume_uuid = ""):
    result = add_volume_to_dynamic_blacklist(
        volume_name,
        volume_uuid
    )
    if result:
        log_blacklist_change("ADD", volume_name, volume_uuid)
    return {
        "success": result
    }

@app.get("/blacklist", summary="Просмотреть чёрный список")
def get_blacklist():
    uuids, names = load_dynamic_volume_blacklist()
    return {
        "uuids": list(uuids),
        "names": list(names)
    }
