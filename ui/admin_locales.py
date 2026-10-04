"""
Administración de locales: abrir, renombrar y cerrar tiendas.
Solo admin. El Almacén no se puede cerrar ni renombrar.
"""
import flet as ft
import locales as loc
from ui import estilos as es
from ui.componentes import (
    snack, bottom_sheet, empty_state, mounted,
)


def vista_admin_locales(app):
    page = app.page
    lista = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

    def refrescar():
        lista.controls.clear()
        almacen = loc.obtener_almacen()
        tiendas = loc.listar_tiendas(solo_activas=True)

        # Almacén (fijo, no se puede cerrar)
        if almacen:
            lista.controls.append(_tarjeta_local(
                almacen, on_tap=None, es_almacen=True))

        for t in tiendas:
            lista.controls.append(_tarjeta_local(
                t, on_tap=lambda e, l=t: _acciones_local(app, l, refrescar),
                es_almacen=False))

        if not tiendas:
            lista.controls.append(empty_state(
                ft.Icons.STOREFRONT_OUTLINED,
                "Sin tiendas",
                "Toca 'Abrir tienda' para crear la primera.",
            ))

        if mounted(lista):
            lista.update()

    def abrir(e):
        _dlg_abrir_tienda(app, refrescar)

    refrescar()

    return ft.View(
        route="/admin-locales",
        controls=[
            ft.Container(
                content=ft.FilledButton(
                    "Abrir nueva tienda",
                    icon=ft.Icons.ADD,
                    on_click=abrir,
                    width=10000, height=46,
                    style=es.estilo_boton_marca(),
                ),
                padding=ft.Padding.only(left=14, top=14,
                                        right=14, bottom=4),
            ),
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.all(14)),
        ],
        appbar=ft.AppBar(
            title=ft.Text("Administrar locales", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )


def _tarjeta_local(local, on_tap, es_almacen):
    n_prods = len(_productos_de(local["id"]))
    icono = (ft.Icons.WAREHOUSE if es_almacen
             else ft.Icons.STOREFRONT)
    etiqueta = "Almacén (fijo)" if es_almacen else f"{n_prods} productos"

    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Icon(icono, color=es.COLOR_ACENTO,
                                    size=22),
                    bgcolor=es.COLOR_ACENTO_SUAVE,
                    padding=12, border_radius=12,
                ),
                ft.Column(
                    [
                        ft.Text(local["nombre"], size=15,
                                weight=ft.FontWeight.W_600,
                                color=es.COLOR_TEXTO),
                        ft.Text(etiqueta, size=11,
                                color=es.COLOR_TEXTO_SUAVE),
                    ],
                    spacing=2, expand=True,
                ),
                ft.Icon(ft.Icons.CHEVRON_RIGHT,
                        color=es.COLOR_TEXTO_TENUE, size=20)
                if on_tap else ft.Container(width=1),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=14,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=14,
        on_click=on_tap,
        ink=bool(on_tap),
    )


def _productos_de(local_id):
    from db import get_conn
    with get_conn() as conn:
        return conn.execute(
            "SELECT id FROM productos WHERE local_id=? AND activo=1",
            (local_id,),
        ).fetchall()


def _acciones_local(app, local, on_refresh):
    page = app.page

    def renombrar(e):
        page.pop_dialog()
        _dlg_renombrar(app, local, on_refresh)

    def cerrar(e):
        page.pop_dialog()
        _confirmar_cerrar(app, local, on_refresh)

    contenido = ft.Column(
        [
            ft.Text(local["nombre"], size=17,
                    weight=ft.FontWeight.BOLD,
                    color=es.COLOR_TEXTO),
            ft.Container(height=6),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.EDIT,
                                color=es.COLOR_ACENTO),
                title=ft.Text("Renombrar", color=es.COLOR_TEXTO),
                on_click=renombrar,
            ),
            ft.ListTile(
                leading=ft.Icon(ft.Icons.LOCK,
                                color=es.COLOR_PELIGRO),
                title=ft.Text("Cerrar tienda",
                              color=es.COLOR_PELIGRO),
                on_click=cerrar,
            ),
        ],
        spacing=0, tight=True,
    )
    page.show_dialog(bottom_sheet(contenido, page=page))


def _dlg_abrir_tienda(app, on_refresh):
    page = app.page
    tf = ft.TextField(
        label="Nombre de la nueva tienda",
        autofocus=True,
        **es.estilo_textfield(12), height=54,
    )

    def guardar(e):
        try:
            nuevo_id = loc.abrir_tienda(tf.value or "")
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, f"Tienda «{loc.nombre_local(nuevo_id)}» abierta", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Abrir nueva tienda"),
        content=ft.Column(
            [tf,
             ft.Text("No puede llamarse 'Almacén' ni 'General'.",
                     size=11, color=es.COLOR_TEXTO_SUAVE)],
            tight=True, width=320, spacing=8),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Abrir", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_renombrar(app, local, on_refresh):
    page = app.page
    tf = ft.TextField(
        label="Nuevo nombre",
        value=local["nombre"],
        autofocus=True,
        **es.estilo_textfield(12), height=54,
    )

    def guardar(e):
        try:
            loc.renombrar_local(local["id"], tf.value or "")
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Local renombrado", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Renombrar «{local['nombre']}»"),
        content=ft.Column([tf], tight=True, width=320),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _confirmar_cerrar(app, local, on_refresh):
    page = app.page

    def hacer(e):
        try:
            loc.cerrar_tienda(local["id"], app.usuario["username"])
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, f"«{local['nombre']}» cerrada. Sus productos "
                    f"pasaron al Almacén.", "ok")
        # Si el local actual era el que se cerró, volver al Almacén
        if app.local_id == local["id"]:
            almacen = loc.obtener_almacen()
            if almacen:
                app.cambiar_local(almacen["id"])
                return
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Cerrar tienda"),
        content=ft.Text(
            f"¿Seguro que quieres cerrar «{local['nombre']}»?\n\n"
            "Todos sus productos se traspasarán al Almacén y "
            "quedará inactiva. No se puede deshacer desde la app.",
            size=13, color=es.COLOR_TEXTO),
        actions=[
            ft.TextButton("Cancelar",
                        on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Cerrar tienda", on_click=hacer,
                            style=ft.ButtonStyle(
                                bgcolor=es.COLOR_PELIGRO,
                                color="white")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))