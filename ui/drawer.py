"""
Panel lateral (contenido).
Se usa dentro de un Stack en app.abrir_drawer().
El drawer ahora es secundario: las acciones principales están
en Perfil. Aquí solo atajos rápidos.
"""
import flet as ft
from ui import estilos as es


def construir_drawer_panel(app):
    page = app.page
    u = app.usuario

    def cerrar():
        app.cerrar_drawer()

    def ir_a(ruta):
        def _h(e):
            cerrar()
            async def _nav():
                import asyncio
                await asyncio.sleep(0.12)
                app.ir(ruta)
            page.run_task(_nav)
        return _h

    def abrir_tipos(e):
        cerrar()
        async def _nav():
            import asyncio
            await asyncio.sleep(0.12)
            from ui.principal import _abrir_selector_tipo
            try:
                _abrir_selector_tipo(app)
            except Exception as ex:
                print(f"[DRAWER] error abriendo tipos: {ex}")
        page.run_task(_nav)

    def cerrar_sesion(e):
        cerrar()
        async def _nav():
            import asyncio
            await asyncio.sleep(0.12)
            app.cerrar_sesion()
        page.run_task(_nav)

    async def task_exportar_excel(e):
        cerrar()
        import asyncio
        await asyncio.sleep(0.12)
        from ui.exportar import exportar_excel
        await exportar_excel(app)

    async def task_backup_interno(e):
        cerrar()
        import asyncio
        await asyncio.sleep(0.12)
        from ui.exportar import backup_interno
        await backup_interno(app)

    def cb_excel(e):
        page.run_task(task_exportar_excel, e)

    def cb_backup_interno(e):
        page.run_task(task_backup_interno, e)

    rol = u["rol"]

    header = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.PERSON,
                                    color=es.COLOR_ACENTO, size=22),
                    bgcolor=es.COLOR_ACENTO_SUAVE,
                    padding=10, border_radius=50),
                ft.IconButton(
                    ft.Icons.CLOSE,
                    icon_color=es.COLOR_TEXTO_SUAVE,
                    icon_size=20,
                    tooltip="Cerrar menú",
                    on_click=lambda e: cerrar(),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=6),
            ft.Text(u["username"], size=17,
                    weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
            ft.Text(u["rol"].capitalize(), size=11,
                    color=es.COLOR_TEXTO_SUAVE),
        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.START),
        padding=ft.Padding.only(left=16, top=20, right=8, bottom=20),
        bgcolor=es.COLOR_SUPERFICIE_2,
    )

    def tile(icono, texto, on_click, color=None):
        color = color or es.COLOR_ACENTO
        return ft.ListTile(
            leading=ft.Icon(icono, color=color, size=22),
            title=ft.Text(texto, size=14, color=es.COLOR_TEXTO),
            on_click=on_click,
        )

    tiles = []

    # ── Atajos rápidos ──
    tiles.append(tile(ft.Icons.HOME, "Inicio",
                      ir_a("/principal")))
    if rol in ("admin", "almacen"):
        tiles.append(tile(ft.Icons.POINT_OF_SALE, "Nueva venta (POS)",
                          ir_a("/pos"), color=es.COLOR_EXITO))
    tiles.append(tile(ft.Icons.RECEIPT_LONG, "Órdenes de venta",
                      ir_a("/ordenes"), color=es.COLOR_AMBAR))
    tiles.append(tile(ft.Icons.PEOPLE_OUTLINE, "Clientes",
                      ir_a("/clientes"), color=es.COLOR_INFO))
    tiles.append(tile(ft.Icons.LOCK_CLOCK, "Caja",
                      ir_a("/caja"), color=es.COLOR_ACENTO))

    tiles.append(ft.Divider(height=1, color=es.COLOR_BORDE))

    # ── Administración ──
    if rol in ("admin", "almacen"):
        tiles.append(tile(ft.Icons.CATEGORY, "Tipos de producto",
                          abrir_tipos, color=es.COLOR_INFO))
        tiles.append(tile(ft.Icons.TUNE, "Umbrales de colores",
                          ir_a("/umbrales"), color=es.COLOR_AMBAR))
        tiles.append(tile(ft.Icons.STORE, "Datos del negocio",
                          ir_a("/config-negocio"), color=es.COLOR_EXITO))

    if rol == "admin":
        tiles.append(tile(ft.Icons.STOREFRONT, "Administrar locales",
                          ir_a("/admin-locales")))
        tiles.append(tile(ft.Icons.PEOPLE, "Gestionar usuarios",
                          ir_a("/usuarios"), color=es.COLOR_PELIGRO))

    tiles.append(ft.Divider(height=1, color=es.COLOR_BORDE))

    # ── Datos ──
    if rol in ("admin", "almacen"):
        tiles.append(tile(ft.Icons.TABLE_CHART, "Exportar Excel",
                          cb_excel, color=es.COLOR_EXITO))
        tiles.append(tile(ft.Icons.SAVE, "Hacer backup rápido",
                          cb_backup_interno))

    tiles.append(ft.Divider(height=1, color=es.COLOR_BORDE))

    # ── Sesión ──
    tiles.append(tile(ft.Icons.LOGOUT, "Cerrar sesión", cerrar_sesion,
                    color=es.COLOR_PELIGRO))

    return ft.Column(
        [
            header,
            ft.Container(
                content=ft.Column(tiles, spacing=0,
                                scroll=ft.ScrollMode.AUTO),
                expand=True,
                padding=ft.Padding.only(bottom=20),
            ),
        ],
        spacing=0,
        expand=True,
    )