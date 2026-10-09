import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module=r"flet\..*")

from pathlib import Path

import flet as ft
from db import inicializar_db, get_pref
from ui import estilos as es
from ui.app import AlmacenApp


def _ruta_icono_ventana() -> str | None:
    """Windows necesita .ico para el icono de la ventana."""
    raiz = Path(__file__).resolve().parent
    # Preferir .ico; si no existe, intentar .png
    for nombre in ("icon.ico", "icon.png"):
        p = raiz / "assets" / nombre
        if p.exists():
            return str(p)
    return None


def main(page: ft.Page):
    page.title = "Almacen"
    page.padding = 0

    # ── IMPORTANTE: setear el icono ANTES de cualquier otra cosa ──
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
    ft.run(main, assets_dir="assets")