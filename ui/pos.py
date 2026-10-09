"""
POS — Nueva Venta.
- Búsqueda por nombre/código + chips de categoría.
- Lista de productos con botón "+" para agregar al carrito.
- Carrito en bottom sheet con edición, cliente, descuento global.
- Modal de cobro con hasta 3 pagos y pago mixto.
- Al confirmar: registra venta + muestra ticket para compartir.
"""
import flet as ft
from db import GENERAL_ID
import inventario as inv
import categorias as cats
import locales as loc
import clientes as cli
import ventas as ven
import configuracion_negocio as cfg
from ui import estilos as es
from ui.componentes import (
    campo_busqueda, empty_state, snack, bottom_sheet, mounted,
    toast, copiar_portapapeles,
)
from ui._scroll import columna_scroll

PASO_PAGINACION = 40


def vista_pos(app):
    page = app.page

    if app.local_id == GENERAL_ID:
        return ft.View(
            route="/pos",
            controls=[empty_state(
                ft.Icons.POINT_OF_SALE, "Cambia de local",
                "El POS no funciona en la vista General.")],
            appbar=ft.AppBar(
                title=ft.Text("Nueva Venta", color=es.COLOR_TEXTO),
                bgcolor=es.COLOR_SUPERFICIE),
            navigation_bar=_nav(app, 1),
            bgcolor=es.COLOR_FONDO,
        )

    if app._carrito_pos is None:
        app._carrito_pos = ven.nuevo_carrito()

    estado = {"filtro": "", "cat": None, "visibles": PASO_PAGINACION}
    lista = columna_scroll("/pos", app, [], spacing=8)
    contenedor_carrito = ft.Container()

    # ─── BÚSQUEDA ───
    def on_search(e):
        estado["filtro"] = (e.control.value or "").lower()
        estado["visibles"] = PASO_PAGINACION
        refrescar()

    cap = campo_busqueda(
        hint="Buscar producto por nombre o código…",
        on_change=on_search,
    )

    # ─── CHIPS CATEGORÍA ───
    def chip_cat(cat_id, nombre, activo):
        def _click(e):
            estado["cat"] = cat_id
            estado["visibles"] = PASO_PAGINACION
            refrescar()
        return ft.Container(
            content=ft.Text(nombre, size=12,
                            color=("#ffffff" if activo
                                   else es.COLOR_TEXTO_SUAVE),
                            weight=ft.FontWeight.W_600),
            bgcolor=(es.COLOR_ACENTO if activo
                     else es.COLOR_SUPERFICIE),
            border=ft.Border.all(
                1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
            padding=ft.Padding.symmetric(horizontal=14, vertical=7),
            border_radius=20,
            on_click=_click,
            ink=True,
        )

    fila_cats = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=6)

    def rebuild_cats():
        fila_cats.controls.clear()
        fila_cats.controls.append(
            chip_cat(None, "Todos", estado["cat"] is None))
        for c in cats.listar_categorias(solo_activas=True):
            fila_cats.controls.append(
                chip_cat(c["id"], c["nombre"], estado["cat"] == c["id"]))
        if mounted(fila_cats):
            fila_cats.update()

    # ─── AGREGAR AL CARRITO ───
    def agregar(producto, cantidad=1):
        try:
            ven.agregar_item(app._carrito_pos, producto, cantidad)
        except Exception as ex:
            toast(page, str(ex), "error")
            return
        toast(page, f"+{inv.fmt_cantidad(cantidad)} {producto['nombre']}",
              "ok")
        refrescar_carrito()
        refrescar()

    # ─── FILA PRODUCTO POS ───
    def fila_pos(p):
        stock = float(p["stock"] or 0)
        color = inv.color_de_producto(p)
        c = {"verde": es.COLOR_VERDE, "amarillo": es.COLOR_AMARILLO,
             "rojo": es.COLOR_ROJO}.get(color, es.COLOR_TEXTO_TENUE)
        disponible = stock > 0

        def tap_add(e):
            if not disponible:
                toast(page, "Sin stock", "error")
                return
            agregar(p, 1)

        return ft.Container(
            content=ft.Row([
                ft.Container(width=6, height=44, bgcolor=c,
                             border_radius=3),
                ft.Column([
                    ft.Text(p["nombre"], size=14,
                            weight=ft.FontWeight.W_600,
                            color=es.COLOR_TEXTO, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        ft.Text(p.get("codigo") or "—", size=11,
                                color=es.COLOR_ACENTO,
                                weight=ft.FontWeight.BOLD),
                        ft.Text("·", size=11,
                                color=es.COLOR_TEXTO_TENUE),
                        ft.Text(f"Stock {inv.fmt_cantidad(stock)}",
                                size=11, color=es.COLOR_TEXTO_SUAVE),
                    ], spacing=6, tight=True),
                ], spacing=2, expand=True),
                ft.Column([
                    ft.Text(f"${inv.fmt_precio(p['precio_unitario'])}",
                            size=14, weight=ft.FontWeight.BOLD,
                            color=es.COLOR_ACENTO,
                            text_align=ft.TextAlign.RIGHT),
                    ft.Text("CUP", size=10,
                            color=es.COLOR_TEXTO_TENUE,
                            text_align=ft.TextAlign.RIGHT),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
                ft.IconButton(
                    ft.Icons.ADD_CIRCLE,
                    icon_color=(es.COLOR_EXITO if disponible
                                else es.COLOR_TEXTO_TENUE),
                    icon_size=32,
                    on_click=tap_add,
                ),
            ], spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            bgcolor=es.COLOR_SUPERFICIE,
            border=ft.Border.all(1, es.COLOR_BORDE),
            border_radius=12,
            on_click=tap_add,
            ink=disponible,
            opacity=1.0 if disponible else 0.5,
        )

    # ─── REFRESCAR LISTA ───
    def refrescar():
        lista.controls.clear()
        prods = inv.listar_productos(app.local_id, solo_activos=True)
        if estado["cat"] is not None:
            prods = [p for p in prods
                     if p.get("categoria_id") == estado["cat"]]
        f = estado["filtro"]
        if f:
            prods = [p for p in prods
                     if f in p["nombre"].lower()
                     or f in (p.get("codigo") or "").lower()]

        total = len(prods)
        visibles = prods[:estado["visibles"]]
        for p in visibles:
            lista.controls.append(fila_pos(p))

        if not prods:
            lista.controls.append(empty_state(
                ft.Icons.INBOX_OUTLINED, "Sin resultados",
                "Ajusta la búsqueda o el filtro."))
        elif total > estado["visibles"]:
            restantes = total - estado["visibles"]

            def mas(e):
                estado["visibles"] += PASO_PAGINACION
                refrescar()

            lista.controls.append(ft.Container(
                content=ft.TextButton(
                    f"Ver más ({restantes} restantes)",
                    icon=ft.Icons.EXPAND_MORE,
                    on_click=mas,
                    style=ft.ButtonStyle(color=es.COLOR_ACENTO)),
                alignment=ft.Alignment.CENTER, padding=16))

        if mounted(lista):
            lista.update()

    # ─── CARRITO — BOTÓN FLOTANTE ───
    def refrescar_carrito():
        tot = ven.calcular_totales(app._carrito_pos)
        n = sum(1 for _ in app._carrito_pos["items"])
        if n == 0:
            contenedor_carrito.content = ft.Container()
        else:
            contenedor_carrito.content = ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(str(n), size=14,
                                        color="#ffffff",
                                        weight=ft.FontWeight.BOLD),
                        bgcolor=es.COLOR_PELIGRO,
                        padding=ft.Padding.symmetric(
                            horizontal=10, vertical=4),
                        border_radius=20),
                    ft.Text("Ver carrito", size=15,
                            color="#ffffff",
                            weight=ft.FontWeight.BOLD, expand=True),
                    ft.Text(f"${tot['total']:,.2f}", size=16,
                            color="#ffffff",
                            weight=ft.FontWeight.BOLD),
                ], spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                bgcolor=es.COLOR_ACENTO,
                border_radius=30,
                on_click=lambda e: _abrir_carrito(app, refrescar,
                                                   refrescar_carrito),
                ink=True,
                shadow=ft.BoxShadow(
                    blur_radius=20, spread_radius=0,
                    color="#00000066",
                    offset=ft.Offset(0, 4)),
            )
        if mounted(contenedor_carrito):
            contenedor_carrito.update()

    rebuild_cats()
    refrescar()
    refrescar_carrito()

    return ft.View(
        route="/pos",
        controls=[
            ft.Container(
                content=ft.Column([
                    cap,
                    ft.Container(height=2),
                    fila_cats,
                ], spacing=6),
                padding=ft.Padding.only(left=14, top=14,
                                        right=14, bottom=6)),
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.only(left=14, right=14)),
            ft.Container(
                content=contenedor_carrito,
                padding=ft.Padding.only(left=14, right=14,
                                        top=8, bottom=14)),
        ],
        appbar=ft.AppBar(
            title=ft.Text(
                f"Nueva Venta — {loc.nombre_local(app.local_id)}",
                size=15, color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.CLOSE,
                on_click=lambda e: _salir_pos(app),
                icon_color=es.COLOR_ACENTO),
            actions=[
                ft.IconButton(
                    ft.Icons.DELETE_SWEEP,
                    tooltip="Vaciar carrito",
                    on_click=lambda e: _vaciar(app, refrescar_carrito),
                    icon_color=es.COLOR_PELIGRO),
            ],
        ),
        navigation_bar=_nav(app, 1),
        bgcolor=es.COLOR_FONDO,
    )


# ────────────────────────────────────────────────────────────
# NAV
# ────────────────────────────────────────────────────────────

def _nav(app, indice):
    def cambiar(e):
        rutas = ["/principal", "/pos", "/dashboard",
                 "/movimientos", "/perfil"]
        app.ir(rutas[e.control.selected_index])

    return ft.NavigationBar(
        selected_index=indice,
        bgcolor=es.COLOR_SUPERFICIE,
        indicator_color=es.COLOR_ACENTO_SUAVE,
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED,
                selected_icon=ft.Icons.HOME, label="Inicio"),
            ft.NavigationBarDestination(
                icon=ft.Icons.POINT_OF_SALE_OUTLINED,
                selected_icon=ft.Icons.POINT_OF_SALE, label="POS"),
            ft.NavigationBarDestination(
                icon=ft.Icons.BAR_CHART_OUTLINED,
                selected_icon=ft.Icons.BAR_CHART, label="Métricas"),
            ft.NavigationBarDestination(
                icon=ft.Icons.HISTORY_OUTLINED,
                selected_icon=ft.Icons.HISTORY, label="Historial"),
            ft.NavigationBarDestination(
                icon=ft.Icons.PERSON_OUTLINE,
                selected_icon=ft.Icons.PERSON, label="Perfil"),
        ],
        on_change=cambiar,
    )


