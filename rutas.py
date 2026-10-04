"""
Rutas centralizadas. Portables entre escritorio y APK Android.

En APK (Flet), FLET_APP_STORAGE_DATA apunta a la carpeta privada
de la app en el dispositivo. En escritorio, se usa la carpeta del
proyecto.
"""
import os
from pathlib import Path


def _raiz_app() -> Path:
    storage = os.getenv("FLET_APP_STORAGE_DATA")
    if storage:
        return Path(storage)
    return Path(__file__).resolve().parent


RAIZ    = _raiz_app()
DATOS   = RAIZ / "datos"
BACKUPS = RAIZ / "backups"
LOGS    = RAIZ / "logs"

DB_PATH = DATOS / "almacen.db"

for _c in (DATOS, BACKUPS, LOGS):
    _c.mkdir(parents=True, exist_ok=True)