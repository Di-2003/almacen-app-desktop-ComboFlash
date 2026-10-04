"""
Perfil de usuario + configuración + administración + datos.
"""
import flet as ft
import inventario as inv
from ui import estilos as es
from ui.componentes import (
    snack, bottom_sheet, ruta_asset, imagen_opcional, mounted,
)
from ui.principal import barra_navegacion


def _tile(icono, titulo, subtitulo, on_click, color=None):
    color = color or es.COLOR_ACENTO
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Icon(icono, color=color, size=22),
                    bgcolor=ft.Colors.with_opacity(0.15, color),
                    padding=10, border_radius=12,
                ),
                ft.Column(
                    [
                        ft.Text(titulo, size=14,
                                weight=ft.FontWeight.W_600,
                                color=es.COLOR_TEXTO),
                        ft.Text(subtitulo, size=11,
                                color=es.COLOR_TEXTO_SUAVE)
                        if subtitulo else ft.Container(height=1),
                    ],
                    spacing=2, expand=True,
                ),
                ft.Icon(ft.Icons.CHEVRON_RIGHT,
                        color=es.COLOR_TEXTO_TENUE, size=20),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=14,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=14,
        on_click=on_click,
        ink=True,
    )


def _tile_switch(icono, titulo, subtitulo, valor, on_change, color=None):
    color = color or es.COLOR_ACENTO
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Icon(icono, color=color, size=22),
                    bgcolor=ft.Colors.with_opacity(0.15, color),
                    padding=10, border_radius=12,
                ),
                ft.Column(
                    [
                        ft.Text(titulo, size=14,
                                weight=ft.FontWeight.W_600,
                                color=es.COLOR_TEXTO),
                        ft.Text(subtitulo, size=11,
                                color=es.COLOR_TEXTO_SUAVE)
                        if subtitulo else ft.Container(height=1),
                    ],
                    spacing=2, expand=True,
                ),
                ft.Switch(value=valor, on_change=on_change,
                          active_color=es.COLOR_ACENTO),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=14,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=14,
    )


def _seccion_label(texto):
    return ft.Text(texto.upper(), size=11,
                   weight=ft.FontWeight.BOLD,
                   color=es.COLOR_TEXTO_TENUE)


def vista_perfil(app):
    u = app.usuario
    page = app.page

    # ---------- acciones ----------

    def abrir_perfil(e):
        _modal_editar_perfil(app)

    def abrir_umbrales(e):
        app.ir("/umbrales")

    def abrir_usuarios(e):
        app.ir("/usuarios")

    def abrir_locales(e):
        app.ir("/admin-locales")

    def cerrar_sesion(e):
        app.cerrar_sesion()

    def toggle_tema(e):
        nuevo = "oscuro" if e.control.value else "claro"
        try:
            inv.set_config("tema", nuevo)
        except Exception:
            pass
        es.aplicar_tema(nuevo)
        page.theme_mode = (ft.ThemeMode.DARK if nuevo == "oscuro"
                           else ft.ThemeMode.LIGHT)
        page.bgcolor = es.COLOR_FONDO
        app.refrescar()

    # ---------- datos (Excel / BD) ----------

    def export_excel(e):
        from ui.exportar import exportar_excel
        page.run_task(exportar_excel, app)

    def export_backup(e):
        from ui.exportar import exportar_backup
        page.run_task(exportar_backup, app)

    def import_backup(e):
        from ui.exportar import importar_backup
        page.run_task(importar_backup, app)

    def backup_ahora(e):
        from ui.exportar import backup_ahora as bk
        bk(app)

    # ---------- header ----------

    logo_fallback = ft.Container(
        content=ft.Icon(ft.Icons.INVENTORY_2,
                        color=es.COLOR_ACENTO, size=30),
        width=56, height=56, alignment=ft.Alignment.CENTER,
    )
    logo = imagen_opcional("icon.png", logo_fallback,
                           width=56, height=56)

    header = ft.Container(
        content=ft.Row(
            [
                logo,
                ft.Column(
                    [
                        ft.Text(u["username"], size=20,
                                weight=ft.FontWeight.BOLD,
                                color=es.COLOR_TEXTO),
                        ft.Container(
                            content=ft.Text(
                                u["rol"].capitalize(),
                                size=11,
                                color=es.COLOR_MARCA_NEGRO,
                                weight=ft.FontWeight.BOLD),
                            bgcolor=es.COLOR_ACENTO,
                            padding=ft.Padding.symmetric(
                                horizontal=10, vertical=3),
                            border_radius=20,
                        ),
                    ],
                    spacing=6, expand=True,
                ),
            ],
            spacing=14,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=20,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=20,
    )

    # ---------- bloques ----------

    bloques = [
        header,
        ft.Container(height=20),
        _seccion_label("Cuenta"),
        _tile(ft.Icons.EDIT, "Editar perfil",
              "Cambiar usuario o contraseña", abrir_perfil,
              color=es.COLOR_INFO),
        ft.Container(height=16),
        _seccion_label("Configuración"),
        _tile_switch(
            ft.Icons.DARK_MODE, "Modo oscuro",
            "Alternar entre tema claro y oscuro",
            es.es_oscuro(), toggle_tema,
            color="#8b5cf6"),
    ]

    if u["rol"] in ("admin", "almacen"):
        bloques += [
            ft.Container(height=8),
            _tile(ft.Icons.TUNE, "Umbrales de colores",
                  "Ajustar límites verde/amarillo por producto",
                  abrir_umbrales,
                  color=es.COLOR_AMBAR),
        ]

    if u["rol"] == "admin":
        bloques += [
            ft.Container(height=16),
            _seccion_label("Administración"),
            _tile(ft.Icons.STOREFRONT, "Administrar locales",
                  "Abrir, renombrar o cerrar tiendas",
                  abrir_locales,
                  color=es.COLOR_ACENTO),
            _tile(ft.Icons.PEOPLE, "Gestionar usuarios",
                  "Crear, editar o eliminar usuarios",
                  abrir_usuarios,
                  color=es.COLOR_PELIGRO),
        ]

    # Datos: admin + almacén
    if u["rol"] in ("admin", "almacen"):
        bloques += [
            ft.Container(height=16),
            _seccion_label("Datos"),
            _tile(ft.Icons.TABLE_CHART, "Exportar Excel",
                  "Genera el libro completo con todos los locales",
                  export_excel, color=es.COLOR_EXITO),
            _tile(ft.Icons.SAVE, "Exportar copia de seguridad",
                  "Descarga el archivo .db completo",
                  export_backup, color=es.COLOR_INFO),
            _tile(ft.Icons.UPLOAD, "Importar copia de seguridad",
                  "Reemplaza la BD actual con un archivo .db",
                  import_backup, color=es.COLOR_AMBAR),
            _tile(ft.Icons.ARCHIVE, "Backup interno ahora",
                  "Copia la BD a la carpeta backups/",
                  backup_ahora, color=es.COLOR_TEXTO_SUAVE),
        ]

    bloques += [
        ft.Container(height=24),
        ft.OutlinedButton(
            "Cerrar sesión",
            icon=ft.Icons.LOGOUT,
            on_click=cerrar_sesion,
            width=10000, height=48,
            style=ft.ButtonStyle(
                color=es.COLOR_PELIGRO,
                side=ft.BorderSide(1, es.COLOR_PELIGRO),
                shape=ft.RoundedRectangleBorder(
                    radius=ft.BorderRadius.all(12)),
            ),
        ),
        ft.Container(height=24),
    ]

    contenido = ft.Container(
        content=ft.Column(
            controls=bloques,
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=ft.Padding.all(16),
        expand=True,
    )

    return ft.View(
        route="/perfil",
        controls=[contenido],
        appbar=ft.AppBar(
            title=ft.Text("Mi perfil", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            elevation=0,
        ),
        navigation_bar=barra_navegacion(app, 3),
        bgcolor=es.COLOR_FONDO,
    )


def _modal_editar_perfil(app):
    page = app.page
    import usuarios as um

    tf_u = ft.TextField(
        label="Usuario", value=app.usuario["username"],
        **es.estilo_textfield(12), height=54,
    )
    tf_a = ft.TextField(
        label="Contraseña actual", password=True,
        can_reveal_password=True,
        **es.estilo_textfield(12), height=54,
    )
    tf_n = ft.TextField(
        label="Nueva contraseña (opcional)", password=True,
        can_reveal_password=True,
        **es.estilo_textfield(12), height=54,
    )
    tf_n2 = ft.TextField(
        label="Repetir nueva", password=True,
        can_reveal_password=True,
        **es.estilo_textfield(12), height=54,
    )

    def guardar(e):
        n = tf_n.value or ""
        c = tf_n2.value or ""
        if (n or c) and n != c:
            snack(page, "Las contraseñas no coinciden", "error")
            return
        try:
            nuevo = um.actualizar_perfil(
                usuario_id=app.usuario["id"],
                nuevo_username=tf_u.value,
                password_actual=tf_a.value,
                nuevo_password=n if n else None)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        app.usuario = nuevo
        page.pop_dialog()
        snack(page, "Perfil actualizado", "ok")
        app.refrescar()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Editar perfil"),
        content=ft.Column(
            [tf_u, tf_a, tf_n, tf_n2],
            tight=True, width=320, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                        on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))