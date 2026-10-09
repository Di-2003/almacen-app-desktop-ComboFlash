"""
Vista de proveedores: lista + crear/editar + detalle con saldo.
"""
import flet as ft
import proveedores as pv
from ui import estilos as es
from ui.componentes import (
    campo_busqueda, empty_state, snack, bottom_sheet, mounted, toast,
)
from ui._scroll import columna_scroll


def vista_proveedores(app):
    page = app.page
    estado = {"filtro": "", "ver_con_saldo": False}
    lista = columna_scroll("/proveedores", app, [], spacing=8)

    def refrescar():
        lista.controls.clear()
        if estado["ver_con_saldo"]:
            proveedores = pv.listar_con_saldo()
        else:
            proveedores = pv.listar_proveedores(
                solo_activos=True, texto=estado["filtro"] or None)

        for p in proveedores:
            lista.controls.append(_fila_proveedor(app, p, refrescar))

        if not proveedores:
            lista.controls.append(empty_state(
                ft.Icons.PEOPLE_OUTLINED,
                "Sin proveedores" if not estado["ver_con_saldo"]
                else "Sin saldos pendientes",
                "Crea el primero con el botón de arriba."))

        if mounted(lista):
            lista.update()

    def on_search(e):
        estado["filtro"] = (e.control.value or "").strip()
        refrescar()

    cap = campo_busqueda(hint="Buscar proveedor…", on_change=on_search)

    def toggle_saldo(e):
        estado["ver_con_saldo"] = not estado["ver_con_saldo"]
        _rebuild_botones()
        refrescar()

    def nuevo(e):
        _dlg_proveedor(app, None, refrescar)

    # Botón que se reconstruye para cambiar de texto
    boton_toggle_holder = ft.Container()

    def _rebuild_botones():
        filtrado = estado["ver_con_saldo"]
        boton_toggle_holder.content = ft.OutlinedButton(
            "Ver todos" if filtrado else "Ver cuentas por pagar",
            icon=(ft.Icons.PEOPLE if filtrado
                  else ft.Icons.RECEIPT_LONG),
            on_click=toggle_saldo, height=42,
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

    _rebuild_botones()
    refrescar()

    return ft.View(
        route="/proveedores",
        controls=[
            ft.Container(
                content=ft.Column([
                    cap,
                    ft.FilledButton(
                        "Nuevo proveedor", icon=ft.Icons.ADD,
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
            title=ft.Text("Proveedores", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )


def _fila_proveedor(app, p, on_refresh):
    saldo = p.get("saldo")
    if saldo is None:
        saldo = pv.saldo_proveedor(p["id"])
    deuda = saldo > 0.01
    a_favor = saldo < -0.01

    def tap(e):
        _detalle_proveedor(app, p, on_refresh)
    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.STOREFRONT,
                                color=es.COLOR_ACENTO, size=22),
                bgcolor=es.COLOR_ACENTO_SUAVE,
                padding=12, border_radius=10),
            ft.Column([
                ft.Text(p["nombre"], size=14,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(p.get("telefono") or "Sin teléfono", size=11,
                        color=es.COLOR_TEXTO_SUAVE),
            ], spacing=2, expand=True),
            ft.Column([
                ft.Text(f"${saldo:,.2f}", size=14,
                        color=(es.COLOR_PELIGRO if deuda
                               else es.COLOR_TEXTO_TENUE),
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.RIGHT),
                ft.Text(
                    "le debes" if deuda
                    else ("te debe" if a_favor else "al día"),
                    size=10,
                    color=(es.COLOR_PELIGRO if deuda
                           else es.COLOR_EXITO if a_favor
                           else es.COLOR_TEXTO_TENUE),
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


def _detalle_proveedor(app, p, on_refresh):
    page = app.page
    contenido_col = ft.Column(spacing=8, tight=True)

    def rebuild():
        contenido_col.controls.clear()
        saldo = pv.saldo_proveedor(p["id"])
        total_ent = pv.total_entradas_proveedor(p["id"])
        total_pag = pv.total_pagado_proveedor(p["id"])
        productos = pv.productos_de_proveedor(p["id"])
        pagos = pv.listar_pagos(p["id"], limite=30)

        contenido_col.controls += [
            ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.STOREFRONT,
                                    color=es.COLOR_ACENTO, size=28),
                    bgcolor=es.COLOR_ACENTO_SUAVE,
                    padding=14, border_radius=50),
                ft.Column([
                    ft.Text(p["nombre"], size=18,
                            weight=ft.FontWeight.BOLD,
                            color=es.COLOR_TEXTO),
                    ft.Text(p.get("telefono") or "—", size=12,
                            color=es.COLOR_TEXTO_SUAVE),
                ], spacing=2, expand=True),
            ]),
            ft.Container(height=6),
            ft.Container(
                content=ft.Column([
                    ft.Text("Saldo pendiente", size=11,
                            color=es.COLOR_TEXTO_TENUE),
                    ft.Text(f"${saldo:,.2f}", size=26,
                            weight=ft.FontWeight.BOLD,
                            color=(es.COLOR_PELIGRO if saldo > 0
                                   else es.COLOR_EXITO)),
                    ft.Text(
                        f"Entradas: ${total_ent:,.2f}  ·  "
                        f"Pagado: ${total_pag:,.2f}",
                        size=10, color=es.COLOR_TEXTO_TENUE),
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
                    on_click=lambda e: _dlg_proveedor(app, p, on_refresh),
                    expand=True,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_INFO, color="#ffffff")),
                ft.FilledButton(
                    "Registrar pago", icon=ft.Icons.PAYMENTS,
                    on_click=lambda e: _dlg_pago(app, p, rebuild),
                    expand=True,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_EXITO, color="#ffffff")),
            ], spacing=8),
            ft.Divider(height=1, color=es.COLOR_BORDE),
            ft.Text(f"Productos que provee ({len(productos)})",
                    size=13, weight=ft.FontWeight.BOLD,
                    color=es.COLOR_TEXTO),
        ]
        if not productos:
            contenido_col.controls.append(ft.Text(
                "Sin productos asociados todavía.",
                size=11, color=es.COLOR_TEXTO_SUAVE))
        else:
            for nombre in productos[:20]:
                contenido_col.controls.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INVENTORY_2,
                                color=es.COLOR_ACENTO, size=16),
                        ft.Text(nombre, size=12, expand=True,
                                color=es.COLOR_TEXTO),
                    ], spacing=8),
                    padding=8,
                    bgcolor=es.COLOR_SUPERFICIE_2,
                    border_radius=8))

        contenido_col.controls.append(ft.Divider(height=1,
                                                   color=es.COLOR_BORDE))
        contenido_col.controls.append(ft.Text(
            f"Historial de pagos ({len(pagos)})",
            size=13, weight=ft.FontWeight.BOLD,
            color=es.COLOR_TEXTO))
        if not pagos:
            contenido_col.controls.append(ft.Text(
                "Sin pagos registrados.",
                size=11, color=es.COLOR_TEXTO_SUAVE))
        else:
            for pago in pagos[:20]:
                contenido_col.controls.append(ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(pago["fecha"][:16], size=11,
                                    color=es.COLOR_TEXTO_SUAVE),
                            ft.Text(pago.get("metodo") or "—",
                                    size=10,
                                    color=es.COLOR_TEXTO_TENUE),
                        ], spacing=2, expand=True),
                        ft.Text(
                            f"{pago['monto']:,.2f} {pago['moneda']}",
                            size=12,
                            color=es.COLOR_EXITO,
                            weight=ft.FontWeight.BOLD),
                    ], spacing=8),
                    padding=10,
                    bgcolor=es.COLOR_SUPERFICIE_2,
                    border_radius=8))

        if mounted(contenido_col):
            contenido_col.update()

    rebuild()
    page.show_dialog(bottom_sheet(contenido_col, page=page,
                                    alto_max_pct=0.92))


