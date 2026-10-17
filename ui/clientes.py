"""
CRUD de clientes + vista cuentas por cobrar + detalle + abonos.
"""
import flet as ft
import math
import clientes as cli
import inventario as inv
from ui import estilos as es
from ui.componentes import (
    campo_busqueda, empty_state, snack, bottom_sheet, mounted,
    dlg_destino_sobrante,
)
from ui._scroll import columna_scroll


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def _es_efectivo_usd_eur(metodo_conf, moneda=None) -> bool:
    if not metodo_conf:
        return False
    if metodo_conf.get("clave") != "Efectivo":
        return False
    if moneda is not None:
        return (moneda or "").upper() in ("USD", "EUR")
    return metodo_conf.get("moneda_fija") in ("USD", "EUR")


def _redondear_efectivo(monto: float, moneda: str) -> float:
    """Redondea hacia arriba a entero para USD/EUR."""
    if (moneda or "").upper() in ("USD", "EUR"):
        return float(math.ceil(monto))
    return round(monto, 2)


def vista_clientes(app):
    page = app.page
    estado = {"filtro": "", "ver_deuda": False, "ver_inactivos": False}
    lista = columna_scroll("/clientes", app, [], spacing=10)

    def refrescar():
        lista.controls.clear()
        if estado["ver_deuda"]:
            cs = cli.listar_con_deuda()
        else:
            cs = cli.listar_clientes(
                solo_activos=not estado["ver_inactivos"],
                texto=estado["filtro"] or None)

        for c in cs:
            lista.controls.append(_fila_cliente(app, c, refrescar))

        if not cs:
            if estado["ver_deuda"]:
                titulo = "Sin deudas"
            elif estado["ver_inactivos"]:
                titulo = "Sin clientes inactivos"
            else:
                titulo = "Sin clientes"
            lista.controls.append(empty_state(
                ft.Icons.PEOPLE_OUTLINED, titulo,
                "Agrega el primero con el botón de arriba."))

        if mounted(lista):
            lista.update()

    def on_search(e):
        estado["filtro"] = (e.control.value or "").strip()
        refrescar()

    cap = campo_busqueda(hint="Buscar cliente…", on_change=on_search)

    boton_toggle_holder = ft.Container()
    boton_inactivos_holder = ft.Container()

    def _rebuild_botones():
        filtrado = estado["ver_deuda"]
        boton_toggle_holder.content = ft.OutlinedButton(
            "Ver todos" if filtrado else "Ver cuentas por cobrar",
            icon=(ft.Icons.PEOPLE if filtrado
                  else ft.Icons.RECEIPT_LONG),
            on_click=toggle_deuda, height=42,
            width=10000,
            style=ft.ButtonStyle(
                color=es.COLOR_ACENTO,
                side=ft.BorderSide(1, es.COLOR_ACENTO),
                shape=ft.RoundedRectangleBorder(
                    radius=ft.BorderRadius.all(12))))

        vi = estado["ver_inactivos"]
        boton_inactivos_holder.content = ft.OutlinedButton(
            "Ver activos" if vi else "Ver inactivos",
            icon=(ft.Icons.PERSON if vi else ft.Icons.PERSON_OFF),
            on_click=toggle_inactivos, height=42,
            width=10000,
            style=ft.ButtonStyle(
                color=es.COLOR_TEXTO_SUAVE,
                side=ft.BorderSide(1, es.COLOR_BORDE),
                shape=ft.RoundedRectangleBorder(
                    radius=ft.BorderRadius.all(12))))
        try:
            boton_toggle_holder.update()
            boton_inactivos_holder.update()
        except Exception:
            pass

    def toggle_deuda(e):
        estado["ver_deuda"] = not estado["ver_deuda"]
        if estado["ver_deuda"]:
            estado["ver_inactivos"] = False
        _rebuild_botones()
        refrescar()

    def toggle_inactivos(e):
        estado["ver_inactivos"] = not estado["ver_inactivos"]
        if estado["ver_inactivos"]:
            estado["ver_deuda"] = False
        _rebuild_botones()
        refrescar()

    def nuevo(e):
        _dlg_editar(app, None, refrescar)

    _rebuild_botones()
    refrescar()

    return ft.View(
        route="/clientes",
        controls=[
            ft.Container(
                content=ft.Column([
                    cap,
                    ft.FilledButton(
                        "Nuevo cliente", icon=ft.Icons.ADD,
                        on_click=nuevo, height=42,
                        width=10000,
                        style=ft.ButtonStyle(
                            bgcolor=es.COLOR_EXITO,
                            color="#ffffff",
                            shape=ft.RoundedRectangleBorder(
                                radius=ft.BorderRadius.all(12)))),
                    boton_toggle_holder,
                    boton_inactivos_holder,
                ], spacing=8),
                padding=ft.Padding.only(left=14, top=14,
                                        right=14, bottom=4)),
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.all(14)),
        ],
        appbar=ft.AppBar(
            title=ft.Text("Clientes", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )


def _fila_cliente(app, c, on_refresh):
    saldo = cli.saldo_pendiente(c["id"])
    deuda = saldo > 0.01
    inactivo = c.get("activo", 1) == 0

    def tap(e):
        _detalle_cliente(app, c, on_refresh)

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(
                    ft.Icons.PERSON_OFF if inactivo
                    else ft.Icons.PERSON,
                    color=(es.COLOR_TEXTO_TENUE if inactivo
                           else es.COLOR_ACENTO), size=22),
                bgcolor=(es.COLOR_SUPERFICIE_2 if inactivo
                         else es.COLOR_ACENTO_SUAVE),
                padding=12, border_radius=10),
            ft.Column([
                ft.Text(c["nombre"], size=14,
                        color=(es.COLOR_TEXTO_TENUE if inactivo
                               else es.COLOR_TEXTO),
                        weight=ft.FontWeight.W_600),
                ft.Text(
                    (c.get("telefono") or "Sin teléfono")
                    + ("   · inactivo" if inactivo else ""),
                    size=11,
                    color=(es.COLOR_TEXTO_TENUE if inactivo
                           else es.COLOR_TEXTO_SUAVE)),
            ], spacing=2, expand=True),
            ft.Column([
                ft.Text(f"${saldo:,.2f}", size=14,
                        color=(es.COLOR_PELIGRO if deuda
                               else es.COLOR_TEXTO_TENUE),
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.RIGHT),
                ft.Text("deuda" if deuda else "sin deuda", size=10,
                        color=es.COLOR_TEXTO_TENUE,
                        text_align=ft.TextAlign.RIGHT),
            ], spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.END),
            ft.Icon(ft.Icons.CHEVRON_RIGHT,
                    color=es.COLOR_TEXTO_TENUE),
        ], spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=12,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=12,
        on_click=tap, ink=True,
        opacity=0.65 if inactivo else 1.0,
    )


