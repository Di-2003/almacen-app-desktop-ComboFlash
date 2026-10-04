"""
Edición masiva de umbrales por local.
"""
import flet as ft
import inventario as inv
from ui import estilos as es
from ui.componentes import snack, chip_estado


def vista_umbrales(app):
    page = app.page
    productos = inv.listar_productos(app.local_id, solo_activos=True)
    originales = {p["id"]: (p["umbral_verde"], p["umbral_amarillo"])
                  for p in productos}
    widgets = {}
    lista = ft.Column(spacing=8, expand=True, scroll=ft.ScrollMode.AUTO)

    def recolor(pid):
        w = widgets.get(pid)
        if not w:
            return
        try:
            uv = int(w["tf_v"].value or 0)
            ua = int(w["tf_a"].value or 0)
        except ValueError:
            return
        if uv <= ua:
            w["chip"].content = ft.Text(
                "inválido", size=10, color="white",
                weight=ft.FontWeight.BOLD)
            w["chip"].bgcolor = es.COLOR_PELIGRO
        else:
            color = inv.color_stock(w["prod"]["stock"], uv, ua)
            w["chip"].content = chip_estado(color).content
            w["chip"].bgcolor = es.COLOR_ESTADO_FONDO[color]
        w["chip"].padding = ft.Padding.symmetric(horizontal=8, vertical=3)
        w["chip"].border_radius = 8
        try:
            w["chip"].update()
        except Exception:
            pass

    for p in productos:
        tf_v = ft.TextField(
            value=str(p["umbral_verde"]),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=90, text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding.symmetric(vertical=10),
            **es.estilo_textfield(8),
        )
        tf_a = ft.TextField(
            value=str(p["umbral_amarillo"]),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=90, text_align=ft.TextAlign.CENTER,
            content_padding=ft.Padding.symmetric(vertical=10),
            **es.estilo_textfield(8),
        )
        chip = ft.Container()
        widgets[p["id"]] = {"tf_v": tf_v, "tf_a": tf_a,
                            "chip": chip, "prod": p}
        tf_v.on_change = (lambda e, pid=p["id"]: recolor(pid))
        tf_a.on_change = (lambda e, pid=p["id"]: recolor(pid))

        tarjeta = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(p["nombre"], size=14,
                            weight=ft.FontWeight.W_600, expand=True,
                            color=es.COLOR_TEXTO),
                    ft.Text(f"Stock: {inv.fmt_cantidad(p['stock'])}",
                            size=11, color=es.COLOR_TEXTO_SUAVE),
                ]),
                ft.Row([
                    ft.Text("Verde ≥", size=12,
                            color=es.COLOR_TEXTO_SUAVE), tf_v,
                    ft.Text("Amarillo ≥", size=12,
                            color=es.COLOR_TEXTO_SUAVE), tf_a,
                    chip,
                ], spacing=6, wrap=True),
            ], spacing=8),
            padding=12, bgcolor=es.COLOR_SUPERFICIE,
            border=ft.Border.all(1, es.COLOR_BORDE), border_radius=10,
        )
        lista.controls.append(tarjeta)
        recolor(p["id"])

    def guardar(e):
        cambios = 0
        for pid, w in widgets.items():
            try:
                uv = int(w["tf_v"].value or 0)
                ua = int(w["tf_a"].value or 0)
            except ValueError:
                snack(page, "Umbrales inválidos", "error")
                return
            if uv <= ua:
                snack(page,
                       f"Inválidos en {w['prod']['nombre']}", "error")
                return
            if (uv, ua) == originales[pid]:
                continue
            try:
                inv.cambiar_umbrales(pid, uv, ua,
                                     usuario=app.usuario)
                cambios += 1
            except Exception as ex:
                snack(page, str(ex), "error")
                return
        snack(page,
              f"{cambios} actualizado(s)" if cambios else "Sin cambios",
              "ok" if cambios else "info")
        app.ir("/perfil")

    return ft.View(
        route="/umbrales",
        controls=[
            ft.Container(content=lista, expand=True,
                         padding=ft.Padding.all(12)),
            ft.Container(
                content=ft.FilledButton(
                    "Guardar cambios", icon=ft.Icons.SAVE,
                    on_click=guardar,
                    width=10000, height=48,
                    style=es.estilo_boton_marca()),
                padding=ft.Padding.all(12)),
        ],
        appbar=ft.AppBar(
            title=ft.Text(
                f"Umbrales — {inv.fmt_cantidad(len(productos))} productos",
                size=15, color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )