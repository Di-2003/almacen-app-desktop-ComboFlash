import warnings

# Silenciar TODOS los DeprecationWarning. Flet 1.0.3 emite cientos de
# avisos por propiedades que se eliminarán en 1.3.
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module=r"flet\..*")

import flet as ft
from db import inicializar_db, get_pref
from ui import estilos as es
from ui.app import AlmacenApp


def main(page: ft.Page):
    page.title = "Almacen"
    page.padding = 0

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
        try:
            page.theme = ft.Theme(
                color_scheme=ft.ColorScheme(primary=es.COLOR_ACENTO)
            )
        except Exception:
            pass

    page.theme_mode = (ft.ThemeMode.DARK if modo == "oscuro"
                       else ft.ThemeMode.LIGHT)
    page.bgcolor = es.COLOR_FONDO

    try:
        page.window.icon = "recursos/icon.png"
    except Exception:
        pass

    AlmacenApp(page).iniciar()


if __name__ == "__main__":
    ft.run(main, assets_dir="recursos")