"""
Diálogos y bottom sheets de la app.

Contiene:
  - Detalle de producto (bottom sheet) con todas las acciones
  - Modal de entrada
  - Modal de salida (con motivo libre + rebaja)
  - Modal de traspaso entre locales
  - Diálogos: precio costo, precio venta, código, renombrar, umbrales, baja
"""
import flet as ft
import inventario as inv
import locales as loc
from db import GENERAL_ID
from ui import estilos as es
from ui.componentes import (
    chip_estado, snack, caja_info, bottom_sheet, cursor_al_final,
)


# ============ helpers ============

def _mensaje_movimiento(info: dict, accion: str,
                        delta: str) -> tuple[str, str]:
    c_antes = info["color_antes"]
    c_desp  = info["color_despues"]
    nombre  = info["nombre"]
    stock   = info["stock"]

    if c_desp == "rojo" and c_antes != "rojo":
        return (f"⚠️ {nombre} cayó a CRÍTICO "
                f"(stock: {inv.fmt_cantidad(stock)})", "error")
    if c_desp == "amarillo" and c_antes == "verde":
        return (f"⚠️ {nombre} bajó a BAJO "
                f"(stock: {inv.fmt_cantidad(stock)})", "warn")
    if c_desp == "verde" and c_antes in ("rojo", "amarillo"):
        return (f"✅ {nombre} volvió a OK "
                f"(stock: {inv.fmt_cantidad(stock)})", "ok")
    return (f"{accion}: {nombre} {delta}", "ok")


# ============ detalle de producto (bottom sheet) ============

def abrir_detalle_producto(app, prod, on_refresh=None):
    page = app.page
    color = inv.color_de_producto(prod)
    pc = float(prod.get("precio_costo", 0) or 0)
    pu = float(prod.get("precio_unitario", 0) or 0)
    rol = app.usuario["rol"]
    puede_operar = rol in ("admin", "almacen")
    es_general = app.es_general() or prod.get("id") is None

    cabecera = ft.Row(
        [
            ft.Column(
                [
                    ft.Text(prod["nombre"], size=17,
                            weight=ft.FontWeight.BOLD,
                            color=es.COLOR_TEXTO,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(prod.get("codigo") or "—",
                            size=11,
                            color=es.COLOR_TEXTO_SUAVE),
                    ft.Text(prod.get("fecha_ultima_mod") or "",
                            size=10,
                            color=es.COLOR_TEXTO_TENUE),
                ],
                spacing=1, expand=True,
            ),
            chip_estado(color),
        ],
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    stats = ft.Row(
        [
            _stat_box("Stock", inv.fmt_cantidad(prod["stock"])),
            _stat_box("Costo", f"${inv.fmt_precio(pc)}"),
            _stat_box("Venta", f"${inv.fmt_precio(pu)}"),
        ],
        spacing=8,
    )

    contenido = [cabecera, ft.Container(height=2), stats]

    if puede_operar and not es_general:
        def ent(e):
            page.pop_dialog()
            modal_entrada(app, producto=prod, on_refresh=on_refresh)

        def sal(e):
            page.pop_dialog()
            modal_salida(app, producto=prod, on_refresh=on_refresh)

        def trasp(e):
            page.pop_dialog()
            modal_traspaso(app, producto=prod, on_refresh=on_refresh)

        def pr_costo(e):
            page.pop_dialog()
            _dlg_precio_costo(app, prod, on_refresh)

        def pr_venta(e):
            page.pop_dialog()
            _dlg_precio_venta(app, prod, on_refresh)

        def cod(e):
            page.pop_dialog()
            _dlg_codigo(app, prod, on_refresh)

        def ren(e):
            page.pop_dialog()
            _dlg_renombrar(app, prod, on_refresh)

        def umb(e):
            page.pop_dialog()
            _dlg_umbrales(app, prod, on_refresh)

        def baja(e):
            page.pop_dialog()
            _conf_baja(app, prod, on_refresh)

        contenido += [
            ft.Container(height=6),
            ft.Row([
                _tile(ft.Icons.ADD, es.COLOR_EXITO, "Entrada", ent),
                _tile(ft.Icons.REMOVE, es.COLOR_PELIGRO, "Salida", sal),
                _tile(ft.Icons.SWAP_HORIZ, es.COLOR_INFO,
                      "Traspaso", trasp),
            ], spacing=8),
            ft.Row([
                _tile(ft.Icons.ATTACH_MONEY, es.COLOR_AMBAR,
                      "P. Costo", pr_costo),
                _tile(ft.Icons.SELL, es.COLOR_ACENTO,
                      "P. Venta", pr_venta),
                _tile(ft.Icons.TAG, es.COLOR_ACENTO,
                      "Código", cod),
            ], spacing=8),
            ft.Row([
                _tile(ft.Icons.EDIT, es.COLOR_ACENTO,
                      "Renombrar", ren),
                _tile(ft.Icons.TUNE, es.COLOR_AMBAR,
                      "Umbrales", umb),
                ft.Container(expand=True),
            ], spacing=8),
            ft.Container(height=2),
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.DELETE_OUTLINE,
                                color=es.COLOR_PELIGRO, size=18),
                        ft.Text("Dar de baja", size=12,
                                color=es.COLOR_PELIGRO,
                                weight=ft.FontWeight.W_600),
                    ],
                    spacing=8, alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(vertical=10),
                bgcolor=es.COLOR_PELIGRO_SUAVE,
                border_radius=10,
                on_click=baja, ink=True,
                alignment=ft.Alignment.CENTER,
            ),
        ]
    elif es_general:
        contenido += [
            ft.Container(height=4),
            caja_info("Vista General: no se puede editar. "
                    "Cambia a un local para operar.", "info"),
        ]
    else:
        contenido += [
            ft.Container(height=4),
            caja_info("Modo solo lectura: no puedes operar el stock.", "info"),
        ]

    page.show_dialog(bottom_sheet(
        ft.Column(contenido, spacing=6, tight=True),
        page = page,
    ))


