"""
Vista dedicada para listas filtradas desde el Dashboard.
Busca por nombre/código. Si el filtro es "inactivos", muestra botón
Reactivar en cada fila.
"""
import flet as ft
import inventario as inv
import locales as loc
from ui import estilos as es
from ui.componentes import (
    campo_busqueda, empty_state, snack, mounted,
)
from ui import modales
from ui._scroll import columna_scroll


def vista_lista_productos(app):
    page = app.page
    filtro_tipo = app.lista_filtro
    titulo = app.lista_titulo or "Productos"

    estado = {"filtro_texto": ""}
    lista_cont = columna_scroll("/lista-productos", app, [], spacing=10)

    def cargar_productos():
        if filtro_tipo == "inactivos":
            return inv.listar_productos_inactivos(app.local_id)
        prods = inv.listar_productos(app.local_id, solo_activos=True)
        if filtro_tipo == "verde":
            prods = [p for p in prods
                     if inv.color_de_producto(p) == "verde"]
        elif filtro_tipo == "amarillo":
            prods = [p for p in prods
                     if inv.color_de_producto(p) == "amarillo"]
        elif filtro_tipo == "critico":
            prods = [p for p in prods
                     if inv.color_de_producto(p) == "rojo"]
        elif filtro_tipo == "stock0":
            prods = [p for p in prods if float(p["stock"] or 0) == 0]
        return prods

    def reactivar(producto):
        def _hacer(e):
            try:
                inv.reactivar_producto(producto["id"], app.usuario)
                snack(page, f"{producto['nombre']} reactivado", "ok")
                refrescar()
            except Exception as ex:
                snack(page, str(ex), "error")
        return _hacer

    def refrescar():
        lista_cont.controls.clear()
        prods = cargar_productos()
        f = estado["filtro_texto"]
        if f:
            prods = [p for p in prods
                     if f in p["nombre"].lower()
                     or f in (p.get("codigo") or "").lower()]
        es_inactivos = (filtro_tipo == "inactivos")

        for p in prods:
            color = inv.color_de_producto(p)
            color_map = {"verde": es.COLOR_VERDE,
                         "amarillo": es.COLOR_AMARILLO,
                         "rojo": es.COLOR_ROJO}
            c = color_map.get(color, es.COLOR_TEXTO_TENUE)

            hijos = [
                ft.Container(width=6, height=40, bgcolor=c,
                             border_radius=3),
                ft.Column([
                    ft.Text(p["nombre"], size=14,
                            weight=ft.FontWeight.W_600,
                            color=es.COLOR_TEXTO, max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        ft.Text(p.get("codigo") or "—", size=11,
                                color=es.COLOR_ACENTO,
                                weight=ft.FontWeight.BOLD),
                        ft.Text("·", size=11,
                                color=es.COLOR_TEXTO_TENUE),
                        ft.Text(f"Stock {inv.fmt_cantidad(p['stock'])}",
                                size=11, color=es.COLOR_TEXTO_SUAVE),
                    ], spacing=6, tight=True),
                ], spacing=2, expand=True),
            ]

            if es_inactivos:
                hijos.append(ft.IconButton(
                    ft.Icons.RESTORE,
                    icon_color=es.COLOR_EXITO,
                    tooltip="Reactivar",
                    on_click=reactivar(p),
                ))

            lista_cont.controls.append(ft.Container(
                content=ft.Row(hijos, spacing=12,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=12,
                bgcolor=es.COLOR_SUPERFICIE,
                border=ft.Border.all(1, es.COLOR_BORDE),
                border_radius=10,
                on_click=None if es_inactivos else (
                    lambda e, prod=p: modales.abrir_detalle_producto(
                        app, prod, on_refresh=refrescar)),
                ink=not es_inactivos,
                opacity=0.65 if es_inactivos else 1.0,
            ))

        if not prods:
            lista_cont.controls.append(empty_state(
                ft.Icons.INBOX_OUTLINED, "Sin coincidencias",
                "Ajusta la búsqueda."))

        if mounted(lista_cont):
            lista_cont.update()

    def on_search(e):
        estado["filtro_texto"] = (e.control.value or "").lower()
        refrescar()

    cap = campo_busqueda(
        hint="Buscar por nombre o código…",
        on_change=on_search,
    )

    refrescar()

    return ft.View(
        route="/lista-productos",
        controls=[
            ft.Container(content=cap,
                         padding=ft.Padding.only(left=14, top=14,
                                                 right=14, bottom=4)),
            ft.Container(content=lista_cont, expand=True,
                         padding=ft.Padding.all(14)),
        ],
        appbar=ft.AppBar(
            title=ft.Text(
                f"{titulo} — {loc.nombre_local(app.local_id)}",
                size=15, color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            elevation=0,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/dashboard"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )