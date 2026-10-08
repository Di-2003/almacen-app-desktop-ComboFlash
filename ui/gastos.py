"""
Vista de gastos: lista + modal nuevo/editar + filtros.
"""
import flet as ft
from datetime import datetime, timedelta
import gastos as gs
import locales as loc
from ui import estilos as es
from ui.componentes import (
    empty_state, snack, bottom_sheet, mounted, toast,
)


def _rango_mes_actual():
    hoy = datetime.now()
    inicio = hoy.replace(day=1, hour=0, minute=0, second=0,
                        microsecond=0)
    if inicio.month == 12:
        fin = inicio.replace(year=inicio.year + 1, month=1)
    else:
        fin = inicio.replace(month=inicio.month + 1)
    return (inicio.strftime("%Y-%m-%d %H:%M:%S"),
            fin.strftime("%Y-%m-%d %H:%M:%S"))


def vista_gastos(app):
    page = app.page
    estado = {
        "rango": "mes",
        "categoria": "__all__",
        "local": "__all__",
    }
    total_lbl = ft.Text("", size=18, weight=ft.FontWeight.BOLD,
                        color=es.COLOR_ACENTO)
    lista = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)

    def _rango(periodo):
        hoy = datetime.now()
        if periodo == "hoy":
            ini = hoy.replace(hour=0, minute=0, second=0,
                            microsecond=0)
            fin = ini + timedelta(days=1)
        elif periodo == "semana":
            ini = (hoy - timedelta(days=hoy.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0)
            fin = ini + timedelta(days=7)
        elif periodo == "mes":
            return _rango_mes_actual()
        elif periodo == "anio":
            ini = hoy.replace(month=1, day=1, hour=0, minute=0,
                            second=0, microsecond=0)
            fin = ini.replace(year=ini.year + 1)
        else:
            return None, None
        return (ini.strftime("%Y-%m-%d %H:%M:%S"),
                fin.strftime("%Y-%m-%d %H:%M:%S"))

    def refrescar():
        desde, hasta = _rango(estado["rango"])
        li = estado["local"]
        if li == "__all__":
            li_arg = "__all__"
        elif li == "global":
            li_arg = None
        else:
            li_arg = int(li)

        gastos = gs.listar_gastos(
            local_id=li_arg, desde=desde, hasta=hasta,
            categoria_id=estado["categoria"], limite=500,
        )

        total = sum(float(g["monto_cup"] or 0) for g in gastos)
        total_lbl.value = f"${total:,.2f}"

        lista.controls.clear()
        for g in gastos:
            lista.controls.append(_fila_gasto(app, g, refrescar))
        if not gastos:
            lista.controls.append(empty_state(
                ft.Icons.RECEIPT_LONG_OUTLINED, "Sin gastos",
                "Registra el primero con el botón de arriba."))
        if mounted(lista):
            lista.update()
        try:
            total_lbl.update()
        except Exception:
            pass

    def chip_periodo(texto, valor):
        activo = estado["rango"] == valor

        def click(e):
            estado["rango"] = valor
            _rebuild_chips()
            refrescar()

        return ft.Container(
            content=ft.Text(texto, size=12,
                            color=("#ffffff" if activo
                                   else es.COLOR_TEXTO_SUAVE),
                            weight=ft.FontWeight.W_600),
            bgcolor=(es.COLOR_ACENTO if activo
                     else es.COLOR_SUPERFICIE),
            border=ft.Border.all(
                1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
            padding=ft.Padding.symmetric(horizontal=14, vertical=7),
            border_radius=20,
            on_click=click, ink=True)

    fila_chips = ft.Row(spacing=6, scroll=ft.ScrollMode.AUTO)

    def _rebuild_chips():
        fila_chips.controls = [
            chip_periodo("Hoy", "hoy"),
            chip_periodo("Semana", "semana"),
            chip_periodo("Mes", "mes"),
            chip_periodo("Año", "anio"),
            chip_periodo("Total", "total"),
        ]
        if mounted(fila_chips):
            fila_chips.update()

    def _local_options():
        ops = [
            ft.DropdownOption(key="__all__", text="Todos los locales"),
            ft.DropdownOption(key="global", text="Solo globales"),
        ]
        for l in loc.listar_locales(solo_activos=True):
            ops.append(ft.DropdownOption(
                key=str(l["id"]), text=l["nombre"]))
        return ops

    def _categoria_options():
        ops = [
            ft.DropdownOption(key="__all__", text="Todas"),
            ft.DropdownOption(key="0", text="Sin categoría"),
        ]
        for c in gs.listar_categorias_gastos(solo_activas=True):
            ops.append(ft.DropdownOption(
                key=str(c["id"]), text=c["nombre"]))
        return ops

    dd_local = ft.Dropdown(
        value="__all__", options=_local_options(),
        dense=True, **es.borde_textfield(10))
    dd_cat = ft.Dropdown(
        value="__all__", options=_categoria_options(),
        dense=True, **es.borde_textfield(10))

    def _on_local(e):
        estado["local"] = dd_local.value or "__all__"
        refrescar()

    def _on_cat(e):
        v = dd_cat.value or "__all__"
        if v == "0":
            estado["categoria"] = None
        elif v == "__all__":
            estado["categoria"] = "__all__"
        else:
            estado["categoria"] = int(v)
        refrescar()

    dd_local.on_change = _on_local
    dd_cat.on_change = _on_cat

    def nuevo(e):
        _dlg_gasto(app, None, on_saved=refrescar)

    def categorias(e):
        from ui.admin_categorias_gastos import (
            abrir_admin_categorias_gastos,
        )
        abrir_admin_categorias_gastos(app, on_done=refrescar)

    _rebuild_chips()
    refrescar()

    return ft.View(
        route="/gastos",
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.FilledButton(
                        "Nuevo gasto", icon=ft.Icons.ADD,
                        on_click=nuevo, height=42,
                        width=10000,
                        style=ft.ButtonStyle(
                            bgcolor=es.COLOR_PELIGRO,
                            color="#ffffff",
                            shape=ft.RoundedRectangleBorder(
                                radius=ft.BorderRadius.all(12)))),
                    ft.OutlinedButton(
                        "Categorías", icon=ft.Icons.CATEGORY,
                        on_click=categorias, height=42,
                        width=10000,
                        style=ft.ButtonStyle(
                            color=es.COLOR_ACENTO,
                            side=ft.BorderSide(1, es.COLOR_ACENTO),
                            shape=ft.RoundedRectangleBorder(
                                radius=ft.BorderRadius.all(12)))),
                    ft.Container(height=4),
                    fila_chips,
                    ft.Container(height=6),
                    ft.Row([
                        ft.Container(content=dd_local, expand=True),
                        ft.Container(content=dd_cat, expand=True),
                    ], spacing=8),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.PAYMENTS,
                                    color=es.COLOR_PELIGRO, size=22),
                            ft.Text("Total del período", size=12,
                                    color=es.COLOR_TEXTO_SUAVE,
                                    expand=True),
                            total_lbl,
                        ], spacing=10,
                            vertical_alignment=(
                                ft.CrossAxisAlignment.CENTER)),
                        padding=14,
                        bgcolor=es.COLOR_SUPERFICIE,
                        border=ft.Border.all(1, es.COLOR_PELIGRO),
                        border_radius=12),
                ], spacing=8),
                padding=ft.Padding.only(left=14, top=14,
                                        right=14, bottom=4)),
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.all(14)),
        ],
        appbar=ft.AppBar(
            title=ft.Text("Gastos operativos", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )


def _fila_gasto(app, g, on_refresh):
    def tap(e):
        _menu_gasto(app, g, on_refresh)

    cat = g.get("categoria_nombre") or "Sin categoría"
    local = g.get("local_nombre") or "Global"
    moneda = g.get("moneda") or "CUP"
    monto = float(g.get("monto") or 0)
    monto_cup = float(g.get("monto_cup") or 0)

    sub = f"{cat} · {local}"
    if moneda != "CUP":
        sub += f"  ·  ≈ ${monto_cup:,.2f} CUP"

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.PAYMENTS,
                                color=es.COLOR_PELIGRO, size=20),
                bgcolor=es.COLOR_PELIGRO_SUAVE,
                padding=10, border_radius=10),
            ft.Column([
                ft.Text(g.get("descripcion") or cat,
                        size=14, color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(sub, size=11, color=es.COLOR_TEXTO_SUAVE,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(g["fecha"][:16], size=10,
                        color=es.COLOR_TEXTO_TENUE),
            ], spacing=2, expand=True),
            ft.Column([
                ft.Text(f"{monto:,.2f} {moneda}", size=14,
                        color=es.COLOR_PELIGRO,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.RIGHT),
                ft.Text(g["usuario"], size=10,
                        color=es.COLOR_TEXTO_TENUE,
                        text_align=ft.TextAlign.RIGHT),
            ], spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.END),
        ], spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=12,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=12,
        on_click=tap, ink=True,
    )


def _menu_gasto(app, g, on_refresh):
    page = app.page

    def editar(e):
        page.pop_dialog()
        _dlg_gasto(app, g, on_saved=on_refresh)

    def eliminar(e):
        page.pop_dialog()
        _confirmar_eliminar(app, g, on_refresh)

    contenido = ft.Column([
        ft.Text(g.get("descripcion") or "Gasto", size=17,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Container(height=6),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.EDIT, color=es.COLOR_ACENTO),
            title=ft.Text("Editar", color=es.COLOR_TEXTO),
            on_click=editar),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.DELETE, color=es.COLOR_PELIGRO),
            title=ft.Text("Eliminar", color=es.COLOR_PELIGRO),
            on_click=eliminar),
    ], spacing=0, tight=True)

    page.show_dialog(bottom_sheet(contenido, page=page))


def _confirmar_eliminar(app, g, on_refresh):
    page = app.page

    def hacer(e):
        try:
            gs.eliminar_gasto(g["id"])
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        toast(page, "Gasto eliminado", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Eliminar gasto"),
        content=ft.Text("¿Eliminar este gasto? No se puede deshacer.",
                        color=es.COLOR_TEXTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Eliminar", on_click=hacer,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_PELIGRO, color="white")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _dlg_gasto(app, gasto, on_saved=None):
    page = app.page
    es_nuevo = gasto is None

    tf_monto = ft.TextField(
        label="Monto",
        value=f"{float(gasto['monto']):.2f}" if gasto else "",
        keyboard_type=ft.KeyboardType.NUMBER,
        autofocus=True,
        **es.estilo_textfield(12), height=54)

    dd_moneda = ft.Dropdown(
        label="Moneda",
        value=(gasto["moneda"] if gasto else "CUP"),
        options=[
            ft.DropdownOption(key="CUP", text="$  CUP"),
            ft.DropdownOption(key="USD", text="USD$  USD"),
            ft.DropdownOption(key="EUR", text="€  EUR"),
        ],
        **es.borde_textfield(12))

    cat_ops = [ft.DropdownOption(key="0", text="Sin categoría")]
    for c in gs.listar_categorias_gastos(solo_activas=True):
        cat_ops.append(ft.DropdownOption(
            key=str(c["id"]), text=c["nombre"]))
    cat_default = "0"
    if gasto and gasto.get("categoria_id"):
        cat_default = str(gasto["categoria_id"])

    dd_cat = ft.Dropdown(
        label="Categoría", value=cat_default,
        options=cat_ops, **es.borde_textfield(12))

    loc_ops = [ft.DropdownOption(key="0", text="Global (toda la empresa)")]
    for l in loc.listar_locales(solo_activos=True):
        loc_ops.append(ft.DropdownOption(key=str(l["id"]),
                                          text=l["nombre"]))
    loc_default = "0"
    if gasto and gasto.get("local_id"):
        loc_default = str(gasto["local_id"])

    dd_local = ft.Dropdown(
        label="Local", value=loc_default,
        options=loc_ops, **es.borde_textfield(12))

    from configuracion_negocio import listar_metodos_pago
    metodos = listar_metodos_pago(solo_activos=True)
    met_ops = [ft.DropdownOption(key="", text="Sin especificar")]
    for m in metodos:
        met_ops.append(ft.DropdownOption(
            key=m["clave"], text=m["etiqueta"]))
    met_default = (gasto.get("metodo") or "") if gasto else "Efectivo CUP"

    dd_met = ft.Dropdown(
        label="Método de pago", value=met_default,
        options=met_ops, **es.borde_textfield(12))

    tf_desc = ft.TextField(
        label="Descripción (opcional)",
        value=(gasto.get("descripcion") or "") if gasto else "",
        **es.estilo_textfield(12), height=54)

    fecha_default = (gasto.get("fecha") if gasto
                     else datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    tf_fecha = ft.TextField(
        label="Fecha (YYYY-MM-DD HH:MM:SS)",
        value=fecha_default,
        **es.estilo_textfield(12), height=54)

    import caja as cj
    sesion_abierta = cj.sesion_abierta(
        app.local_id, app.usuario["username"]) \
        if app.local_id and app.local_id != -1 else None

    sw_caja = None
    if sesion_abierta:
        sw_caja = ft.Switch(
            label="Pagado de la caja abierta",
            value=False,
            active_color=es.COLOR_ACENTO,
        )

    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            monto = float((tf_monto.value or "0").replace(",", "."))
        except ValueError:
            error_lbl.value = "Monto inválido"
            page.update()
            return

        cat_id = None
        if dd_cat.value and dd_cat.value != "0":
            try:
                cat_id = int(dd_cat.value)
            except ValueError:
                cat_id = None

        loc_id = None
        if dd_local.value and dd_local.value != "0":
            try:
                loc_id = int(dd_local.value)
            except ValueError:
                loc_id = None

        metodo = dd_met.value or None
        desc = tf_desc.value or None
        fecha = (tf_fecha.value or "").strip() or None
        moneda = dd_moneda.value or "CUP"

        caja_id = None
        if sw_caja is not None and sw_caja.value:
            caja_id = sesion_abierta["id"]

        try:
            if es_nuevo:
                gs.registrar_gasto(
                    monto=monto, moneda=moneda, usuario=app.usuario,
                    local_id=loc_id, categoria_id=cat_id,
                    metodo=metodo, descripcion=desc,
                    fecha=fecha, caja_sesion_id=caja_id)
            else:
                gs.editar_gasto(
                    gasto["id"],
                    monto=monto, moneda=moneda,
                    categoria_id=cat_id if cat_id else 0,
                    metodo=metodo, descripcion=desc,
                    fecha=fecha,
                    local_id=loc_id if loc_id else 0)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return

        page.pop_dialog()
        toast(page, "Gasto guardado", "ok")
        if on_saved:
            on_saved()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Nuevo gasto" if es_nuevo else "Editar gasto"),
        content=ft.Column([
            tf_monto, dd_moneda, dd_cat, dd_local, dd_met,
            tf_desc, tf_fecha,
            sw_caja if sw_caja else ft.Container(height=0),
            error_lbl,
        ], tight=True, width=340, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Guardar", on_click=guardar,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_PELIGRO, color="#ffffff")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))