def _salir_pos(app):
    if app._carrito_pos and app._carrito_pos["items"]:
        page = app.page

        def confirmar(e):
            page.pop_dialog()
            app._carrito_pos = ven.nuevo_carrito()
            app.ir("/principal")

        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Salir del POS"),
            content=ft.Text(
                "Tienes un carrito con productos. ¿Salir sin cobrar?",
                color=es.COLOR_TEXTO),
            actions=[
                ft.TextButton("Seguir aquí",
                              on_click=lambda e: page.pop_dialog()),
                ft.FilledButton(
                    "Salir", on_click=confirmar,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_PELIGRO, color="white")),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))
    else:
        app.ir("/principal")


def _vaciar(app, on_change):
    carrito = app._carrito_pos
    if not carrito["items"]:
        return
    page = app.page

    def hacer(e):
        carrito["items"].clear()
        carrito["cliente_id"] = None
        carrito["descuento_global_pct"] = 0
        page.pop_dialog()
        on_change()
        snack(page, "Carrito vaciado", "info")

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Vaciar carrito"),
        content=ft.Text("¿Eliminar todos los productos?",
                        color=es.COLOR_TEXTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Vaciar", on_click=hacer,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_PELIGRO, color="white")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


# ────────────────────────────────────────────────────────────
# CARRITO (bottom sheet)
# ────────────────────────────────────────────────────────────

def _abrir_carrito(app, on_refresh_lista, on_refresh_carrito):
    page = app.page
    carrito = app._carrito_pos
    bs_ref = {"bs": None}
    contenido_col = ft.Column(spacing=8, tight=True)

    def rebuild():
        contenido_col.controls.clear()
        tot = ven.calcular_totales(carrito)

        # Items
        if not carrito["items"]:
            contenido_col.controls.append(empty_state(
                ft.Icons.SHOPPING_CART_OUTLINED, "Carrito vacío",
                "Agrega productos desde la lista."))
        else:
            for i, it in enumerate(carrito["items"]):
                contenido_col.controls.append(_item_carrito(
                    app, i, it, rebuild, on_refresh_lista,
                    on_refresh_carrito))

        # Cliente
        contenido_col.controls.append(ft.Divider(
            height=1, color=es.COLOR_BORDE))
        contenido_col.controls.append(_selector_cliente(app, rebuild))

        # Descuento global
        contenido_col.controls.append(_campo_descuento(app, rebuild))

        # Totales
        contenido_col.controls.append(ft.Container(
            content=ft.Column([
                _fila_total("Subtotal", f"${tot['subtotal']:,.2f}"),
                _fila_total("Descuento",
                            f"-${tot['descuento']:,.2f}",
                            color=es.COLOR_PELIGRO)
                if tot["descuento"] > 0 else ft.Container(height=0),
                ft.Divider(height=1, color=es.COLOR_BORDE),
                _fila_total("TOTAL", f"${tot['total']:,.2f}",
                            grande=True),
            ], spacing=6),
            padding=14,
            bgcolor=es.COLOR_SUPERFICIE_2,
            border_radius=12,
            margin=ft.Margin.only(top=4),
        ))

        # Botón cobrar
        if carrito["items"]:
            contenido_col.controls.append(ft.Container(
                content=ft.FilledButton(
                    f"Cobrar ${tot['total']:,.2f}",
                    icon=ft.Icons.PAYMENTS,
                    on_click=lambda e: _abrir_cobro(
                        app, bs_ref["bs"], rebuild,
                        on_refresh_lista, on_refresh_carrito),
                    width=10000, height=52,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_ACENTO, color="#ffffff",
                        shape=ft.RoundedRectangleBorder(
                            radius=ft.BorderRadius.all(12)))),
                padding=ft.Padding.only(top=8, bottom=4),
            ))

        if mounted(contenido_col):
            contenido_col.update()

    rebuild()
    bs = bottom_sheet(contenido_col, page=page, alto_max_pct=0.9)
    bs_ref["bs"] = bs
    page.show_dialog(bs)


