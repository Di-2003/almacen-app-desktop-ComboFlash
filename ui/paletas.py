"""
Selector de paletas + modo claro/oscuro.
"""
import flet as ft
from db import get_pref, set_pref
from ui import estilos as es
from ui.componentes import snack


def vista_paletas(app):
    page = app.page
    paleta_actual = es.paleta_actual()
    modo_actual = es.modo_actual()

    contenido = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO,
                          expand=True)

    def aplicar(paleta, modo):
        es.aplicar_tema(modo=modo, paleta=paleta)
        try:
            set_pref("paleta", paleta)
            set_pref("tema", modo)
        except Exception:
            pass
        page.theme_mode = (ft.ThemeMode.DARK if modo == "oscuro"
                           else ft.ThemeMode.LIGHT)
        page.bgcolor = es.COLOR_FONDO
        snack(page, "Tema aplicado", "ok")
        app.refrescar()

    contenido.controls.append(ft.Text(
        "Modo", size=14, weight=ft.FontWeight.BOLD,
        color=es.COLOR_TEXTO))

    def boton_modo(texto, valor):
        activo = (modo_actual == valor)

        def click(e):
            aplicar(paleta_actual, valor)

        return ft.Container(
            content=ft.Text(texto, size=13,
                            color=("#ffffff" if activo
                                   else es.COLOR_TEXTO),
                            weight=ft.FontWeight.W_600),
            bgcolor=(es.COLOR_ACENTO if activo
                     else es.COLOR_SUPERFICIE_2),
            border=ft.Border.all(
                1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
            padding=ft.Padding.symmetric(horizontal=20, vertical=12),
            border_radius=12,
            on_click=click, ink=True, expand=True,
            alignment=ft.Alignment.CENTER)

    contenido.controls.append(ft.Row([
        boton_modo("☀ Claro", "claro"),
        boton_modo("🌙 Oscuro", "oscuro"),
    ], spacing=10))

    contenido.controls.append(ft.Container(height=6))
    contenido.controls.append(ft.Text(
        "Paleta", size=14, weight=ft.FontWeight.BOLD,
        color=es.COLOR_TEXTO))

    for clave in es.PALETAS_ORDEN:
        p = es.PALETAS[clave]
        activa = (paleta_actual == clave)

        def click(e, c=clave):
            aplicar(c, modo_actual)

        contenido.controls.append(ft.Container(
            content=ft.Row([
                ft.Container(
                    width=36, height=36,
                    bgcolor=p["acento_dark"],
                    border_radius=18,
                    border=ft.Border.all(1, es.COLOR_BORDE)),
                ft.Container(
                    width=36, height=36,
                    bgcolor=p["acento_light"],
                    border_radius=18,
                    border=ft.Border.all(1, es.COLOR_BORDE)),
                ft.Text(p["nombre"], size=14, expand=True,
                        color=es.COLOR_TEXTO,
                        weight=(ft.FontWeight.BOLD if activa
                                else ft.FontWeight.NORMAL)),
                ft.Icon(ft.Icons.CHECK_CIRCLE if activa
                        else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        color=(es.COLOR_ACENTO if activa
                               else es.COLOR_TEXTO_TENUE),
                        size=24),
            ], spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=12,
            bgcolor=(es.COLOR_ACENTO_SUAVE if activa
                     else es.COLOR_SUPERFICIE),
            border=ft.Border.all(
                1, es.COLOR_ACENTO if activa else es.COLOR_BORDE),
            border_radius=12,
            on_click=click, ink=True,
        ))

    return ft.View(
        route="/paletas",
        controls=[ft.Container(content=contenido, expand=True,
                               padding=ft.Padding.all(16))],
        appbar=ft.AppBar(
            title=ft.Text("Apariencia", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )