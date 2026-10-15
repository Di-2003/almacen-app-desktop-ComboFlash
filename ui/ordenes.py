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

# ── Icono de abono con fallback (Flet 1.0.3 no tiene ft.Icons.CASH) ──
_ICON_ABONO = (
    getattr(ft.Icons, "ATTACH_MONEY", None)
    or getattr(ft.Icons, "PAYMENTS", None)
    or getattr(ft.Icons, "MONETIZATION_ON", None)
)

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
        on_click=lambda e: ver_orden_detalle(app, o["id"],
                                             on_refresh=on_refresh),
        ink=True,
    )


def ver_orden_detalle(app, orden_id, on_refresh=None):
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

    # ── Pagos ──
    from configuracion_negocio import obtener_metodo_pago

    pagos_reales = []
    pagos_fiado = []
    for p in o["pagos"]:
        m_conf = obtener_metodo_pago(p["metodo"])
        if m_conf and m_conf.get("es_credito"):
            pagos_fiado.append(p)
        else:
            pagos_reales.append(p)

    if pagos_reales:
        contenido.controls.append(ft.Divider(height=1,
                                             color=es.COLOR_BORDE))
        contenido.controls.append(ft.Text("Pagos", size=12,
                                          color=es.COLOR_TEXTO_SUAVE))
        for p in pagos_reales:
            contenido.controls.append(_fila_pago_detalle(p))

    # ── Abonos ──
    if o["abonos"]:
        contenido.controls.append(ft.Divider(height=1,
                                             color=es.COLOR_BORDE))
        contenido.controls.append(ft.Text("Abonos", size=12,
                                          color=es.COLOR_TEXTO_SUAVE))
        for a in o["abonos"]:
            contenido.controls.append(_fila_abono_detalle(a))

    # ── Fiado (informativo) ──
    if pagos_fiado:
        contenido.controls.append(ft.Divider(height=1,
                                             color=es.COLOR_BORDE))
        contenido.controls.append(ft.Text(
            "Fiado (pendiente)", size=12,
            color=es.COLOR_TEXTO_SUAVE))
        for p in pagos_fiado:
            contenido.controls.append(ft.Row([
                ft.Text(p["metodo"], size=12, expand=True,
                        color=es.COLOR_TEXTO),
                ft.Text(f"{p['monto']:.2f} {p['moneda']}", size=12,
                        color=es.COLOR_PELIGRO,
                        weight=ft.FontWeight.BOLD),
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

    # ── Resumen de efectivo cobrado ──
    resumen = _calcular_resumen_cobros(o)
    if resumen["efectivo_cup"] > 0.01 or resumen["vuelto_cup"] > 0.01 \
            or resumen["propina_cup"] > 0.01:
        contenido.controls.append(ft.Container(height=4))
        contenido.controls.append(ft.Container(
            content=ft.Column([
                ft.Text("Resumen de cobros", size=11,
                        color=es.COLOR_TEXTO_TENUE,
                        weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text("Cobrado (pagos + abonos)", size=12,
                            color=es.COLOR_TEXTO_SUAVE, expand=True),
                    ft.Text(f"${resumen['cobrado_cup']:,.2f}",
                            size=12, color=es.COLOR_TEXTO),
                ]),
                ft.Row([
                    ft.Text("Efectivo recibido", size=12,
                            color=es.COLOR_TEXTO_SUAVE, expand=True),
                    ft.Text(f"${resumen['efectivo_cup']:,.2f}",
                            size=12, color=es.COLOR_TEXTO),
                ]) if resumen["efectivo_cup"] > 0.01 else
                ft.Container(height=0),
                ft.Row([
                    ft.Text("Vuelto entregado", size=12,
                            color=es.COLOR_TEXTO_SUAVE, expand=True),
                    ft.Text(f"-${resumen['vuelto_cup']:,.2f}",
                            size=12, color=es.COLOR_INFO),
                ]) if resumen["vuelto_cup"] > 0.01 else
                ft.Container(height=0),
                ft.Row([
                    ft.Text("Propina dejada", size=12,
                            color=es.COLOR_TEXTO_SUAVE, expand=True),
                    ft.Text(f"${resumen['propina_cup']:,.2f}",
                            size=12, color=es.COLOR_AMBAR,
                            weight=ft.FontWeight.BOLD),
                ]) if resumen["propina_cup"] > 0.01 else
                ft.Container(height=0),
            ], spacing=4),
            padding=12,
            bgcolor=es.COLOR_SUPERFICIE_2,
            border=ft.Border.all(1, es.COLOR_BORDE),
            border_radius=12,
        ))

    # ── Acciones ──
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
            on_click=lambda e: _abrir_editar_orden(
                app, orden_id, on_refresh=on_refresh),
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


# ═══════════════════════════════════════════════════════════
# HELPERS DE DETALLE
# ═══════════════════════════════════════════════════════════

def _calcular_resumen_cobros(o) -> dict:
    """
    Devuelve un resumen del efectivo real cobrado y desglosado:
      - cobrado_cup: suma de pagos reales + abonos (aplicado)
      - efectivo_cup: bruto de pagos + abonos (sin descontar vuelto)
      - vuelto_cup: suma de vueltos dados (incluye el vuelto de la
        orden por pagos en divisa redondeados al alza)
      - propina_cup: suma de propinas (bruto - aplicado - vuelto)
    """
    from configuracion_negocio import obtener_metodo_pago

    cobrado_cup = 0.0
    efectivo_cup = 0.0
    vuelto_cup = 0.0
    propina_cup = 0.0

    for p in o["pagos"]:
        m_conf = obtener_metodo_pago(p["metodo"])
        if m_conf and m_conf.get("es_credito"):
            continue
        monto_cup = float(p["monto_cup"] or 0)
        cobrado_cup += monto_cup
        if p["metodo"] == "Efectivo":
            efectivo_cup += monto_cup

    for a in o["abonos"]:
        monto = float(a.get("monto") or 0)
        tasa = float(a.get("tasa") or 1.0)
        aplicado = float(a.get("monto_cup") or 0)
        vu = float(a.get("vuelto_cup") or 0)
        bruto = monto * tasa
        prop = max(0.0, bruto - aplicado - vu)

        cobrado_cup += aplicado
        efectivo_cup += bruto
        vuelto_cup += vu
        propina_cup += prop

    # Vuelto registrado a nivel de la orden (pago inicial en divisa
    # redondeado al alza, ej. 34 USD × 770 = 26,180 → vuelto 290).
    vuelto_cup += float(o.get("vuelto_cup") or 0)

    return {
        "cobrado_cup": cobrado_cup,
        "efectivo_cup": efectivo_cup,
        "vuelto_cup": vuelto_cup,
        "propina_cup": propina_cup,
    }

def _fila_pago_detalle(p) -> ft.Container:
    """Fila informativa de un pago real (no Fiado)."""
    moneda = (p["moneda"] or "CUP").upper()
    monto = float(p["monto"] or 0)
    monto_cup = float(p["monto_cup"] or 0)

    sub = f"{monto:.2f} {moneda}"
    if moneda != "CUP":
        sub += f"  =  ${monto_cup:,.2f} CUP"

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.PAYMENTS,
                                color=es.COLOR_EXITO, size=16),
                bgcolor=es.COLOR_EXITO_SUAVE,
                padding=6, border_radius=6),
            ft.Column([
                ft.Text(p["metodo"], size=12,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.Text(sub, size=11,
                        color=es.COLOR_TEXTO_SUAVE),
            ], spacing=1, expand=True),
            ft.Text(f"${monto_cup:,.2f}", size=12,
                    color=es.COLOR_EXITO,
                    weight=ft.FontWeight.BOLD),
        ], spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=8,
        bgcolor=es.COLOR_SUPERFICIE_2,
        border_radius=8)