def _detalle_cliente(app, c, on_refresh):
    page = app.page
    contenido_col = ft.Column(spacing=8, tight=True)
    inactivo = c.get("activo", 1) == 0

    def rebuild():
        contenido_col.controls.clear()
        saldo = cli.saldo_pendiente(c["id"])
        ordenes = cli.historial_compras(c["id"], limite=20)

        contenido_col.controls += [
            ft.Row([
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.PERSON_OFF if inactivo
                        else ft.Icons.PERSON,
                        color=(es.COLOR_TEXTO_SUAVE if inactivo
                               else es.COLOR_ACENTO), size=28),
                    bgcolor=(es.COLOR_SUPERFICIE_2 if inactivo
                             else es.COLOR_ACENTO_SUAVE),
                    padding=14, border_radius=50),
                ft.Column([
                    ft.Text(c["nombre"], size=18,
                            weight=ft.FontWeight.BOLD,
                            color=(es.COLOR_TEXTO_TENUE if inactivo
                                   else es.COLOR_TEXTO)),
                    ft.Text(c.get("telefono") or "—", size=12,
                            color=es.COLOR_TEXTO_SUAVE),
                    ft.Text(c.get("direccion") or "", size=11,
                            color=es.COLOR_TEXTO_TENUE),
                    ft.Container(
                        content=ft.Text(
                            "INACTIVO" if inactivo else "ACTIVO",
                            size=9, color="white",
                            weight=ft.FontWeight.BOLD),
                        bgcolor=(es.COLOR_TEXTO_TENUE if inactivo
                                 else es.COLOR_EXITO),
                        padding=ft.Padding.symmetric(
                            horizontal=8, vertical=2),
                        border_radius=8,
                    ),
                ], spacing=2, expand=True),
            ]),
            ft.Container(height=6),
            ft.Container(
                content=ft.Column([
                    ft.Text("Saldo pendiente", size=11,
                            color=es.COLOR_TEXTO_TENUE),
                    ft.Text(f"${saldo:,.2f}",
                            size=26, weight=ft.FontWeight.BOLD,
                            color=(es.COLOR_PELIGRO if saldo > 0
                                   else es.COLOR_EXITO)),
                ], spacing=2,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=16,
                bgcolor=(es.COLOR_PELIGRO_SUAVE if saldo > 0
                         else es.COLOR_EXITO_SUAVE),
                border_radius=14,
            ),
            ft.Container(height=6),
            ft.Row([
                ft.FilledButton(
                    "Editar", icon=ft.Icons.EDIT,
                    on_click=lambda e: _dlg_editar(app, c, on_refresh),
                    expand=True,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_INFO, color="#ffffff")),
                ft.FilledButton(
                    "Abonar", icon=ft.Icons.PAYMENTS,
                    on_click=lambda e: _dlg_abonar(app, c, rebuild,
                                                  on_refresh),
                    expand=True,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_EXITO, color="#ffffff"),
                    disabled=inactivo or saldo <= 0.01),
            ], spacing=8),
        ]

        if inactivo:
            contenido_col.controls.append(ft.Container(height=4))
            contenido_col.controls.append(ft.FilledButton(
                "Reactivar cliente",
                icon=ft.Icons.RESTORE,
                on_click=lambda e: _reactivar_cliente(
                    app, c, rebuild, on_refresh),
                expand=True,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_EXITO,
                    color="#ffffff")))

        contenido_col.controls.append(
            ft.Divider(height=1, color=es.COLOR_BORDE))
        contenido_col.controls.append(
            ft.Text("Historial de compras", size=14,
                    weight=ft.FontWeight.BOLD,
                    color=es.COLOR_TEXTO))

        if not ordenes:
            contenido_col.controls.append(ft.Text(
                "Sin compras registradas.", size=12,
                color=es.COLOR_TEXTO_SUAVE))
        else:
            for o in ordenes:
                estado_color = {
                    "pagada": es.COLOR_EXITO,
                    "parcial": es.COLOR_AMBAR,
                    "pendiente": es.COLOR_PELIGRO,
                    "anulada": es.COLOR_TEXTO_TENUE,
                    "devuelta": es.COLOR_INFO,
                }.get(o["estado"], es.COLOR_TEXTO_SUAVE)
                contenido_col.controls.append(ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(o["numero_ticket"] or f"#{o['id']}",
                                    size=13, color=es.COLOR_TEXTO,
                                    weight=ft.FontWeight.W_600),
                            ft.Text(o["fecha"], size=10,
                                    color=es.COLOR_TEXTO_SUAVE),
                        ], spacing=2, expand=True),
                        ft.Column([
                            ft.Text(f"${o['total']:,.2f}", size=13,
                                    color=es.COLOR_TEXTO,
                                    weight=ft.FontWeight.BOLD),
                            ft.Text(o["estado"], size=10,
                                    color=estado_color),
                        ], spacing=2,
                            horizontal_alignment=(
                                ft.CrossAxisAlignment.END)),
                    ], spacing=8),
                    padding=10,
                    bgcolor=es.COLOR_SUPERFICIE_2,
                    border_radius=10,
                    on_click=lambda e, oid=o["id"]:
                        _ver_orden(app, oid),
                    ink=True))

        if mounted(contenido_col):
            contenido_col.update()

    rebuild()
    page.show_dialog(bottom_sheet(contenido_col, page=page))


