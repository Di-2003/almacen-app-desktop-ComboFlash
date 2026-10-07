import warnings

# Silenciar TODOS los DeprecationWarning. Flet 1.0.3 emite cientos de
# avisos por propiedades que se eliminarán en 1.3 (border_radius,
# border_color, InputBorder.OUTLINE, etc.). La app funciona bien; es
# solo ruido en consola. Cuando salga Flet 1.3, se migran los helpers
# de ui/estilos.py y se borra este bloque.
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module=r"flet\..*")

import flet as ft
from db import inicializar_db, get_pref
from ui import estilos as es
from ui.app import AlmacenApp


def main(page: ft.Page):
    page.title = "Almacen"
    page.padding = 0

    # ─── SPLASH SCREEN (imagen durante el arranque) ─────────────
    # Cuando tengas la imagen lista, colócala en recursos/splash.png
    # y descomenta las 4 líneas siguientes. Muestra un fondo con el
    # logo mientras la BD se inicializa, y luego se desvanece.
    #
    # from pathlib import Path
    # ruta_splash = Path("recursos/splash.png")
    # if ruta_splash.exists():
    #     page.add(ft.Image(src="recursos/splash.png",
    #                       fit=ft.BoxFit.COVER,
    #                       expand=True))
    #     page.update()
    # ───────────────────────────────────────────────────────────

    inicializar_db()
    # NOTA: el backup automático al arranque se removió por pedido
    # del usuario. Ahora el backup se hace manualmente desde
    # Perfil → "Exportar copia de seguridad" o "Copia rápida a
    # carpeta". Así el usuario decide dónde guardarlo.

    try:
        modo = get_pref("tema") or "oscuro"
    except Exception:
        modo = "oscuro"
    es.aplicar_tema(modo)

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