def _fila_abono_detalle(a) -> ft.Container:
    """
    Fila informativa de un abono.
    Muestra: monto original + CUP, aplicado, vuelto, propina.
    """
    moneda = (a.get("moneda") or "CUP").upper()
    monto = float(a.get("monto") or 0)
    tasa = float(a.get("tasa") or 1.0)
    aplicado = float(a.get("monto_cup") or 0)
    vuelto = float(a.get("vuelto_cup") or 0)
    bruto = monto * tasa
    propina = max(0.0, bruto - aplicado - vuelto)

    # Línea principal: monto original + equivalencia CUP
    linea_bruto = f"{monto:.2f} {moneda}"
    if moneda != "CUP":
        linea_bruto += f"  =  ${bruto:,.2f} CUP"

    # Línea de desglose: aplicado + vuelto + propina
    partes = [f"Aplicado: ${aplicado:,.2f}"]
    if vuelto > 0.01:
        partes.append(f"Vuelto: ${vuelto:,.2f}")
    if propina > 0.01:
        partes.append(f"Propina: ${propina:,.2f}")
    linea_desglose = "  ·  ".join(partes)

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(_ICON_ABONO,
                                color=es.COLOR_EXITO, size=16),
                bgcolor=es.COLOR_EXITO_SUAVE,
                padding=6, border_radius=6),
            ft.Column([
                ft.Text(f"Abono · {a.get('metodo') or '—'}",
                        size=12, color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.Text(linea_bruto, size=11,
                        color=es.COLOR_ACENTO),
                ft.Text(linea_desglose, size=11,
                        color=es.COLOR_TEXTO_SUAVE),
                ft.Text(a.get("fecha", "")[:16], size=10,
                        color=es.COLOR_TEXTO_TENUE),
            ], spacing=2, expand=True),
            ft.Text(f"${aplicado:,.2f}", size=12,
                    color=es.COLOR_EXITO,
                    weight=ft.FontWeight.BOLD),
        ], spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.START),
        padding=10,
        bgcolor=es.COLOR_SUPERFICIE_2,
        border_radius=8)

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