def _stat_box(label, valor):
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(label, size=10,
                        color=es.COLOR_TEXTO_SUAVE,
                        weight=ft.FontWeight.W_600),
                ft.Text(valor, size=15,
                        weight=ft.FontWeight.BOLD,
                        color=es.COLOR_TEXTO),
            ],
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor=es.COLOR_SUPERFICIE_2,
        border_radius=10,
        expand=True,
    )


def _tile(icono, color_bg, label, on_click):
    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(icono, color="white", size=20),
                    bgcolor=color_bg,
                    padding=10, border_radius=12,
                ),
                ft.Text(label, size=12,
                        weight=ft.FontWeight.W_600,
                        color=es.COLOR_TEXTO,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
            ],
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=6, vertical=12),
        bgcolor=es.COLOR_SUPERFICIE_2,
        border_radius=12,
        on_click=on_click, ink=True,
        alignment=ft.Alignment.CENTER,
        expand=True,
    )


# ============ modal entrada ============

def modal_entrada(app, producto=None, on_refresh=None):
    page = app.page
    tf_p = ft.TextField(
        label="Producto",
        value=producto["nombre"] if producto else "",
        autofocus=True,
        **es.estilo_textfield(12), height=54,
    )
    tf_cod = ft.TextField(
        label="Código",
        value=(producto.get("codigo") or "") if producto
              else (inv.siguiente_codigo(app.local_id) or ""),
        **es.estilo_textfield(12), height=54,
    )
    tf_c = ft.TextField(
        label="Cantidad", value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )
    tf_pc = ft.TextField(
        label="Precio costo (opcional)",
        value=(str(producto.get("precio_costo", 0)) if producto else ""),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )
    tf_pu = ft.TextField(
        label="Precio venta (opcional)",
        value=(str(producto.get("precio_unitario", 0)) if producto
               else ""),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )
    lbl = ft.Container()

    def upd(e=None):
        n = (tf_p.value or "").strip()
        if not n:
            lbl.content = caja_info("Escribe un producto.")
        else:
            p = inv.buscar_producto_por_nombre(n, app.local_id)
            if p is None:
                lbl.content = caja_info("✨ Producto nuevo.", "info")
            else:
                lbl.content = caja_info(
                    f"Stock actual: {inv.fmt_cantidad(p['stock'])}",
                    "info")
        try:
            lbl.update()
        except Exception:
            pass

    tf_p.on_change = upd
    tf_p.on_focus = cursor_al_final
    upd()

    def guardar(e):
        n = (tf_p.value or "").strip()
        try:
            c = float((tf_c.value or "").replace(",", "."))
        except ValueError:
            snack(page, "Cantidad inválida", "error")
            return
        codigo = (tf_cod.value or "").strip() or None
        try:
            pc = float((tf_pc.value or "0").replace(",", ".")) or None
        except ValueError:
            pc = None
        try:
            pu = float((tf_pu.value or "0").replace(",", ".")) or None
        except ValueError:
            pu = None

        try:
            info = inv.registrar_entrada(
                nombre=n, cantidad=c,
                usuario=app.usuario, local_id=app.local_id,
                codigo=codigo, precio_costo=pc, precio_unitario=pu,
            )
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        texto, tipo = _mensaje_movimiento(
            info, "Entrada", f"+{inv.fmt_cantidad(c)}")
        snack(page, texto, tipo)
        if on_refresh:
            on_refresh()

    dlg = ft.AlertDialog(
        title=ft.Text("Registrar entrada"),
        content=ft.Column(
            [tf_p, tf_cod, tf_c, tf_pc, tf_pu, lbl],
            tight=True, spacing=10, width=340,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Guardar", on_click=guardar,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_EXITO, color="white",
                    shape=ft.RoundedRectangleBorder(
                        radius=ft.BorderRadius.all(10))),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)