def _item_carrito(app, idx, it, rebuild, on_refresh_lista,
                  on_refresh_carrito):
    page = app.page
    carrito = app._carrito_pos
    sub = ven.subtotal_item(it)

    def menos(e):
        try:
            if it["cantidad"] > 1:
                ven.editar_item(carrito, idx,
                                cantidad=it["cantidad"] - 1)
            else:
                ven.eliminar_item(carrito, idx)
        except Exception as ex:
            toast(page, str(ex), "error")
        rebuild()
        on_refresh_carrito()

    def mas(e):
        try:
            ven.editar_item(carrito, idx,
                            cantidad=it["cantidad"] + 1)
        except Exception as ex:
            toast(page, str(ex), "error")
        rebuild()
        on_refresh_carrito()

    def quitar(e):
        ven.eliminar_item(carrito, idx)
        rebuild()
        on_refresh_carrito()
        on_refresh_lista()

    def editar(e):
        _editar_item(app, idx, rebuild, on_refresh_carrito)

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(it["nombre"], size=13,
                            weight=ft.FontWeight.W_600,
                            color=es.COLOR_TEXTO, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(
                        f"${inv.fmt_precio(it['precio'])}"
                        + (f" · desc ${inv.fmt_precio(it['rebaja'])}"
                           if it["rebaja"] > 0 else ""),
                        size=11, color=es.COLOR_TEXTO_SUAVE),
                ], spacing=2, expand=True),
                ft.IconButton(ft.Icons.CLOSE, icon_size=18,
                              icon_color=es.COLOR_PELIGRO,
                              on_click=quitar,
                              tooltip="Quitar"),
            ]),
            ft.Row([
                ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE,
                              icon_color=es.COLOR_PELIGRO, on_click=menos),
                ft.Text(inv.fmt_cantidad(it["cantidad"]), size=15,
                        weight=ft.FontWeight.BOLD,
                        color=es.COLOR_TEXTO, width=40,
                        text_align=ft.TextAlign.CENTER),
                ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE,
                              icon_color=es.COLOR_EXITO, on_click=mas),
                ft.Container(expand=True),
                ft.TextButton("Editar", icon=ft.Icons.EDIT,
                              on_click=editar,
                              style=ft.ButtonStyle(
                                  color=es.COLOR_ACENTO)),
                ft.Text(f"${sub:,.2f}", size=15,
                        weight=ft.FontWeight.BOLD,
                        color=es.COLOR_ACENTO),
            ], spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
        ], spacing=4),
        padding=10,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=12,
    )


def _editar_item(app, idx, rebuild, on_refresh_carrito):
    page = app.page
    carrito = app._carrito_pos
    it = carrito["items"][idx]

    tf_c = ft.TextField(label="Cantidad",
                        value=inv.fmt_cantidad(it["cantidad"]),
                        keyboard_type=ft.KeyboardType.NUMBER,
                        **es.estilo_textfield(12), height=54)
    tf_r = ft.TextField(label="Rebaja por unidad (CUP)",
                        value=inv.fmt_precio(it["rebaja"]),
                        keyboard_type=ft.KeyboardType.NUMBER,
                        **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            c = float((tf_c.value or "0").replace(",", "."))
            r = float((tf_r.value or "0").replace(",", "."))
            ven.editar_item(carrito, idx, cantidad=c, rebaja=r)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        rebuild()
        on_refresh_carrito()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(it["nombre"]),
        content=ft.Column([tf_c, tf_r, error_lbl],
                          tight=True, width=320, spacing=10),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _selector_cliente(app, rebuild):
    page = app.page
    carrito = app._carrito_pos
    cliente_id = carrito.get("cliente_id")
    nombre = "Cliente ocasional"
    if cliente_id:
        c = cli.obtener_cliente(cliente_id)
        if c:
            saldo = cli.saldo_pendiente(cliente_id)
            nombre = c["nombre"]
            if saldo > 0:
                nombre += f"  (deuda ${saldo:,.2f})"

    def abrir_selector(e):
        _modal_cliente(app, rebuild)

    def quitar(e):
        carrito["cliente_id"] = None
        rebuild()

    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.PERSON, color=es.COLOR_ACENTO, size=20),
            ft.Column([
                ft.Text("Cliente", size=10,
                        color=es.COLOR_TEXTO_TENUE),
                ft.Text(nombre, size=13,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
            ], spacing=0, expand=True),
            ft.IconButton(ft.Icons.CLOSE, icon_size=18,
                          icon_color=es.COLOR_TEXTO_SUAVE,
                          on_click=quitar,
                          visible=cliente_id is not None),
            ft.IconButton(ft.Icons.SEARCH, icon_size=20,
                          icon_color=es.COLOR_ACENTO,
                          on_click=abrir_selector),
        ], spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=10,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=12,
    )


