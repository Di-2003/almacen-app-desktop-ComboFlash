"""
Listado de órdenes de venta + detalle + anular + devolver.
"""
import flet as ft
import inventario as inv
import ventas as ven
import clientes as cli
from ui import estilos as es
from ui.componentes import (
    campo_busqueda, empty_state, snack, bottom_sheet, mounted,
)
from ui._scroll import columna_scroll


def vista_ordenes(app):
    page = app.page
    estado = {"filtro": "", "estado": None, "limite": 50}
    lista = columna_scroll("/ordenes", app, [], spacing=8)

    def rebuild():
        lista.controls.clear()
        o = ven.listar_ordenes(
            local_id=app.local_id,
            estado=estado["estado"],
            texto=estado["filtro"] or None,
            limite=estado["limite"])
        for orden in o:
            lista.controls.append(_fila_orden(app, orden, rebuild))
        if not o:
            lista.controls.append(empty_state(
                ft.Icons.RECEIPT_LONG_OUTLINED, "Sin órdenes",
                "Aún no hay ventas registradas por POS."))
        if mounted(lista):
            lista.update()

    def on_search(e):
        estado["filtro"] = (e.control.value or "").strip()
        rebuild()

    cap = campo_busqueda(hint="Buscar por ticket o cliente…",
                          on_change=on_search)

    fila_chips = ft.Row(spacing=6, scroll=ft.ScrollMode.AUTO)

    def chip(texto, val, actual):
        activo = val == actual

        def click(e):
            estado["estado"] = val
            rebuild_chips()
            rebuild()

        return ft.Container(
            content=ft.Text(texto, size=12,
                            color=("#ffffff" if activo
                                   else es.COLOR_TEXTO_SUAVE),
                            weight=ft.FontWeight.W_600),
            bgcolor=es.COLOR_ACENTO if activo else es.COLOR_SUPERFICIE,
            border=ft.Border.all(
                1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
            padding=ft.Padding.symmetric(horizontal=14, vertical=7),
            border_radius=20,
            on_click=click, ink=True)

    def rebuild_chips():
        fila_chips.controls = [
            chip("Todas", None, estado["estado"]),
            chip("Pagadas", "pagada", estado["estado"]),
            chip("Parcial", "parcial", estado["estado"]),
            chip("Pendientes", "pendiente", estado["estado"]),
            chip("Anuladas", "anulada", estado["estado"]),
        ]
        if mounted(fila_chips):
            fila_chips.update()

    rebuild_chips()
    rebuild()

    return ft.View(
        route="/ordenes",
        controls=[
            ft.Container(
                content=ft.Column([cap, fila_chips], spacing=8),
                padding=ft.Padding.only(left=14, top=14,
                                        right=14, bottom=6)),
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.all(14)),
        ],
        appbar=ft.AppBar(
            title=ft.Text("Órdenes de venta", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )


def _fila_orden(app, o, on_refresh):
    color_estado = {
        "pagada": es.COLOR_EXITO,
        "parcial": es.COLOR_AMBAR,
        "pendiente": es.COLOR_PELIGRO,
        "anulada": es.COLOR_TEXTO_TENUE,
        "devuelta": es.COLOR_INFO,
    }.get(o["estado"], es.COLOR_TEXTO_SUAVE)

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.RECEIPT_LONG,
                                color=es.COLOR_ACENTO, size=20),
                bgcolor=es.COLOR_ACENTO_SUAVE,
                padding=10, border_radius=10),
            ft.Column([
                ft.Text(o["numero_ticket"] or f"#{o['id']}",
                        size=13, color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.Text(
                    (o.get("cliente_nombre") or "Sin cliente")
                    + "  ·  " + o["fecha"][:16],
                    size=11, color=es.COLOR_TEXTO_SUAVE),
            ], spacing=2, expand=True),
            ft.Column([
                ft.Text(f"${o['total']:,.2f}", size=14,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.RIGHT),
                ft.Text(o["estado"], size=10, color=color_estado,
                        text_align=ft.TextAlign.RIGHT),
            ], spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.END),
        ], spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=12,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=12,
        on_click=lambda e: ver_orden_detalle(app, o["id"]),
        ink=True,
    )


