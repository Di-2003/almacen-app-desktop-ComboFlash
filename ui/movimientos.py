"""
Historial de movimientos con filtros y edición.
Incluye opción de eliminar (solo admin) que revierte el stock.
"""
import flet as ft
import inventario as inv
import locales as loc
from ui import estilos as es
from ui.componentes import (
    campo_busqueda, empty_state, snack, bottom_sheet, mounted,
)
from ui.principal import barra_navegacion


_TIPOS_COLOR = {
    "ENTRADA":      (es.COLOR_EXITO, es.COLOR_EXITO_SUAVE,
                     ft.Icons.ADD_CIRCLE),
    "SALIDA":       (es.COLOR_PELIGRO, es.COLOR_PELIGRO_SUAVE,
                     ft.Icons.REMOVE_CIRCLE),
    "BAJA":         (es.COLOR_TEXTO_SUAVE, es.COLOR_BORDE,
                     ft.Icons.DELETE_OUTLINE),
    "UMBRAL":       (es.COLOR_INFO, es.COLOR_INFO_SUAVE,
                     ft.Icons.TUNE),
    "AJUSTE":       (es.COLOR_AMBAR, es.COLOR_AMBAR_SUAVE,
                     ft.Icons.ATTACH_MONEY),
    "TRASPASO_SALIDA":  (es.COLOR_INFO, es.COLOR_INFO_SUAVE,
                         ft.Icons.LOGOUT),
    "TRASPASO_ENTRADA": (es.COLOR_INFO, es.COLOR_INFO_SUAVE,
                         ft.Icons.LOGIN),
}


