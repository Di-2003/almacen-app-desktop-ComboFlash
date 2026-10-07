"""
Diálogos. Incluye moneda original, promedio ponderado y moneda
de visualización.
"""
from datetime import datetime
import flet as ft
import inventario as inv
import locales as loc
from db import GENERAL_ID
from ui import estilos as es
from ui.componentes import (
    chip_estado, chip_inactivo, snack, caja_info, bottom_sheet,
    cursor_al_final, cerrar_dialogo,
)


def _mensaje_movimiento(info, accion, delta):
    c_antes = info["color_antes"]
    c_desp = info["color_despues"]
    nombre = info["nombre"]
    stock = info["stock"]
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


def _ahora_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============ detalle de producto ============

def abrir_detalle_producto(app, prod, on_refresh=None):
    page = app.page
    color = inv.color_de_producto(prod)
    pc_cup = float(prod.get("precio_costo", 0) or 0)
    pu_cup = float(prod.get("precio_unitario", 0) or 0)
    pc_orig = float(prod.get("precio_costo_orig", 0) or 0)
    pu_orig = float(prod.get("precio_unitario_orig", 0) or 0)
    mc = (prod.get("moneda_costo") or "CUP").upper()
    mv = (prod.get("moneda_venta") or "CUP").upper()

    rol = app.usuario["rol"]
    puede_operar = rol in ("admin", "almacen")
    es_general = app.es_general() or prod.get("id") is None
    esta_activo = prod.get("activo", 1) == 1

    cabecera = ft.Row([
        ft.Column([
            ft.Text(prod["nombre"], size=17, weight=ft.FontWeight.BOLD,
                    color=es.COLOR_TEXTO, max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(prod.get("codigo") or "—", size=11,
                    color=es.COLOR_TEXTO_SUAVE),
            ft.Text(prod.get("fecha_ultima_mod") or "", size=10,
                    color=es.COLOR_TEXTO_TENUE),
        ], spacing=1, expand=True),
        chip_estado(color) if esta_activo else chip_inactivo(),
    ], vertical_alignment=ft.CrossAxisAlignment.START)

    def _stat(label, valor, sub=""):
        hijos = [
            ft.Text(label, size=10, color=es.COLOR_TEXTO_SUAVE,
                    weight=ft.FontWeight.W_600),
            ft.Text(valor, size=15, weight=ft.FontWeight.BOLD,
                    color=es.COLOR_TEXTO),
        ]
        if sub:
            hijos.append(ft.Text(sub, size=10, color=es.COLOR_ACENTO))
        return ft.Container(
            content=ft.Column(hijos, spacing=2,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=es.COLOR_SUPERFICIE_2,
            border_radius=10, expand=True,
        )

    sub_costo = (f"{inv.fmt_precio(pc_orig)} {mc}"
                 if mc != "CUP" else "")
    sub_venta = (f"{inv.fmt_precio(pu_orig)} {mv}"
                 if mv != "CUP" else "")

    stats = ft.Row([
        _stat("Stock", inv.fmt_cantidad(prod["stock"])),
        _stat("Costo", f"${inv.fmt_precio(pc_cup)}", sub_costo),
        _stat("Venta", f"${inv.fmt_precio(pu_cup)}", sub_venta),
    ], spacing=8)

    contenido = [cabecera, ft.Container(height=2), stats]

    if not esta_activo and puede_operar and not es_general:
        def reactivar(e):
            cerrar_dialogo(page)
            try:
                inv.reactivar_producto(prod["id"], app.usuario)
                snack(page, f"{prod['nombre']} reactivado", "ok")
                if on_refresh:
                    on_refresh()
            except Exception as ex:
                snack(page, str(ex), "error")
        contenido += [
            ft.Container(height=6),
            caja_info("Este producto está dado de baja. "
                      "Reactívalo para operarlo.", "warn"),
            ft.Container(height=6),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.RESTORE, color="white", size=20),
                    ft.Text("Reactivar producto", size=14,
                            color="white", weight=ft.FontWeight.W_600),
                ], spacing=10, alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(vertical=14),
                bgcolor=es.COLOR_EXITO, border_radius=12,
                on_click=reactivar, ink=True,
                alignment=ft.Alignment.CENTER,
            ),
        ]
        page.show_dialog(bottom_sheet(
            ft.Column(contenido, spacing=6, tight=True), page=page))
        return

    if puede_operar and not es_general:
        def ent(e):
            cerrar_dialogo(page)
            modal_entrada(app, producto=prod, on_refresh=on_refresh)
        def sal(e):
            cerrar_dialogo(page)
            modal_salida(app, producto=prod, on_refresh=on_refresh)
        def trasp(e):
            cerrar_dialogo(page)
            modal_traspaso(app, producto=prod, on_refresh=on_refresh)
        def pr_costo(e):
            cerrar_dialogo(page)
            _dlg_precio_costo(app, prod, on_refresh)
        def pr_venta(e):
            cerrar_dialogo(page)
            _dlg_precio_venta(app, prod, on_refresh)
        def cod(e):
            cerrar_dialogo(page)
            _dlg_codigo(app, prod, on_refresh)
        def ren(e):
            cerrar_dialogo(page)
            _dlg_renombrar(app, prod, on_refresh)
        def umb(e):
            cerrar_dialogo(page)
            _dlg_umbrales(app, prod, on_refresh)
        def baja(e):
            cerrar_dialogo(page)
            _conf_baja(app, prod, on_refresh)

        contenido += [
            ft.Container(height=6),
            ft.Row([
                _tile(ft.Icons.ADD, es.COLOR_EXITO, "Entrada", ent),
                _tile(ft.Icons.REMOVE, es.COLOR_PELIGRO, "Salida", sal),
                _tile(ft.Icons.SWAP_HORIZ, es.COLOR_INFO, "Traspaso", trasp),
            ], spacing=8),
            ft.Row([
                _tile(ft.Icons.ATTACH_MONEY, es.COLOR_AMBAR, "P. Costo", pr_costo),
                _tile(ft.Icons.SELL, es.COLOR_ACENTO, "P. Venta", pr_venta),
                _tile(ft.Icons.TAG, es.COLOR_ACENTO, "Código", cod),
            ], spacing=8),
            ft.Row([
                _tile(ft.Icons.EDIT, es.COLOR_ACENTO, "Renombrar", ren),
                _tile(ft.Icons.TUNE, es.COLOR_AMBAR, "Umbrales", umb),
                ft.Container(expand=True),
            ], spacing=8),
            ft.Container(height=2),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.DELETE_OUTLINE,
                            color=es.COLOR_PELIGRO, size=18),
                    ft.Text("Dar de baja", size=12,
                            color=es.COLOR_PELIGRO,
                            weight=ft.FontWeight.W_600),
                ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(vertical=10),
                bgcolor=es.COLOR_PELIGRO_SUAVE,
                border_radius=10,
                on_click=baja, ink=True,
                alignment=ft.Alignment.CENTER,
            ),
        ]
    elif es_general:
        contenido += [ft.Container(height=4),
                      caja_info("Vista General: no editable.", "info")]
    else:
        contenido += [ft.Container(height=4),
                      caja_info("Modo solo lectura.", "info")]

    page.show_dialog(bottom_sheet(
        ft.Column(contenido, spacing=6, tight=True), page=page))


def _tile(icono, color_bg, label, on_click):
    return ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Icon(icono, color="white", size=20),
                bgcolor=color_bg, padding=10, border_radius=12,
            ),
            ft.Text(label, size=12, weight=ft.FontWeight.W_600,
                    color=es.COLOR_TEXTO, text_align=ft.TextAlign.CENTER,
                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=6, vertical=12),
        bgcolor=es.COLOR_SUPERFICIE_2,
        border_radius=12, on_click=on_click, ink=True,
        alignment=ft.Alignment.CENTER, expand=True,
    )


# ============ modal entrada ============

def modal_entrada(app, producto=None, on_refresh=None):
    page = app.page
    tf_p = ft.TextField(
        label="Producto",
        value=producto["nombre"] if producto else "",
        autofocus=True, **es.estilo_textfield(12), height=54)
    tf_cod = ft.TextField(
        label="Código",
        value=(producto.get("codigo") or "") if producto
              else (inv.siguiente_codigo(app.local_id) or ""),
        **es.estilo_textfield(12), height=54)
    tf_c = ft.TextField(
        label="Cantidad", value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)
    tf_pc = ft.TextField(
        label="Precio costo (opcional)",
        value=(str(producto.get("precio_costo_orig", 0)) if producto else ""),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)
    tf_pu = ft.TextField(
        label="Precio venta (opcional)",
        value=(str(producto.get("precio_unitario_orig", 0)) if producto else ""),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)

    moneda_default = "CUP"
    if producto and producto.get("moneda_costo"):
        moneda_default = producto["moneda_costo"]

    dd_moneda = ft.Dropdown(
        label="Moneda",
        value=moneda_default,
        options=[
            ft.DropdownOption(key="CUP", text="CUP  $"),
            ft.DropdownOption(key="USD", text="USD  USD$"),
            ft.DropdownOption(key="EUR", text="EUR  €"),
        ],
        **es.borde_textfield(12),
    )
    tf_fecha = ft.TextField(
        label="Fecha y hora (YYYY-MM-DD)",
        value=_ahora_str(),
        **es.estilo_textfield(12), height=54)
    lbl = ft.Container()
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def upd(e=None):
        n = (tf_p.value or "").strip()
        if not n:
            lbl.content = caja_info("Escribe un producto.")
        else:
            p = inv.buscar_producto_por_nombre(n, app.local_id)
            if p is None:
                pg = inv.buscar_producto_global_por_nombre(n)
                if pg:
                    lbl.content = caja_info(
                        f"Existe en «{pg['local_nombre']}». "
                        f"Se creará en este local.", "info")
                else:
                    lbl.content = caja_info("✨ Producto nuevo.", "info")
            else:
                lbl.content = caja_info(
                    f"Stock actual: {inv.fmt_cantidad(p['stock'])}  ·  "
                    f"Moneda: {p.get('moneda_costo','CUP')}", "info")
                if p.get("moneda_costo"):
                    dd_moneda.value = p["moneda_costo"]
        try:
            lbl.update()
        except Exception:
            pass

    def autocompletar_desde_codigo(e):
        cod = (tf_cod.value or "").strip()
        if not cod:
            return
        p = inv.buscar_producto_por_codigo(cod, app.local_id)
        if p is not None:
            if not (tf_p.value or "").strip():
                tf_p.value = p["nombre"]
        else:
            pg = inv.buscar_producto_global_por_codigo(cod)
            if pg and not (tf_p.value or "").strip():
                tf_p.value = pg["nombre"]
        upd()
        try:
            page.update()
        except Exception:
            pass

    def autocompletar_desde_nombre(e):
        nom = (tf_p.value or "").strip()
        if not nom:
            return
        p = inv.buscar_producto_por_nombre(nom, app.local_id)
        if p is not None:
            if not (tf_cod.value or "").strip():
                tf_cod.value = p.get("codigo") or ""
        else:
            pg = inv.buscar_producto_global_por_nombre(nom)
            if pg and not (tf_cod.value or "").strip():
                tf_cod.value = pg.get("codigo") or ""
        upd()
        try:
            page.update()
        except Exception:
            pass

    tf_p.on_change = autocompletar_desde_nombre
    tf_cod.on_change = autocompletar_desde_codigo
    tf_p.on_focus = cursor_al_final
    upd()

    def guardar(e):
        error_lbl.value = ""
        n = (tf_p.value or "").strip()
        if not n:
            error_lbl.value = "El nombre no puede estar vacío"
            page.update()
            return
        try:
            c = float((tf_c.value or "").replace(",", "."))
        except ValueError:
            error_lbl.value = "Cantidad inválida"
            page.update()
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
        fecha = (tf_fecha.value or "").strip() or None
        moneda = dd_moneda.value or "CUP"

        try:
            info = inv.registrar_entrada(
                nombre=n, cantidad=c, usuario=app.usuario,
                local_id=app.local_id, codigo=codigo,
                precio_costo=pc, precio_unitario=pu,
                moneda=moneda, fecha=fecha)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        texto, tipo = _mensaje_movimiento(
            info, "Entrada", f"+{inv.fmt_cantidad(c)}")

        def _despues():
            snack(page, texto, tipo)
            if on_refresh:
                on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text("Registrar entrada"),
        content=ft.Column([
            tf_p, tf_cod, tf_c, tf_pc, tf_pu, dd_moneda,
            ft.Container(height=10), tf_fecha, lbl, error_lbl,
        ], tight=True, spacing=10, width=340, scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton(
                "Guardar", on_click=guardar,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_EXITO, color="white",
                    shape=ft.RoundedRectangleBorder(
                        radius=ft.BorderRadius.all(10)))),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


# ============ modal salida ============

def modal_salida(app, producto=None, on_refresh=None):
    page = app.page
    tf_p = ft.TextField(
        label="Producto",
        value=producto["nombre"] if producto else "",
        autofocus=True, **es.estilo_textfield(12), height=54)
    tf_c = ft.TextField(
        label="Cantidad", value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)
    tf_motivo = ft.TextField(
        label="Motivo", value=inv.motivo_default_salida(),
        **es.estilo_textfield(12), height=54)
    tf_rebaja = ft.TextField(
        label="Rebaja por unidad (opcional)", value="0",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)
    tf_fecha = ft.TextField(
        label="Fecha y hora (YYYY-MM-DD)",
        value=_ahora_str(), **es.estilo_textfield(12), height=54)
    lbl = ft.Container()
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def upd(e=None):
        n = (tf_p.value or "").strip()
        if not n:
            lbl.content = caja_info("Selecciona un producto.")
        else:
            p = inv.buscar_producto(n, app.local_id)
            if p is None or not p.get("activo", 1):
                lbl.content = caja_info("No encontrado o inactivo.", "error")
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
                        f"Rebaja > precio (${inv.fmt_precio(pu)})", "error")
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
        error_lbl.value = ""
        n = (tf_p.value or "").strip()
        if not n:
            error_lbl.value = "Selecciona un producto"
            page.update()
            return
        try:
            c = float((tf_c.value or "").replace(",", "."))
        except ValueError:
            error_lbl.value = "Cantidad inválida"
            page.update()
            return
        try:
            reb = float((tf_rebaja.value or "0").replace(",", "."))
        except ValueError:
            reb = 0.0
        motivo = (tf_motivo.value or "").strip() or None
        fecha = (tf_fecha.value or "").strip() or None
        try:
            info = inv.registrar_salida(
                nombre_o_codigo=n, cantidad=c, usuario=app.usuario,
                local_id=app.local_id, motivo=motivo,
                rebaja=reb, fecha=fecha)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        texto, tipo = _mensaje_movimiento(
            info, "Salida", f"-{inv.fmt_cantidad(c)}")

        def _despues():
            snack(page, texto, tipo)
            if on_refresh:
                on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text("Registrar salida"),
        content=ft.Column([
            tf_p, tf_c, tf_motivo, tf_rebaja,
            ft.Container(height=10), tf_fecha, lbl, error_lbl,
        ], tight=True, spacing=10, width=340, scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton(
                "Guardar", on_click=guardar,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_PELIGRO, color="white",
                    shape=ft.RoundedRectangleBorder(
                        radius=ft.BorderRadius.all(10)))),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


# ============ traspaso ============

def modal_traspaso(app, producto=None, on_refresh=None):
    page = app.page
    locales_destino = [
        l for l in loc.listar_locales(solo_activos=True)
        if l["id"] != app.local_id
    ]
    if not locales_destino:
        snack(page, "No hay otros locales", "error")
        return

    tf_p = ft.TextField(
        label="Producto",
        value=producto["nombre"] if producto else "",
        autofocus=True, **es.estilo_textfield(12), height=54)
    tf_c = ft.TextField(
        label="Cantidad", value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)
    dd_dest = ft.Dropdown(
        label="Local destino",
        value=str(locales_destino[0]["id"]),
        options=[ft.DropdownOption(key=str(l["id"]), text=l["nombre"])
                 for l in locales_destino],
        **es.borde_textfield(12))
    lbl = ft.Container()
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    lbl_origen = ft.Text(f"Origen: {loc.nombre_local(app.local_id)}",
                          size=12, color=es.COLOR_TEXTO_SUAVE)
    dlg_ref = {"dlg": None}

    def upd(e=None):
        n = (tf_p.value or "").strip()
        if not n:
            lbl.content = caja_info("Selecciona un producto.")
        else:
            p = inv.buscar_producto(n, app.local_id)
            if p is None or not p.get("activo", 1):
                lbl.content = caja_info("No encontrado o inactivo.", "error")
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
        error_lbl.value = ""
        n = (tf_p.value or "").strip()
        if not n:
            error_lbl.value = "Selecciona un producto"
            page.update()
            return
        try:
            c = float((tf_c.value or "").replace(",", "."))
        except ValueError:
            error_lbl.value = "Cantidad inválida"
            page.update()
            return
        if not dd_dest.value:
            error_lbl.value = "Selecciona destino"
            page.update()
            return
        try:
            inv.registrar_traspaso(
                nombre_o_codigo=n, cantidad=c, usuario=app.usuario,
                local_origen_id=app.local_id,
                local_destino_id=int(dd_dest.value))
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        txt = f"Traspaso: {n} -{inv.fmt_cantidad(c)}"

        def _despues():
            snack(page, txt, "ok")
            if on_refresh:
                on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text("Traspaso"),
        content=ft.Column([
            lbl_origen, tf_p, tf_c, dd_dest, lbl, error_lbl,
        ], tight=True, spacing=10, width=340, scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton(
                "Traspasar", on_click=guardar,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_INFO, color="white",
                    shape=ft.RoundedRectangleBorder(
                        radius=ft.BorderRadius.all(10)))),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


# ============ diálogos de edición ============

def _dlg_precio(app, prod, cual, on_refresh=None):
    page = app.page
    campo_orig = ("precio_costo_orig" if cual == "costo"
                  else "precio_unitario_orig")
    campo_moneda = ("moneda_costo" if cual == "costo"
                    else "moneda_venta")
    titulo = "Precio costo" if cual == "costo" else "Precio venta"
    valor_actual = float(prod.get(campo_orig, 0) or 0)
    moneda_actual = prod.get(campo_moneda) or "CUP"

    tf = ft.TextField(
        label=titulo, value=str(valor_actual),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)

    dd_moneda = ft.Dropdown(
        label="Moneda del valor",
        value=moneda_actual,
        options=[
            ft.DropdownOption(key="CUP", text="$  CUP"),
            ft.DropdownOption(key="USD", text="USD$  USD"),
            ft.DropdownOption(key="EUR", text="€  EUR"),
        ],
        **es.borde_textfield(12))

    lbl_tasas = ft.Text(
        f"1 USD = {inv.get_tasa_usd():.2f} CUP  ·  "
        f"1 EUR = {inv.get_tasa_eur():.2f} CUP",
        size=11, color=es.COLOR_TEXTO_SUAVE)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def guardar(e):
        error_lbl.value = ""
        try:
            valor = float((tf.value or "0").replace(",", "."))
        except ValueError:
            error_lbl.value = "Valor inválido"
            page.update()
            return
        if valor < 0:
            error_lbl.value = "El precio no puede ser negativo"
            page.update()
            return
        moneda = dd_moneda.value or "CUP"
        try:
            if cual == "costo":
                inv.set_precio_costo(prod["id"], valor, moneda,
                                     usuario=app.usuario)
            else:
                inv.set_precio_unitario(prod["id"], valor, moneda,
                                        usuario=app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        tasa = inv.get_tasa(moneda)
        cup = valor * tasa
        msg = (f"{titulo}: {valor} {moneda} = ${cup:,.2f} CUP "
               f"(propagado)")

        def _despues():
            snack(page, msg, "ok")
            if on_refresh:
                on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text(f"{titulo}: {prod['nombre']}"),
        content=ft.Column([tf, dd_moneda, lbl_tasas, error_lbl],
                          tight=True, width=340, spacing=10),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


def _dlg_precio_costo(app, prod, on_refresh=None):
    _dlg_precio(app, prod, "costo", on_refresh)


def _dlg_precio_venta(app, prod, on_refresh=None):
    _dlg_precio(app, prod, "venta", on_refresh)


def _dlg_codigo(app, prod, on_refresh=None):
    page = app.page
    tf = ft.TextField(
        label="Código (Fxyyyy o vacío)",
        value=(prod.get("codigo") or ""),
        **es.estilo_textfield(12), height=54)
    tf.on_focus = cursor_al_final
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def guardar(e):
        error_lbl.value = ""
        try:
            inv.set_codigo(prod["id"], tf.value, usuario=app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        def _despues():
            snack(page, "Código actualizado (propagado)", "ok")
            if on_refresh:
                on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text(f"Código: {prod['nombre']}"),
        content=ft.Column([
            tf,
            ft.Text(f"Sugerido: {inv.siguiente_codigo(app.local_id) or '—'}",
                    size=11, color=es.COLOR_TEXTO_SUAVE),
            error_lbl,
        ], tight=True, width=300, spacing=6),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


def _dlg_renombrar(app, prod, on_refresh=None):
    page = app.page
    tf = ft.TextField(
        label="Nuevo nombre", value=prod["nombre"], autofocus=True,
        **es.estilo_textfield(12), height=54)
    tf.on_focus = cursor_al_final
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def guardar(e):
        error_lbl.value = ""
        try:
            inv.renombrar_producto(prod["id"], tf.value,
                                    usuario=app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        def _despues():
            snack(page, "Producto renombrado (propagado)", "ok")
            if on_refresh:
                on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text(f"Renombrar: {prod['nombre']}"),
        content=ft.Column([tf, error_lbl], tight=True, width=320),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


def _dlg_umbrales(app, prod, on_refresh=None):
    page = app.page
    tf_v = ft.TextField(
        label="Umbral verde", value=str(prod["umbral_verde"]),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)
    tf_a = ft.TextField(
        label="Umbral amarillo", value=str(prod["umbral_amarillo"]),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def guardar(e):
        error_lbl.value = ""
        try:
            inv.cambiar_umbrales(prod["id"], int(tf_v.value),
                                  int(tf_a.value), usuario=app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        def _despues():
            snack(page, "Umbrales actualizados", "ok")
            if on_refresh:
                on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text(f"Umbrales: {prod['nombre']}"),
        content=ft.Column([tf_v, tf_a, error_lbl],
                          tight=True, width=300, spacing=10),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)


def _conf_baja(app, prod, on_refresh=None):
    page = app.page
    tf_m = ft.TextField(
        label="Motivo", value="Merma",
        **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)
    dlg_ref = {"dlg": None}

    def hacer(e):
        error_lbl.value = ""
        m = (tf_m.value or "Merma").strip() or "Merma"
        try:
            inv.dar_baja(prod["id"], usuario=app.usuario, motivo=m)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        nombre = prod['nombre']

        def _despues():
            snack(page, f"{nombre} dado de baja", "ok")
            if on_refresh:
                on_refresh()

        cerrar_dialogo(page, dlg_ref["dlg"], on_close=_despues)

    dlg = ft.AlertDialog(
        title=ft.Text("Dar de baja"),
        content=ft.Column([
            ft.Text(f"¿Dar de baja «{prod['nombre']}»?"),
            tf_m, error_lbl,
        ], tight=True, width=320, spacing=12),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: cerrar_dialogo(page, dlg_ref["dlg"])),
            ft.FilledButton("Dar de baja", on_click=hacer,
                            style=ft.ButtonStyle(
                                bgcolor=es.COLOR_PELIGRO, color="white")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dlg_ref["dlg"] = dlg
    page.show_dialog(dlg)