def ver_orden_detalle(app, orden_id):
    page = app.page
    o = ven.obtener_orden(orden_id)
    if o is None:
        snack(page, "Orden no encontrada", "error")
        return

    contenido = ft.Column(spacing=8, tight=True)
    contenido.controls += [
        ft.Row([
            ft.Text(o["numero_ticket"] or f"#{o['id']}", size=18,
                    weight=ft.FontWeight.BOLD,
                    color=es.COLOR_TEXTO, expand=True),
            ft.Container(
                content=ft.Text(o["estado"], size=11,
                                color="#ffffff",
                                weight=ft.FontWeight.BOLD),
                bgcolor={"pagada": es.COLOR_EXITO,
                         "parcial": es.COLOR_AMBAR,
                         "pendiente": es.COLOR_PELIGRO,
                         "anulada": es.COLOR_TEXTO_TENUE,
                         "devuelta": es.COLOR_INFO
                         }.get(o["estado"], es.COLOR_TEXTO_SUAVE),
                padding=ft.Padding.symmetric(horizontal=10, vertical=3),
                border_radius=10),
        ]),
        ft.Text(o["fecha"], size=11, color=es.COLOR_TEXTO_SUAVE),
        ft.Text(f"Local: {o['local_nombre']}", size=11,
                color=es.COLOR_TEXTO_SUAVE),
        ft.Text(f"Vendedor: {o['usuario']}", size=11,
                color=es.COLOR_TEXTO_SUAVE),
    ]
    if o.get("cliente_nombre"):
        contenido.controls.append(ft.Text(
            f"Cliente: {o['cliente_nombre']}", size=11,
            color=es.COLOR_ACENTO))

    contenido.controls.append(ft.Divider(height=1,
                                          color=es.COLOR_BORDE))

    for it in o["items"]:
        contenido.controls.append(ft.Row([
            ft.Column([
                ft.Text(it["nombre"], size=13,
                        color=es.COLOR_TEXTO, expand=True),
                ft.Text(
                    f"{it['cantidad']:g} × "
                    f"${it['precio_unitario']:,.2f}"
                    + (f"  (desc ${it['rebaja']:,.2f}/u)"
                       if it["rebaja"] > 0.001 else ""),
                    size=11, color=es.COLOR_TEXTO_SUAVE),
            ], spacing=2, expand=True),
            ft.Text(f"${it['importe']:,.2f}", size=13,
                    color=es.COLOR_TEXTO,
                    weight=ft.FontWeight.W_600),
        ]))

    contenido.controls += [
        ft.Divider(height=1, color=es.COLOR_BORDE),
        ft.Row([
            ft.Text("Subtotal", size=12,
                    color=es.COLOR_TEXTO_SUAVE, expand=True),
            ft.Text(f"${o['subtotal']:,.2f}", size=12,
                    color=es.COLOR_TEXTO),
        ]),
    ]
    if o["descuento_global"] > 0.001:
        contenido.controls.append(ft.Row([
            ft.Text("Descuento", size=12,
                    color=es.COLOR_TEXTO_SUAVE, expand=True),
            ft.Text(f"-${o['descuento_global']:,.2f}", size=12,
                    color=es.COLOR_PELIGRO),
        ]))
    contenido.controls.append(ft.Row([
        ft.Text("TOTAL", size=15, weight=ft.FontWeight.BOLD,
                color=es.COLOR_TEXTO, expand=True),
        ft.Text(f"${o['total']:,.2f}", size=16,
                color=es.COLOR_ACENTO,
                weight=ft.FontWeight.BOLD),
    ]))

    # Pagos
    if o["pagos"]:
        contenido.controls.append(ft.Divider(height=1,
                                              color=es.COLOR_BORDE))
        contenido.controls.append(ft.Text("Pagos", size=12,
                                          color=es.COLOR_TEXTO_SUAVE))
        for p in o["pagos"]:
            contenido.controls.append(ft.Row([
                ft.Text(p["metodo"], size=12, expand=True,
                        color=es.COLOR_TEXTO),
                ft.Text(f"{p['monto']:.2f} {p['moneda']}", size=12,
                        color=es.COLOR_TEXTO_SUAVE),
            ]))

    # Abonos
    if o["abonos"]:
        contenido.controls.append(ft.Divider(height=1,
                                              color=es.COLOR_BORDE))
        contenido.controls.append(ft.Text("Abonos", size=12,
                                          color=es.COLOR_TEXTO_SUAVE))
        for a in o["abonos"]:
            contenido.controls.append(ft.Row([
                ft.Text(a["fecha"][:16], size=11, expand=True,
                        color=es.COLOR_TEXTO_SUAVE),
                ft.Text(f"${a['monto_cup']:,.2f}", size=12,
                        color=es.COLOR_EXITO),
            ]))

    if o["saldo_pendiente"] > 0.01:
        contenido.controls.append(ft.Container(
            content=ft.Column([
                ft.Text("SALDO PENDIENTE", size=11,
                        color=es.COLOR_TEXTO_TENUE),
                ft.Text(f"${o['saldo_pendiente']:,.2f}", size=22,
                        weight=ft.FontWeight.BOLD,
                        color=es.COLOR_PELIGRO),
            ], spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=14,
            bgcolor=es.COLOR_PELIGRO_SUAVE,
            border_radius=12,
        ))

    # Acciones
    puede_editar = o["estado"] in ("pagada", "parcial", "pendiente")
    acciones = ft.Row([
        ft.FilledButton("Ticket", icon=ft.Icons.RECEIPT_LONG,
                        on_click=lambda e: _ver_ticket(app, orden_id),
                        expand=True,
                        style=ft.ButtonStyle(
                            bgcolor=es.COLOR_INFO, color="#ffffff")),
    ], spacing=8)
    
    if puede_editar:
        acciones.controls.append(ft.FilledButton(
            "Editar", icon=ft.Icons.EDIT,
            on_click=lambda e: _abrir_editar_orden(app, orden_id),
            expand=True,
            style=ft.ButtonStyle(
                bgcolor=es.COLOR_ACENTO, color="#ffffff")))

    puede_devolver = o["estado"] in ("pagada", "parcial")
    if puede_devolver:
        acciones.controls.append(ft.FilledButton(
            "Devolver", icon=ft.Icons.KEYBOARD_RETURN,
            on_click=lambda e: _abrir_devolucion(app, orden_id),
            expand=True,
            style=ft.ButtonStyle(
                bgcolor=es.COLOR_AMBAR, color="#ffffff")))

    if app.usuario["rol"] == "admin" and o["estado"] != "anulada":
        acciones.controls.append(ft.FilledButton(
            "Anular", icon=ft.Icons.CANCEL,
            on_click=lambda e: _confirmar_anular(app, orden_id),
            expand=True,
            style=ft.ButtonStyle(
                bgcolor=es.COLOR_PELIGRO, color="#ffffff")))

    contenido.controls += [ft.Container(height=6), acciones]

    page.show_dialog(bottom_sheet(contenido, page=page))


def _ver_ticket(app, orden_id):
    from ui.pos import _mostrar_ticket
    _mostrar_ticket(app, orden_id)


def _abrir_devolucion(app, orden_id):
    import devoluciones as dev
    page = app.page
    o = ven.obtener_orden(orden_id)

    items_ui = []
    for it in o["items"]:
        ya_dev = 0
        try:
            with __import__("db").get_conn() as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(cantidad),0) AS c "
                    "FROM devoluciones WHERE item_id=?",
                    (it["id"],)).fetchone()
                ya_dev = float(row["c"] or 0)
        except Exception:
            pass
        disponible = float(it["cantidad"]) - ya_dev
        tf = ft.TextField(
            value="0", width=80,
            keyboard_type=ft.KeyboardType.NUMBER,
            text_align=ft.TextAlign.CENTER,
            disabled=(disponible <= 0),
            **es.estilo_textfield(8))
        items_ui.append({
            "item": it, "tf": tf, "disponible": disponible,
            "ya_dev": ya_dev})

    tf_motivo = ft.TextField(
        label="Motivo",
        value="Producto defectuoso",
        **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        devueltos = []
        for ui in items_ui:
            try:
                v = float((ui["tf"].value or "0").replace(",", "."))
            except ValueError:
                v = 0
            if v > 0:
                devueltos.append({
                    "item_id": ui["item"]["id"], "cantidad": v})
        if not devueltos:
            error_lbl.value = "Selecciona al menos un ítem"
            page.update()
            return
        try:
            dev.registrar_devolucion(
                orden_id=orden_id,
                items_devueltos=devueltos,
                motivo=tf_motivo.value,
                usuario=app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Devolución registrada", "ok")

    filas = []
    for ui in items_ui:
        it = ui["item"]
        filas.append(ft.Container(
            content=ft.Column([
                ft.Text(it["nombre"], size=13,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.Text(
                    f"Vendidos: {it['cantidad']:g}  ·  "
                    f"Devueltos: {ui['ya_dev']:g}  ·  "
                    f"Disponibles: {ui['disponible']:g}",
                    size=11, color=es.COLOR_TEXTO_SUAVE),
                ft.Row([
                    ft.Text("Cantidad a devolver:", size=12,
                            color=es.COLOR_TEXTO_SUAVE),
                    ui["tf"],
                ], spacing=8),
            ], spacing=4),
            padding=10,
            bgcolor=es.COLOR_SUPERFICIE_2,
            border_radius=10,
        ))

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Devolución — {o['numero_ticket']}"),
        content=ft.Column([
            *filas, tf_motivo, error_lbl,
        ], tight=True, width=360, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Registrar devolución", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _confirmar_anular(app, orden_id):
    page = app.page

    def hacer(e):
        try:
            ven.anular_orden(orden_id, app.usuario)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Orden anulada. Stock restaurado.", "ok")

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Anular orden"),
        content=ft.Text(
            "Se restaurará el stock de todos los productos "
            "y la orden quedará marcada como anulada.",
            color=es.COLOR_TEXTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Anular", on_click=hacer,
                            style=ft.ButtonStyle(
                                bgcolor=es.COLOR_PELIGRO,
                                color="#ffffff")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))
    
def _abrir_editar_orden(app, orden_id):
    """Abre un diálogo para editar los items de una orden."""
    page = app.page
    o = ven.obtener_orden(orden_id)
    if o is None:
        snack(page, "Orden no encontrada", "error")
        return

    # Estado editable (copia de los items actuales)
    items_state = []
    for it in o["items"]:
        items_state.append({
            "producto_id": it["producto_id"],
            "nombre": it["nombre"],
            "codigo": it["codigo"],
            "precio_unitario": float(it["precio_unitario"] or 0),
            "cantidad": float(it["cantidad"] or 0),
            "rebaja": float(it["rebaja"] or 0),
        })

    contenido_col = ft.Column(spacing=8, tight=True)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    total_lbl = ft.Text("", size=16,
                        weight=ft.FontWeight.BOLD,
                        color=es.COLOR_ACENTO)

    def rebuild():
        contenido_col.controls.clear()
        for i, it in enumerate(items_state):
            contenido_col.controls.append(
                _fila_item_editable(app, i, it, items_state,
                                     rebuild, total_lbl))
        # Recalcular
        desc_pct = 0.0
        if float(o["subtotal"] or 0) > 0:
            desc_pct = (float(o["descuento_global"] or 0)
                        / float(o["subtotal"])) * 100.0
        sub = sum((it["precio_unitario"] - it["rebaja"])
                  * it["cantidad"] for it in items_state)
        desc = sub * (desc_pct / 100.0)
        total = sub - desc
        total_lbl.value = f"Total: ${total:,.2f}"
        if mounted(contenido_col):
            contenido_col.update()
        try:
            total_lbl.update()
        except Exception:
            pass

    def guardar(e):
        error_lbl.value = ""
        if not items_state:
            error_lbl.value = "Debe haber al menos un ítem"
            page.update()
            return
        try:
            ven.editar_items_orden(
                orden_id=orden_id,
                items_nuevos=items_state,
                usuario=app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Orden actualizada", "ok")

    rebuild()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Editar {o['numero_ticket']}"),
        content=ft.Column([
            ft.Text("Modifica la cantidad o quita ítems.",
                    size=12, color=es.COLOR_TEXTO_SUAVE),
            ft.Container(height=6),
            contenido_col,
            ft.Divider(height=1, color=es.COLOR_BORDE),
            total_lbl,
            error_lbl,
        ], tight=True, width=400, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar cambios", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _fila_item_editable(app, idx, it, items_state, rebuild, total_lbl):
    """Fila editable: producto + cantidad + botón quitar."""
    tf_cant = ft.TextField(
        value=inv.fmt_cantidad(it["cantidad"]),
        keyboard_type=ft.KeyboardType.NUMBER,
        width=80, text_align=ft.TextAlign.CENTER,
        content_padding=ft.Padding.symmetric(vertical=8),
        **es.estilo_textfield(8),
    )

    def on_cant(e):
        try:
            v = float((tf_cant.value or "0").replace(",", "."))
            if v <= 0:
                v = 1
        except ValueError:
            v = 1
        items_state[idx]["cantidad"] = v
        # Recalcular total en el label
        try:
            sub = sum(
                (x["precio_unitario"] - x["rebaja"]) * x["cantidad"]
                for x in items_state)
            total_lbl.value = f"Total (sin desc): ${sub:,.2f}"
            total_lbl.update()
        except Exception:
            pass

    tf_cant.on_change = on_cant

    def quitar(e):
        items_state.pop(idx)
        rebuild()

    return ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(it["nombre"], size=13,
                        weight=ft.FontWeight.W_600,
                        color=es.COLOR_TEXTO,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(f"${it['precio_unitario']:,.2f}",
                        size=11, color=es.COLOR_ACENTO),
            ], spacing=2, expand=True),
            tf_cant,
            ft.IconButton(ft.Icons.CLOSE, icon_size=18,
                          icon_color=es.COLOR_PELIGRO,
                          tooltip="Quitar ítem",
                          on_click=quitar),
        ], spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=10,
        bgcolor=es.COLOR_SUPERFICIE_2,
        border_radius=10,
    ) 
    
