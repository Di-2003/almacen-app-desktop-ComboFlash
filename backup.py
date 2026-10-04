"""
Backup automático de la base de datos.

Se ejecuta al arrancar la app:
  1. Copia datos/almacen.db a backups/almacen_YYYY-MM-DD_HHMMSS.db
  2. Borra los backups con más de RETENCION_DIAS días.

Si la BD no existe todavía (primer arranque), no hace nada.
"""
import shutil
from datetime import datetime, timedelta
from rutas import DB_PATH, BACKUPS

RETENCION_DIAS = 30


def hacer_backup() -> str | None:
    """
    Crea una copia de la BD con timestamp.
    Devuelve la ruta del backup creado, o None si no había BD aún.
    """
    if not DB_PATH.exists():
        return None

    sello = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = BACKUPS / f"almacen_{sello}.db"

    shutil.copy2(DB_PATH, destino)
    _limpiar_antiguos()
    return str(destino)


def _limpiar_antiguos() -> None:
    """Borra backups más antiguos que RETENCION_DIAS."""
    limite = datetime.now() - timedelta(days=RETENCION_DIAS)

    for archivo in BACKUPS.glob("almacen_*.db"):
        try:
            sello = archivo.stem.replace("almacen_", "")
            fecha = datetime.strptime(sello, "%Y-%m-%d_%H%M%S")
            if fecha < limite:
                archivo.unlink()
        except (ValueError, OSError):
            pass