def _modal_cliente(app, on_select):
    page = app.page
    lista = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO,
                       height=320)

    def rebuild(texto=""):
        lista.controls.clear()
        for c in cli.listar_clientes(solo_activos=True, texto=texto):
            saldo = cli.saldo_pendiente(c["id"])

            def elegir(e, cid=c["id"]):
                app._carrito_pos["cliente_id"] = cid
                page.pop_dialog()
                on_select()

            lista.controls.append(ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(c["nombre"], size=14,
                                color=es.COLOR_TEXTO,
                                weight=ft.FontWeight.W_600),
                        ft.Text(
                            c.get("telefono") or "Sin teléfono",
                            size=11, color=es.COLOR_TEXTO_SUAVE),
                    ], spacing=2, expand=True),
                    ft.Text(f"${saldo:,.2f}", size=13,
                            color=(es.COLOR_PELIGRO if saldo > 0
                                   else es.COLOR_TEXTO_TENUE),
                            weight=ft.FontWeight.BOLD),
                ], spacing=8),
                padding=12,
                bgcolor=es.COLOR_SUPERFICIE_2,
                border_radius=10,
                on_click=elegir, ink=True))
        if not lista.controls:
            lista.controls.append(empty_state(
                ft.Icons.PERSON_OFF_OUTLINED, "Sin clientes",
                "Crea uno desde el menú Clientes."))
        if mounted(lista):
            lista.update()

    def on_search(e):
        rebuild((e.control.value or "").lower())

    def nuevo(e):
        _crear_cliente_rapido(app, rebuild)

    rebuild()

    contenido = ft.Column([
        ft.Text("Seleccionar cliente", size=16,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Container(height=6),
        ft.TextField(
            hint_text="Buscar por nombre o teléfono…",
            on_change=on_search,
            **es.estilo_textfield(12), height=50),
        ft.Container(height=6),
        ft.Row([
            ft.FilledButton("+ Nuevo cliente", icon=ft.Icons.ADD,
                            on_click=nuevo, height=42,
                            style=ft.ButtonStyle(
                                bgcolor=es.COLOR_EXITO,
                                color="#ffffff")),
        ]),
        ft.Divider(height=1, color=es.COLOR_BORDE),
        lista,
    ], spacing=6, tight=True)

    page.show_dialog(bottom_sheet(contenido, page=page))


def _crear_cliente_rapido(app, on_creado):
    page = app.page
    tf_n = ft.TextField(label="Nombre", autofocus=True,
                        **es.estilo_textfield(12), height=54)
    tf_t = ft.TextField(label="Teléfono (opcional)",
                        keyboard_type=ft.KeyboardType.PHONE,
                        **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            cid = cli.crear_cliente(
                tf_n.value or "", telefono=tf_t.value)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        app._carrito_pos["cliente_id"] = cid
        page.pop_dialog()
        on_creado()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Nuevo cliente"),
        content=ft.Column([tf_n, tf_t, error_lbl],
                          tight=True, width=320, spacing=10),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Crear", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _campo_descuento(app, rebuild):
    page = app.page
    carrito = app._carrito_pos
    tf = ft.TextField(
        value=str(carrito.get("descuento_global_pct") or 0),
        keyboard_type=ft.KeyboardType.NUMBER,
        width=80, text_align=ft.TextAlign.CENTER,
        content_padding=ft.Padding.symmetric(vertical=10),
        **es.estilo_textfield(8),
    )

    def on_change(e):
        try:
            v = float((tf.value or "0").replace(",", "."))
        except ValueError:
            v = 0.0
        if v < 0:
            v = 0
        if v > 90:
            v = 90
        carrito["descuento_global_pct"] = v
        rebuild()

    tf.on_change = on_change

    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.PERCENT, color=es.COLOR_AMBAR, size=20),
            ft.Text("Descuento global", size=13,
                    color=es.COLOR_TEXTO, expand=True),
            tf,
            ft.Text("%", size=14, color=es.COLOR_TEXTO_SUAVE),
        ], spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=10,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=12,
    )


def _fila_total(label, valor, color=None, grande=False):
    return ft.Row([
        ft.Text(label, size=15 if grande else 13,
                color=es.COLOR_TEXTO if grande else es.COLOR_TEXTO_SUAVE,
                weight=ft.FontWeight.BOLD if grande
                else ft.FontWeight.NORMAL, expand=True),
        ft.Text(valor,
                size=20 if grande else 13,
                color=color or (es.COLOR_ACENTO if grande
                                else es.COLOR_TEXTO),
                weight=ft.FontWeight.BOLD if grande
                else ft.FontWeight.W_600),
    ])


# ────────────────────────────────────────────────────────────
# COBRO
# ────────────────────────────────────────────────────────────