def _abrir_editar_orden(app, orden_id, on_refresh=None):
    """Abre un diálogo para editar los items y pagos de una orden."""
    page = app.page
    o = ven.obtener_orden(orden_id)
    if o is None:
        snack(page, "Orden no encontrada", "error")
        return

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
    total_lbl = ft.Text("", size=16, weight=ft.FontWeight.BOLD,
                        color=es.COLOR_ACENTO)

    def rebuild():
        contenido_col.controls.clear()
        for i, it in enumerate(items_state):
            contenido_col.controls.append(
                _fila_item_editable(app, i, it, items_state,
                                     rebuild, total_lbl))
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

    def agregar_producto(e):
        _dlg_agregar_producto_orden(app, items_state, rebuild)

    def editar_pagos(e):
        _dlg_editar_pagos_orden(app, orden_id, on_refresh=on_refresh)

    def guardar(e):
        error_lbl.value = ""
        if not items_state:
            error_lbl.value = "Debe haber al menos un ítem"
            page.update()
            return

        # ── VALIDACIÓN: al menos un pago real o abono ──
        o_actual = ven.obtener_orden(orden_id)
        from configuracion_negocio import obtener_metodo_pago
        pagos_reales = [
            p for p in o_actual["pagos"]
            if not (obtener_metodo_pago(p["metodo"]) or {}).get("es_credito")
        ]
        abonos = o_actual.get("abonos") or []
        if not pagos_reales and not abonos:
            error_lbl.value = (
                "La orden no puede quedar sin pagos. "
                "Agrega al menos uno desde el botón «Pagos».")
            page.update()
            return

        # ── VALIDACIÓN: Fiado requiere cliente ──
        tiene_fiado = any(
            (obtener_metodo_pago(p["metodo"]) or {}).get("es_credito")
            for p in o_actual["pagos"]
        )
        if tiene_fiado and not o_actual.get("cliente_id"):
            error_lbl.value = (
                "Esta orden tiene un pago Fiado pero no tiene "
                "cliente. Asígnalo desde «Pagos» → Fiado.")
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
        if on_refresh:
            on_refresh()

    rebuild()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Editar {o['numero_ticket']}"),
        content=ft.Column([
            ft.Text("Modifica cantidad, quita o añade ítems.",
                    size=12, color=es.COLOR_TEXTO_SUAVE),
            ft.Container(height=6),
            contenido_col,
            ft.Container(height=6),
            ft.Row([
                ft.OutlinedButton(
                    "+ Producto", icon=ft.Icons.ADD,
                    on_click=agregar_producto, expand=True,
                    style=ft.ButtonStyle(
                        color=es.COLOR_ACENTO,
                        side=ft.BorderSide(1, es.COLOR_ACENTO))),
                ft.OutlinedButton(
                    "Pagos", icon=ft.Icons.PAYMENTS,
                    on_click=editar_pagos, expand=True,
                    style=ft.ButtonStyle(
                        color=es.COLOR_ACENTO,
                        side=ft.BorderSide(1, es.COLOR_ACENTO))),
            ], spacing=8),
            ft.Divider(height=1, color=es.COLOR_BORDE),
            total_lbl,
            error_lbl,
        ], tight=True, width=440, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar cambios", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_agregar_producto_orden(app, items_state, on_done):
    """Busca un producto y lo añade a items_state."""
    page = app.page
    tf_buscar = ft.TextField(
        label="Buscar producto", autofocus=True,
        **es.estilo_textfield(12), height=54)
    lista = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=280)

    def rebuild(q=""):
        lista.controls.clear()
        q = (q or "").strip().lower()
        if not q:
            if mounted(lista):
                lista.update()
            return
        prods = inv.listar_productos(app.local_id, solo_activos=True)
        matches = [p for p in prods
                   if q in p["nombre"].lower()
                   or q in (p.get("codigo") or "").lower()][:20]
        for p in matches:
            def elegir(e, prod=p):
                page.pop_dialog()
                _dlg_cantidad_producto_orden(
                    app, prod, items_state, on_done)
            lista.controls.append(ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(p["nombre"], size=13,
                                color=es.COLOR_TEXTO,
                                weight=ft.FontWeight.W_600),
                        ft.Text(
                            f"{p.get('codigo') or '—'}  ·  "
                            f"Stock {inv.fmt_cantidad(p['stock'])}  ·  "
                            f"${inv.fmt_precio(p['precio_unitario'])}",
                            size=11, color=es.COLOR_TEXTO_SUAVE),
                    ], spacing=2, expand=True),
                    ft.Icon(ft.Icons.ADD_CIRCLE,
                            color=es.COLOR_EXITO, size=24),
                ], spacing=8),
                padding=10, bgcolor=es.COLOR_SUPERFICIE_2,
                border_radius=8, on_click=elegir, ink=True))
        if not matches:
            lista.controls.append(ft.Text("Sin coincidencias", size=12,
                                          color=es.COLOR_TEXTO_SUAVE))
        if mounted(lista):
            lista.update()

    tf_buscar.on_change = lambda e: rebuild(e.control.value)

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Agregar producto"),
        content=ft.Column([tf_buscar, lista],
                          tight=True, width=380, spacing=10),
        actions=[ft.TextButton("Cancelar",
                               on_click=lambda e: page.pop_dialog())],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_cantidad_producto_orden(app, prod, items_state, on_done):
    """Pide cantidad y añade (o suma) el producto a items_state."""
    page = app.page
    tf_c = ft.TextField(label="Cantidad", value="1",
                        keyboard_type=ft.KeyboardType.NUMBER,
                        autofocus=True,
                        **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    existente = next((it for it in items_state
                      if it["producto_id"] == prod["id"]), None)

    def guardar(e):
        error_lbl.value = ""
        try:
            c = float((tf_c.value or "0").replace(",", "."))
        except ValueError:
            error_lbl.value = "Cantidad inválida"
            page.update()
            return
        if c <= 0:
            error_lbl.value = "Debe ser mayor que 0"
            page.update()
            return
        if existente:
            existente["cantidad"] += c
        else:
            items_state.append({
                "producto_id": prod["id"],
                "nombre": prod["nombre"],
                "codigo": prod.get("codigo"),
                "precio_unitario": float(prod["precio_unitario"] or 0),
                "cantidad": c,
                "rebaja": 0.0,
            })
        page.pop_dialog()
        on_done()

    tf_c.on_submit = guardar

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Añadir {prod['nombre']}"),
        content=ft.Column([
            ft.Text(f"Stock: {inv.fmt_cantidad(prod['stock'])}",
                    size=12, color=es.COLOR_TEXTO_SUAVE),
            tf_c, error_lbl,
        ], tight=True, width=320, spacing=10),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Añadir", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_editar_pagos_orden(app, orden_id, on_refresh=None):
    """Lista pagos + abonos + agregar/eliminar."""
    page = app.page
    from configuracion_negocio import (
        listar_metodos_pago, obtener_metodo_pago,
    )
    metodos = listar_metodos_pago(solo_activos=True)

    lista_col = ft.Column(spacing=8, tight=True)
    resumen_lbl = ft.Text("", size=12, color=es.COLOR_TEXTO_SUAVE)

    def _es_credito(metodo_clave):
        m = obtener_metodo_pago(metodo_clave)
        return bool(m and m.get("es_credito"))

    def rebuild():
        lista_col.controls.clear()
        o = ven.obtener_orden(orden_id)

        if o:
            # ── Sección: pagos reales (no crédito) ──
            pagos_reales = [
                p for p in o["pagos"] if not _es_credito(p["metodo"])
            ]
            pagos_credito = [
                p for p in o["pagos"] if _es_credito(p["metodo"])
            ]

            if pagos_reales:
                lista_col.controls.append(ft.Text(
                    "Pagos", size=11, color=es.COLOR_TEXTO_TENUE,
                    weight=ft.FontWeight.BOLD))
                for p in pagos_reales:
                    lista_col.controls.append(
                        _fila_pago_edit(app, p, metodos, rebuild))

            # ── Sección: abonos ──
            if o["abonos"]:
                lista_col.controls.append(ft.Container(height=4))
                lista_col.controls.append(ft.Text(
                    "Abonos", size=11, color=es.COLOR_TEXTO_TENUE,
                    weight=ft.FontWeight.BOLD))
                for a in o["abonos"]:
                    lista_col.controls.append(_fila_abono(a))

            # ── Sección: fiado (informativo) ──
            if pagos_credito:
                lista_col.controls.append(ft.Container(height=4))
                lista_col.controls.append(ft.Text(
                    "Fiado", size=11, color=es.COLOR_TEXTO_TENUE,
                    weight=ft.FontWeight.BOLD))
                for p in pagos_credito:
                    lista_col.controls.append(
                        _fila_pago_edit(app, p, metodos, rebuild))

            if not (pagos_reales or pagos_credito or o["abonos"]):
                lista_col.controls.append(ft.Text(
                    "Sin movimientos registrados.", size=12,
                    color=es.COLOR_TEXTO_SUAVE))

            # ── Resumen ──
            pagado = 0.0
            for x in pagos_reales:
                pagado += float(x["monto_cup"] or 0)
            for x in o["abonos"]:
                pagado += float(x["monto_cup"] or 0)
            total = float(o["total"] or 0)
            saldo = max(0.0, total - pagado)
            vuelto = max(0.0, pagado - total)
            resumen_lbl.value = (
                f"Total orden: ${total:,.2f}   ·   "
                f"Cobrado: ${pagado:,.2f}   ·   "
                f"Saldo: ${saldo:,.2f}"
                + (f"   ·   Vuelto: ${vuelto:,.2f}"
                   if vuelto > 0.01 else "")
            )
        else:
            lista_col.controls.append(ft.Text(
                "Sin pagos registrados.", size=12,
                color=es.COLOR_TEXTO_SUAVE))
            resumen_lbl.value = ""

        try:
            lista_col.update()
            resumen_lbl.update()
        except Exception:
            pass
        if on_refresh:
            on_refresh()

    def agregar(e):
        _dlg_agregar_pago_orden(app, orden_id, metodos, rebuild)

    rebuild()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Editar pagos"),
        content=ft.Column([
            ft.Text(
                "Solo puedes cambiar método y moneda. El monto se "
                "recalcula automáticamente para no descuadrar la caja.",
                size=12, color=es.COLOR_TEXTO_SUAVE),
            ft.Container(height=6),
            lista_col,
            ft.Divider(height=1, color=es.COLOR_BORDE),
            resumen_lbl,
            ft.Container(height=6),
            ft.FilledButton(
                "Agregar pago", icon=ft.Icons.ADD,
                on_click=agregar, width=10000, height=42,
                style=es.estilo_boton_marca()),
        ], tight=True, width=440, spacing=8,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.FilledButton(
                "Cerrar",
                on_click=lambda e: page.pop_dialog(),
                style=es.estilo_boton_marca())
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _fila_abono(a):
    """Fila visual de un abono (informativa)."""
    moneda = (a.get("moneda") or "CUP").upper()
    monto = float(a.get("monto") or 0)
    monto_cup = float(a.get("monto_cup") or 0)
    tasa = float(a.get("tasa") or 1.0)
    vuelto_cup = float(a.get("vuelto_cup") or 0)
    bruto_cup = monto * tasa
    propina_cup = max(0.0, bruto_cup - monto_cup - vuelto_cup)

    partes = []
    if moneda != "CUP":
        partes.append(f"{monto:,.2f} {moneda} = ${bruto_cup:,.2f} CUP")
    else:
        partes.append(f"${bruto_cup:,.2f} CUP")
    partes.append(f"aplicado: ${monto_cup:,.2f}")
    if vuelto_cup > 0.01:
        partes.append(f"vuelto: ${vuelto_cup:,.2f}")
    if propina_cup > 0.01:
        partes.append(f"propina: ${propina_cup:,.2f}")

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.PAYMENTS,
                                color=es.COLOR_EXITO, size=18),
                bgcolor=es.COLOR_EXITO_SUAVE,
                padding=8, border_radius=8),
            ft.Column([
                ft.Text(f"Abono · {a.get('metodo') or '—'}",
                        size=12, color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.Text("  ·  ".join(partes),
                        size=11, color=es.COLOR_TEXTO_SUAVE),
                ft.Text(a.get("fecha", "")[:16], size=10,
                        color=es.COLOR_TEXTO_TENUE),
            ], spacing=2, expand=True),
        ], spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=10, bgcolor=es.COLOR_SUPERFICIE_2,
        border_radius=8)

