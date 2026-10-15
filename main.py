import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module=r"flet\..*")

from pathlib import Path

import flet as ft
from db import inicializar_db, get_pref
from ui import estilos as es
from ui.app import AlmacenApp


# ═══════════════════════════════════════════════════════════
# LOCK DE INSTANCIA ÚNICA
# ═══════════════════════════════════════════════════════════
# Evita que dos procesos abran la misma BD a la vez. Sin esto,
# dos cajeros en la misma PC podrían corromper almacen.db o
# generar tickets correlativos duplicados.

_LOCK_FILE = None  # se mantiene abierto toda la vida del proceso


def _ruta_lock():
    from rutas import DATOS
    DATOS.mkdir(parents=True, exist_ok=True)
    return DATOS / "almacen.lock"


def _adquirir_lock_instancia() -> bool:
    """
    Intenta adquirir un lock exclusivo sobre datos/almacen.lock.
    Devuelve True si lo consiguió, False si ya hay otra instancia.
    """
    global _LOCK_FILE
    try:
        f = open(_ruta_lock(), "w")
    except Exception:
        # Si no podemos ni abrir el lock, no bloqueamos la app.
        return True

    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Guardar el handle para que el lock no se libere
        _LOCK_FILE = f
        return True
    except (OSError, IOError):
        f.close()
        return False


def _mostrar_error_instancia():
    """Muestra un aviso al usuario de que ya hay otra instancia."""
    msg = ("Almacén ComboFlash ya está abierto.\n\n"
           "Cierra la otra ventana antes de volver a abrirlo.")
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0, msg, "Almacén ComboFlash", 0x30)  # MB_ICONWARNING
            return
        except Exception:
            pass
    # Fallback: consola
    print(msg)
    try:
        input("Presiona Enter para cerrar…")
    except Exception:
        pass


def _ruta_icono_ventana() -> str | None:
    """Windows necesita .ico para el icono de la ventana."""
    raiz = Path(__file__).resolve().parent
    for nombre in ("icon.ico", "icon.png"):
        p = raiz / "assets" / nombre
        if p.exists():
            return str(p)
    return None


def main(page: ft.Page):
    page.title = "Almacen"
    page.padding = 0

    icono = _ruta_icono_ventana()
    if icono:
        try:
            page.window.icon = icono
        except Exception as ex:
            print(f"[icon] error: {ex}")

    try:
        page.window.width = 1280
        page.window.height = 820
        page.window.min_width = 900
        page.window.min_height = 600
    except Exception:
        pass

    inicializar_db()

    try:
        paleta = get_pref("paleta") or "dorado"
        modo = get_pref("tema") or "oscuro"
    except Exception:
        paleta, modo = "dorado", "oscuro"
    es.aplicar_tema(modo=modo, paleta=paleta)

    try:
        page.theme = ft.Theme(color_scheme_seed=es.COLOR_ACENTO)
    except Exception:
        pass

    page.theme_mode = (ft.ThemeMode.DARK if modo == "oscuro"
                       else ft.ThemeMode.LIGHT)
    page.bgcolor = es.COLOR_FONDO

    AlmacenApp(page).iniciar()


if __name__ == "__main__":
    if not _adquirir_lock_instancia():
        _mostrar_error_instancia()
        sys.exit(0)
    ft.run(main, assets_dir="assets")
    
