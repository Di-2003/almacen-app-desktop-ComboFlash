"""
CRUD de categorías de gastos. Modal reutilizable.
"""
import flet as ft
import gastos as gs
from ui import estilos as es
from ui.componentes import snack, empty_state, mounted, mostrar_modal


def abrir_admin_categorias_gastos(app, on_done=None):
    page = app.page
    cerrar_ref = {"fn": None}

    def cerrar():
        if cerrar_ref["fn"]:
            cerrar_ref["fn"]()

    lista_col = ft.Column(spacing=6, tight=True)

    def rebuild():
        lista_col.controls.clear()
        cats = gs.listar_categorias_gastos(solo_activas=False)
        for c in cats:
            activa = c["activo"] == 1
            lista_col.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(
                        ft.Icons.CATEGORY,
                        color=(es.COLOR_ACENTO if activa
                               else es.COLOR_TEXTO_TENUE),
                        size=20),
                    ft.Text(c["nombre"], size=14, expand=True,
                            color=(es.COLOR_TEXTO if activa
                                   else es.COLOR_TEXTO_TENUE),
                            weight=ft.FontWeight.W_600),
                    ft.IconButton(
                        ft.Icons.EDIT, icon_size=18,
                        icon_color=es.COLOR_ACENTO,
                        tooltip="Renombrar",
                        on_click=lambda e, cat=c:
                            _dlg_editar_categoria(app, cat, rebuild)),
                    ft.IconButton(
                        ft.Icons.TOGGLE_ON if activa
                        else ft.Icons.TOGGLE_OFF,
                        icon_size=18,
                        icon_color=(es.COLOR_EXITO if activa
                                    else es.COLOR_TEXTO_TENUE),
                        tooltip=("Desactivar" if activa
                                 else "Activar"),
                        on_click=lambda e, cat=c:
                            _toggle_categoria(app, cat, rebuild)),
                ], spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=10,
                bgcolor=es.COLOR_SUPERFICIE_2,
                border_radius=10))
        if not cats:
            lista_col.controls.append(empty_state(
                ft.Icons.CATEGORY_OUTLINED, "Sin categorías",
                "Crea la primera con el botón de abajo."))
        if mounted(lista_col):
            lista_col.update()

    # Cabecera con título + X
    cabecera = ft.Row([
        ft.Text("Categorías de gastos", size=16,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO,
                expand=True),
        ft.IconButton(
            ft.Icons.CLOSE,
            icon_color=es.COLOR_TEXTO_SUAVE,
            tooltip="Cerrar",
            on_click=lambda e: cerrar()),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    contenido = ft.Column([
        cabecera,
        ft.Container(height=10),
        lista_col,
        ft.Container(height=10),
        ft.FilledButton(
            "Nueva categoría", icon=ft.Icons.ADD,
            on_click=lambda e: _dlg_nueva_categoria(app, rebuild),
            width=10000, height=44,
            style=es.estilo_boton_marca()),
    ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO)

    panel = ft.Container(
        content=contenido,
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=16,
        padding=20,
        width=420,
        shadow=ft.BoxShadow(
            blur_radius=20, spread_radius=0,
            color="#00000099",
            offset=ft.Offset(0, 6)),
        border=ft.Border.all(1, es.COLOR_BORDE),
    )

    cerrar_ref["fn"] = mostrar_modal(
        page, panel, on_close=on_done if on_done else None)
    rebuild()


def _dlg_nueva_categoria(app, on_done):
    page = app.page
    tf = ft.TextField(label="Nombre", autofocus=True,
                      **es.estilo_textfield(12), height=54)
    err = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        err.value = ""
        try:
            gs.crear_categoria_gasto(tf.value or "")
        except Exception as ex:
            err.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Categoría creada", "ok")
        on_done()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Nueva categoría de gasto"),
        content=ft.Column([tf, err], tight=True, width=320),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Crear", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_editar_categoria(app, cat, on_done):
    page = app.page
    tf = ft.TextField(label="Nuevo nombre", value=cat["nombre"],
                      autofocus=True,
                      **es.estilo_textfield(12), height=54)
    err = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        err.value = ""
        try:
            gs.renombrar_categoria_gasto(cat["id"], tf.value or "")
        except Exception as ex:
            err.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Categoría renombrada", "ok")
        on_done()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Editar: {cat['nombre']}"),
        content=ft.Column([tf, err], tight=True, width=320),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _toggle_categoria(app, cat, on_done):
    try:
        if cat["activo"]:
            gs.desactivar_categoria_gasto(cat["id"])
        else:
            gs.crear_categoria_gasto(cat["nombre"])
        on_done()
    except Exception as ex:
        snack(app.page, str(ex), "error")