def _fila_pago_edit(app, p, metodos, on_refresh):
    page = app.page

    def abrir_editor(e):
        _dlg_editar_pago(app, p, metodos, on_refresh)

    def eliminar(e):
        _confirmar_eliminar_pago(app, p, on_refresh)

    moneda = (p["moneda"] or "CUP").upper()
    sub = f"{float(p['monto']):,.2f} {moneda}"
    if moneda != "CUP":
        sub += f"   =  ${float(p['monto_cup']):,.2f} CUP"

    return ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(p["metodo"], size=13,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.Text(sub, size=11, color=es.COLOR_TEXTO_SUAVE),
            ], spacing=2, expand=True),
            ft.IconButton(
                ft.Icons.EDIT, icon_size=20,
                icon_color=es.COLOR_ACENTO,
                tooltip="Editar método/moneda",
                on_click=abrir_editor),
            ft.IconButton(
                ft.Icons.DELETE_OUTLINE, icon_size=20,
                icon_color=es.COLOR_PELIGRO,
                tooltip="Eliminar pago",
                on_click=eliminar),
        ], spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=10, bgcolor=es.COLOR_SUPERFICIE_2,
        border_radius=8)


def _dlg_editar_pago(app, p, metodos, on_refresh):
    """
    Edita SOLO método y moneda de un pago ya registrado.
    El monto NO es editable — se recalcula para preservar el
    `monto_cup` original (la caja no se descuadra).

    Usa CHIPS para método Y moneda porque el Dropdown de Flet
    1.0.3 no propaga on_change de forma fiable.
    """
    from configuracion_negocio import (
        moneda_efectiva_metodo, es_credito_metodo,
    )
    page = app.page

    # Valor en CUP que NO cambia nunca
    monto_cup = float(p["monto_cup"] or 0)

    # Estado mutable del diálogo
    estado = {
        "metodo": p["metodo"],
        "moneda": (p["moneda"] or "CUP").upper(),
    }

    # Cliente de la orden (para Fiado)
    _o = ven.obtener_orden(p["orden_id"])
    cliente_holder = {"id": _o.get("cliente_id") if _o else None}

    # ── Chips de método ──
    contenedor_metodos = ft.Row(spacing=6, wrap=True)
    # ── Chips de moneda ──
    contenedor_chips = ft.Row(spacing=6, wrap=True)
    # ── Bloque cliente (solo para Fiado) ──
    contenedor_cliente = ft.Container(visible=False)
    # ── Monto (read-only) ──
    tf_monto = ft.TextField(
        label="Monto (se recalcula automáticamente)",
        value=f"{float(p['monto']):.2f}",
        read_only=True,
        **es.estilo_textfield(12), height=54)

    lbl_info = ft.Text("", size=11, color=es.COLOR_TEXTO_SUAVE)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def _rebuild_cliente():
        m_conf = next(
            (m for m in metodos if m["clave"] == estado["metodo"]),
            None)
        if m_conf is None or not es_credito_metodo(m_conf):
            contenedor_cliente.visible = False
            try:
                contenedor_cliente.update()
            except Exception:
                pass
            return
        contenedor_cliente.visible = True
        cid = cliente_holder["id"]
        if cid:
            c = cli.obtener_cliente(cid)
            nombre = c["nombre"] if c else "Cliente desconocido"
            contenedor_cliente.content = ft.Row([
                ft.Icon(ft.Icons.PERSON, color=es.COLOR_EXITO,
                        size=20),
                ft.Column([
                    ft.Text("Cliente", size=10,
                            color=es.COLOR_TEXTO_TENUE),
                    ft.Text(nombre, size=13, color=es.COLOR_TEXTO,
                            weight=ft.FontWeight.W_600),
                ], spacing=0, expand=True),
                ft.TextButton(
                    "Cambiar",
                    icon=ft.Icons.SWAP_HORIZ,
                    on_click=lambda e: _elegir_cliente()),
            ], spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER)
            contenedor_cliente.bgcolor = es.COLOR_EXITO_SUAVE
            contenedor_cliente.border = ft.Border.all(1, es.COLOR_EXITO)
        else:
            contenedor_cliente.content = ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER,
                        color=es.COLOR_AMBAR, size=20),
                ft.Text("Sin cliente. Selecciona o crea uno.",
                        size=12, color=es.COLOR_TEXTO, expand=True),
                ft.TextButton(
                    "Elegir",
                    icon=ft.Icons.PERSON_SEARCH,
                    on_click=lambda e: _elegir_cliente()),
            ], spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER)
            contenedor_cliente.bgcolor = es.COLOR_AMBAR_SUAVE
            contenedor_cliente.border = ft.Border.all(1, es.COLOR_AMBAR)
        contenedor_cliente.padding = 10
        contenedor_cliente.border_radius = 10
        try:
            contenedor_cliente.update()
        except Exception:
            pass

    def _on_cliente_actualizado():
        _o2 = ven.obtener_orden(p["orden_id"])
        cliente_holder["id"] = _o2.get("cliente_id") if _o2 else None
        _rebuild_cliente()

    def _elegir_cliente():
        _modal_cliente_orden(app, p["orden_id"],
                             _on_cliente_actualizado)

    def _elegir_metodo(met):
        if estado["metodo"] == met:
            return
        estado["metodo"] = met
        m_conf = next(
            (m for m in metodos if m["clave"] == met), None)
        if m_conf is None:
            return
        # ── FIADO: forzar CUP ──
        if es_credito_metodo(m_conf):
            estado["moneda"] = "CUP"
        else:
            mf = moneda_efectiva_metodo(m_conf)
            if mf:
                estado["moneda"] = mf
        _rebuild_metodos()
        _rebuild_chips()
        _rebuild_cliente()
        _refrescar_monto()
        _rec_info()

    def _elegir_moneda(m):
        if estado["moneda"] == m:
            return
        estado["moneda"] = m
        _rebuild_chips()
        _refrescar_monto()
        _rec_info()

    def _rebuild_metodos():
        contenedor_metodos.controls.clear()
        for m in metodos:
            activo = estado["metodo"] == m["clave"]
            color = es.COLOR_ACENTO if activo else es.COLOR_SUPERFICIE
            color_txt = ("#ffffff" if activo
                         else es.COLOR_TEXTO_SUAVE)
            contenedor_metodos.controls.append(ft.Container(
                content=ft.Text(m["etiqueta"], size=12,
                                color=color_txt,
                                weight=ft.FontWeight.BOLD),
                bgcolor=color,
                border=ft.Border.all(
                    1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
                padding=ft.Padding.symmetric(horizontal=12,
                                             vertical=8),
                border_radius=20,
                on_click=lambda e, c=m["clave"]: _elegir_metodo(c),
                ink=True))
        try:
            contenedor_metodos.update()
        except Exception:
            pass

    def _rebuild_chips():
        contenedor_chips.controls.clear()
        m_conf = next(
            (m for m in metodos if m["clave"] == estado["metodo"]),
            None)
        if m_conf is None:
            try:
                contenedor_chips.update()
            except Exception:
                pass
            return

        mon_fija = moneda_efectiva_metodo(m_conf)
        es_credito = es_credito_metodo(m_conf)

        if es_credito:
            contenedor_chips.controls.append(ft.Container(
                content=ft.Text("Crédito — sin moneda", size=12,
                                color=es.COLOR_TEXTO_SUAVE),
                padding=ft.Padding.symmetric(horizontal=12,
                                             vertical=8),
                bgcolor=es.COLOR_SUPERFICIE_2,
                border_radius=20))
            try:
                contenedor_chips.update()
            except Exception:
                pass
            return

        opciones = (["CUP", "USD", "EUR"] if mon_fija is None
                    else [mon_fija])
        for op in opciones:
            activo = estado["moneda"] == op
            color = es.COLOR_ACENTO if activo else es.COLOR_SUPERFICIE
            color_txt = ("#ffffff" if activo
                         else es.COLOR_TEXTO_SUAVE)
            contenedor_chips.controls.append(ft.Container(
                content=ft.Text(op, size=12, color=color_txt,
                                weight=ft.FontWeight.BOLD),
                bgcolor=color,
                border=ft.Border.all(
                    1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
                padding=ft.Padding.symmetric(horizontal=14,
                                             vertical=8),
                border_radius=20,
                on_click=lambda e, m=op: _elegir_moneda(m),
                ink=True))
        try:
            contenedor_chips.update()
        except Exception:
            pass

    def _refrescar_monto():
        m = estado["moneda"]
        t = inv.get_tasa(m)
        monto_num = (monto_cup / t) if t > 0 else 0.0
        tf_monto.value = f"{monto_num:.2f}"
        try:
            tf_monto.update()
        except Exception:
            pass

    def _rec_info():
        m = estado["moneda"]
        t = inv.get_tasa(m)
        lbl_info.value = (
            f"1 {m} = {t:.2f} CUP  ·  "
            f"equivalente fijo: ${monto_cup:,.2f} CUP")
        try:
            lbl_info.update()
        except Exception:
            pass

    # Arranque
    _rebuild_metodos()
    _rebuild_chips()
    _rebuild_cliente()
    _refrescar_monto()
    _rec_info()

    def guardar(e):
        error_lbl.value = ""
        m_conf = next(
            (m for m in metodos if m["clave"] == estado["metodo"]),
            None)
        if m_conf is None:
            error_lbl.value = "Selecciona un método"
            page.update()
            return
        if es_credito_metodo(m_conf) and not cliente_holder["id"]:
            error_lbl.value = ("Fiado requiere un cliente. "
                               "Selecciona o crea uno.")
            page.update()
            return
        try:
            ven.editar_pago(
                pago_id=p["id"],
                nuevo_metodo=estado["metodo"],
                nueva_moneda=estado["moneda"],
                usuario=app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Pago actualizado", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Editar pago"),
        content=ft.Column([
            ft.Text("Método", size=11,
                    color=es.COLOR_TEXTO_SUAVE),
            contenedor_metodos,
            ft.Container(height=4),
            ft.Text("Moneda", size=11,
                    color=es.COLOR_TEXTO_SUAVE),
            contenedor_chips,
            ft.Container(height=4),
            contenedor_cliente,
            tf_monto,
            lbl_info, error_lbl,
        ], tight=True, width=380, spacing=8,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))

def _dlg_agregar_pago_orden(app, orden_id, metodos, on_refresh):
    """Agrega un pago nuevo a una orden existente."""
    from configuracion_negocio import (
        moneda_efectiva_metodo, es_credito_metodo,
    )
    page = app.page

    o = ven.obtener_orden(orden_id)
    if o is None:
        snack(page, "Orden no encontrada", "error")
        return

    pagado = sum(float(x["monto_cup"] or 0) for x in o["pagos"])
    pagado += sum(float(x["monto_cup"] or 0) for x in o["abonos"])
    total = float(o["total"] or 0)
    falta_cup = max(0.0, total - pagado)

    if falta_cup <= 0.01:
        snack(page, "Esta orden ya está completamente pagada", "info")
        return

    ya_usados = {p["metodo"] for p in o["pagos"]}
    metodos_disponibles = [
        m for m in metodos if m["clave"] not in ya_usados]

    if not metodos_disponibles:
        snack(page, "Todos los métodos ya están usados en esta "
                    "orden. Edita uno existente o elimínalo.",
              "info")
        return

    estado = {
        "metodo": metodos_disponibles[0]["clave"],
        "moneda": "CUP",
    }
    m_conf_ini = metodos_disponibles[0]
    mf_ini = moneda_efectiva_metodo(m_conf_ini)
    if mf_ini:
        estado["moneda"] = mf_ini

    cliente_holder = {"id": o.get("cliente_id")}

    contenedor_metodos = ft.Row(spacing=6, wrap=True)
    contenedor_chips = ft.Row(spacing=6, wrap=True)
    contenedor_cliente = ft.Container(visible=False)

    tf_monto = ft.TextField(
        label="Monto", value=f"{falta_cup:.2f}",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)
    lbl_info = ft.Text("", size=11, color=es.COLOR_TEXTO_SUAVE)
    lbl_aviso = ft.Text("", size=11, color=es.COLOR_PELIGRO,
                        weight=ft.FontWeight.BOLD)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def _leer_monto():
        try:
            return float((tf_monto.value or "0").replace(",", "."))
        except ValueError:
            return 0.0

    def _metodo_conf_actual():
        return next(
            (m for m in metodos_disponibles
             if m["clave"] == estado["metodo"]), None)

    def _rebuild_cliente():
        m_conf = _metodo_conf_actual()
        if m_conf is None or not es_credito_metodo(m_conf):
            contenedor_cliente.visible = False
            try:
                contenedor_cliente.update()
            except Exception:
                pass
            return
        contenedor_cliente.visible = True
        cid = cliente_holder["id"]
        if cid:
            c = cli.obtener_cliente(cid)
            nombre = c["nombre"] if c else "Cliente desconocido"
            contenedor_cliente.content = ft.Row([
                ft.Icon(ft.Icons.PERSON, color=es.COLOR_EXITO,
                        size=20),
                ft.Column([
                    ft.Text("Cliente", size=10,
                            color=es.COLOR_TEXTO_TENUE),
                    ft.Text(nombre, size=13, color=es.COLOR_TEXTO,
                            weight=ft.FontWeight.W_600),
                ], spacing=0, expand=True),
                ft.TextButton(
                    "Cambiar", icon=ft.Icons.SWAP_HORIZ,
                    on_click=lambda e: _elegir_cliente()),
            ], spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER)
            contenedor_cliente.bgcolor = es.COLOR_EXITO_SUAVE
            contenedor_cliente.border = ft.Border.all(1, es.COLOR_EXITO)
        else:
            contenedor_cliente.content = ft.Row([
                ft.Icon(ft.Icons.WARNING_AMBER,
                        color=es.COLOR_AMBAR, size=20),
                ft.Text("Sin cliente. Selecciona o crea uno.",
                        size=12, color=es.COLOR_TEXTO, expand=True),
                ft.TextButton(
                    "Elegir", icon=ft.Icons.PERSON_SEARCH,
                    on_click=lambda e: _elegir_cliente()),
            ], spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER)
            contenedor_cliente.bgcolor = es.COLOR_AMBAR_SUAVE
            contenedor_cliente.border = ft.Border.all(1, es.COLOR_AMBAR)
        contenedor_cliente.padding = 10
        contenedor_cliente.border_radius = 10
        try:
            contenedor_cliente.update()
        except Exception:
            pass

    def _on_cliente_actualizado():
        o2 = ven.obtener_orden(orden_id)
        cliente_holder["id"] = o2.get("cliente_id") if o2 else None
        _rebuild_cliente()

    def _elegir_cliente():
        _modal_cliente_orden(app, orden_id, _on_cliente_actualizado)

    def _elegir_metodo(met):
        if estado["metodo"] == met:
            return
        estado["metodo"] = met
        m_conf = next(
            (m for m in metodos_disponibles if m["clave"] == met),
            None)
        if m_conf is None:
            return
        # ── FIADO: forzar CUP y monto al saldo ──
        if es_credito_metodo(m_conf):
            estado["moneda"] = "CUP"
            tf_monto.value = f"{falta_cup:.2f}"
            try:
                tf_monto.update()
            except Exception:
                pass
        else:
            mf = moneda_efectiva_metodo(m_conf)
            if mf and estado["moneda"] != mf:
                _convertir_moneda(mf)
        _rebuild_metodos()
        _rebuild_chips()
        _rebuild_cliente()
        _rec_info()

    def _elegir_moneda(m):
        if estado["moneda"] == m:
            return
        _convertir_moneda(m)
        _rebuild_chips()
        _rec_info()

    def _convertir_moneda(m):
        v_antes = _leer_monto()
        m_antes = estado["moneda"]
        t_antes = inv.get_tasa(m_antes)
        t_nueva = inv.get_tasa(m)
        if t_antes > 0 and t_nueva > 0 and m_antes != m:
            v_nueva = round(v_antes * t_antes / t_nueva, 2)
            tf_monto.value = f"{v_nueva:.2f}"
            try:
                tf_monto.update()
            except Exception:
                pass
        estado["moneda"] = m

    def _rebuild_metodos():
        contenedor_metodos.controls.clear()
        for m in metodos_disponibles:
            activo = estado["metodo"] == m["clave"]
            color = es.COLOR_ACENTO if activo else es.COLOR_SUPERFICIE
            color_txt = ("#ffffff" if activo
                         else es.COLOR_TEXTO_SUAVE)
            contenedor_metodos.controls.append(ft.Container(
                content=ft.Text(m["etiqueta"], size=12,
                                color=color_txt,
                                weight=ft.FontWeight.BOLD),
                bgcolor=color,
                border=ft.Border.all(
                    1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
                padding=ft.Padding.symmetric(horizontal=12,
                                             vertical=8),
                border_radius=20,
                on_click=lambda e, c=m["clave"]: _elegir_metodo(c),
                ink=True))
        try:
            contenedor_metodos.update()
        except Exception:
            pass

    def _rebuild_chips():
        contenedor_chips.controls.clear()
        m_conf = _metodo_conf_actual()
        if m_conf is None:
            try:
                contenedor_chips.update()
            except Exception:
                pass
            return

        mon_fija = moneda_efectiva_metodo(m_conf)
        es_credito = es_credito_metodo(m_conf)

        if es_credito:
            contenedor_chips.controls.append(ft.Container(
                content=ft.Text("Crédito — sin moneda", size=12,
                                color=es.COLOR_TEXTO_SUAVE),
                padding=ft.Padding.symmetric(horizontal=12,
                                             vertical=8),
                bgcolor=es.COLOR_SUPERFICIE_2,
                border_radius=20))
            try:
                contenedor_chips.update()
            except Exception:
                pass
            return

        opciones = (["CUP", "USD", "EUR"] if mon_fija is None
                    else [mon_fija])
        for op in opciones:
            activo = estado["moneda"] == op
            color = es.COLOR_ACENTO if activo else es.COLOR_SUPERFICIE
            color_txt = ("#ffffff" if activo
                         else es.COLOR_TEXTO_SUAVE)
            contenedor_chips.controls.append(ft.Container(
                content=ft.Text(op, size=12, color=color_txt,
                                weight=ft.FontWeight.BOLD),
                bgcolor=color,
                border=ft.Border.all(
                    1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
                padding=ft.Padding.symmetric(horizontal=14,
                                             vertical=8),
                border_radius=20,
                on_click=lambda e, mm=op: _elegir_moneda(mm),
                ink=True))
        try:
            contenedor_chips.update()
        except Exception:
            pass

    def _rec_info():
        m = estado["moneda"]
        t = inv.get_tasa(m)
        v = _leer_monto()
        monto_cup = v * t
        lbl_info.value = (
            f"1 {m} = {t:.2f} CUP  ·  "
            f"equivalente: ${monto_cup:,.2f} CUP  ·  "
            f"falta: ${falta_cup:,.2f} CUP")

        m_conf = _metodo_conf_actual()
        es_credito = bool(m_conf and m_conf.get("es_credito"))
        es_efectivo = bool(m_conf and m_conf.get("clave") == "Efectivo")

        # Aviso si el monto supera el saldo (excepto Efectivo)
        if not es_efectivo and monto_cup > falta_cup + 0.01:
            if es_credito:
                lbl_aviso.value = (
                    f"⚠️ El Fiado no puede superar el saldo "
                    f"pendiente (${falta_cup:,.2f} CUP).")
            else:
                lbl_aviso.value = (
                    f"⚠️ El monto supera el saldo pendiente "
                    f"(${falta_cup:,.2f} CUP).")
        else:
            lbl_aviso.value = ""

        try:
            lbl_info.update()
            lbl_aviso.update()
        except Exception:
            pass

    tf_monto.on_change = lambda e: _rec_info()

    _rebuild_metodos()
    _rebuild_chips()
    _rebuild_cliente()
    _rec_info()

    def guardar(e):
        error_lbl.value = ""
        m_conf = _metodo_conf_actual()
        if m_conf is None:
            error_lbl.value = "Selecciona un método"
            page.update()
            return
        es_credito = es_credito_metodo(m_conf)
        es_efectivo = m_conf.get("clave") == "Efectivo"

        if es_credito and not cliente_holder["id"]:
            error_lbl.value = ("Fiado requiere un cliente. "
                               "Selecciona o crea uno.")
            page.update()
            return

        if es_credito:
            monto = falta_cup
            moneda = "CUP"
        else:
            mf = moneda_efectiva_metodo(m_conf)
            moneda = mf or estado["moneda"]
            monto = _leer_monto()
            if monto <= 0:
                error_lbl.value = "El monto debe ser mayor que 0"
                page.update()
                return
            # Aviso UI antes de intentar guardar
            monto_cup = monto * inv.get_tasa(moneda)
            if not es_efectivo and monto_cup > falta_cup + 0.01:
                error_lbl.value = (
                    f"El monto ({monto_cup:,.2f} CUP) supera el saldo "
                    f"pendiente ({falta_cup:,.2f} CUP).")
                page.update()
                return

        try:
            ven.agregar_pago_a_orden(
                orden_id=orden_id,
                metodo=m_conf["clave"],
                moneda=moneda,
                monto=monto,
                usuario=app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Pago agregado", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Agregar pago"),
        content=ft.Column([
            ft.Text(f"Falta por pagar: ${falta_cup:,.2f} CUP",
                    size=12, color=es.COLOR_TEXTO_SUAVE),
            ft.Container(height=4),
            ft.Text("Método", size=11,
                    color=es.COLOR_TEXTO_SUAVE),
            contenedor_metodos,
            ft.Container(height=4),
            ft.Text("Moneda", size=11,
                    color=es.COLOR_TEXTO_SUAVE),
            contenedor_chips,
            ft.Container(height=4),
            contenedor_cliente,
            tf_monto,
            lbl_info,
            lbl_aviso,
            error_lbl,
        ], tight=True, width=380, spacing=8,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Agregar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))



def _confirmar_eliminar_pago(app, p, on_refresh):
    page = app.page

    def hacer(e):
        try:
            ven.eliminar_pago(p["id"], app.usuario)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Pago eliminado", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Eliminar pago"),
        content=ft.Text(
            f"¿Eliminar el pago de "
            f"{float(p['monto']):,.2f} {p['moneda']} "
            f"con {p['metodo']}?\n\n"
            "El saldo pendiente de la orden se recalculará.",
            size=13, color=es.COLOR_TEXTO),
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


# ═══════════════════════════════════════════════════════════
# CLIENTE EN ÓRDENES EXISTENTES (para pagos Fiado)
# ═══════════════════════════════════════════════════════════

def _modal_cliente_orden(app, orden_id, on_select):
    """Selector de cliente. Al elegir, actualiza la orden."""
    page = app.page
    lista = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, height=280)

    def rebuild(texto=""):
        lista.controls.clear()
        for c in cli.listar_clientes(solo_activos=True, texto=texto):
            saldo = cli.saldo_pendiente(c["id"])

            def elegir(e, cid=c["id"]):
                try:
                    ven.set_cliente_orden(orden_id, cid, app.usuario)
                except Exception as ex:
                    snack(page, str(ex), "error")
                    return
                page.pop_dialog()
                on_select()

            lista.controls.append(ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(c["nombre"], size=14,
                                color=es.COLOR_TEXTO,
                                weight=ft.FontWeight.W_600),
                        ft.Text(c.get("telefono") or "Sin teléfono",
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
            lista.controls.append(ft.Text("Sin clientes", size=12,
                                          color=es.COLOR_TEXTO_SUAVE))
        try:
            lista.update()
        except Exception:
            pass

    def on_search(e):
        rebuild((e.control.value or "").lower())

    def nuevo(e):
        _crear_cliente_rapido_orden(app, orden_id, on_select)

    rebuild()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Seleccionar cliente"),
        content=ft.Container(
            content=ft.Column([
                ft.TextField(
                    hint_text="Buscar por nombre o teléfono…",
                    on_change=on_search,
                    **es.estilo_textfield(12), height=50),
                ft.Container(height=6),
                ft.FilledButton(
                    "+ Nuevo cliente", icon=ft.Icons.ADD,
                    on_click=nuevo, height=42,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_EXITO,
                        color="#ffffff")),
                ft.Divider(height=1, color=es.COLOR_BORDE),
                lista,
            ], spacing=6, tight=True),
            width=380),
        actions=[
            ft.TextButton(
                "Cancelar",
                on_click=lambda e: page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _crear_cliente_rapido_orden(app, orden_id, on_creado):
    """Crea un cliente nuevo y lo asigna a la orden."""
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
            cid = cli.crear_cliente(tf_n.value or "",
                                    telefono=tf_t.value)
            ven.set_cliente_orden(orden_id, cid, app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        # Cerrar este diálogo y el de la lista (si está abierto)
        try:
            page.pop_dialog()
        except Exception:
            pass
        try:
            page.pop_dialog()
        except Exception:
            pass
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
    