# ============ modal salida ============

def modal_salida(app, producto=None, on_refresh=None):
    page = app.page
    tf_p = ft.TextField(
        label="Producto",
        value=producto["nombre"] if producto else "",
        autofocus=True,
        **es.estilo_textfield(12), height=54,
    )
    tf_c = ft.TextField(
        label="Cantidad", value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )
    tf_motivo = ft.TextField(
        label="Motivo",
        value=inv.motivo_default_salida(),
        **es.estilo_textfield(12), height=54,
    )
    tf_rebaja = ft.TextField(
        label="Rebaja por unidad (opcional)",
        value="0",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )
    lbl = ft.Container()

    def upd(e=None):
        n = (tf_p.value or "").strip()
        if not n:
            lbl.content = caja_info("Selecciona un producto.")
        else:
            p = inv.buscar_producto(n, app.local_id)
            if p is None or not p.get("activo", 1):
                lbl.content = caja_info("No encontrado o inactivo.",
                                        "error")
            else:
                try:
                    c = float((tf_c.value or "0").replace(",", "."))
                except ValueError:
                    c = 0
                try:
                    reb = float((tf_rebaja.value or "0").replace(",", "."))
                except ValueError:
                    reb = 0
                pu = float(p["precio_unitario"] or 0)
                if c > p["stock"]:
                    lbl.content = caja_info(
                        f"Stock insuficiente "
                        f"({inv.fmt_cantidad(p['stock'])})", "error")
                elif reb > pu:
                    lbl.content = caja_info(
                        f"Rebaja > precio (${inv.fmt_precio(pu)})",
                        "error")
                else:
                    total = (pu - reb) * c
                    lbl.content = caja_info(
                        f"{inv.fmt_cantidad(p['stock'])} → "
                        f"{inv.fmt_cantidad(p['stock'] - c)}  ·  "
                        f"Total: ${total:,.2f}", "ok")
        try:
            lbl.update()
        except Exception:
            pass

    tf_p.on_change = upd
    tf_c.on_change = upd
    tf_rebaja.on_change = upd
    tf_p.on_focus = cursor_al_final
    upd()

    def guardar(e):
        n = (tf_p.value or "").strip()
        try:
            c = float((tf_c.value or "").replace(",", "."))
        except ValueError:
            snack(page, "Cantidad inválida", "error")
            return
        try:
            reb = float((tf_rebaja.value or "0").replace(",", "."))
        except ValueError:
            reb = 0.0
        motivo = (tf_motivo.value or "").strip() or None

        try:
            info = inv.registrar_salida(
                nombre_o_codigo=n, cantidad=c,
                usuario=app.usuario, local_id=app.local_id,
                motivo=motivo, rebaja=reb,
            )
        except inv.StockInsuficiente as ex:
            snack(page, str(ex), "error")
            return
        except inv.ProductoNoExiste as ex:
            snack(page, str(ex), "error")
            return
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        texto, tipo = _mensaje_movimiento(
            info, "Salida", f"-{inv.fmt_cantidad(c)}")
        snack(page, texto, tipo)
        if on_refresh:
            on_refresh()

    dlg = ft.AlertDialog(
        title=ft.Text("Registrar salida"),
        content=ft.Column(
            [tf_p, tf_c, tf_motivo, tf_rebaja, lbl],
            tight=True, spacing=10, width=340,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Guardar", on_click=guardar,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_PELIGRO, color="white",
                    shape=ft.RoundedRectangleBorder(
                        radius=ft.BorderRadius.all(10))),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)


# ============ modal traspaso ============

def modal_traspaso(app, producto=None, on_refresh=None):
    page = app.page
    locales_destino = [
        l for l in loc.listar_locales(solo_activos=True)
        if l["id"] != app.local_id
    ]
    if not locales_destino:
        snack(page, "No hay otros locales disponibles", "error")
        return

    tf_p = ft.TextField(
        label="Producto",
        value=producto["nombre"] if producto else "",
        autofocus=True,
        **es.estilo_textfield(12), height=54,
    )
    tf_c = ft.TextField(
        label="Cantidad", value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )
    dd_dest = ft.Dropdown(
        label="Local destino",
        value=str(locales_destino[0]["id"]),
        options=[ft.DropdownOption(key=str(l["id"]), text=l["nombre"])
                 for l in locales_destino],
        **es.borde_textfield(12),
    )
    lbl = ft.Container()
    lbl_origen = ft.Text(
        f"Origen: {loc.nombre_local(app.local_id)}",
        size=12, color=es.COLOR_TEXTO_SUAVE,
    )

    def upd(e=None):
        n = (tf_p.value or "").strip()
        if not n:
            lbl.content = caja_info("Selecciona un producto.")
        else:
            p = inv.buscar_producto(n, app.local_id)
            if p is None or not p.get("activo", 1):
                lbl.content = caja_info("No encontrado o inactivo.",
                                        "error")
            else:
                try:
                    c = float((tf_c.value or "0").replace(",", "."))
                except ValueError:
                    c = 0
                if c > p["stock"]:
                    lbl.content = caja_info(
                        f"Stock insuficiente "
                        f"({inv.fmt_cantidad(p['stock'])})", "error")
                else:
                    lbl.content = caja_info(
                        f"{loc.nombre_local(app.local_id)}: "
                        f"{inv.fmt_cantidad(p['stock'])} → "
                        f"{inv.fmt_cantidad(p['stock'] - c)}", "ok")
        try:
            lbl.update()
        except Exception:
            pass

    tf_p.on_change = upd
    tf_c.on_change = upd
    tf_p.on_focus = cursor_al_final
    upd()

    def guardar(e):
        n = (tf_p.value or "").strip()
        try:
            c = float((tf_c.value or "").replace(",", "."))
        except ValueError:
            snack(page, "Cantidad inválida", "error")
            return
        dest_id = dd_dest.value
        if not dest_id:
            snack(page, "Selecciona destino", "error")
            return
        try:
            inv.registrar_traspaso(
                nombre_o_codigo=n, cantidad=c,
                usuario=app.usuario,
                local_origen_id=app.local_id,
                local_destino_id=int(dest_id),
            )
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, f"Traspaso: {n} -{inv.fmt_cantidad(c)}", "ok")
        if on_refresh:
            on_refresh()

    dlg = ft.AlertDialog(
        title=ft.Text("Traspaso entre locales"),
        content=ft.Column(
            [lbl_origen, tf_p, tf_c, dd_dest, lbl],
            tight=True, spacing=10, width=340,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Traspasar", on_click=guardar,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_INFO, color="white",
                    shape=ft.RoundedRectangleBorder(
                        radius=ft.BorderRadius.all(10))),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    page.show_dialog(dlg)


# ============ diálogos de edición ============

def _dlg_precio_costo(app, prod, on_refresh=None):
    page = app.page
    tf = ft.TextField(
        label="Precio costo",
        value=str(float(prod.get("precio_costo", 0) or 0)),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )

    def guardar(e):
        try:
            inv.set_precio_costo(
                prod["id"],
                float((tf.value or "0").replace(",", ".")),
                usuario=app.usuario)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Precio costo actualizado (propagado)", "ok")
        if on_refresh:
            on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Precio costo: {prod['nombre']}"),
        content=ft.Column([tf], tight=True, width=300),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_precio_venta(app, prod, on_refresh=None):
    page = app.page
    tf = ft.TextField(
        label="Precio venta",
        value=str(float(prod.get("precio_unitario", 0) or 0)),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )

    def guardar(e):
        try:
            inv.set_precio_unitario(
                prod["id"],
                float((tf.value or "0").replace(",", ".")),
                usuario=app.usuario)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Precio venta actualizado (propagado)", "ok")
        if on_refresh:
            on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Precio venta: {prod['nombre']}"),
        content=ft.Column([tf], tight=True, width=300),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_codigo(app, prod, on_refresh=None):
    page = app.page
    tf = ft.TextField(
        label="Código (Fxyyyy o vacío)",
        value=(prod.get("codigo") or ""),
        **es.estilo_textfield(12), height=54,
    )
    tf.on_focus = cursor_al_final

    def guardar(e):
        try:
            inv.set_codigo(prod["id"], tf.value, usuario=app.usuario)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Código actualizado (propagado)", "ok")
        if on_refresh:
            on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Código: {prod['nombre']}"),
        content=ft.Column(
            [
                tf,
                ft.Text(
                    "Sugerido: "
                    f"{inv.siguiente_codigo(app.local_id) or '—'}",
                    size=11, color=es.COLOR_TEXTO_SUAVE),
            ],
            tight=True, width=300, spacing=6,
        ),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_renombrar(app, prod, on_refresh=None):
    page = app.page
    tf = ft.TextField(
        label="Nuevo nombre",
        value=prod["nombre"],
        autofocus=True,
        **es.estilo_textfield(12), height=54,
    )
    tf.on_focus = cursor_al_final

    def guardar(e):
        try:
            inv.renombrar_producto(prod["id"], tf.value,
                                    usuario=app.usuario)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Producto renombrado (propagado)", "ok")
        if on_refresh:
            on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Renombrar: {prod['nombre']}"),
        content=ft.Column([tf], tight=True, width=320),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_umbrales(app, prod, on_refresh=None):
    page = app.page
    tf_v = ft.TextField(
        label="Umbral verde",
        value=str(prod["umbral_verde"]),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )
    tf_a = ft.TextField(
        label="Umbral amarillo",
        value=str(prod["umbral_amarillo"]),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )

    def guardar(e):
        try:
            inv.cambiar_umbrales(
                prod["id"], int(tf_v.value), int(tf_a.value),
                usuario=app.usuario)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Umbrales actualizados", "ok")
        if on_refresh:
            on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Umbrales: {prod['nombre']}"),
        content=ft.Column([tf_v, tf_a], tight=True, width=300, spacing=10),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _conf_baja(app, prod, on_refresh=None):
    page = app.page
    tf_m = ft.TextField(
        label="Motivo", value="Merma",
        **es.estilo_textfield(12), height=54,
    )

    def hacer(e):
        m = (tf_m.value or "Merma").strip() or "Merma"
        try:
            inv.dar_baja(prod["id"], usuario=app.usuario, motivo=m)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, f"{prod['nombre']} dado de baja", "ok")
        if on_refresh:
            on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Dar de baja"),
        content=ft.Column(
            [ft.Text(f"¿Dar de baja «{prod['nombre']}»?"), tf_m],
            tight=True, width=320, spacing=12),
        actions=[
            ft.TextButton("Cancelar",
                        on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Dar de baja", on_click=hacer,
                            style=ft.ButtonStyle(
                                bgcolor=es.COLOR_PELIGRO, color="white")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))