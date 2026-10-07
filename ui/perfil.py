"""
Perfil de usuario + configuración + administración + datos.
Incluye selector de moneda de visualización y recálculo automático
de precios al cambiar las tasas.
"""
import flet as ft
import inventario as inv
from ui import estilos as es
from ui.componentes import snack, imagen_opcional, cerrar_dialogo
from ui.principal import barra_navegacion


def _fmt_num(x) -> str:
    try:
        f = float(x)
        if f.is_integer():
            return str(int(f))
        return f"{f:g}"
    except (TypeError, ValueError):
        return "1"


def _subtitulo_tasa(clave, moneda):
    try:
        tasa = float(inv.get_config(clave) or 1.0)
    except (TypeError, ValueError):
        tasa = 1.0
    return f"1 {moneda} = {_fmt_num(tasa)} CUP"


def _tile(icono, titulo, subtitulo, on_click, color=None):
    color = color or es.COLOR_ACENTO
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(icono, color=color, size=22),
                bgcolor=ft.Colors.with_opacity(0.15, color),
                padding=10, border_radius=12),
            ft.Column([
                ft.Text(titulo, size=14, weight=ft.FontWeight.W_600,
                        color=es.COLOR_TEXTO),
                ft.Text(subtitulo, size=11, color=es.COLOR_TEXTO_SUAVE,
                        max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)
                if subtitulo else ft.Container(height=1),
            ], spacing=2, expand=True),
            ft.Icon(ft.Icons.CHEVRON_RIGHT,
                    color=es.COLOR_TEXTO_TENUE, size=20),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=14, bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=14, on_click=on_click, ink=True)


def _tile_switch(icono, titulo, subtitulo, valor, on_change, color=None):
    color = color or es.COLOR_ACENTO
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(icono, color=color, size=22),
                bgcolor=ft.Colors.with_opacity(0.15, color),
                padding=10, border_radius=12),
            ft.Column([
                ft.Text(titulo, size=14, weight=ft.FontWeight.W_600,
                        color=es.COLOR_TEXTO),
                ft.Text(subtitulo, size=11, color=es.COLOR_TEXTO_SUAVE)
                if subtitulo else ft.Container(height=1),
            ], spacing=2, expand=True),
            ft.Switch(value=valor, on_change=on_change,
                      active_color=es.COLOR_ACENTO),
        ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=14, bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE), border_radius=14)


def _seccion_label(texto):
    return ft.Text(texto.upper(), size=11, weight=ft.FontWeight.BOLD,
                   color=es.COLOR_TEXTO_TENUE)


async def _task_backup_destino(app):
    from ui.exportar import backup_destino
    await backup_destino(app)
    app.refrescar()


async def _task_backup_interno(app):
    from ui.exportar import backup_interno
    await backup_interno(app)


async def _task_exportar_excel(app):
    from ui.exportar import exportar_excel
    await exportar_excel(app)


async def _task_importar_backup(app):
    from ui.exportar import importar_backup
    await importar_backup(app)