def vista_movimientos(app):
    page = app.page
    estado = {"filtro": "", "tipo": None, "limite": 300}
    lista = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)
    info = ft.Text("", size=11, color=es.COLOR_TEXTO_SUAVE)
    filtros_row = ft.Row(spacing=8, scroll=ft.ScrollMode.AUTO)

    def _chip_filtro(texto, activo, on_click):
        return ft.Container(
            content=ft.Text(texto, size=12,
                            color=(es.COLOR_MARCA_NEGRO if activo
                                   else es.COLOR_TEXTO_SUAVE),
                            weight=ft.FontWeight.W_600),
            bgcolor=(es.COLOR_ACENTO if activo
                     else es.COLOR_SUPERFICIE),
            border=ft.Border.all(
                1, es.COLOR_ACENTO if activo else es.COLOR_BORDE),
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=20,
            on_click=on_click,
            ink=True,
        )

    def _rebuild_filtros():
        filtros_row.controls.clear()
        filtros_row.controls.extend([
            _chip_filtro("Todos", estado["tipo"] is None,
                         lambda e: set_filtro(None)),
            _chip_filtro("Entradas", estado["tipo"] == "ENTRADA",
                         lambda e: set_filtro("ENTRADA")),
            _chip_filtro("Salidas", estado["tipo"] == "SALIDA",
                         lambda e: set_filtro("SALIDA")),
            _chip_filtro("Traspasos", estado["tipo"] == "TRASPASO",
                         lambda e: set_filtro("TRASPASO")),
            _chip_filtro("Bajas", estado["tipo"] == "BAJA",
                         lambda e: set_filtro("BAJA")),
        ])
        if mounted(filtros_row):
            filtros_row.update()

    def set_filtro(t):
        estado["tipo"] = t
        _rebuild_filtros()
        refrescar()

    def refrescar():
        lista.controls.clear()
        movs = inv.listar_movimientos(
            local_id=app.local_id, limite=estado["limite"])
        f = estado["filtro"]
        t = estado["tipo"]

        if t:
            if t == "TRASPASO":
                movs = [m for m in movs
                        if m["tipo"] in ("TRASPASO_SALIDA",
                                         "TRASPASO_ENTRADA")]
            else:
                movs = [m for m in movs if m["tipo"] == t]
        if f:
            movs = [m for m in movs
                    if f in (m["producto"] or "").lower()
                    or f in (m["motivo"] or "").lower()
                    or f in (m.get("codigo") or "").lower()]

        puede_editar = app.usuario["rol"] in ("admin", "almacen")

        for m in movs:
            tipo = m["tipo"]
            c, bg, ic = _TIPOS_COLOR.get(
                tipo, (es.COLOR_TEXTO_SUAVE, es.COLOR_BORDE,
                       ft.Icons.CIRCLE))
            cant = (inv.fmt_cantidad(m["cantidad"])
                    if m["cantidad"] else "—")

            lista.controls.append(ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ic, color="white", size=16),
                            bgcolor=c, padding=8, border_radius=10,
                        ),
                        ft.Column([
                            ft.Text(m["producto"], size=14,
                                    weight=ft.FontWeight.W_600,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    color=es.COLOR_TEXTO),
                            ft.Text(tipo, size=10, color=c,
                                    weight=ft.FontWeight.BOLD),
                        ], spacing=1, expand=True),
                        ft.Column([
                            ft.Text(f"{cant} u", size=13,
                                    weight=ft.FontWeight.BOLD,
                                    color=es.COLOR_TEXTO,
                                    text_align=ft.TextAlign.RIGHT),
                            ft.Text(f"👤 {m['usuario']}", size=10,
                                    color=es.COLOR_TEXTO_TENUE,
                                    text_align=ft.TextAlign.RIGHT),
                        ], spacing=1,
                            horizontal_alignment=(
                                ft.CrossAxisAlignment.END)),
                    ], spacing=10,
                        vertical_alignment=(
                            ft.CrossAxisAlignment.CENTER)),
                    ft.Row([
                        ft.Text(m["fecha"], size=11,
                                color=es.COLOR_TEXTO_SUAVE),
                        ft.Text("•", size=11,
                                color=es.COLOR_TEXTO_TENUE),
                        ft.Text(m["motivo"] or "—", size=11,
                                color=es.COLOR_TEXTO_SUAVE,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                expand=True),
                    ], spacing=6),
                ], spacing=8),
                padding=14,
                bgcolor=es.COLOR_SUPERFICIE,
                border=ft.Border.all(1, es.COLOR_BORDE),
                border_radius=14,
                on_click=(lambda e, mv=m:
                          _detalle_movimiento(app, mv, refrescar))
                if puede_editar else None,
                ink=puede_editar,
            ))

        if not movs:
            lista.controls.append(empty_state(
                ft.Icons.HISTORY_TOGGLE_OFF, "Sin movimientos",
                "Ajusta los filtros o agrega un movimiento."))

        info.value = f"{len(movs)} movimiento(s)"
        if mounted(lista):
            lista.update()
        if mounted(info):
            info.update()

    def on_search(e):
        estado["filtro"] = (e.control.value or "").lower()
        refrescar()

    cap = campo_busqueda(
        hint="Buscar por producto, código o motivo…",
        on_change=on_search,
    )

    _rebuild_filtros()
    refrescar()

    return ft.View(
        route="/movimientos",
        controls=[
            ft.Container(
                content=ft.Column([cap, filtros_row, info],
                                  spacing=8),
                padding=ft.Padding.only(left=14, top=14,
                                        right=14, bottom=4),
            ),
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.all(14)),
        ],
        appbar=ft.AppBar(
            title=ft.Text(
                f"Historial — {loc.nombre_local(app.local_id)}",
                size=15, color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            elevation=0,
        ),
        navigation_bar=barra_navegacion(app, 2),
        bgcolor=es.COLOR_FONDO,
    )


