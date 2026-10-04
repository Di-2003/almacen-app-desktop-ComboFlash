"""
Gestión de usuarios (solo admin).
"""
import flet as ft
import usuarios as usuarios_mod
from ui import estilos as es
from ui.componentes import snack, bottom_sheet, mounted

ROLES = [("admin", "Admin"), ("almacen", "Almacén"), ("comun", "Común")]
ETIQ = dict(ROLES)


def vista_usuarios(app):
    page = app.page
    lista = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)

    def refrescar():
        lista.controls.clear()
        try:
            usuarios = usuarios_mod.listar_usuarios(app.usuario)
        except PermissionError as ex:
            snack(page, str(ex), "error")
            usuarios = []

        for u in usuarios:
            es_yo = u["id"] == app.usuario["id"]
            ce = es.COLOR_EXITO if u["activo"] else es.COLOR_TEXTO_TENUE
            lista.controls.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(
                            u["username"] + (" (tú)" if es_yo else ""),
                            size=15, weight=ft.FontWeight.W_600,
                            expand=True, color=es.COLOR_TEXTO),
                        ft.Container(
                            content=ft.Text(ETIQ.get(u["rol"], u["rol"]),
                                            size=10,
                                            color=es.COLOR_MARCA_NEGRO,
                                            weight=ft.FontWeight.BOLD),
                            bgcolor=es.COLOR_ACENTO,
                            padding=ft.Padding.symmetric(
                                horizontal=8, vertical=3),
                            border_radius=8),
                    ]),
                    ft.Row([
                        ft.Container(width=8, height=8, bgcolor=ce,
                                     border_radius=4),
                        ft.Text("Activo" if u["activo"] else "Inactivo",
                                size=11, color=es.COLOR_TEXTO_SUAVE),
                        ft.Text("•", size=11,
                                color=es.COLOR_TEXTO_TENUE),
                        ft.Text(u["creado"][:10], size=11,
                                color=es.COLOR_TEXTO_SUAVE),
                    ], spacing=6),
                ], spacing=6),
                padding=12, bgcolor=es.COLOR_SUPERFICIE,
                border=ft.Border.all(1, es.COLOR_BORDE),
                border_radius=10,
                on_click=lambda e, usr=u: _acciones(app, usr, refrescar),
                ink=True))

        if mounted(lista):
            lista.update()

    def nuevo(e):
        _dlg_nuevo(app, refrescar)

    refrescar()

    return ft.View(
        route="/usuarios",
        controls=[
            ft.Container(
                content=ft.FilledButton(
                    "Nuevo usuario", icon=ft.Icons.ADD,
                    on_click=nuevo,
                    width=10000, height=46,
                    style=es.estilo_boton_marca()),
                padding=ft.Padding.only(left=12, top=12,
                                        right=12, bottom=4)),
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.all(12)),
        ],
        appbar=ft.AppBar(
            title=ft.Text("Usuarios", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )


def _acciones(app, u, on_refresh):
    page = app.page
    if u["id"] == app.usuario["id"]:
        snack(page, "Usa Editar perfil para tu usuario", "info")
        return

    def rol(e):
        page.pop_dialog()
        _dlg_rol(app, u, on_refresh)

    def reset(e):
        page.pop_dialog()
        _dlg_reset(app, u, on_refresh)

    def toggle(e):
        try:
            usuarios_mod.activar_usuario(
                u["id"], not u["activo"], solicitante=app.usuario)
            page.pop_dialog()
            on_refresh()
            snack(page, "Actualizado", "ok")
        except Exception as ex:
            snack(page, str(ex), "error")

    def elim(e):
        page.pop_dialog()
        _confirmar_elim(app, u, on_refresh)

    bs = bottom_sheet(ft.Column([
        ft.Text(u["username"], size=17,
                weight=ft.FontWeight.BOLD,
                color=es.COLOR_TEXTO),
        ft.Container(height=6),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.THEATER_COMEDY,
                            color=es.COLOR_ACENTO),
            title=ft.Text("Cambiar rol", color=es.COLOR_TEXTO),
            on_click=rol),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.KEY, color=es.COLOR_ACENTO),
            title=ft.Text("Resetear contraseña",
                          color=es.COLOR_TEXTO),
            on_click=reset),
        ft.ListTile(
            leading=ft.Icon(
                ft.Icons.TOGGLE_ON if u["activo"]
                else ft.Icons.TOGGLE_OFF,
                color=es.COLOR_TEXTO_SUAVE),
            title=ft.Text(
                "Desactivar" if u["activo"] else "Activar",
                color=es.COLOR_TEXTO),
            on_click=toggle),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.DELETE,
                            color=es.COLOR_PELIGRO),
            title=ft.Text("Eliminar", color=es.COLOR_PELIGRO),
            on_click=elim),
    ], tight=True), page=page)
    page.show_dialog(bs)


def _dlg_rol(app, u, on_ok):
    page = app.page
    dd = ft.Dropdown(
        label="Rol", value=u["rol"],
        options=[ft.DropdownOption(key=k, text=e) for k, e in ROLES],
        **es.borde_textfield(12),
    )

    def guardar(e):
        try:
            usuarios_mod.cambiar_rol(u["id"], dd.value,
                                     solicitante=app.usuario)
            page.pop_dialog()
            on_ok()
            snack(page, "Rol actualizado", "ok")
        except Exception as ex:
            snack(page, str(ex), "error")

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Cambiar rol"),
        content=ft.Column([dd], tight=True, width=280),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_reset(app, u, on_ok):
    page = app.page
    tf = ft.TextField(
        label="Nueva contraseña", password=True,
        can_reveal_password=True,
        **es.estilo_textfield(12), height=54,
    )

    def guardar(e):
        try:
            usuarios_mod.resetear_password(
                u["id"], tf.value, solicitante=app.usuario)
            page.pop_dialog()
            on_ok()
            snack(page, "Contraseña actualizada", "ok")
        except Exception as ex:
            snack(page, str(ex), "error")

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Resetear a {u['username']}"),
        content=ft.Column([tf], tight=True, width=300),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _confirmar_elim(app, u, on_ok):
    page = app.page

    def hacer(e):
        try:
            usuarios_mod.eliminar_usuario(
                u["id"], app.usuario["id"],
                solicitante=app.usuario)
            page.pop_dialog()
            on_ok()
            snack(page, "Usuario eliminado", "ok")
        except Exception as ex:
            snack(page, str(ex), "error")

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Eliminar usuario"),
        content=ft.Text(
            f"¿Eliminar a «{u['username']}»? No se puede deshacer.",
            color=es.COLOR_TEXTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Eliminar", on_click=hacer,
                            style=ft.ButtonStyle(
                                bgcolor=es.COLOR_PELIGRO,
                                color="white")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_nuevo(app, on_ok):
    page = app.page
    tf_u = ft.TextField(label="Usuario",
                        **es.estilo_textfield(12), height=54)
    tf_p = ft.TextField(label="Contraseña", password=True,
                        can_reveal_password=True,
                        **es.estilo_textfield(12), height=54)
    tf_p2 = ft.TextField(label="Repetir contraseña", password=True,
                         can_reveal_password=True,
                         **es.estilo_textfield(12), height=54)
    dd = ft.Dropdown(
        label="Rol", value="comun",
        options=[ft.DropdownOption(key=k, text=et)
                 for k, et in ROLES],
        **es.borde_textfield(12),
    )

    def guardar(e):
        if (tf_p.value or "") != (tf_p2.value or ""):
            snack(page, "Las contraseñas no coinciden", "error")
            return
        try:
            usuarios_mod.crear_usuario(
                tf_u.value, tf_p.value, dd.value,
                solicitante=app.usuario)
            page.pop_dialog()
            on_ok()
            snack(page, "Usuario creado", "ok")
        except Exception as ex:
            snack(page, str(ex), "error")

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Nuevo usuario"),
        content=ft.Column([tf_u, tf_p, tf_p2, dd],
                          tight=True, width=320, spacing=10,
                          scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Crear", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))