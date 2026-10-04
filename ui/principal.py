import flet as ft
import inventario as inv
import locales as loc
from db import GENERAL_ID
from ui import estilos as es
from ui.componentes import (
    fila_producto, snack, campo_busqueda, empty_state,
    bottom_sheet, ruta_asset, imagen_opcional, mounted,
)
from ui import modales


def barra_navegacion(app, indice):
    def cambiar(e):
        rutas = ["/principal", "/dashboard", "/movimientos", "/perfil"]
        app.ir(rutas[e.control.selected_index])

    return ft.NavigationBar(
        selected_index=indice,
        bgcolor=es.COLOR_SUPERFICIE,
        indicator_color=es.COLOR_ACENTO_SUAVE,
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED,
                selected_icon=ft.Icons.HOME,
                label="Inicio",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.BAR_CHART_OUTLINED,
                selected_icon=ft.Icons.BAR_CHART,
                label="Métricas",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.HISTORY_OUTLINED,
                selected_icon=ft.Icons.HISTORY,
                label="Historial",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.PERSON_OUTLINE,
                selected_icon=ft.Icons.PERSON,
                label="Perfil",
            ),
        ],
        on_change=cambiar,
    )


def _tarjeta_resumen(total, n_productos, n_rojo=0):
    extras = []
    if n_rojo > 0:
        extras.append(
            ft.Container(
                content=ft.Text(f"{n_rojo} en crítico",
                                size=10, color="white",
                                weight=ft.FontWeight.BOLD),
                bgcolor=es.COLOR_PELIGRO,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=20,
            )
        )

    fila_sup = ft.Row(
        [
            ft.Container(
                content=ft.Icon(ft.Icons.INVENTORY_2,
                                color=es.COLOR_MARCA_NEGRO, size=18),
                bgcolor=es.COLOR_ACENTO,
                padding=10, border_radius=10,
            ),
            ft.Text("Valor del inventario", size=12,
                    color=es.COLOR_TEXTO_SUAVE,
                    weight=ft.FontWeight.W_600,
                    expand=True),
            ft.Container(
                content=ft.Text(f"{n_productos} prod.",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=es.COLOR_ACENTO),
                bgcolor=es.COLOR_ACENTO_SUAVE,
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=20,
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    fila_valor = ft.Text(
        f"${total:,.2f}",
        size=22, weight=ft.FontWeight.BOLD,
        color=es.COLOR_TEXTO,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    contenido = [fila_sup, ft.Container(height=6), fila_valor]
    if extras:
        contenido += [ft.Container(height=6), ft.Row(extras, spacing=6)]

    return ft.Container(
        content=ft.Column(contenido, spacing=0),
        padding=14,
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=16,
        shadow=ft.BoxShadow(
            blur_radius=10, spread_radius=0,
            color=es.SOMBRA_CARD,
            offset=ft.Offset(0, 2),
        ),
    )


def _chip_local(app):
    """Chip con el local actual, tocable para abrir el selector."""
    nombre = loc.nombre_local(app.local_id)

    def abrir_selector(e):
        _abrir_selector_local(app)

    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.STOREFRONT,
                        color=es.COLOR_ACENTO, size=18),
                ft.Text(nombre, size=13,
                        weight=ft.FontWeight.W_600,
                        color=es.COLOR_TEXTO),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN,
                        color=es.COLOR_ACENTO, size=18),
            ],
            spacing=6,
            tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor=es.COLOR_ACENTO_SUAVE,
        border_radius=20,
        on_click=abrir_selector,
        ink=True,
    )


def _abrir_selector_local(app):
    page = app.page
    items = loc.listar_para_menu()
    actual = app.local_id

    def elegir(lid):
        def _hacer(e):
            page.pop_dialog()
            app.cambiar_local(lid)
        return _hacer

    tiles = []
    for lid, nombre in items:
        es_actual = (lid == actual)
        icono = (ft.Icons.STAR if es_actual
                 else ft.Icons.STOREFRONT_OUTLINED)
        color = es.COLOR_ACENTO if es_actual else es.COLOR_TEXTO_SUAVE
        tiles.append(ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icono, color=color, size=20),
                    ft.Text(nombre, size=14,
                            color=es.COLOR_TEXTO,
                            weight=(ft.FontWeight.BOLD if es_actual
                                    else ft.FontWeight.NORMAL),
                            expand=True),
                    ft.Icon(ft.Icons.CHECK,
                            color=es.COLOR_ACENTO, size=20)
                    if es_actual else ft.Container(width=20),
                ],
                spacing=12,
            ),
            padding=14,
            bgcolor=(es.COLOR_ACENTO_SUAVE if es_actual
                    else es.COLOR_SUPERFICIE_2),
            border_radius=10,
            on_click=elegir(lid),
            ink=True,
        ))

    contenido = ft.Column(
        [
            ft.Text("Cambiar de local", size=16,
                    weight=ft.FontWeight.BOLD,
                    color=es.COLOR_TEXTO),
            ft.Container(height=4),
            ft.Column(tiles, spacing=6),
        ],
        spacing=6, tight=True,
    )
    page.show_dialog(bottom_sheet(contenido))

def vista_principal(app):
    page = app.page

    contenedor_resumen = ft.Container()

    lista_cont = ft.Column(
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    def refrescar():
        try:
            lista_cont.controls.clear()
            productos = inv.listar_productos(
                app.local_id,
                solo_activos=not app.ver_inactivos,
            )
            f = app.filtro
            if f:
                productos = [
                    p for p in productos
                    if f in p["nombre"].lower()
                    or f in (p.get("codigo") or "").lower()
                ]

            for p in productos:
                lista_cont.controls.append(fila_producto(
                    p,
                    on_tap=lambda e, prod=p:
                        modales.abrir_detalle_producto(
                            app, prod, on_refresh=refrescar)))

            if not productos:
                lista_cont.controls.append(empty_state(
                    ft.Icons.INBOX_OUTLINED,
                    "Sin productos",
                    ("No hay coincidencias para tu búsqueda."
                    if f else
                    ("No hay inactivos en este local."
                    if app.ver_inactivos else
                    "Empieza agregando tu primer producto.")),
                ))

            t = inv.totales_local(app.local_id)
            n_rojo = len([p for p in productos
                        if inv.color_de_producto(p) == "rojo"])
            contenedor_resumen.content = _tarjeta_resumen(
                t["invertido"], len(productos), n_rojo
            )

            # Solo actualizar si los controles ya están montados.
            # En el primer render, vista_principal se llama antes de que
            # el View esté en la página, así que update() fallaría.
            if mounted(lista_cont):
                lista_cont.update()
            if mounted(contenedor_resumen):
                contenedor_resumen.update()
        except Exception as ex:
            print(f"[ERROR] refrescar(): {ex}")
            import traceback
            traceback.print_exc()

    def on_search(e):
        app.filtro = (e.control.value or "").lower()
        refrescar()

    cap = campo_busqueda(
        hint="Buscar producto por nombre o código…",
        valor=app.filtro,
        on_change=on_search,
    )

    def abrir_entrada(e):
        modales.modal_entrada(app, on_refresh=refrescar)

    def abrir_salida(e):
        modales.modal_salida(app, on_refresh=refrescar)

    def toggle_inactivos(e):
        app.ver_inactivos = not app.ver_inactivos
        app.refrescar()

    rol = app.usuario["rol"]
    puede_operar = rol in ("admin", "almacen") and not app.es_general()

    if puede_operar:
        botones = ft.Row(
            [
                ft.FilledButton(
                    "Entrada", icon=ft.Icons.ADD,
                    on_click=abrir_entrada,
                    expand=True, height=46,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_EXITO, color="white",
                        shape=ft.RoundedRectangleBorder(
                            radius=ft.BorderRadius.all(12)),
                    ),
                ),
                ft.FilledButton(
                    "Salida", icon=ft.Icons.REMOVE,
                    on_click=abrir_salida,
                    expand=True, height=46,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_PELIGRO, color="white",
                        shape=ft.RoundedRectangleBorder(
                            radius=ft.BorderRadius.all(12)),
                    ),
                ),
            ],
            spacing=10,
        )
    else:
        botones = ft.Container(height=0)

    activo_toggle = app.ver_inactivos
    toggle_row = ft.Row(
        [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.FILTER_ALT,
                            size=14,
                            color=(es.COLOR_MARCA_NEGRO if activo_toggle
                                   else es.COLOR_TEXTO_SUAVE),
                        ),
                        ft.Text(
                            "Todos" if activo_toggle else "Inactivos",
                            size=11,
                            color=(es.COLOR_MARCA_NEGRO if activo_toggle
                                   else es.COLOR_TEXTO_SUAVE),
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                    spacing=6, tight=True,
                ),
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                bgcolor=(es.COLOR_ACENTO if activo_toggle
                         else es.COLOR_SUPERFICIE),
                border=ft.Border.all(
                    1,
                    es.COLOR_ACENTO if activo_toggle
                    else es.COLOR_BORDE,
                ),
                border_radius=20,
                on_click=toggle_inactivos,
                ink=True,
            ),
        ],
        alignment=ft.MainAxisAlignment.END,
    )

    cabecera = ft.Container(
        content=ft.Column(
            [
                _chip_local(app),
                ft.Container(height=2),
                cap,
                ft.Container(height=2),
                contenedor_resumen,
                ft.Container(height=2),
                botones,
                toggle_row,
            ],
            spacing=8,
        ),
        padding=ft.Padding.only(left=14, top=14, right=14, bottom=4),
        bgcolor=es.COLOR_FONDO,
    )

    # Render inicial (no hace update() porque aún no está montado)
    refrescar()

    logo_fallback = ft.Icon(ft.Icons.INVENTORY_2,
                            color=es.COLOR_ACENTO, size=26)
    logo = imagen_opcional("icon.png", logo_fallback,
                           width=30, height=30)

    return ft.View(
        route="/principal",
        controls=[
            cabecera,
            ft.Container(content=lista_cont, expand=True),
        ],
        appbar=ft.AppBar(
            title=ft.Row(
                [logo,
                 ft.Text("Almacén Raidel", size=15,
                         color=es.COLOR_TEXTO)],
                spacing=8,
            ),
            bgcolor=es.COLOR_SUPERFICIE,
            elevation=0,
            actions=[
                ft.IconButton(
                    ft.Icons.REFRESH,
                    on_click=lambda e: (refrescar(),
                                        snack(page, "Actualizado", "ok")),
                    icon_color=es.COLOR_ACENTO,
                ),
            ],
        ),
        navigation_bar=barra_navegacion(app, 0),
        bgcolor=es.COLOR_FONDO,
    )