def vista_perfil(app):
    u = app.usuario
    page = app.page

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

    def configurar_moneda_visualizacion(e):
        _dlg_moneda_visualizacion(app)

    def configurar_tasa_usd(e):
        _dlg_tasa(app, "tasa_usd", "Tasa USD → CUP",
                  "CUP por 1 USD", "USD")

    def configurar_tasa_eur(e):
        _dlg_tasa(app, "tasa_eur", "Tasa EUR → CUP",
                  "CUP por 1 EUR", "EUR")

    def cb_exportar_excel(e):
        page.run_task(_task_exportar_excel, app)

    def cb_importar_backup(e):
        page.run_task(_task_importar_backup, app)

    def cb_backup_destino(e):
        page.run_task(_task_backup_destino, app)

    def cb_backup_interno(e):
        page.run_task(_task_backup_interno, app)

    logo_fallback = ft.Container(
        content=ft.Icon(ft.Icons.INVENTORY_2,
                        color=es.COLOR_ACENTO, size=30),
        width=56, height=56, alignment=ft.Alignment.CENTER)
    logo = imagen_opcional("icon.png", logo_fallback, width=56, height=56)

    header = ft.Container(
        content=ft.Row([
            logo,
            ft.Column([
                ft.Text(u["username"], size=20,
                        weight=ft.FontWeight.BOLD,
                        color=es.COLOR_TEXTO),
                ft.Container(
                    content=ft.Text(u["rol"].capitalize(), size=11,
                                    color=es.COLOR_MARCA_NEGRO,
                                    weight=ft.FontWeight.BOLD),
                    bgcolor=es.COLOR_ACENTO,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=3),
                    border_radius=20),
            ], spacing=6, expand=True),
        ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=20, bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE), border_radius=20)

    sub_usd = _subtitulo_tasa("tasa_usd", "USD")
    sub_eur = _subtitulo_tasa("tasa_eur", "EUR")
    sub_mon = f"Ver precios en {inv.get_moneda_visualizacion()}"

    bloques = [
        header,
        ft.Container(height=20),
        _seccion_label("Cuenta"),
        _tile(ft.Icons.EDIT, "Editar perfil",
              "Cambiar usuario o contraseña", abrir_perfil,
              color=es.COLOR_INFO),
        ft.Container(height=16),
        _seccion_label("Configuración"),
        _tile_switch(ft.Icons.DARK_MODE, "Modo oscuro",
                     "Alternar entre tema claro y oscuro",
                     es.es_oscuro(), toggle_tema, color="#8b5cf6"),
        _tile(ft.Icons.VISIBILITY, "Moneda de visualización",
              sub_mon, configurar_moneda_visualizacion,
              color=es.COLOR_INFO),
        _tile(ft.Icons.ATTACH_MONEY, "Tasa de cambio USD",
              sub_usd, configurar_tasa_usd, color=es.COLOR_AMBAR),
        _tile(ft.Icons.EURO_SYMBOL, "Tasa de cambio EUR",
              sub_eur, configurar_tasa_eur, color=es.COLOR_AMBAR),
    ]

    if u["rol"] in ("admin", "almacen"):
        bloques += [
            ft.Container(height=8),
            _tile(ft.Icons.TUNE, "Umbrales de colores",
                  "Ajustar límites verde/amarillo por producto",
                  abrir_umbrales, color=es.COLOR_AMBAR),
        ]

    if u["rol"] == "admin":
        bloques += [
            ft.Container(height=16),
            _seccion_label("Administración"),
            _tile(ft.Icons.STOREFRONT, "Administrar locales",
                  "Abrir, renombrar o cerrar tiendas",
                  abrir_locales, color=es.COLOR_ACENTO),
            _tile(ft.Icons.PEOPLE, "Gestionar usuarios",
                  "Crear, editar o eliminar usuarios",
                  abrir_usuarios, color=es.COLOR_PELIGRO),
        ]

    if u["rol"] in ("admin", "almacen"):
        bloques += [
            ft.Container(height=16),
            _seccion_label("Datos"),
            _tile(ft.Icons.TABLE_CHART, "Exportar Excel",
                  "Genera el libro completo con todos los locales",
                  cb_exportar_excel, color=es.COLOR_EXITO),
            _tile(ft.Icons.UPLOAD, "Importar copia de seguridad",
                  "Reemplaza la BD actual con un archivo .db",
                  cb_importar_backup, color=es.COLOR_AMBAR),
            _tile(ft.Icons.FOLDER_OPEN, "Backup Destino",
                  "Elige carpeta destino de backup",
                  cb_backup_destino, color=es.COLOR_INFO),
            _tile(ft.Icons.SAVE, "Backup Interno",
                  "Backup en la carpeta destino",
                  cb_backup_interno, color=es.COLOR_ACENTO),
        ]

    bloques += [
        ft.Container(height=24),
        ft.OutlinedButton(
            "Cerrar sesión", icon=ft.Icons.LOGOUT,
            on_click=cerrar_sesion, width=10000, height=48,
            style=ft.ButtonStyle(
                color=es.COLOR_PELIGRO,
                side=ft.BorderSide(1, es.COLOR_PELIGRO),
                shape=ft.RoundedRectangleBorder(
                    radius=ft.BorderRadius.all(12)))),
        ft.Container(height=24),
    ]

    contenido = ft.Container(
        content=ft.Column(controls=bloques, spacing=8,
                          scroll=ft.ScrollMode.AUTO, expand=True),
        padding=ft.Padding.all(16), expand=True)

    return ft.View(
        route="/perfil", controls=[contenido],
        appbar=ft.AppBar(
            title=ft.Text("Mi perfil", size=16, color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE, elevation=0),
        navigation_bar=barra_navegacion(app, 3),
        bgcolor=es.COLOR_FONDO)


# ============ Diálogo de tasa ============

def _dlg_tasa(app, clave, titulo, label, moneda):
    page = app.page
    actual = _fmt_num(inv.get_config(clave) or "1")
    tf = ft.TextField(label=label, value=actual,
                      keyboard_type=ft.KeyboardType.NUMBER,
                      **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def guardar(e):
        error_lbl.value = ""
        try:
            valor = float((tf.value or "1").replace(",", "."))
            if valor <= 0:
                raise ValueError("Debe ser mayor que 0")
        except ValueError:
            error_lbl.value = "Valor inválido"
            page.update()
            return

        inv.set_config(clave, str(valor))

        # FASE 2: recalcular TODOS los precios en USD/EUR
        n = inv.recalcular_todos_los_precios()

        def _despues():
            snack(page,
                  f"1 {moneda} = {_fmt_num(valor)} CUP. "
                  f"{n} producto(s) actualizados.", "ok")
            app.refrescar()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    def cancelar(e):
        cerrar_dialogo(page, dlg_ref["dlg"])

    dlg = ft.AlertDialog(
        title=ft.Text(titulo),
        content=ft.Column([
            ft.Text("Al guardar, se recalcularán TODOS los precios "
                    "en USD/EUR de los productos con la nueva tasa. "
                    "Los productos en CUP no se modifican.",
                    size=12, color=es.COLOR_TEXTO_SUAVE),
            ft.Container(height=8),
            tf, error_lbl,
        ], tight=True, width=320, spacing=8),
        actions=[
            ft.TextButton("Cancelar", on_click=cancelar),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END)
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


# ============ Diálogo de moneda visualización ============

def _dlg_moneda_visualizacion(app):
    page = app.page
    actual = inv.get_moneda_visualizacion()
    dd = ft.Dropdown(
        label="Ver precios en",
        value=actual,
        options=[
            ft.DropdownOption(key="CUP", text="$  CUP"),
            ft.DropdownOption(key="USD", text="USD$  USD"),
            ft.DropdownOption(key="EUR", text="€  EUR"),
        ],
        **es.borde_textfield(12))
    dlg_ref = {"dlg": None}

    def guardar(e):
        inv.set_moneda_visualizacion(dd.value or "CUP")

        def _despues():
            snack(page, f"Moneda cambiada a {dd.value}", "ok")
            app.refrescar()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    def cancelar(e):
        cerrar_dialogo(page, dlg_ref["dlg"])

    dlg = ft.AlertDialog(
        title=ft.Text("Moneda de visualización"),
        content=ft.Column([
            ft.Text("Se usará para mostrar los totales y el margen "
                    "del dashboard.", size=12,
                    color=es.COLOR_TEXTO_SUAVE),
            ft.Container(height=8),
            dd,
        ], tight=True, width=300, spacing=8),
        actions=[
            ft.TextButton("Cancelar", on_click=cancelar),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END)
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


# ============ Editar perfil ============

def _modal_editar_perfil(app):
    page = app.page
    import usuarios as um

    tf_u = ft.TextField(label="Usuario",
                        value=app.usuario["username"],
                        **es.estilo_textfield(12), height=54)
    tf_a = ft.TextField(label="Contraseña actual", password=True,
                        can_reveal_password=True,
                        **es.estilo_textfield(12), height=54)
    tf_n = ft.TextField(label="Nueva contraseña (opcional)",
                        password=True, can_reveal_password=True,
                        **es.estilo_textfield(12), height=54)
    tf_n2 = ft.TextField(label="Repetir nueva", password=True,
                         can_reveal_password=True,
                         **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def guardar(e):
        error_lbl.value = ""
        n = tf_n.value or ""
        c = tf_n2.value or ""
        if (n or c) and n != c:
            error_lbl.value = "Las contraseñas no coinciden"
            page.update()
            return
        try:
            nuevo = um.actualizar_perfil(
                usuario_id=app.usuario["id"],
                nuevo_username=tf_u.value,
                password_actual=tf_a.value,
                nuevo_password=n if n else None)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        app.usuario = nuevo

        def _despues():
            snack(page, "Perfil actualizado", "ok")
            app.refrescar()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    def cancelar(e):
        cerrar_dialogo(page, dlg_ref["dlg"])

    dlg = ft.AlertDialog(
        title=ft.Text("Editar perfil"),
        content=ft.Column([tf_u, tf_a, tf_n, tf_n2, error_lbl],
                        tight=True, width=320, spacing=10,
                        scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar", on_click=cancelar),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END)
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)