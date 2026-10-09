"""
Rutas centralizadas. Portable + empaquetado por Flet.
"""
import ctypes
import os
import sys
import tempfile
from pathlib import Path


# ============================================================
# ¿Estamos dentro de un .exe compilado con Flet?
# ============================================================

def _ruta_exe() -> Path | None:
    """
    Devuelve la carpeta del .exe real (Windows).
    Devuelve None si corriendo en dev mode (flet run).

    Usa GetModuleFileNameW de Win32, que da la ruta del proceso
    principal — es decir, del .exe que arrancó, no del Python
    embebido.
    """
    if sys.platform != "win32":
        return None
    try:
        buf = ctypes.create_unicode_buffer(32768)
        ctypes.windll.kernel32.GetModuleFileNameW(None, buf, 32768)
        p = Path(buf.value)
        # Si el proceso principal es el propio Python, no estamos
        # dentro de un .exe empaquetado.
        if p.name.lower() in ("python.exe", "pythonw.exe"):
            return None
        return p.parent
    except Exception:
        return None


def _es_empaquetado() -> bool:
    """True si corremos dentro del .exe compilado por Flet."""
    if os.environ.get("FLET_APP_STORAGE_DATA"):
        return True
    if getattr(sys, "frozen", False):
        return True
    if _ruta_exe() is not None:
        return True
    return False


# ============================================================
# Raíz de datos
# ============================================================

def _puedo_escribir(carpeta: Path) -> bool:
    """Intenta crear/borrar un archivo invisible para validar."""
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        test = carpeta / ".almacen_write_test"
        test.touch()
        test.unlink()
        return True
    except Exception:
        return False


def _raiz_datos() -> Path:
    """
    Carpeta donde van datos/, backups/, logs/, tickets/.

    1. Dev mode  → carpeta del proyecto.
    2. Empaquetado → intenta AL LADO DEL .EXE (portable).
    3. Si no se puede → %LOCALAPPDATA%\\Almacen\\
    4. Último recurso → temp.
    """
    # ── Dev mode ──
    if not _es_empaquetado():
        return Path(__file__).resolve().parent

    # ── Empaquetado: intenta al lado del .exe ──
    exe_dir = _ruta_exe()
    if exe_dir is not None and _puedo_escribir(exe_dir):
        return exe_dir

    # ── Fallback: %LOCALAPPDATA%\Almacen ──
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        p = Path(base) / "Almacen"
        if _puedo_escribir(p):
            return p

    # ── Último recurso: temp ──
    p = Path(tempfile.gettempdir()) / "Almacen"
    _puedo_escribir(p)
    return p


# ============================================================
# Raíz de recursos (assets embebidos — NO se toca)
# ============================================================

def _raiz_recursos() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS",
                            Path(sys.executable).parent))
        return base / "recursos"
    return Path(__file__).resolve().parent / "recursos"


# ============================================================
# Paths globales
# ============================================================

RAIZ = _raiz_datos()
DATOS   = RAIZ / "datos"
BACKUPS = RAIZ / "backups"
LOGS    = RAIZ / "logs"
TICKETS = RAIZ / "tickets"

DB_PATH    = DATOS / "almacen.db"
EXCEL_PATH = DATOS / "inventario.xlsx"

RECURSOS = _raiz_recursos()


# Crear carpetas necesarias
for _c in (DATOS, BACKUPS, LOGS, TICKETS):
    try:
        _c.mkdir(parents=True, exist_ok=True)
    except Exception as _e:
        print(f"[rutas] no se pudo crear {_c}: {_e}")