def _abrir_cobro(app, bs_carrito, rebuild_carrito,
                 on_refresh_lista, on_refresh_carrito):
    page = app.page
    if bs_carrito is not None:
        try:
            page.pop_dialog()
        except Exception:
            pass

    carrito = app._carrito_pos
    tot = ven.calcular_totales(carrito)
    metodos = cfg.listar_metodos_pago(solo_activos=True)

    if not metodos:
        snack(page, "No hay métodos de pago activos", "error")
        return

    pagos_state = {"pagos": []}
    contenido_col = ft.Column(spacing=8, tight=True)

    def rebuild():
        contenido_col.controls.clear()

        # Lista de pagos
        if not pagos_state["pagos"]:
            contenido_col.controls.append(ft.Container(
                content=ft.Text("Sin pagos todavía. Agrega uno abajo.",
                                size=12,
                                color=es.COLOR_TEXTO_SUAVE),
                padding=10,
                bgcolor=es.COLOR_SUPERFICIE_2,
                border_radius=10,
            ))
        else:
            for i, p in enumerate(pagos_state["pagos"]):
                contenido_col.controls.append(_fila_pago(
                    app, i, p, pagos_state, rebuild, tot))

        # Sumas
        total_pagado_cup = sum(
            p["monto"] * p["tasa"] for p in pagos_state["pagos"]
        )
        falta = tot["total"] - total_pagado_cup
        color_falta = (es.COLOR_EXITO if falta <= 0.01
                       else es.COLOR_PELIGRO)

        contenido_col.controls.append(ft.Container(
            content=ft.Column([
                _fila_total("Total venta", f"${tot['total']:,.2f}"),
                _fila_total("Pagado",
                            f"${total_pagado_cup:,.2f}",
                            color=es.COLOR_EXITO),
                _fila_total(
                    "Falta" if falta > 0.01 else "Sobra (vuelto)",
                    f"${abs(falta):,.2f}",
                    color=color_falta, grande=True),
            ], spacing=6),
            padding=14,
            bgcolor=es.COLOR_SUPERFICIE_2,
            border_radius=12,
        ))

        # Botón agregar pago
        puede_agregar = len(pagos_state["pagos"]) < 3
        contenido_col.controls.append(ft.FilledButton(
            f"+ Agregar pago ({3 - len(pagos_state['pagos'])} restantes)",
            icon=ft.Icons.ADD,
            disabled=not puede_agregar,
            on_click=lambda e: _elegir_metodo(app, metodos, pagos_state,
                                              rebuild),
            width=10000, height=46,
            style=ft.ButtonStyle(
                bgcolor=es.COLOR_INFO, color="#ffffff",
                shape=ft.RoundedRectangleBorder(
                    radius=ft.BorderRadius.all(12))) if puede_agregar
            else None,
        ))

        # Botón confirmar
        confirmar_ok = (falta <= 0.01 and len(pagos_state["pagos"]) > 0)
        contenido_col.controls.append(ft.FilledButton(
            "Confirmar venta",
            icon=ft.Icons.CHECK_CIRCLE,
            disabled=not confirmar_ok,
            on_click=lambda e: _confirmar_venta(
                app, pagos_state["pagos"], on_refresh_lista,
                on_refresh_carrito),
            width=10000, height=52,
            style=ft.ButtonStyle(
                bgcolor=es.COLOR_EXITO, color="#ffffff",
                shape=ft.RoundedRectangleBorder(
                    radius=ft.BorderRadius.all(12))),
        ))

        if mounted(contenido_col):
            contenido_col.update()

    rebuild()

    page.show_dialog(bottom_sheet(
        ft.Column([
            ft.Text("Cobrar", size=18,
                    weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
            ft.Container(height=4),
            contenido_col,
        ], spacing=6, tight=True, scroll=ft.ScrollMode.AUTO),
        page=page, alto_max_pct=0.92))


def _fila_pago(app, idx, p, pagos_state, rebuild, tot):
    page = app.page

    def quitar(e):
        pagos_state["pagos"].pop(idx)
        rebuild()

    def editar(e):
        from configuracion_negocio import obtener_metodo_pago
        metodo = obtener_metodo_pago(p["metodo"])
        if metodo is None:
            snack(page, "Método no encontrado", "error")
            return
        # Falta si quitáramos este pago
        total_pagado = sum(q["monto"] * q["tasa"]
                           for q in pagos_state["pagos"])
        este = p["monto"] * p["tasa"]
        falta_sin_este = max(0, tot["total"] - (total_pagado - este))
        _agregar_pago(
            app, metodo, falta_sin_este, pagos_state, rebuild,
            indice_existente=idx, valores_actuales=p)

    return ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(p["metodo"], size=13,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.Text(
                    f"{p['monto']:.2f} {p['moneda']}"
                    + (f"  = ${p['monto'] * p['tasa']:,.2f} CUP"
                       if p["moneda"] != "CUP" else ""),
                    size=11, color=es.COLOR_TEXTO_SUAVE),
            ], spacing=2, expand=True),
            ft.IconButton(ft.Icons.EDIT, icon_size=18,
                          icon_color=es.COLOR_ACENTO,
                          tooltip="Editar",
                          on_click=editar),
            ft.IconButton(ft.Icons.CLOSE, icon_size=18,
                          icon_color=es.COLOR_PELIGRO,
                          tooltip="Quitar",
                          on_click=quitar),
        ], spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=10,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=10,
    )


def _elegir_metodo(app, metodos, pagos_state, rebuild):
    page = app.page
    tot = ven.calcular_totales(app._carrito_pos)
    pagado = sum(p["monto"] * p["tasa"]
                 for p in pagos_state["pagos"])
    falta = max(0, tot["total"] - pagado)

    contenido = ft.Column([
        ft.Text("Selecciona método de pago", size=15,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Container(height=6),
    ], spacing=6, tight=True, scroll=ft.ScrollMode.AUTO)

    for m in metodos:
        def elegir(e, met=m):
            page.pop_dialog()
            _agregar_pago(app, met, falta, pagos_state, rebuild)

        contenido.controls.append(ft.Container(
            content=ft.Row([
                ft.Icon(
                    ft.Icons.ACCOUNT_BALANCE_WALLET
                    if not m.get("es_credito")
                    else ft.Icons.RECEIPT_LONG,
                    color=(es.COLOR_EXITO if not m.get("es_credito")
                           else es.COLOR_AMBAR),
                    size=22),
                ft.Text(m["etiqueta"], size=14,
                        color=es.COLOR_TEXTO, expand=True),
                ft.Icon(ft.Icons.CHEVRON_RIGHT,
                        color=es.COLOR_TEXTO_TENUE, size=20),
            ], spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=14,
            bgcolor=es.COLOR_SUPERFICIE_2,
            border_radius=10,
            on_click=elegir, ink=True))

    page.show_dialog(bottom_sheet(contenido, page=page))


def _agregar_pago(app, metodo, falta_cup, pagos_state, rebuild,
                  indice_existente=None, valores_actuales=None):
    page = app.page
    moneda = "CUP"
    monto_default = None

    if valores_actuales is not None:
        # Modo edición: usar los valores actuales
        moneda = (valores_actuales.get("moneda") or "CUP").upper()
        monto_default = float(valores_actuales.get("monto") or 0)
    else:
        # Modo nuevo: elegir moneda por defecto según el método
        if metodo["clave"] == "Efectivo USD":
            moneda = "USD"
        elif metodo["clave"] == "Efectivo EUR":
            moneda = "EUR"
        elif metodo["clave"] in ("MLC", "Zelle"):
            moneda = "USD"

    if monto_default is None:
        tasa = inv.get_tasa(moneda)
        monto_default = (falta_cup / tasa) if tasa > 0 else falta_cup

    tf_monto = ft.TextField(
        label=f"Monto ({moneda})",
        value=f"{monto_default:.2f}",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
        **es.estilo_textfield(12), height=54)

    dd_moneda = ft.Dropdown(
        label="Moneda",
        value=moneda,
        options=[ft.DropdownOption(key="CUP", text="$ CUP"),
                 ft.DropdownOption(key="USD", text="USD$ USD"),
                 ft.DropdownOption(key="EUR", text="€ EUR")],
        **es.borde_textfield(12))

    lbl_info = ft.Text("", size=11, color=es.COLOR_TEXTO_SUAVE)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def actualizar_info(e=None):
        m = (dd_moneda.value or "CUP").upper()
        t = inv.get_tasa(m)
        try:
            v = float((tf_monto.value or "0").replace(",", "."))
        except ValueError:
            v = 0
        lbl_info.value = (f"1 {m} = {t:.2f} CUP  ·  "
                          f"Equivale a ${v * t:,.2f} CUP")
        try:
            lbl_info.update()
        except Exception:
            pass

    dd_moneda.on_change = actualizar_info
    tf_monto.on_change = actualizar_info
    actualizar_info()

    # Cuenta/QR si aplica
    widgets_extra = []
    if metodo.get("cuenta"):
        widgets_extra.append(ft.Container(
            content=ft.Column([
                ft.Text("Datos para el cliente", size=11,
                        color=es.COLOR_TEXTO_TENUE),
                ft.Text(metodo["cuenta"], size=14,
                        color=es.COLOR_ACENTO,
                        weight=ft.FontWeight.BOLD),
            ], spacing=2),
            padding=10,
            bgcolor=es.COLOR_ACENTO_SUAVE,
            border_radius=10,
        ))
    if metodo.get("qr_imagen"):
        from pathlib import Path
        if Path(metodo["qr_imagen"]).exists():
            widgets_extra.append(ft.Image(src=metodo["qr_imagen"],
                                          height=140))

    def guardar(e):
        error_lbl.value = ""
        m = (dd_moneda.value or "CUP").upper()
        try:
            v = float((tf_monto.value or "0").replace(",", "."))
        except ValueError:
            error_lbl.value = "Monto inválido"
            page.update()
            return
        if v <= 0:
            error_lbl.value = "El monto debe ser mayor que 0"
            page.update()
            return
        nuevo = {
            "metodo": metodo["clave"],
            "moneda": m,
            "monto": v,
            "tasa": inv.get_tasa(m),
        }
        if indice_existente is not None:
            pagos_state["pagos"][indice_existente] = nuevo
        else:
            pagos_state["pagos"].append(nuevo)
        page.pop_dialog()
        rebuild()

    titulo = (f"Editar pago: {metodo['etiqueta']}"
              if indice_existente is not None
              else f"Pago: {metodo['etiqueta']}")
    texto_boton = ("Guardar" if indice_existente is not None
                   else "Agregar")

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(titulo),
        content=ft.Column(
            [dd_moneda, tf_monto, *widgets_extra,
             lbl_info, error_lbl],
            tight=True, width=340, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(texto_boton, on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _confirmar_venta(app, pagos, on_refresh_lista, on_refresh_carrito):
    page = app.page
    carrito = app._carrito_pos

    try:
        resultado = ven.registrar_venta(
            carrito=carrito, pagos=pagos, usuario=app.usuario,
            local_id=app.local_id)
    except Exception as ex:
        snack(page, str(ex), "error")
        return

    app._carrito_pos = ven.nuevo_carrito()
    on_refresh_lista()
    on_refresh_carrito()

    page.pop_dialog()  # cerrar cobro
    _mostrar_ticket(app, resultado["orden_id"])


# ────────────────────────────────────────────────────────────
# TICKET
# ────────────────────────────────────────────────────────────

def _mostrar_ticket(app, orden_id):
    page = app.page
    import ticket as tk

    def guardar_pdf(e):
        try:
            ruta = tk.guardar_ticket(orden_id, "pdf")
            snack(page, f"PDF guardado en: {ruta}", "ok")
        except Exception as ex:
            snack(page, f"Error al guardar PDF: {ex}", "error")

    def guardar_png(e):
        try:
            ruta = tk.guardar_ticket(orden_id, "png")
            snack(page, f"PNG guardado en: {ruta}", "ok")
        except Exception as ex:
            snack(page, f"Error al guardar PNG: {ex}", "error")

    def copiar_texto(e):
        """Copia el ticket en texto plano para pegar en WhatsApp."""
        try:
            txt = tk.texto_plano_ticket(orden_id)
            copiar_portapapeles(page, txt)
        except Exception as ex:
            snack(page, f"Error al copiar: {ex}", "error")

    def preparar_envio(e):
        """Guarda PDF + PNG, copia el texto al portapapeles y muestra
        dónde están los archivos."""
        try:
            ruta_pdf = tk.guardar_ticket(orden_id, "pdf")
            ruta_png = tk.guardar_ticket(orden_id, "png")
            txt = tk.texto_plano_ticket(orden_id)
            copiar_portapapeles(page, txt)
        except Exception as ex:
            snack(page, f"Error al preparar: {ex}", "error")
            return

        from pathlib import Path
        nombre_pdf = Path(ruta_pdf).name
        nombre_png = Path(ruta_png).name
        carpeta = str(Path(ruta_pdf).parent)

        page.pop_dialog()
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Listo para enviar"),
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CHECK_CIRCLE,
                                    color=es.COLOR_EXITO, size=22),
                            ft.Text(
                                "Texto del ticket copiado al "
                                "portapapeles.",
                                size=13, color=es.COLOR_TEXTO,
                                expand=True),
                        ], spacing=10,
                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER)),
                        padding=12,
                        bgcolor=es.COLOR_EXITO_SUAVE,
                        border_radius=10,
                    ),
                    ft.Container(height=10),
                    ft.Text("Abre WhatsApp y pega el texto "
                            "manteniendo pulsado.",
                            size=12, color=es.COLOR_TEXTO_SUAVE),
                    ft.Container(height=14),
                    ft.Text("Archivos guardados:",
                            size=11,
                            color=es.COLOR_TEXTO_TENUE,
                            weight=ft.FontWeight.W_600),
                    ft.Container(height=6),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.PICTURE_AS_PDF,
                                    color=es.COLOR_PELIGRO,
                                    size=18),
                            ft.Text(nombre_pdf, size=12,
                                    color=es.COLOR_TEXTO,
                                    expand=True,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS),
                        ], spacing=8),
                        padding=10,
                        bgcolor=es.COLOR_SUPERFICIE_2,
                        border_radius=8,
                    ),
                    ft.Container(height=4),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.IMAGE,
                                    color=es.COLOR_INFO,
                                    size=18),
                            ft.Text(nombre_png, size=12,
                                    color=es.COLOR_TEXTO,
                                    expand=True,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS),
                        ], spacing=8),
                        padding=10,
                        bgcolor=es.COLOR_SUPERFICIE_2,
                        border_radius=8,
                    ),
                    ft.Container(height=10),
                    ft.Text("Carpeta:",
                            size=10,
                            color=es.COLOR_TEXTO_TENUE),
                    ft.Text(carpeta, size=10,
                            color=es.COLOR_TEXTO_SUAVE,
                            selectable=True),
                ], tight=True, spacing=0),
                width=360,
            ),
            actions=[
                ft.FilledButton(
                    "Entendido",
                    on_click=lambda e: page.pop_dialog(),
                    style=es.estilo_boton_marca()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))
        
    def cerrar(e):
        page.pop_dialog()
        app.ir("/principal")

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("✅ Venta registrada"),
        content=ft.Column([
            ft.Text(f"Ticket #{orden_id}", size=13,
                    color=es.COLOR_TEXTO_SUAVE),
            ft.Text("¿Qué quieres hacer con el ticket?", size=14,
                    color=es.COLOR_TEXTO),
        ], tight=True, width=340, spacing=8),
        actions=[
            ft.TextButton("Preparar envío",
                        icon=ft.Icons.SHARE,
                        on_click=preparar_envio),
            ft.TextButton("Copiar texto",
                        icon=ft.Icons.COPY,
                        on_click=copiar_texto),
            ft.TextButton("PDF", icon=ft.Icons.PICTURE_AS_PDF,
                        on_click=guardar_pdf),
            ft.TextButton("PNG", icon=ft.Icons.IMAGE,
                        on_click=guardar_png),
            ft.FilledButton("Cerrar", on_click=cerrar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))