def _reactivar_cliente(app, c, rebuild, on_refresh):
    page = app.page

    def hacer(e):
        try:
            cli.activar_cliente(c["id"], True)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, f"Cliente «{c['nombre']}» reactivado", "ok")
        rebuild()
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Reactivar cliente"),
        content=ft.Text(
            f"¿Reactivar a «{c['nombre']}»?\n\n"
            "Volverá a aparecer en la lista de clientes activos "
            "y podrás hacerle ventas al fiado y abonos.",
            color=es.COLOR_TEXTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Reactivar", on_click=hacer,
                            style=ft.ButtonStyle(
                                bgcolor=es.COLOR_EXITO,
                                color="white")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _ver_orden(app, orden_id):
    from ui.ordenes import ver_orden_detalle
    ver_orden_detalle(app, orden_id)


def _dlg_editar(app, cliente, on_refresh):
    page = app.page
    es_nuevo = cliente is None
    tf_n = ft.TextField(label="Nombre",
                        value=(cliente["nombre"] if cliente else ""),
                        autofocus=True,
                        **es.estilo_textfield(12), height=54)
    tf_t = ft.TextField(label="Teléfono",
                        value=(cliente.get("telefono") if cliente
                               else ""),
                        keyboard_type=ft.KeyboardType.PHONE,
                        **es.estilo_textfield(12), height=54)
    tf_d = ft.TextField(label="Dirección",
                        value=(cliente.get("direccion") if cliente
                               else ""),
                        **es.estilo_textfield(12), height=54)
    tf_e = ft.TextField(label="Email",
                        value=(cliente.get("email") if cliente
                               else ""),
                        **es.estilo_textfield(12), height=54)
    tf_l = ft.TextField(label="Límite de crédito (CUP)",
                        value=str(cliente.get("limite_credito") if cliente
                                  else 0),
                        keyboard_type=ft.KeyboardType.NUMBER,
                        **es.estilo_textfield(12), height=54)
    tf_no = ft.TextField(label="Notas",
                         value=(cliente.get("notas") if cliente
                                else ""),
                         multiline=True, min_lines=2, max_lines=4,
                         **es.estilo_textfield(12))
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            if es_nuevo:
                cli.crear_cliente(
                    nombre=tf_n.value,
                    telefono=tf_t.value,
                    direccion=tf_d.value,
                    email=tf_e.value,
                    limite_credito=float(tf_l.value or 0),
                    notas=tf_no.value)
            else:
                cli.editar_cliente(
                    cliente["id"],
                    nombre=tf_n.value,
                    telefono=tf_t.value,
                    direccion=tf_d.value,
                    email=tf_e.value,
                    limite_credito=float(tf_l.value or 0),
                    notas=tf_no.value)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Cliente guardado", "ok")
        on_refresh()

    def desactivar(e):
        page.pop_dialog()
        _confirmar_eliminar(app, cliente, on_refresh)

    acciones = [
        ft.TextButton("Cancelar",
                      on_click=lambda e: page.pop_dialog()),
        ft.FilledButton(
            "Guardar", on_click=guardar,
            style=es.estilo_boton_marca()),
    ]
    if not es_nuevo and cliente.get("activo", 1) == 1:
        acciones.insert(0, ft.TextButton(
            "Desactivar", icon=ft.Icons.PERSON_OFF,
            on_click=desactivar,
            style=ft.ButtonStyle(color=es.COLOR_PELIGRO)))

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Nuevo cliente" if es_nuevo
                      else f"Editar: {cliente['nombre']}"),
        content=ft.Column([
            tf_n, tf_t, tf_d, tf_e, tf_l, tf_no, error_lbl,
        ], tight=True, width=340, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=acciones,
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _confirmar_eliminar(app, cliente, on_refresh):
    page = app.page
    saldo = cli.saldo_pendiente(cliente["id"])

    def hacer(e):
        if saldo > 0.01:
            snack(page, "No se puede desactivar: tiene deuda pendiente",
                  "error")
            return
        cli.activar_cliente(cliente["id"], False)
        page.pop_dialog()
        snack(page, "Cliente desactivado", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Desactivar cliente"),
        content=ft.Text(
            f"¿Desactivar a «{cliente['nombre']}»?\n\n"
            "Su historial se conserva pero no aparecerá en la "
            "lista. Podrás reactivarlo desde el filtro "
            "«Ver inactivos».",
            color=es.COLOR_TEXTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Desactivar", on_click=hacer,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_PELIGRO, color="#ffffff")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_abonar(app, cliente, rebuild, on_refresh):
    from configuracion_negocio import (
        listar_metodos_pago, moneda_efectiva_metodo, es_credito_metodo,
    )
    import ventas as ven
    page = app.page
    ordenes = cli.listar_ordenes_pendientes(cliente["id"])
    if not ordenes:
        snack(page, "No hay órdenes pendientes", "info")
        return

    metodos = [
        m for m in listar_metodos_pago(solo_activos=True)
        if not m.get("es_credito")
    ]
    if not metodos:
        snack(page, "No hay métodos de pago activos", "error")
        return

    ordenes_por_id = {str(o["id"]): o for o in ordenes}

    estado = {
        "orden_id": str(ordenes[0]["id"]),
        "metodo": metodos[0]["clave"],
        "moneda": "CUP",
        "cup_objetivo": float(ordenes[0]["saldo_pendiente"]),
    }
    mf_ini = moneda_efectiva_metodo(metodos[0])
    if mf_ini:
        estado["moneda"] = mf_ini

    def _saldo_orden():
        o = ordenes_por_id.get(estado["orden_id"])
        return float(o["saldo_pendiente"]) if o else 0.0

    def _metodo_conf():
        return next((m for m in metodos if m["clave"] == estado["metodo"]), None)

    dd_orden = ft.Dropdown(
        label="Orden", value=estado["orden_id"],
        options=[ft.DropdownOption(
            key=str(o["id"]),
            text=f"{o['numero_ticket']} · ${o['saldo_pendiente']:,.2f}")
            for o in ordenes],
        **es.borde_textfield(12))

    contenedor_metodos = ft.Row(spacing=6, wrap=True)
    contenedor_chips = ft.Row(spacing=6, wrap=True)

    tasa_ini = inv.get_tasa(estado["moneda"])
    monto_ini = (_saldo_orden() / tasa_ini) if tasa_ini > 0 else _saldo_orden()
    if estado["moneda"] != "CUP":
        monto_ini = ven.redondear_divisa(monto_ini, estado["moneda"])
    else:
        monto_ini = round(monto_ini, 2)

    tf_monto = ft.TextField(
        label=f"Monto ({estado['moneda']})",
        value=f"{monto_ini:g}",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)

    lbl_resumen = ft.Text("", size=12, color=es.COLOR_TEXTO, weight=ft.FontWeight.W_600)
    lbl_vuelto = ft.Text("", size=13, color=es.COLOR_AMBAR, weight=ft.FontWeight.BOLD)
    tf_no = ft.TextField(label="Notas (opcional)", **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def _leer_monto():
        try: return float((tf_monto.value or "0").replace(",", "."))
        except ValueError: return 0.0

    def _convertir_moneda(nueva):
        if nueva == estado["moneda"]: return
        t_nueva = inv.get_tasa(nueva)
        if t_nueva > 0:
            v_nueva = estado["cup_objetivo"] / t_nueva
            if (nueva or "").upper() != "CUP":
                v_nueva = ven.redondear_divisa(v_nueva, nueva)
            else:
                v_nueva = round(v_nueva, 2)
            tf_monto.value = f"{v_nueva:g}"
            tf_monto.label = f"Monto ({nueva})"
            try: tf_monto.update()
            except: pass
        estado["moneda"] = nueva

    def _elegir_moneda(m):
        if estado["moneda"] == m: return
        _convertir_moneda(m); _rebuild_chips(); _rec_info()

    def _elegir_metodo(c):
        if estado["metodo"] == c: return
        estado["metodo"] = c
        m_conf = _metodo_conf()
        if m_conf:
            mf = moneda_efectiva_metodo(m_conf)
            if mf and mf != estado["moneda"]:
                _convertir_moneda(mf)
        _rebuild_metodos(); _rebuild_chips(); _rec_info()

    def _on_orden_change(e):
        estado["orden_id"] = dd_orden.value or estado["orden_id"]
        estado["cup_objetivo"] = _saldo_orden()
        _convertir_moneda(estado["moneda"]) # Fuerza recálculo
        _rec_info()

    def _rebuild_metodos():
        contenedor_metodos.controls.clear()
        for m in metodos:
            activo = estado["metodo"] == m["clave"]
            color = es.COLOR_ACENTO if activo else es.COLOR_SUPERFICIE
            color_txt = "#ffffff" if activo else es.COLOR_TEXTO_SUAVE
            contenedor_metodos.controls.append(ft.Container(
                content=ft.Text(m["etiqueta"], size=12, color=color_txt, weight=ft.FontWeight.BOLD),
                bgcolor=color, border=ft.Border.all(1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8), border_radius=20,
                on_click=lambda e, c=m["clave"]: _elegir_metodo(c), ink=True))
        try: contenedor_metodos.update()
        except: pass

    def _rebuild_chips():
        contenedor_chips.controls.clear()
        m_conf = _metodo_conf()
        if not m_conf: return
        mon_fija = moneda_efectiva_metodo(m_conf)
        opciones = [mon_fija] if mon_fija else ["CUP", "USD", "EUR"]
        for op in opciones:
            activo = estado["moneda"] == op
            color = es.COLOR_ACENTO if activo else es.COLOR_SUPERFICIE
            color_txt = "#ffffff" if activo else es.COLOR_TEXTO_SUAVE
            contenedor_chips.controls.append(ft.Container(
                content=ft.Text(op, size=12, color=color_txt, weight=ft.FontWeight.BOLD),
                bgcolor=color, border=ft.Border.all(1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8), border_radius=20,
                on_click=lambda e, m=op: _elegir_moneda(m), ink=True))
        try: contenedor_chips.update()
        except: pass

    def _rec_info():
        m = estado["moneda"]
        t = inv.get_tasa(m)
        v = _leer_monto()
        saldo = _saldo_orden()
        bruto = v * t
        lbl_resumen.value = f"Recibes: ${bruto:,.2f} CUP · Saldo: ${saldo:,.2f}"
        sobrante = max(0.0, bruto - saldo)
        if sobrante > 0.01:
            lbl_vuelto.value = f"Sobrante: ${sobrante:,.2f} CUP"
        else:
            lbl_vuelto.value = ""
        try: lbl_resumen.update(); lbl_vuelto.update()
        except: pass

    def _on_monto_editado(e):
        try: estado["cup_objetivo"] = _leer_monto() * inv.get_tasa(estado["moneda"])
        except: pass
        _rec_info()

    tf_monto.on_change = _on_monto_editado
    dd_orden.on_change = _on_orden_change

    _rebuild_metodos(); _rebuild_chips(); _rec_info()

    def guardar(e):
        error_lbl.value = ""
        m = estado["moneda"]
        v = _leer_monto()
        if v <= 0:
            error_lbl.value = "El monto debe ser mayor que 0"
            page.update()
            return

        if (m or "").upper() != "CUP":
            v = ven.redondear_divisa(v, m)
            tf_monto.value = f"{v:g}"
            tf_monto.update()

        monto_cup_bruto = v * inv.get_tasa(m)
        sobrante = max(0.0, monto_cup_bruto - _saldo_orden())

        def _finalizar(destino=None):
            cli.registrar_abono(
                orden_id=int(estado["orden_id"]),
                monto=v,
                moneda=m,
                metodo=estado["metodo"],
                usuario=app.usuario,
                notas=tf_no.value,
                destino_sobrante=destino)
            page.pop_dialog()
            snack(page, "Abono registrado", "ok")
            rebuild()
            on_refresh()

        if sobrante > 0.01:
            page.pop_dialog()
            dlg_destino_sobrante(page, sobrante, _finalizar)
        else:
            _finalizar()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Abonar a {cliente['nombre']}"),
        content=ft.Column([
            dd_orden,
            ft.Text("Método", size=11, color=es.COLOR_TEXTO_SUAVE),
            contenedor_metodos,
            ft.Text("Moneda", size=11, color=es.COLOR_TEXTO_SUAVE),
            contenedor_chips,
            tf_monto,
            lbl_resumen,
            lbl_vuelto,
            tf_no,
            error_lbl,
        ], tight=True, width=460, spacing=8, scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Registrar abono", on_click=guardar, style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END
    ))

