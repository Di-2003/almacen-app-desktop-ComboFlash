"""
CRUD de clientes + vista cuentas por cobrar + detalle + abonos.
"""
import flet as ft
import clientes as cli
from ui import estilos as es
from ui.componentes import (
    campo_busqueda, empty_state, snack, bottom_sheet, mounted,
)


def vista_clientes(app):
    page = app.page
    estado = {"filtro": "", "ver_deuda": False}
    lista = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    def refrescar():
        lista.controls.clear()
        if estado["ver_deuda"]:
            cs = cli.listar_con_deuda()
        else:
            cs = cli.listar_clientes(
                solo_activos=True, texto=estado["filtro"] or None)

        for c in cs:
            lista.controls.append(_fila_cliente(app, c, refrescar))

        if not cs:
            lista.controls.append(empty_state(
                ft.Icons.PEOPLE_OUTLINED,
                "Sin clientes" if not estado["ver_deuda"]
                else "Sin deudas",
                "Agrega el primero con el botón de arriba."))

        if mounted(lista):
            lista.update()

    def on_search(e):
        estado["filtro"] = (e.control.value or "").strip()
        refrescar()

    cap = campo_busqueda(hint="Buscar cliente…", on_change=on_search)

    boton_toggle_holder = ft.Container()

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
        try:
            boton_toggle_holder.update()
        except Exception:
            pass

    def toggle_deuda(e):
        estado["ver_deuda"] = not estado["ver_deuda"]
        _rebuild_botones()
        refrescar()

    _rebuild_botones()

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
    page = app.page
    saldo = cli.saldo_pendiente(c["id"])
    deuda = saldo > 0.01

    def tap(e):
        _detalle_cliente(app, c, on_refresh)

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.PERSON,
                                color=es.COLOR_ACENTO, size=22),
                bgcolor=es.COLOR_ACENTO_SUAVE,
                padding=12, border_radius=10),
            ft.Column([
                ft.Text(c["nombre"], size=14,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.Text(c.get("telefono") or "Sin teléfono", size=11,
                        color=es.COLOR_TEXTO_SUAVE),
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
    )


def _detalle_cliente(app, c, on_refresh):
    page = app.page
    contenido_col = ft.Column(spacing=8, tight=True)

    def rebuild():
        contenido_col.controls.clear()
        saldo = cli.saldo_pendiente(c["id"])
        ordenes = cli.historial_compras(c["id"], limite=20)

        contenido_col.controls += [
            ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.PERSON,
                                    color=es.COLOR_ACENTO, size=28),
                    bgcolor=es.COLOR_ACENTO_SUAVE,
                    padding=14, border_radius=50),
                ft.Column([
                    ft.Text(c["nombre"], size=18,
                            weight=ft.FontWeight.BOLD,
                            color=es.COLOR_TEXTO),
                    ft.Text(c.get("telefono") or "—", size=12,
                            color=es.COLOR_TEXTO_SUAVE),
                    ft.Text(c.get("direccion") or "", size=11,
                            color=es.COLOR_TEXTO_TENUE),
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
                        bgcolor=es.COLOR_EXITO, color="#ffffff")),
            ], spacing=8),
            ft.Divider(height=1, color=es.COLOR_BORDE),
            ft.Text("Historial de compras", size=14,
                    weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ]

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
    dlg_ref = {"dlg": None}

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

    def eliminar(e):
        page.pop_dialog()
        _confirmar_eliminar(app, cliente, on_refresh)

    acciones = [
        ft.TextButton("Cancelar",
                      on_click=lambda e: page.pop_dialog()),
        ft.FilledButton(
            "Guardar", on_click=guardar,
            style=es.estilo_boton_marca()),
    ]
    if not es_nuevo:
        acciones.insert(0, ft.TextButton(
            "Desactivar", icon=ft.Icons.PERSON_OFF,
            on_click=eliminar,
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
            "Su historial se conserva pero no aparecerá en la lista.",
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
    page = app.page
    ordenes = cli.listar_ordenes_pendientes(cliente["id"])

    if not ordenes:
        snack(page, "No hay órdenes pendientes", "info")
        return

    dd_orden = ft.Dropdown(
        label="Orden",
        value=str(ordenes[0]["id"]),
        options=[ft.DropdownOption(
            key=str(o["id"]),
            text=f"{o['numero_ticket']} · ${o['saldo_pendiente']:,.2f}")
            for o in ordenes],
        **es.borde_textfield(12))

    from configuracion_negocio import listar_metodos_pago
    metodos = listar_metodos_pago(solo_activos=True)
    if not metodos:
        snack(page, "No hay métodos de pago activos", "error")
        return

    dd_met = ft.Dropdown(
        label="Método",
        value=metodos[0]["clave"],
        options=[ft.DropdownOption(key=m["clave"], text=m["etiqueta"])
                 for m in metodos],
        **es.borde_textfield(12))

    tf_m = ft.TextField(label="Monto (CUP)",
                        keyboard_type=ft.KeyboardType.NUMBER,
                        autofocus=True,
                        **es.estilo_textfield(12), height=54)
    tf_no = ft.TextField(label="Notas (opcional)",
                         **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            cli.registrar_abono(
                orden_id=int(dd_orden.value),
                monto=float((tf_m.value or "0").replace(",", ".")),
                moneda="CUP",
                metodo=dd_met.value,
                usuario=app.usuario,
                notas=tf_no.value)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Abono registrado", "ok")
        rebuild()
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Abonar a {cliente['nombre']}"),
        content=ft.Column([dd_orden, dd_met, tf_m, tf_no, error_lbl],
                          tight=True, width=340, spacing=10,
                          scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Registrar abono", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))