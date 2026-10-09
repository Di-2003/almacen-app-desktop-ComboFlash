"""
Vista de caja: abrir, cerrar, historial, detalle.
"""
import flet as ft
import caja as cj
import locales as loc
from ui import estilos as es
from ui.componentes import (
    snack, empty_state, bottom_sheet, mounted,
)
from ui._scroll import columna_scroll

def vista_caja(app):
    page = app.page
    lista = columna_scroll("/caja", app, [], spacing=10)
    sesion_actual = ft.Container()

    def refrescar():
        lista.controls.clear()
        s = cj.sesion_abierta(app.local_id, app.usuario["username"])

        if s:
            sesion_actual.content = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.LOCK_OPEN,
                                color=es.COLOR_EXITO, size=22),
                        ft.Text("Sesión ABIERTA", size=14,
                                weight=ft.FontWeight.BOLD,
                                color=es.COLOR_EXITO, expand=True),
                    ]),
                    ft.Text(f"Abierta: {s['abierta']}", size=11,
                            color=es.COLOR_TEXTO_SUAVE),
                    ft.Text(f"Saldo inicial: "
                            f"${s['saldo_inicial']:,.2f}",
                            size=11, color=es.COLOR_TEXTO_SUAVE),
                    ft.Container(height=6),
                    ft.FilledButton(
                        "Cerrar caja", icon=ft.Icons.LOCK,
                        on_click=lambda e: _cerrar_caja(app, s, refrescar),
                        width=10000, height=44,
                        style=ft.ButtonStyle(
                            bgcolor=es.COLOR_PELIGRO,
                            color="#ffffff")),
                ], spacing=6),
                padding=14,
                bgcolor=es.COLOR_EXITO_SUAVE,
                border=ft.Border.all(1, es.COLOR_EXITO),
                border_radius=14)
        else:
            sesion_actual.content = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.LOCK, color=es.COLOR_TEXTO_SUAVE,
                                size=22),
                        ft.Text("Sin sesión abierta", size=14,
                                weight=ft.FontWeight.BOLD,
                                color=es.COLOR_TEXTO_SUAVE, expand=True),
                    ]),
                    ft.Text(
                        "Abre una sesión para cuadrar el efectivo del turno.",
                        size=11, color=es.COLOR_TEXTO_SUAVE),
                    ft.Container(height=6),
                    ft.FilledButton(
                        "Abrir caja", icon=ft.Icons.LOCK_OPEN,
                        on_click=lambda e: _abrir_caja(app, refrescar),
                        width=10000, height=44,
                        style=es.estilo_boton_marca()),
                ], spacing=6),
                padding=14,
                bgcolor=es.COLOR_SUPERFICIE,
                border=ft.Border.all(1, es.COLOR_BORDE),
                border_radius=14)

        sesiones = cj.listar_sesiones(app.local_id, limite=30)
        for ss in sesiones:
            lista.controls.append(_fila_sesion(app, ss, refrescar))

        if not sesiones:
            lista.controls.append(empty_state(
                ft.Icons.LOCK_OUTLINED, "Sin sesiones",
                "Aún no se ha cerrado ninguna caja en este local."))

        if mounted(lista):
            lista.update()
        if mounted(sesion_actual):
            sesion_actual.update()

    refrescar()

    return ft.View(
        route="/caja",
        controls=[
            ft.Container(content=sesion_actual,
                         padding=ft.Padding.all(14)),
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.only(left=14, right=14,
                                                 bottom=14)),
        ],
        appbar=ft.AppBar(
            title=ft.Text(
                f"Caja — {loc.nombre_local(app.local_id)}",
                size=15, color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )


def _fila_sesion(app, s, on_refresh):
    cerrada = s["cerrada"] is not None
    dif = float(s["diferencia"] or 0)
    color_dif = (es.COLOR_EXITO if abs(dif) < 0.01
                 else es.COLOR_PELIGRO if dif < 0
                 else es.COLOR_AMBAR)

    def tap(e):
        _detalle_sesion(app, s)

    return ft.Container(
        content=ft.Row([
            ft.Icon(
                ft.Icons.LOCK if cerrada else ft.Icons.LOCK_OPEN,
                color=es.COLOR_TEXTO_SUAVE, size=20),
            ft.Column([
                ft.Text(f"#{s['id']} · {s['usuario']}", size=13,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.Text(s["abierta"], size=11,
                        color=es.COLOR_TEXTO_SUAVE),
                ft.Text(
                    "Cerrada: " + (s["cerrada"] or "—"),
                    size=10, color=es.COLOR_TEXTO_TENUE),
            ], spacing=2, expand=True),
            ft.Column([
                ft.Text(
                    f"${(s['saldo_final'] or 0):,.2f}",
                    size=13, color=es.COLOR_TEXTO,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.RIGHT),
                ft.Text(f"dif ${dif:,.2f}", size=10,
                        color=color_dif,
                        text_align=ft.TextAlign.RIGHT)
                if cerrada else ft.Text("abierta", size=10,
                                        color=es.COLOR_EXITO),
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


def _abrir_caja(app, on_refresh):
    page = app.page
    tf = ft.TextField(label="Saldo inicial en cajón (CUP)",
                      value="0",
                      keyboard_type=ft.KeyboardType.NUMBER,
                      autofocus=True,
                      **es.estilo_textfield(12), height=54)
    tf_no = ft.TextField(label="Notas (opcional)",
                         **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            cj.abrir_sesion(
                local_id=app.local_id,
                usuario=app.usuario["username"],
                saldo_inicial=float((tf.value or "0").replace(",", ".")),
                notas=tf_no.value)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Caja abierta", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Abrir caja"),
        content=ft.Column([tf, tf_no, error_lbl],
                          tight=True, width=320, spacing=10),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Abrir", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _cerrar_caja(app, s, on_refresh):
    page = app.page
    esperado = cj.calcular_saldo_sistema(s["id"])

    tf = ft.TextField(label="Efectivo contado (CUP)",
                      value=f"{esperado:.2f}",
                      keyboard_type=ft.KeyboardType.NUMBER,
                      autofocus=True,
                      **es.estilo_textfield(12), height=54)
    tf_no = ft.TextField(label="Notas (opcional)",
                         multiline=True, min_lines=2,
                         **es.estilo_textfield(12))

    lbl_dif = ft.Text("", size=12)

    def on_change(e):
        try:
            v = float((tf.value or "0").replace(",", "."))
        except ValueError:
            v = 0
        dif = v - esperado
        if abs(dif) < 0.01:
            lbl_dif.value = "✅ Cuadra exacto"
            lbl_dif.color = es.COLOR_EXITO
        elif dif < 0:
            lbl_dif.value = f"⚠️ Falta ${abs(dif):,.2f}"
            lbl_dif.color = es.COLOR_PELIGRO
        else:
            lbl_dif.value = f"Sobra ${dif:,.2f}"
            lbl_dif.color = es.COLOR_AMBAR
        try:
            lbl_dif.update()
        except Exception:
            pass

    tf.on_change = on_change
    on_change(None)

    def guardar(e):
        try:
            v = float((tf.value or "0").replace(",", "."))
            cj.cerrar_sesion(s["id"], v, notas=tf_no.value)
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        page.pop_dialog()
        snack(page, "Caja cerrada", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Cerrar caja"),
        content=ft.Column([
            ft.Text(f"Esperado en sistema: ${esperado:,.2f}",
                    size=12, color=es.COLOR_TEXTO_SUAVE),
            tf, lbl_dif, tf_no,
        ], tight=True, width=340, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Cerrar caja", on_click=guardar,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_PELIGRO, color="#ffffff")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _detalle_sesion(app, s):
    page = app.page
    res = cj.resumen_sesion(s["id"])

    contenido = ft.Column([
        ft.Text(f"Sesión #{s['id']}", size=16,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Text(f"Usuario: {s['usuario']}", size=12,
                color=es.COLOR_TEXTO_SUAVE),
        ft.Text(f"Abierta: {s['abierta']}", size=11,
                color=es.COLOR_TEXTO_SUAVE),
        ft.Text(f"Cerrada: {s['cerrada'] or '—'}", size=11,
                color=es.COLOR_TEXTO_SUAVE),
        ft.Divider(height=1, color=es.COLOR_BORDE),
        ft.Row([
            ft.Text("Saldo inicial", size=12, expand=True,
                    color=es.COLOR_TEXTO_SUAVE),
            ft.Text(f"${s['saldo_inicial']:,.2f}", size=12,
                    color=es.COLOR_TEXTO),
        ]),
    ], spacing=6, tight=True)

    if res.get("por_metodo"):
        contenido.controls.append(ft.Divider(height=1,
                                              color=es.COLOR_BORDE))
        contenido.controls.append(ft.Text("Pagos por método", size=12,
                                          color=es.COLOR_TEXTO_SUAVE))
        for m in res["por_metodo"]:
            contenido.controls.append(ft.Row([
                ft.Text(f"{m['metodo']} ({m['moneda']})", size=12,
                        expand=True, color=es.COLOR_TEXTO),
                ft.Text(f"{m['monto']:,.2f}", size=12,
                        color=es.COLOR_TEXTO_SUAVE),
            ]))

    if res.get("por_metodo_abonos"):
        contenido.controls.append(ft.Divider(height=1,
                                              color=es.COLOR_BORDE))
        contenido.controls.append(ft.Text("Abonos por método", size=12,
                                          color=es.COLOR_TEXTO_SUAVE))
        for m in res["por_metodo_abonos"]:
            contenido.controls.append(ft.Row([
                ft.Text(f"{m['metodo']} ({m['moneda']})", size=12,
                        expand=True, color=es.COLOR_TEXTO),
                ft.Text(f"{m['monto']:,.2f}", size=12,
                        color=es.COLOR_TEXTO_SUAVE),
            ]))
    
    if res.get("gastos_sesion", 0) > 0.01:
        contenido.controls.append(ft.Divider(height=1, color=es.COLOR_BORDE))
        contenido.controls.append(ft.Row([
            ft.Text("Gastos de la sesión", size=12, expand=True,
                    color=es.COLOR_TEXTO_SUAVE),
            ft.Text(f"-${res['gastos_sesion']:,.2f}", size=12,
                    color=es.COLOR_PELIGRO),
        ]))
    
    if s["cerrada"]:
        contenido.controls += [
            ft.Divider(height=1, color=es.COLOR_BORDE),
            ft.Row([
                ft.Text("Sistema", size=12, expand=True,
                        color=es.COLOR_TEXTO_SUAVE),
                ft.Text(f"${(s['saldo_sistema'] or 0):,.2f}", size=12,
                        color=es.COLOR_TEXTO),
            ]),
            ft.Row([
                ft.Text("Contado", size=12, expand=True,
                        color=es.COLOR_TEXTO_SUAVE),
                ft.Text(f"${(s['saldo_final'] or 0):,.2f}", size=12,
                        color=es.COLOR_TEXTO),
            ]),
            ft.Row([
                ft.Text("Diferencia", size=13, expand=True,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.BOLD),
                ft.Text(f"${(s['diferencia'] or 0):,.2f}", size=14,
                        color=(es.COLOR_EXITO
                            if abs(s["diferencia"] or 0) < 0.01
                            else es.COLOR_PELIGRO),
                        weight=ft.FontWeight.BOLD),
            ]),
        ]

    page.show_dialog(bottom_sheet(contenido, page=page))