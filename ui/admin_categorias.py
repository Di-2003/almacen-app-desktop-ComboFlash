"""
CRUD de tipos de producto (categorías). Solo admin/almacén.
"""
import flet as ft
import categorias as cats
from ui import estilos as es
from ui.componentes import snack, empty_state, mounted, cerrar_dialogo


def vista_admin_categorias(app):
    page = app.page
    lista = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

    def refrescar():
        lista.controls.clear()
        cat_list = cats.listar_categorias(solo_activas=False)
        conteo = cats.contar_productos_por_categoria()

        for c in cat_list:
            n = conteo.get(c["id"], 0)
            activa = c["activo"] == 1
            lista.controls.append(ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.CATEGORY,
                                        color=es.COLOR_ACENTO, size=20),
                        bgcolor=es.COLOR_ACENTO_SUAVE,
                        padding=10, border_radius=10),
                    ft.Column([
                        ft.Text(c["nombre"], size=14,
                                weight=ft.FontWeight.W_600,
                                color=es.COLOR_TEXTO),
                        ft.Text(f"{n} producto(s)" + (
                            "" if activa else "  ·  inactivo"),
                            size=11,
                            color=(es.COLOR_TEXTO_SUAVE if activa
                                   else es.COLOR_TEXTO_TENUE)),
                    ], spacing=2, expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT,
                            color=es.COLOR_TEXTO_TENUE, size=20),
                ], spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=12, bgcolor=es.COLOR_SUPERFICIE,
                border=ft.Border.all(1, es.COLOR_BORDE),
                border_radius=10,
                on_click=lambda e, cat=c: _acciones(app, cat, refrescar),
                ink=True,
            ))

        if not cat_list:
            lista.controls.append(empty_state(
                ft.Icons.CATEGORY_OUTLINED, "Sin tipos",
                "Crea el primero con el botón de arriba."))

        if mounted(lista):
            lista.update()

    def nuevo(e):
        _dlg_crear(app, refrescar)

    refrescar()

    return ft.View(
        route="/admin-categorias",
        controls=[
            ft.Container(
                content=ft.FilledButton(
                    "Nuevo tipo", icon=ft.Icons.ADD,
                    on_click=nuevo,
                    width=10000, height=46,
                    style=es.estilo_boton_marca()),
                padding=ft.Padding.only(left=14, top=14,
                                        right=14, bottom=4)),
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.all(14)),
        ],
        appbar=ft.AppBar(
            title=ft.Text("Tipos de producto", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )


def _acciones(app, cat, on_refresh):
    page = app.page

    def renombrar(e):
        cerrar_dialogo(page)
        _dlg_renombrar(app, cat, on_refresh)

    def toggle(e):
        cerrar_dialogo(page)
        try:
            if cat["activo"]:
                cats.eliminar_categoria(cat["id"])
            else:
                cats.crear_categoria(cat["nombre"])
            snack(page, "Actualizado", "ok")
            on_refresh()
        except Exception as ex:
            snack(page, str(ex), "error")

    contenido = ft.Column([
        ft.Text(cat["nombre"], size=17, weight=ft.FontWeight.BOLD,
                color=es.COLOR_TEXTO),
        ft.Container(height=6),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.EDIT, color=es.COLOR_ACENTO),
            title=ft.Text("Renombrar", color=es.COLOR_TEXTO),
            on_click=renombrar),
        ft.ListTile(
            leading=ft.Icon(
                ft.Icons.TOGGLE_ON if cat["activo"]
                else ft.Icons.TOGGLE_OFF,
                color=es.COLOR_TEXTO_SUAVE),
            title=ft.Text("Desactivar" if cat["activo"] else "Activar",
                          color=es.COLOR_TEXTO),
            on_click=toggle),
    ], spacing=0, tight=True)

    from ui.componentes import bottom_sheet
    page.show_dialog(bottom_sheet(contenido, page=page))


def _dlg_crear(app, on_refresh):
    page = app.page
    tf = ft.TextField(label="Nombre del tipo", autofocus=True,
                      **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def guardar(e):
        error_lbl.value = ""
        try:
            cats.crear_categoria(tf.value or "")
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        def _despues():
            snack(page, "Tipo creado", "ok")
            on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text("Nuevo tipo"),
        content=ft.Column([tf, error_lbl], tight=True, width=320),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton("Crear", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


def _dlg_renombrar(app, cat, on_refresh):
    page = app.page
    tf = ft.TextField(label="Nuevo nombre", value=cat["nombre"],
                      autofocus=True,
                      **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def guardar(e):
        error_lbl.value = ""
        try:
            cats.renombrar_categoria(cat["id"], tf.value or "")
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        def _despues():
            snack(page, "Tipo renombrado", "ok")
            on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text(f"Renombrar: {cat['nombre']}"),
        content=ft.Column([tf, error_lbl], tight=True, width=320),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)