def _dlg_proveedor(app, proveedor, on_refresh):
    page = app.page
    es_nuevo = proveedor is None

    tf_n = ft.TextField(
        label="Nombre",
        value=(proveedor["nombre"] if proveedor else ""),
        autofocus=True,
        **es.estilo_textfield(12), height=54)
    tf_t = ft.TextField(
        label="Teléfono (opcional)",
        value=(proveedor.get("telefono") or "" if proveedor else ""),
        keyboard_type=ft.KeyboardType.PHONE,
        **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            if es_nuevo:
                pv.crear_proveedor(tf_n.value, telefono=tf_t.value)
            else:
                pv.editar_proveedor(
                    proveedor["id"],
                    nombre=tf_n.value, telefono=tf_t.value)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        toast(page, "Proveedor guardado", "ok")
        if on_refresh:
            on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Nuevo proveedor" if es_nuevo
                      else f"Editar: {proveedor['nombre']}"),
        content=ft.Column([tf_n, tf_t, error_lbl],
                          tight=True, width=340, spacing=10),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_pago(app, proveedor, rebuild):
    page = app.page
    saldo_actual = pv.saldo_proveedor(proveedor["id"])

    tf_monto = ft.TextField(
        label="Monto",
        value=f"{saldo_actual:.2f}" if saldo_actual > 0 else "",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
        **es.estilo_textfield(12), height=54)

    dd_moneda = ft.Dropdown(
        label="Moneda", value="CUP",
        options=[
            ft.DropdownOption(key="CUP", text="$  CUP"),
            ft.DropdownOption(key="USD", text="USD$  USD"),
            ft.DropdownOption(key="EUR", text="€  EUR"),
        ],
        **es.borde_textfield(12))

    from configuracion_negocio import listar_metodos_pago
    metodos = listar_metodos_pago(solo_activos=True)
    met_ops = [ft.DropdownOption(key="", text="Sin especificar")]
    for m in metodos:
        met_ops.append(ft.DropdownOption(
            key=m["clave"], text=m["etiqueta"]))

    dd_met = ft.Dropdown(
        label="Método de pago",
        value="Efectivo CUP",
        options=met_ops,
        **es.borde_textfield(12))

    tf_no = ft.TextField(
        label="Notas (opcional)",
        **es.estilo_textfield(12), height=54)

    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            monto = float((tf_monto.value or "0").replace(",", "."))
        except ValueError:
            error_lbl.value = "Monto inválido"
            page.update()
            return
        try:
            pv.registrar_pago(
                proveedor_id=proveedor["id"],
                monto=monto,
                moneda=dd_moneda.value or "CUP",
                usuario=app.usuario,
                metodo=dd_met.value or None,
                notas=tf_no.value)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        toast(page, "Pago registrado", "ok")
        rebuild()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Pagar a {proveedor['nombre']}"),
        content=ft.Column([
            ft.Text(
                f"Saldo actual: ${saldo_actual:,.2f}",
                size=12, color=es.COLOR_TEXTO_SUAVE),
            ft.Container(height=6),
            tf_monto, dd_moneda, dd_met, tf_no, error_lbl,
        ], tight=True, width=340, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Registrar pago", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))