def _detalle_movimiento(app, mv, on_refresh):
    page = app.page

    def editar(e):
        page.pop_dialog()
        _dlg_edit_mov(app, mv, on_refresh)

    def eliminar(e):
        page.pop_dialog()
        _confirmar_eliminar_mov(app, mv, on_refresh)

    contenido = ft.Column([
        ft.Row([
            ft.Container(
                content=ft.Icon(ft.Icons.RECEIPT_LONG,
                                color="white", size=20),
                bgcolor=es.COLOR_ACENTO, padding=10, border_radius=10,
            ),
            ft.Column([
                ft.Text(f"Movimiento #{mv['id']}", size=16,
                        weight=ft.FontWeight.BOLD,
                        color=es.COLOR_TEXTO),
                ft.Text(mv["fecha"], size=11,
                        color=es.COLOR_TEXTO_SUAVE),
            ], spacing=2),
        ], spacing=12),
        ft.Container(height=8),
        ft.Divider(height=1, color=es.COLOR_BORDE),
        ft.Container(height=8),
        _linea("Tipo", mv["tipo"]),
        _linea("Producto", mv["producto"]),
        _linea("Cantidad", inv.fmt_cantidad(mv["cantidad"])),
        _linea("Motivo", mv["motivo"] or "—"),
        _linea("Rebaja", f"${inv.fmt_precio(mv.get('rebaja', 0))}"),
        _linea("Usuario", mv["usuario"]),
        ft.Container(height=12),
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.EDIT, color=es.COLOR_MARCA_NEGRO,
                        size=18),
                ft.Text("Editar movimiento", size=14,
                        color=es.COLOR_MARCA_NEGRO,
                        weight=ft.FontWeight.W_600),
            ], spacing=10),
            padding=ft.Padding.symmetric(vertical=14),
            bgcolor=es.COLOR_ACENTO,
            border_radius=12,
            on_click=editar, ink=True,
            alignment=ft.Alignment.CENTER,
        ),
    ], spacing=8, tight=True)

    # Botón de eliminar solo para admin
    if app.usuario["rol"] == "admin":
        contenido.controls.append(
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.DELETE, color="white", size=18),
                    ft.Text("Eliminar movimiento", size=14,
                            color="white",
                            weight=ft.FontWeight.W_600),
                ], spacing=10,
                    alignment=ft.MainAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(vertical=14),
                bgcolor=es.COLOR_PELIGRO,
                border_radius=12,
                on_click=eliminar, ink=True,
                alignment=ft.Alignment.CENTER,
            )
        )

    page.show_dialog(bottom_sheet(contenido, page=page))


def _confirmar_eliminar_mov(app, mv, on_refresh):
    page = app.page

    def hacer(e):
        try:
            inv.eliminar_movimiento(mv["id"], app.usuario)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Movimiento eliminado y stock restaurado", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Eliminar movimiento"),
        content=ft.Text(
            f"¿Eliminar el movimiento #{mv['id']} de "
            f"«{mv['producto']}»?\n\n"
            f"Se revertirá su efecto sobre el stock. "
            f"Esta acción no se puede deshacer.",
            size=13, color=es.COLOR_TEXTO),
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


def _linea(label, valor):
    return ft.Row([
        ft.Text(label, size=12, color=es.COLOR_TEXTO_SUAVE,
                weight=ft.FontWeight.W_600, width=90),
        ft.Text(str(valor), size=13, color=es.COLOR_TEXTO,
                expand=True),
    ], vertical_alignment=ft.CrossAxisAlignment.START)


def _dlg_edit_mov(app, mv, on_refresh):
    page = app.page
    opts = []
    for p in inv.listar_productos(app.local_id, solo_activos=False):
        et = p["nombre"] + ("" if p["activo"] else " (inactivo)")
        opts.append(ft.DropdownOption(key=str(p["id"]), text=et))

    dd_p = ft.Dropdown(
        label="Producto", value=str(mv["producto_id"]),
        options=opts, editable=True,
        **es.borde_textfield(12),
    )
    dd_t = ft.Dropdown(
        label="Tipo", value=mv["tipo"],
        options=[ft.DropdownOption(key=t, text=t) for t in
                 ["ENTRADA", "SALIDA", "BAJA",
                  "TRASPASO_SALIDA", "TRASPASO_ENTRADA",
                  "AJUSTE", "UMBRAL"]],
        **es.borde_textfield(12),
    )
    tf_c = ft.TextField(
        label="Cantidad", value=inv.fmt_cantidad(mv["cantidad"]),
        keyboard_type=ft.KeyboardType.NUMBER,
        **es.estilo_textfield(12), height=54,
    )
    tf_m = ft.TextField(
        label="Motivo", value=mv["motivo"] or "",
        **es.estilo_textfield(12), height=54,
    )
    tf_f = ft.TextField(
        label="Fecha (YYYY-MM-DD HH:MM:SS)",
        value=mv["fecha"],
        **es.estilo_textfield(12), height=54,
    )
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            inv.editar_movimiento(
                mov_id=mv["id"],
                producto_id=int(dd_p.value),
                tipo=dd_t.value,
                cantidad=float((tf_c.value or "0").replace(",", ".")),
                motivo=tf_m.value,
                fecha=tf_f.value,
                usuario=app.usuario)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Movimiento actualizado", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Editar #{mv['id']}"),
        content=ft.Column(
            [dd_p, dd_t, tf_c, tf_m, tf_f, error_lbl],
            tight=True, width=340, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                        on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))